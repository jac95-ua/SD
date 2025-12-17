#!/usr/bin/env python3
"""
EV_CP_M - Monitor del punto de carga (Versión Resiliente)
Usa el protocolo <STX><DATA><ETX><LRC>.

Usage: EV_CP_M <IP:Puerto_EV_CP_E> <IP:Puerto_EV_Central> <ID_CP>
"""
import sys
import socket
import time
import json
import threading
import protocol 
import requests

def parse_addr(s):
    try:
        host, port = s.split(':')
        return host, int(port)
    except Exception as e:
        print(f"Error: Dirección '{s}' inválida. Debe tener formato HOST:PORT. {e}")
        sys.exit(1)

def handle_engine_check(engine_addr_str, central_sock, cp_id):
    engine_host, engine_port = parse_addr(engine_addr_str)
    
    while True:
        msg_dict = None # El mensaje será un dict
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

        # --- CAMBIO IMPORTANTE ---
        # Ahora envolvemos el mensaje usando el protocolo
        try:
            if msg_dict:
                wrapped_msg = protocol.wrap_message(msg_dict)
                if wrapped_msg:
                    central_sock.sendall(wrapped_msg)
                else:
                    print("[MONITOR] Error: No se pudo envolver el mensaje.")
        
        except Exception as e:
            print(f"[MONITOR] Conexión con EV_Central perdida: {e}.")
            break 
        # --- FIN DEL CAMBIO ---

        time.sleep(1)
    
    try:
        central_sock.close()
    except Exception:
        pass
    print("[MONITOR] Hilo de comprobación de salud terminado.")


def main():
    if len(sys.argv) < 4:
        print('Usage: EV_CP_M <IP:Puerto_EV_CP_E> <IP:Puerto_EV_Central> <ID_CP>')
        sys.exit(1)
    
    engine_addr = sys.argv[1]
    central_addr_str = sys.argv[2]
    cp_id = sys.argv[3]

    chost, cport = parse_addr(central_addr_str)
    
    reg_msg_dict = {'type':'register','id':cp_id,'location':'Calle Falsa 123','price':0.25}
    
    # --- CAMBIO IMPORTANTE ---
    # Envolvemos el mensaje de registro
    reg_msg_bytes = protocol.wrap_message(reg_msg_dict)
    if not reg_msg_bytes:
        print("[MONITOR] Error fatal: No se pudo crear el mensaje de registro.")
        sys.exit(1)
    # --- FIN DEL CAMBIO ---

    while True:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            print(f"[MONITOR] Intentando conectar con EV_Central en {chost}:{cport}...")
            s.connect((chost, cport))
            print("[MONITOR] ¡Conexión con EV_Central establecida!")

            # Enviamos el mensaje de registro YA ENVUELTO
            s.sendall(reg_msg_bytes)
            print(f"[MONITOR] Mensaje de registro enviado para {cp_id}.")

            t = threading.Thread(target=handle_engine_check, args=(engine_addr, s, cp_id), daemon=True)
            t.start()
            t.join()
            
            print("[MONITOR] El hilo de salud se ha detenido. La conexión debe estar muerta.")

        except (ConnectionRefusedError, TimeoutError):
            print("[MONITOR] EV_Central está offline. Reintentando en 5 segundos...")
        except KeyboardInterrupt:
            print("\n[MONITOR] Apagado manual (Ctrl+C).")
            break
        except Exception as e:
            print(f"[MONITOR] Error inesperado: {e}. Reintentando en 5 segundos...")
        
        time.sleep(5)

if __name__ == '__main__':
    main()