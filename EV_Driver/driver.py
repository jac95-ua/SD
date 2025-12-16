#!/usr/bin/env python3
"""
EV_Driver - Cliente interactivo para carga de vehículos.
(Modificado para permitir PARADA MANUAL por el usuario)

Usage: EV_Driver <KAFKA_BROKER> <ID_Cliente> [CP_ID_opcional]
"""
import sys
import time
import json
import threading
from kafka import KafkaProducer, KafkaConsumer

REQUESTS_TOPIC = 'requests_topic'
CONTROL_TOPIC = 'control_topic'
TELEMETRY_TOPIC = 'telemetry_topic'

# Variable global para controlar el bucle de escucha
stop_event = threading.Event()

def listener_loop(broker, driver_id, current_cp):
    """
    Hilo en segundo plano que escucha mensajes de Kafka:
    1. Telemetría: Para mostrar el progreso de la carga.
    2. Control: Para saber si la carga ha terminado (ticket final).
    """
    consumer = None
    try:
        consumer = KafkaConsumer(
            CONTROL_TOPIC, TELEMETRY_TOPIC,
            bootstrap_servers=[broker],
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='latest' # Solo mensajes nuevos
        )
        
        print(f"[LISTENER] Escuchando telemetría para {current_cp}...")
        
        for msg in consumer:
            if stop_event.is_set():
                break
                
            v = msg.value
            if v.get('cp_id') != current_cp:
                continue

            # 1. Mostrar Telemetría en tiempo real
            if msg.topic == TELEMETRY_TOPIC:
                kwh = v.get('consumo_kwh', 0)
                eur = v.get('importe_eur', 0)
                # Usamos \r para sobrescribir la línea y que parezca un contador
                sys.stdout.write(f"\r[CARGANDO] {current_cp} >> Consumo: {kwh:.2f} kWh | Importe: {eur:.2f} €   ")
                sys.stdout.flush()

                # Detectar ticket final en telemetría
                if v.get('final'):
                    print(f"\n[DRIVER] TICKET FINAL RECIBIDO: {v}")
                    stop_event.set() # Avisar al main para salir

            # 2. Detectar Ticket/Errores en Control
            if msg.topic == CONTROL_TOPIC and v.get('type') == 'ticket':
                 if v.get('driver_id') == driver_id:
                    print(f"\n[DRIVER] TICKET CONTROL RECIBIDO: {v}")
                    stop_event.set()

    except Exception as e:
        print(f"\n[LISTENER] Error: {e}")
    finally:
        if consumer:
            consumer.close()

def main():
    if len(sys.argv) < 3:
        print('Usage: EV_Driver <KAFKA_BROKER> <ID_Cliente> [CP_ID_opcional]')
        sys.exit(1)
    
    broker = sys.argv[1]
    driver_id = sys.argv[2]

    producer = None

    try:
        producer = KafkaProducer(bootstrap_servers=[broker], value_serializer=lambda v: json.dumps(v).encode('utf-8'))
        
        cps = [] 
        if len(sys.argv) == 4:
            cps.append(sys.argv[3])
        else:
            print("[DRIVER] Leyendo requests.txt...")
            try:
                with open('requests.txt','r') as f:
                    cps = [line.strip() for line in f if line.strip()]
            except FileNotFoundError:
                print('requests.txt not found')
                cps = [] 

        for cp in cps:
            print(f"\n{'='*40}")
            print(f"[DRIVER] Iniciando proceso para {cp}")
            
            # 1. Enviar petición
            msg = {'driver_id': driver_id, 'cp_id_solicitado': cp}
            producer.send(REQUESTS_TOPIC, msg)
            print(f"[DRIVER] Petición enviada a {cp}. Esperando autorización...")

            # 2. Preparar el hilo de escucha
            stop_event.clear()
            t = threading.Thread(target=listener_loop, args=(broker, driver_id, cp), daemon=True)
            t.start()

            # 3. Interfaz de usuario bloqueante
            print(f"[DRIVER] Pulsa [ENTER] en cualquier momento para DETENER la carga.")
            
            # Este input bloquea el programa hasta que tú decidas parar
            input() 
            
            # 4. Si el usuario pulsó Enter (y no ha acabado ya por otra razón)
            if not stop_event.is_set():
                print(f"\n[DRIVER] Enviando orden de PARADA manual...")
                # Enviamos el mismo comando que usaría el Admin
                stop_msg = {'type': 'parar', 'cp_id': cp}
                producer.send(CONTROL_TOPIC, stop_msg)
                
                # Esperamos un poco a que llegue el ticket final
                print("[DRIVER] Esperando confirmación de fin de carga...")
                time.sleep(2) # Damos tiempo al listener a recibir el ticket final
                stop_event.set()

            # Esperamos a que el hilo termine limpiamente
            t.join(timeout=2)
            print(f"[DRIVER] Proceso finalizado para {cp}.")
            
            if len(cps) > 1:
                print("[DRIVER] Siguiente petición en 2 segundos...")
                time.sleep(2)

        print('\n[DRIVER] Todas las peticiones procesadas. Adiós.')

    except KeyboardInterrupt:
        print("\n[DRIVER] Interrupción manual (Ctrl+C).")
    
    finally:
        if producer:
            producer.close()

if __name__ == '__main__':
    main()