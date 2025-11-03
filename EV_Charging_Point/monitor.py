#!/usr/bin/env python3
"""
EV_CP_M - Monitor del punto de carga (Versión Resiliente)

Se reconecta automáticamente a EV_Central si la conexión se pierde.

Usage: EV_CP_M <IP:Puerto_EV_CP_E> <IP:Puerto_EV_Central> <ID_CP>
"""
import sys
import socket
import time
import json
import threading

def parse_addr(s):
    try:
        host, port = s.split(':')
        return host, int(port)
    except Exception as e:
        print(f"Error: Dirección '{s}' inválida. Debe tener formato HOST:PORT. {e}")
        sys.exit(1)

def handle_engine_check(engine_addr_str, central_sock, cp_id):
    """
    Este HILO comprueba la salud del Engine local y lo reporta a EV_Central.
    Se ejecuta mientras la conexión a EV_Central (central_sock) esté viva.
    """
    engine_host, engine_port = parse_addr(engine_addr_str)
    
    while True:
        msg_to_central = None
        try:
            # 1. Comprobar salud del Engine local
            with socket.create_connection((engine_host, engine_port), timeout=2) as s_engine:
                s_engine.sendall(b'health_check\n')
                s_engine.settimeout(2)
                data = s_engine.recv(1024).decode('utf-8').strip()
                
                if data == 'OK':
                    msg_to_central = {'type':'ok','id':cp_id}
                else:
                    msg_to_central = {'type':'averia','id':cp_id}
        
        except Exception as e:
            # Fallo al contactar con el Engine -> Avería
            msg_to_central = {'type':'averia','id':cp_id}

        # 2. Enviar el resultado (OK o Avería) a EV_Central
        try:
            if msg_to_central:
                central_sock.sendall((json.dumps(msg_to_central)+'\n').encode('utf-8'))
        
        except Exception as e:
            # ¡FALLO AL ENVIAR A LA CENTRAL!
            # Esto significa que EV_Central se ha caído.
            print(f"[MONITOR] Conexión con EV_Central perdida: {e}. Deteniendo hilo de salud.")
            break # <-- CRÍTICO: Rompe el bucle 'while True' de este hilo

        # Esperar 1 segundo para la siguiente comprobación de salud
        time.sleep(1)
    
    # El bucle 'while True' se ha roto, el hilo va a morir.
    # Cerramos nuestro lado del socket para limpiar.
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
    
    # Mensaje de registro (lo preparamos una vez)
    reg_msg = {'type':'register','id':cp_id,'location':'Calle Falsa 123','price':0.25}
    reg_msg_bytes = (json.dumps(reg_msg)+'\n').encode('utf-8')

    # --- BUCLE DE RECONEXIÓN PRINCIPAL ---
    while True:
        try:
            # 1. Intentar conectar a EV_Central
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            print(f"[MONITOR] Intentando conectar con EV_Central en {chost}:{cport}...")
            s.connect((chost, cport))
            print("[MONITOR] ¡Conexión con EV_Central establecida!")

            # 2. Enviar mensaje de registro
            s.sendall(reg_msg_bytes)
            print(f"[MONITOR] Mensaje de registro enviado para {cp_id}.")

            # 3. Arrancar el hilo de 'health-check' (pasándole el nuevo socket)
            t = threading.Thread(target=handle_engine_check, args=(engine_addr, s, cp_id), daemon=True)
            t.start()

            # 4. Esperar a que el hilo 't' muera
            # t.join() bloquea el hilo principal aquí.
            # El hilo 't' SOLO muere si la conexión con EV_Central se rompe (ver 'break' en handle_engine_check).
            t.join()
            
            # Si llegamos aquí, es porque t.join() se ha desbloqueado, lo que significa que la conexión cayó.
            print("[MONITOR] El hilo de salud se ha detenido. La conexión debe estar muerta.")

        except (ConnectionRefusedError, TimeoutError):
            print("[MONITOR] EV_Central está offline. Reintentando en 5 segundos...")
        except KeyboardInterrupt:
            print("\n[MONITOR] Apagado manual (Ctrl+C).")
            break
        except Exception as e:
            print(f"[MONITOR] Error inesperado: {e}. Reintentando en 5 segundos...")
        
        # Si la conexión falla (Refused) o se cae (join termina), esperamos 5 segundos
        # y el bucle 'while True' principal volverá a intentar conectar.
        time.sleep(5)

if __name__ == '__main__':
    main()