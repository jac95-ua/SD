#!/usr/bin/env python3
"""
EV_Central: socket server for monitors and Kafka consumer/producer

Usage: EV_Central <PORT_SOCKETS> <KAFKA_BROKER> [DB_PATH]

This is a minimal implementation to bootstrap the project specified in the README.
"""
import sys
import threading
import socketserver
import socket
import json
import time
from kafka import KafkaProducer, KafkaConsumer
from . import db

REQUESTS_TOPIC = 'requests_topic'
TELEMETRY_TOPIC = 'telemetry_topic'
CONTROL_TOPIC = 'control_topic'

class MonitorHandler(socketserver.StreamRequestHandler):
    def handle(self):
        self.cp_id = None
        addr = self.client_address[0]
        print(f"[SOCKET] Connection from {addr}")
        
        try:
            for line in self.rfile:
                try:
                    msg = json.loads(line.decode('utf-8').strip())
                except Exception:
                    continue

                cp_id_from_msg = msg.get('id')
                if cp_id_from_msg:
                    self.cp_id = cp_id_from_msg

                typ = msg.get('type')

                if typ == 'register':
                    location = msg.get('location', 'unknown')
                    price = msg.get('price', 0.0) 
                    
                    db.save_cp(self.server.db_path, self.cp_id, location, price=price, state='Activado')
                    self.server.register_monitor(self.cp_id, self.request, location, price)
                    
                    print(f"[REGISTER] CP {self.cp_id} @ {location}")
                
                # --- ¡BLOQUE MODIFICADO! ---
                elif typ == 'averia':
                    cp = self.server.cps.get(self.cp_id)
                    # Solo procesar la avería si NO está ya marcado como 'Averiado'
                    if cp and cp.get('state') != 'Averiado':
                        print(f"[ALERT] AVERÍA from {self.cp_id}")
                        try:
                            # handle_averia ya imprime el estado, así que esto es todo.
                            self.server.handle_averia(self.cp_id)
                        except Exception as e:
                            print(f"[ERROR] handling averia for {self.cp_id}: {e}")
                    # Si ya estaba 'Averiado', ignoramos el mensaje y no imprimimos nada.
                
                elif typ == 'ok':
                    cp = self.server.cps.get(self.cp_id)
                    if cp:
                        current_state = cp.get('state')
                        
                        # Solo re-activa si estaba en un estado de error.
                        if current_state == 'Averiado' or current_state == 'Desconectado':
                            self.server.set_state(self.cp_id, 'Activado')
                        
                        # (Terminal limpia)
                        # print(f"[STATE] {self.cp_id} -> Activado")

        except Exception as e:
            print(f"[SOCKET] Connection error for {self.cp_id or 'unknown'}: {e}")
        
        finally:
            if self.cp_id:
                print(f"[DISCONNECT] Monitor for {self.cp_id} has disconnected.")
                self.server.set_state(self.cp_id, 'Desconectado')
            else:
                print(f"[DISCONNECT] An unknown monitor (never registered) has disconnected.")
class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True

    def __init__(self, server_address, handler_class, db_path, *args, **kwargs):
        super().__init__(server_address, handler_class, *args, **kwargs)
        self.db_path = db_path
        self.monitors = {}  # cp_id -> socket
        self.cps = db.load_cps(db_path)
        self.active_supplies = {}  # cp_id -> driver_id
        self.last_telemetry = {}  # cp_id -> last telemetry dict

        # Forzar todos los CPs cargados de la BBDD a 'Desconectado' al arrancar.
        # Solo se pondrán 'Activado' cuando su Monitor se conecte.
        print("[STATE] CPs conocidos en BBDD:")
        if not self.cps:
            print("[STATE] (Ninguno)")
        else:
            for cp_id, cp in self.cps.items():
                print(f"[STATE] - {cp_id} (Estado en BBDD: {cp['state']}) -> Forzando a Desconectado")
                cp['state'] = 'Desconectado'
    

    def register_monitor(self, cp_id, sock, location, price):
        self.monitors[cp_id] = sock
        # Ahora usamos los valores recibidos para crear/actualizar el CP en memoria
        self.cps[cp_id] = {'id': cp_id, 'location': location, 'price': price, 'state': 'Activado'}

    def set_state(self, cp_id, state):
        cp = self.cps.get(cp_id)
        if cp:
            cp['state'] = state
            db.save_cp(self.db_path, cp_id, cp.get('location','unknown'), price=cp.get('price',0.0), state=state)
            print(f"[STATE] {cp_id} -> {state}")

    def handle_averia(self, cp_id):
        # mark as averiado and instruct engine to stop via Kafka if producer attached
        self.set_state(cp_id, 'Averiado')
        try:
            if hasattr(self, 'producer'):
                self.producer.send(CONTROL_TOPIC, {'type': 'parar', 'cp_id': cp_id})
                print(f"[KAFKA] Sent parar for {cp_id}")
        except Exception as e:
            print(f"[ERROR] sending parar for {cp_id}: {e}")
        # if there was an active supply, produce a ticket aborted with last telemetry if available
        driver = self.active_supplies.get(cp_id)
        if driver:
            telemetry = self.last_telemetry.get(cp_id, {})
            ticket = {'type': 'ticket', 'cp_id': cp_id, 'driver_id': driver, 'aborted': True, 'telemetry': telemetry}
            try:
                if hasattr(self, 'producer'):
                    self.producer.send(CONTROL_TOPIC, ticket)
                    print(f"[KAFKA] Sent aborted ticket for {cp_id} -> {driver}")
            except Exception as e:
                print(f"[ERROR] sending aborted ticket: {e}")
            # cleanup
            try:
                del self.active_supplies[cp_id]
            except KeyError:
                pass

def kafka_consume_requests(broker, producer, central):
    consumer = KafkaConsumer(REQUESTS_TOPIC, bootstrap_servers=[broker], value_deserializer=lambda m: json.loads(m.decode('utf-8')))
    print('[KAFKA] Started consumer for requests_topic')
    for msg in consumer:
        r = msg.value
        print(f"[KAFKA] Request: {r}")
        cp_id = r.get('cp_id_solicitado')
        driver_id = r.get('driver_id')
        cp = central.cps.get(cp_id)
        if not cp or cp.get('state') != 'Activado':
            # Deny
            producer.send(CONTROL_TOPIC, {'type': 'denied', 'cp_id': cp_id, 'driver_id': driver_id})
            print(f"[KAFKA] Denied {driver_id} -> {cp_id}")
        else:
            # Authorize and instruct engine
            producer.send(CONTROL_TOPIC, {'type': 'authorize', 'cp_id': cp_id, 'driver_id': driver_id})
            # record active supply
            central.active_supplies[cp_id] = driver_id
            print(f"[KAFKA] Authorized {driver_id} -> {cp_id}")

def kafka_consume_telemetry(broker, central):
    consumer = KafkaConsumer(TELEMETRY_TOPIC, bootstrap_servers=[broker], value_deserializer=lambda m: json.loads(m.decode('utf-8')))
    print('[KAFKA] Started consumer for telemetry_topic')
    for msg in consumer:
        t = msg.value
        cp_id = t.get('cp_id')
        driver_id = t.get('driver_id')
        consumo = t.get('consumo_kwh')
        importe = t.get('importe_eur')
        cp = central.cps.get(cp_id)
        if cp:
            cp['state'] = 'Suministrando'
            # store last telemetry
            central.last_telemetry[cp_id] = t
            print(f"[TELEMETRY] {cp_id} driver {driver_id} consumo {consumo} kWh importe {importe}€")
            # if this telemetry marks final, produce ticket to driver and cleanup active supply
            if t.get('final'):
                driver = central.active_supplies.get(cp_id)
                ticket = {'type': 'ticket', 'cp_id': cp_id, 'driver_id': driver_id, 'consumo_kwh': consumo, 'importe_eur': importe, 'final': True}
                try:
                    if hasattr(central, 'producer'):
                        central.producer.send(CONTROL_TOPIC, ticket)
                        print(f"[KAFKA] Sent final ticket for {cp_id} -> {driver_id}")
                except Exception as e:
                    print(f"[ERROR] sending final ticket: {e}")
                # mark cp as activated and cleanup
                central.set_state(cp_id, 'Activado')
                try:
                    if cp_id in central.active_supplies:
                        del central.active_supplies[cp_id]
                except Exception:
                    pass

def admin_console_loop(producer, central):
    # Añadimos 'status' a la ayuda
    print('Admin console: use "parar <CP_ID>", "reanudar <CP_ID>" or "status"')
    while True:
        try:
            line = input('> ').strip()
        except EOFError:
            break
        if not line:
            continue
        parts = line.split()

    
        if parts[0] == 'status':
            print("[STATUS] Estado actual de todos los CPs:")
            if not central.cps:
                print("  (No hay CPs registrados)")
            else:
                # Itera sobre el diccionario de CPs del servidor y muestra sus datos
                for cp_id, cp_data in central.cps.items():
                    print(f"  - {cp_id:<10} | Estado: {cp_data.get('state', 'unknown'):<15} | Ubic: {cp_data.get('location', 'unknown')}")
            continue # Volver al input
        

        if parts[0] == 'parar' and len(parts) >= 2:
            cp_id = parts[1]
            central.set_state(cp_id, 'Parado')
            producer.send(CONTROL_TOPIC, {'type': 'parar', 'cp_id': cp_id})
        elif parts[0] == 'reanudar' and len(parts) >= 2:
            cp_id = parts[1]
            central.set_state(cp_id, 'Activado')
            producer.send(CONTROL_TOPIC, {'type': 'reanudar', 'cp_id': cp_id})

def main():
    if len(sys.argv) < 3:
        print('Usage: EV_Central <PORT_SOCKETS> <KAFKA_BROKER> [DB_PATH]')
        sys.exit(1)
    port = int(sys.argv[1])
    broker = sys.argv[2]
    db_path = sys.argv[3] if len(sys.argv) > 3 else 'ev_central.db'
    db.init_db(db_path)

    producer = KafkaProducer(bootstrap_servers=[broker], value_serializer=lambda v: json.dumps(v).encode('utf-8'))

    server = ThreadedTCPServer(('0.0.0.0', port), MonitorHandler, db_path)

    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    print(f"[SOCKET] EV_Central listening on 0.0.0.0:{port}")

    # Kafka consumers
    threading.Thread(target=kafka_consume_requests, args=(broker, producer, server), daemon=True).start()
    threading.Thread(target=kafka_consume_telemetry, args=(broker, server), daemon=True).start()

    # Admin console: only open interactive console if stdin is a TTY.
    try:
        if sys.stdin.isatty():
            admin_console_loop(producer, server)
        else:
            # run headless until interrupted
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print('Shutting down...')
                server.shutdown()
    except KeyboardInterrupt:
        print('Shutting down...')
        server.shutdown()
    except OSError as e:
        # In some detached environments input() raises Bad file descriptor; run headless.
        print('No TTY for admin console, running headless:', e)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print('Shutting down...')
            server.shutdown()

if __name__ == '__main__':
    main()
