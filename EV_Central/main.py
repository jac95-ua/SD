#!/usr/bin/env python3
"""
EV_Central: socket server for monitors and Kafka consumer/producer
Usa el protocolo <STX><DATA><ETX><LRC>.

Usage: EV_Central <PORT_SOCKETS> <KAFKA_BROKER> [DB_PATH]
"""
import sys
import threading
import socketserver
import socket
import json
import time
from flask import Flask, jsonify, request 
import sqlite3 
from kafka import KafkaProducer, KafkaConsumer
import protocol 
from EV_Central import db 

REQUESTS_TOPIC = 'requests_topic'
TELEMETRY_TOPIC = 'telemetry_topic'
CONTROL_TOPIC = 'control_topic'

class MonitorHandler(socketserver.BaseRequestHandler): # <-- CAMBIADO a BaseRequestHandler

    # --- NUEVA FUNCIÓN ---
    def process_message(self, msg_dict):
        """
        Procesa un diccionario de mensaje ya validado y parseado.
        Toda la lógica de 'register', 'averia', 'ok' se mueve aquí.
        """
        try:
            cp_id_from_msg = msg_dict.get('id')
            if cp_id_from_msg:
                self.cp_id = cp_id_from_msg

            typ = msg_dict.get('type')

            if typ == 'register':
                location = msg_dict.get('location', 'unknown')
                price = msg_dict.get('price', 0.0)
                token = msg_dict.get('token') # Recibimos el token
                
                # --- VERIFICACIÓN DE SEGURIDAD ---
                if not validate_token_with_registry(self.cp_id, token):
                    print(f"[AUTH] ⛔ Acceso DENEGADO a CP {self.cp_id}. Token inválido.")
                    # Opcional: Podríamos cerrar el socket aquí
                    return 
                # ---------------------------------

                print(f"[AUTH] ✅ CP {self.cp_id} autenticado correctamente.")
                
                db.save_cp(self.server.db_path, self.cp_id, location, price=price, state='Activado')
                self.server.register_monitor(self.cp_id, self.request, location, price)
            
            elif typ == 'averia':
                cp = self.server.cps.get(self.cp_id)
                if cp and cp.get('state') != 'Averiado':
                    print(f"[ALERT] AVERÍA from {self.cp_id}")
                    self.server.handle_averia(self.cp_id)
            
            elif typ == 'ok':
                cp = self.server.cps.get(self.cp_id)
                if cp:
                    current_state = cp.get('state')
                    
                    # Si el estado era de error (Averiado o Desconectado)
                    if current_state == 'Averiado' or current_state == 'Desconectado':
                        
                        # 1. Marcar como Activado
                        self.server.set_state(self.cp_id, 'Activado')
                        
                        # --- ¡LÓGICA AÑADIDA! ---
                        # 2. Enviar comando 'reanudar' al Engine para que limpie su estado interno.
                        print(f"[RECOVERY] El monitor {self.cp_id} reporta OK. Enviando 'reanudar' al Engine.")
                        try:
                            # Usamos el producer del server, que adjuntamos en main()
                            if hasattr(self.server, 'producer'):
                                self.server.producer.send(CONTROL_TOPIC, {'type': 'reanudar', 'cp_id': self.cp_id})
                        except Exception as e:
                            print(f"[ERROR] Fallo al enviar 'reanudar' para {self.cp_id}: {e}")

        except Exception as e:
            print(f"[PROCESS] Error procesando mensaje: {e}")

    # --- MÉTODO 'handle' TOTALMENTE REESCRITO ---
    def handle(self):
        """
        Lee el socket byte por byte, busca tramas <STX>...<ETX><LRC>
        y las valida antes de procesarlas.
        """
        self.cp_id = None
        addr = self.client_address[0]
        print(f"[SOCKET] Connection from {addr}")

        state = 'WAIT_STX'
        message_buffer = b''
        
        try:
            # Bucle de lectura byte a byte
            while True:
                byte = self.request.recv(1)
                if not byte:
                    # Cliente desconectado
                    break

                # ---- Máquina de estados del protocolo ----
                if state == 'WAIT_STX':
                    if byte == protocol.STX:
                        state = 'IN_MESSAGE'
                        message_buffer = b'' # Limpiamos buffer

                elif state == 'IN_MESSAGE':
                    if byte == protocol.ETX:
                        state = 'WAIT_LRC'
                    else:
                        message_buffer += byte # Acumulamos el JSON

                elif state == 'WAIT_LRC':
                    # Este 'byte' es el LRC que nos envió el monitor
                    received_lrc = byte
                    
                    # 1. Calcular nuestro propio LRC del mensaje
                    calculated_lrc = protocol.calculate_lrc(message_buffer)

                    # 2. Validar
                    if received_lrc == calculated_lrc:
                        # ¡CHECKSUM VÁLIDO!
                        try:
                            msg_dict = json.loads(message_buffer.decode('utf-8'))
                            # Enviamos el dict a procesar
                            self.process_message(msg_dict)
                        except Exception as e:
                            print(f"[PROTO] Error (JSON): {e}. Trama: {message_buffer}")
                    else:
                        # ¡CHECKSUM INVÁLIDO!
                        print(f"[PROTO] Error (Checksum): Recibido {received_lrc} vs Calculado {calculated_lrc}. Trama: {message_buffer}")
                    
                    # 3. Volver al estado inicial y esperar la siguiente trama
                    state = 'WAIT_STX'
                
        except (socket.timeout, ConnectionResetError) as e:
            print(f"[SOCKET] Connection error for {self.cp_id or 'unknown'}: {e}")
        except Exception as e:
            print(f"[SOCKET] Unexpected error for {self.cp_id or 'unknown'}: {e}")
        
        finally:
            # Lógica de desconexión que ya teníamos
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

        print("[STATE] CPs conocidos en BBDD:")
        if not self.cps:
            print("[STATE] (Ninguno)")
        else:
            for cp_id, cp in self.cps.items():
                print(f"[STATE] - {cp_id} (Estado en BBDD: {cp['state']}) -> Forzando a Desconectado")
                cp['state'] = 'Desconectado'

    def register_monitor(self, cp_id, sock, location, price):
        self.monitors[cp_id] = sock
        self.cps[cp_id] = {'id': cp_id, 'location': location, 'price': price, 'state': 'Activado'}

    def set_state(self, cp_id, state):
        cp = self.cps.get(cp_id)
        if cp:
            if cp.get('state') != state:
                cp['state'] = state
                db.save_cp(self.db_path, cp_id, cp.get('location','unknown'), price=cp.get('price',0.0), state=state)
                print(f"[STATE] {cp_id} -> {state}")
                
                # --- NUEVO: Avisar a Kafka del cambio de estado ---
                # Esto permite que el Dashboard visual se actualice
                try:
                    if hasattr(self, 'producer'):
                        msg = {'type': 'state_update', 'cp_id': cp_id, 'state': state}
                        self.producer.send(CONTROL_TOPIC, msg) # Usamos la variable global control_topic
                except Exception as e:
                    print(f"[ERROR] No se pudo enviar actualización de estado a Kafka: {e}")

    def handle_averia(self, cp_id):
        self.set_state(cp_id, 'Averiado')
        try:
            if hasattr(self, 'producer'):
                self.producer.send(CONTROL_TOPIC, {'type': 'parar', 'cp_id': cp_id})
                print(f"[KAFKA] Sent parar for {cp_id}")
        except Exception as e:
            print(f"[ERROR] sending parar for {cp_id}: {e}")
        
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
            producer.send(CONTROL_TOPIC, {'type': 'denied', 'cp_id': cp_id, 'driver_id': driver_id})
            print(f"[KAFKA] Denied {driver_id} -> {cp_id}")
        else:
            producer.send(CONTROL_TOPIC, {'type': 'authorize', 'cp_id': cp_id, 'driver_id': driver_id})
            central.active_supplies[cp_id] = driver_id
            central.set_state(cp_id, 'Suministrando') # Ponemos estado Suministrando
            print(f"[KAFKA] Authorized {driver_id} -> {cp_id}")

def validate_token_with_registry(cp_id, token):
    """Consulta la DB del Registry para ver si el token es válido."""
    try:
        # Asumimos que la DB del registry está en la carpeta raíz SD/ o en SD/EV_Registry/
        # Ajusta la ruta '../EV_Registry/ev_registry.db' o 'ev_registry.db' según donde ejecutes
        conn = sqlite3.connect('ev_registry.db') 
        cur = conn.cursor()
        cur.execute('SELECT token FROM registry WHERE id = ?', (cp_id,))
        row = cur.fetchone()
        conn.close()
        
        if row and row[0] == token:
            return True
        return False
    except Exception as e:
        print(f"[AUTH] Error validando token: {e}")
        return False

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
        if cp: # Comprobamos que el CP existe
            central.last_telemetry[cp_id] = t
            print(f"[TELEMETRY] {cp_id} driver {driver_id} consumo {consumo} kWh importe {importe}€")
            
            if t.get('final'):
                ticket = {'type': 'ticket', 'cp_id': cp_id, 'driver_id': driver_id, 'consumo_kwh': consumo, 'importe_eur': importe, 'final': True}
                try:
                    if hasattr(central, 'producer'):
                        central.producer.send(CONTROL_TOPIC, ticket)
                        print(f"[KAFKA] Sent final ticket for {cp_id} -> {driver_id}")
                except Exception as e:
                    print(f"[ERROR] sending final ticket: {e}")
                
                # --- ¡LÓGICA CORREGIDA! ---
                # Al finalizar, solo lo ponemos 'Activado' si no está
                # ni 'Parado' (por el admin) ni 'Averiado' (por el monitor).
                current_state = cp.get('state')
                if current_state != 'Parado' and current_state != 'Averiado':
                     central.set_state(cp_id, 'Activado')
                # --- FIN DE LA CORRECCIÓN ---

                try:
                    if cp_id in central.active_supplies:
                        del central.active_supplies[cp_id]
                except Exception:
                    pass
def admin_console_loop(producer, central):
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
                    # Imprime la línea principal del CP
                    print(f"  - {cp_id:<10} | Estado: {cp_data.get('state', 'unknown'):<15} | Ubic: {cp_data.get('location', 'unknown')}")
                    
                    # --- ¡MEJORA AÑADIDA AQUÍ! ---
                    # Si está Suministrando, muestra los detalles en tiempo real
                    if cp_data.get('state') == 'Suministrando':
                        driver = central.active_supplies.get(cp_id, '???')
                        telemetry = central.last_telemetry.get(cp_id)
                        
                        if telemetry:
                            consumo = telemetry.get('consumo_kwh', 0.0)
                            importe = telemetry.get('importe_eur', 0.0)
                            # Imprime una sub-línea con la telemetría
                            print(f"    \t└─ Driver: {driver}, Consumo: {consumo} kWh, Importe: {importe}€")
                        else:
                            # Por si acaso la telemetría aún no ha llegado
                            print(f"    \t└─ Driver: {driver}, (Esperando telemetría...)")
            continue # Volver al input
        
        # --- (El resto de la función 'parar' y 'reanudar' sigue igual) ---
        if parts[0] == 'parar' and len(parts) >= 2:
            cp_id = parts[1]
            central.set_state(cp_id, 'Parado')
            producer.send(CONTROL_TOPIC, {'type': 'parar', 'cp_id': cp_id})
        elif parts[0] == 'reanudar' and len(parts) >= 2:
            cp_id = parts[1]
            central.set_state(cp_id, 'Activado')
            producer.send(CONTROL_TOPIC, {'type': 'reanudar', 'cp_id': cp_id})

app_central = Flask(__name__)

@app_central.route('/status', methods=['GET'])
def get_status():
    # Esta función permitirá al Front-end ver el estado
    # Necesitamos acceder a la instancia del servidor 'server'
    # Usaremos una variable global o inyección más adelante.
    return jsonify({"status": "EV_Central Online", "mode": "Release 2"})

def run_api_server():
    # Puerto 8080 para la API de Central (diferente al 6000 del Registry)
    app_central.run(host='0.0.0.0', port=8080)

def main():
    if len(sys.argv) < 3:
        print('Usage: EV_Central <PORT_SOCKETS> <KAFKA_BROKER> [DB_PATH]')
        sys.exit(1)
    port = int(sys.argv[1])
    broker = sys.argv[2]
    db_path = sys.argv[3] if len(sys.argv) > 3 else 'ev_central.db'
    db.init_db(db_path)

    try:
        producer = KafkaProducer(bootstrap_servers=[broker], value_serializer=lambda v: json.dumps(v).encode('utf-8'))
    except Exception as e:
        print(f"[CENTRAL] Error fatal: No se pudo conectar a Kafka en {broker}. {e}")
        sys.exit(1)

    server = ThreadedTCPServer(('0.0.0.0', port), MonitorHandler, db_path)
    server.producer = producer # Adjuntamos el producer al server para que handle_averia lo use

    t_api = threading.Thread(target=run_api_server, daemon=True)
    t_api.start()
    print(f"[API] EV_Central API listening on 0.0.0.0:8080")

    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    print(f"[SOCKET] EV_Central listening on 0.0.0.0:{port}")

    threading.Thread(target=kafka_consume_requests, args=(broker, producer, server), daemon=True).start()
    threading.Thread(target=kafka_consume_telemetry, args=(broker, server), daemon=True).start()
    
    try:
        if sys.stdin.isatty():
            admin_console_loop(producer, server)
        else:
            print('No TTY for admin console, running headless.')
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
        print(f'No TTY for admin console, running headless: {e}')
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print('Shutting down...')
            server.shutdown()

if __name__ == '__main__':
    main()