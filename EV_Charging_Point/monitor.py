#!/usr/bin/env python3
"""
EV_CP_M - Monitor del punto de carga (Versión Resiliente)
Usa el protocolo <STX><DATA><ETX><LRC>.

Usage: EV_CP_M <IP:Puerto_EV_CP_E> <IP:Puerto_EV_Central> <ID_CP> <UBICACION>
"""
import sys
import socket
import time
import json
import threading
import protocol 
import requests
from EV_Charging_Point import security

def register_in_registry(cp_id, location):
    """Contacta con EV_Registry para obtener el token de acceso."""
    registry_url = "http://localhost:6000/register"
    print(f"[BOOT] Registrando en {registry_url}...")
    try:
        payload = {"id": cp_id, "location": location}
        response = requests.post(registry_url, json=payload, timeout=5)
        if response.status_code == 200:
            token = response.json().get("token")
            print(f"[BOOT] ✅ Token obtenido: {token}")
            return token
        else:
            print(f"[BOOT] ❌ Error registro: {response.text}")
            return None
    except Exception as e:
        print(f"[BOOT] ❌ Fallo conexión Registry: {e}")
        return None

def parse_addr(s):
    try:
        host, port = s.split(':')
        return host, int(port)
    except Exception as e:
        print(f"Error: Dirección '{s}' inválida. Debe tener formato HOST:PORT. {e}")
        sys.exit(1)

def handle_engine_check(engine_addr_str, central_sock, cp_id, sym_key): # <--- NUEVO ARGUMENTO
    engine_host, engine_port = parse_addr(engine_addr_str)
    
    while True:
        msg_dict = None 
        try:
            with socket.create_connection((engine_host, engine_port), timeout=2) as s_engine:
                s_engine.sendall(b'health_check\n')
                s_engine.settimeout(2)
                data = s_engine.recv(1024).decode('utf-8').strip()
                
                if data == 'OK':
                    msg_dict = {'type':'ok','id':cp_id}
                else:
                    msg_dict = {'type':'averia','id':cp_id}
        
        except Exception as e:
            msg_dict = {'type':'averia','id':cp_id}

        try:
            if msg_dict:
                # 1. Serializamos el mensaje a JSON plano
                json_str = json.dumps(msg_dict)
                
                # 2. Ciframos ese JSON usando la clave (Devuelve String Base64)
                encrypted_payload = security.encrypt_message(json_str, sym_key)
                
                # 3. Construimos la trama MANUALMENTE para evitar doble codificación
                # Protocolo: STX + BYTES_CIFRADOS + ETX + LRC
                payload_bytes = encrypted_payload.encode('utf-8')
                lrc = protocol.calculate_lrc(payload_bytes)
                
                packet = protocol.STX + payload_bytes + protocol.ETX + lrc
                
                print(f"[DEBUG] Enviando Payload Cifrado ({len(payload_bytes)} bytes): {payload_bytes}")

                central_sock.sendall(packet)
        
        except Exception as e:
            print(f"[MONITOR] Conexión con EV_Central perdida: {e}.")
            break 

        time.sleep(1)
    
    try:
        central_sock.close()
    except Exception:
        pass
    print("[MONITOR] Hilo de comprobación de salud terminado.")

def main():
    # --- CAMBIO 1: Exigir 4 argumentos (Script + 4 args) ---
    if len(sys.argv) < 5:
        print('Usage: EV_CP_M <IP:Puerto_EV_CP_E> <IP:Puerto_EV_Central> <ID_CP> <UBICACION>')
        sys.exit(1)
    
    engine_addr = sys.argv[1]
    central_addr_str = sys.argv[2]
    cp_id = sys.argv[3]
    
    # --- CAMBIO 2: Leer la ubicación de los argumentos ---
    location = sys.argv[4] 
    
    chost, cport = parse_addr(central_addr_str)

    # 2. LLAMADA AL REGISTRO
    token = register_in_registry(cp_id, location)
    if not token:
        print("[FATAL] Sin token no puedo arrancar. Verifica que EV_Registry corre en puerto 6000.")
        sys.exit(1)
    
    # 3. AÑADIR TOKEN AL MENSAJE
    reg_msg_dict = {
        'type': 'register', 
        'id': cp_id, 
        'location': location, # Ahora enviamos la ubicación real (ej: Alicante)
        'price': 0.25,
        'token': token #cambiar para porba
    }
    
    reg_msg_bytes = protocol.wrap_message(reg_msg_dict)
    
    while True:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            print(f"[MONITOR] Conectando a Central {chost}:{cport} desde {location}...")
            s.connect((chost, cport))
            
            # 1. Enviar Registro (Texto plano)
            s.sendall(reg_msg_bytes)
            print(f"[MONITOR] Autenticación enviada. Esperando clave de sesión...")

            # 2. Recibir Clave (Handshake)
            data = s.recv(4096)
            
            # Parseamos la respuesta manualmente (buscando STX y ETX)
            if data and protocol.STX in data and protocol.ETX in data:
                start = data.find(protocol.STX) + 1
                end = data.find(protocol.ETX)
                clean_json = data[start:end].decode('utf-8')
                
                resp = json.loads(clean_json)
                
                if resp.get('status') == 'ok':
                    sym_key = resp.get('sym_key')
                    print(f"[SEC] 🔐 Clave recibida: {sym_key[:10]}...")
                    
                    # 3. Arrancar hilo de Health Check pasando la clave
                    t = threading.Thread(
                        target=handle_engine_check, 
                        args=(engine_addr, s, cp_id, sym_key), # <--- PASAMOS LA CLAVE
                        daemon=True
                    )
                    t.start()
                    t.join()
                else:
                    print(f"[AUTH] Registro rechazado por Central.")
            else:
                print("[AUTH] Respuesta de Central no válida o vacía.")

            print("[MONITOR] Desconectado.")
            time.sleep(2) # Pequeña espera para no saturar si cae

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[MONITOR] Error conectando: {e}")
            time.sleep(5)

if __name__ == '__main__':
    main()