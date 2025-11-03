#!/usr/bin/env python3
"""
EV_Driver - lee requests.txt y produce peticiones a Kafka

Usage: EV_Driver <KAFKA_BROKER> <ID_Cliente>

requests.txt debe estar en el directorio actual con un cp_id por linea.
"""
import sys
import time
import json
from kafka import KafkaProducer, KafkaConsumer

REQUESTS_TOPIC = 'requests_topic'
CONTROL_TOPIC = 'control_topic'
TELEMETRY_TOPIC = 'telemetry_topic'

def main():
    # Modificamos el 'usage' para que muestre el argumento opcional
    if len(sys.argv) < 3:
        print('Usage: EV_Driver <KAFKA_BROKER> <ID_Cliente> [CP_ID_opcional]')
        sys.exit(1)
    
    broker = sys.argv[1]
    driver_id = sys.argv[2]

    producer = KafkaProducer(bootstrap_servers=[broker], value_serializer=lambda v: json.dumps(v).encode('utf-8'))
    consumer = KafkaConsumer(CONTROL_TOPIC, TELEMETRY_TOPIC, bootstrap_servers=[broker], value_deserializer=lambda m: json.loads(m.decode('utf-8')))

    cps = [] # Inicializamos la lista de CPs a solicitar

    # --- INICIO DE LA LÓGICA MODIFICADA ---
    if len(sys.argv) == 4:
        # Caso 1: Se ha pasado un CP_ID específico como argumento
        cp_id_manual = sys.argv[3]
        print(f"[DRIVER] Modo de petición única para: {cp_id_manual}")
        cps.append(cp_id_manual)
    else:
        # Caso 2: No se pasó argumento. Leemos de requests.txt (comportamiento original)
        print("[DRIVER] Modo de fichero: leyendo requests.txt")
        try:
            with open('requests.txt','r') as f:
                cps = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            print('requests.txt not found in current dir')
            cps = [] # La lista se queda vacía y el bucle 'for' no se ejecutará
    # --- FIN DE LA LÓGICA MODIFICADA ---

    for cp in cps:
        msg = {'driver_id': driver_id, 'cp_id_solicitado': cp}
        producer.send(REQUESTS_TOPIC, msg)
        print(f"[DRIVER] Sent request to {cp}")
        # wait for final ticket
        finished = False
        while not finished:
            for rec in consumer.poll(timeout_ms=1000).values():
                for r in rec:
                    v = r.value
                    # may contain ticket
                    if v.get('cp_id') == cp and v.get('driver_id') == driver_id and (v.get('final') or v.get('aborted')):
                        print(f"[DRIVER] Received final ticket: {v}")
                        finished = True
                        break
            # Reducimos el sleep para que no sea tan lento si no hay mensajes
            if not finished:
                time.sleep(0.5)
        
        # Si hay más CPs en la lista (del fichero), esperamos 4 segundos
        if len(cps) > 1:
            print("[DRIVER] Esperando 4 segundos para la siguiente petición...")
            time.sleep(4)

    print('[DRIVER] All requests processed')

if __name__ == '__main__':
    main()
