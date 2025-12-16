#!/usr/bin/env python3
"""
EV_CP_E - Engine del punto de carga (Versión con Suministro Manual)

Usage: EV_CP_E <KAFKA_BROKER> <HOST_HEALTH_PORT> [CP_ID]

Interactivo:
- Pulsa 'f' + Enter para simular avería.
- Pulsa 'm' + Enter para iniciar un suministro manual.
"""
import sys
import threading
import socket
import time
import json
from kafka import KafkaProducer, KafkaConsumer

TELEMETRY_TOPIC = 'telemetry_topic'
CONTROL_TOPIC = 'control_topic'

def health_server(host, port, state):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, port))
    srv.listen(5)
    print(f"[ENGINE] Health server listening on {host}:{port}")
    while True:
        conn, addr = srv.accept()
        try:
            data = conn.recv(1024)
            if not data:
                conn.close(); continue
            
            if state['failed']:
                conn.sendall(b'KO')
            else:
                conn.sendall(b'OK')
        except Exception:
            pass
        finally:
            conn.close()

# --- ¡NUEVA FUNCIÓN! ---
# Hemos movido la lógica de suministro aquí para poder reutilizarla.
def simulate_supply(producer, engine_id, driver_id, state):
    """
    Simula un suministro de energía. Esta función DEBE ser llamada en un hilo.
    """
    # 1. Comprobar si el CP está ocupado
    if state.get('busy'):
        print(f"[ENGINE] Solicitud ignorada: El CP ya está ocupado.")
        return
    
    # 2. Comprobar si el CP está parado por el admin o averiado
    if state.get('failed') or state.get('stop'):
        print(f"[ENGINE] Solicitud ignorada: El CP no está operativo (Parado o Averiado).")
        return

    # 3. Ocupar el CP
    state['busy'] = True
    print(f"[ENGINE] Suministro INICIADO para '{driver_id}' en {engine_id}")
    consumo = 0.0
    importe = 0.0
    
    try:
        # 4. Bucle de simulación
        # CAMBIO: Eliminado el límite de "consumo < 5.0". 
        # Ahora solo para si state['stop'] (botón Parar) o state['failed'] (Avería) son True.
        while not state.get('stop') and not state.get('failed'):
            consumo += 0.5 # Puedes bajar esto a 0.1 si quieres que vaya más lento visualmente
            importe = consumo * 0.25 # Recalculamos importe total basado en precio fijo
            
            telemetry_msg = {
                'cp_id': engine_id, 
                'driver_id': driver_id, 
                'consumo_kwh': round(consumo, 2), 
                'importe_eur': round(importe, 2)
            }
            producer.send(TELEMETRY_TOPIC, telemetry_msg)
            time.sleep(1) # Simula el paso del tiempo (1 segundo)
        
        # 5. Enviar mensaje final
        final_msg = {
            'cp_id': engine_id, 
            'driver_id': driver_id, 
            'consumo_kwh': round(consumo, 2), 
            'importe_eur': round(importe, 2), 
            'final': True
        }
        producer.send(TELEMETRY_TOPIC, final_msg)
        
        if state.get('stop'):
            print(f"[ENGINE] Suministro DETENIDO (orden Parar) para '{driver_id}' en {engine_id}")
        elif state.get('failed'):
            print(f"[ENGINE] Suministro DETENIDO (Avería) para '{driver_id}' en {engine_id}")
        else:
            # Este caso teóricamente ya no se daría solo, salvo error, porque el bucle es infinito
            print(f"[ENGINE] Suministro FINALIZADO para '{driver_id}' en {engine_id}")

    except Exception as e:
        print(f"[ENGINE] Error durante el suministro: {e}")
    
    finally:
        # 6. Liberar el CP
        state['busy'] = False
        state['stop'] = False # Limpiamos el flag de 'stop' para la próxima vez

def kafka_control_loop(broker, producer, engine_id, state):
    """
    Escucha órdenes de 'authorize', 'parar' y 'reanudar' desde EV_Central.
    """
    consumer = KafkaConsumer(CONTROL_TOPIC, bootstrap_servers=[broker], value_deserializer=lambda m: json.loads(m.decode('utf-8')))
    print('[ENGINE] Started Kafka control consumer')
    for msg in consumer:
        m = msg.value
        typ = m.get('type')
        cp_id = m.get('cp_id')
        
        # Solo nos interesan mensajes para este CP
        if cp_id != engine_id:
            continue

        if typ == 'authorize':
            driver_id = m.get('driver_id')
            # --- MODIFICADO ---
            # Lanzamos la simulación en un hilo nuevo
            print(f"[ENGINE] Autorización recibida para '{driver_id}'.")
            threading.Thread(
                target=simulate_supply, 
                args=(producer, engine_id, driver_id, state), 
                daemon=True
            ).start()
        
        elif typ == 'parar':
            state['stop'] = True
            print("[ENGINE] Comando 'parar' recibido. El suministro actual se detendrá.")
        
        elif typ == 'reanudar':
            state['stop'] = False
            state['failed'] = False # Un 'reanudar' también resetea la avería
            print("[ENGINE] Comando 'reanudar' recibido. Listo para operar.")

def main():
    if len(sys.argv) < 3:
        print('Usage: EV_CP_E <KAFKA_BROKER> <HOST:PORT for health server> [CP_ID]')
        sys.exit(1)
    broker = sys.argv[1]
    hostport = sys.argv[2]
    try:
        host, port_str = hostport.split(':')
        port = int(port_str)
    except Exception as e:
        print(f"Error: El formato de HOST:PORT es incorrecto: '{hostport}'")
        sys.exit(1)

    engine_id = sys.argv[3] if len(sys.argv) > 3 else f'CP_{host}_{port}'

    try:
        producer = KafkaProducer(bootstrap_servers=[broker], value_serializer=lambda v: json.dumps(v).encode('utf-8'))
    except Exception as e:
        print(f"[ENGINE] Error fatal: No se pudo conectar a Kafka en {broker}. {e}")
        sys.exit(1)

    # --- MODIFICADO ---
    # Añadimos 'busy' al diccionario de estado.
    state = {'failed': False, 'stop': False, 'busy': False}

    threading.Thread(target=health_server, args=(host, port, state), daemon=True).start()
    threading.Thread(target=kafka_control_loop, args=(broker, producer, engine_id, state), daemon=True).start()

    # --- MODIFICADO ---
    # Añadimos la opción 'm' (manual)
    print(f'[ENGINE] {engine_id} listo. Pulsa: (f) simular avería, (m) suministro manual')
    try:
        while True:
            # Añadimos un '>' para que se vea claro que espera un comando
            cmd = input('> ').strip().lower()
            
            if cmd == 'f':
                state['failed'] = not state['failed']
                print(f"--- Simulación de avería: {state['failed']} ---")
            
            # --- ¡NUEVO COMANDO! ---
            elif cmd == 'm':
                print("[ENGINE] Solicitud de suministro MANUAL recibida.")
                # Lanzamos la simulación con un ID de conductor genérico
                threading.Thread(
                    target=simulate_supply, 
                    args=(producer, engine_id, 'MANUAL_USER', state), 
                    daemon=True
                ).start()
                
    except KeyboardInterrupt:
        print("\n[ENGINE] Apagando...")
        producer.close()

if __name__ == '__main__':
    main()