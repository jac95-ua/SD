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
from EV_Central import security

server_ref = None

REQUESTS_TOPIC = 'requests_topic'
TELEMETRY_TOPIC = 'telemetry_topic'
CONTROL_TOPIC = 'control_topic'

class MonitorHandler(socketserver.BaseRequestHandler): # <-- CAMBIADO a BaseRequestHandler

    # --- NUEVA FUNCIÓN ---
    def process_message(self, msg_dict):
        """
        Procesa un diccionario de mensaje ya validado y parseado.
        Gestiona registro (con seguridad y clima), averías y recuperaciones.
        """
        try:
            # 1. Identificar al CP
            cp_id_from_msg = msg_dict.get('id')
            if cp_id_from_msg:
                self.cp_id = cp_id_from_msg

            typ = msg_dict.get('type')

            # --- CASO 1: REGISTRO ---
            if typ == 'register':
                location = msg_dict.get('location', 'unknown')
                price = msg_dict.get('price', 0.0)
                token = msg_dict.get('token')
                
                # A) VERIFICACIÓN DE SEGURIDAD (Vía API Registry)
                if not validate_token_with_registry(self.cp_id, token):
                    print(f"[AUTH] ⛔ Acceso DENEGADO a CP {self.cp_id}. Token inválido/revocado.")
                    # ¡IMPORTANTE! Lanzamos error para que el 'handle' cierre la conexión
                    raise ConnectionRefusedError(f"Autenticación fallida para {self.cp_id}")
                
                print(f"[AUTH] ✅ CP {self.cp_id} autenticado correctamente.")

                # --- NUEVO: Generar Clave Simétrica y Enviarla ---
                # 1. Generamos clave AES 256
                sym_key = security.generate_sym_key()
                # 2. Guardamos en el servidor asociada a este CP
                self.server.cp_keys[self.cp_id] = sym_key

                print(f"[SEC] 🔐 Clave generada para {self.cp_id}: {sym_key[:10]}...")

                # 3. Enviamos la clave al Monitor (Aún en texto plano, es el handshake)
                response_dict = {'status': 'ok', 'sym_key': sym_key}
                response_bytes = protocol.wrap_message(response_dict)
                self.request.sendall(response_bytes)

                # B) COMPROBACIÓN DE CLIMA (Memoria de alertas)
                # Si la ciudad ya estaba marcada en alerta por EV_W, forzamos inicio PARADO.
                in_alert = False
                if hasattr(self.server, 'city_alerts'):
                    if self.server.city_alerts.get(location.lower()):
                        in_alert = True

                if in_alert:
                    print(f"[CLIMA] 🛑 El CP {self.cp_id} se conecta en zona de ALERTA ({location}). Iniciando PARADO.")
                    
                    # Guardamos estado 'Parado' en DB y memoria
                    db.save_cp(self.server.db_path, self.cp_id, location, price=price, state='Parado')
                    self.server.register_monitor(self.cp_id, self.request, location, price)
                    
                    # Enviamos orden 'parar' inmediata al Engine vía Kafka
                    try:
                        # Pequeña pausa para dar tiempo al Engine a suscribirse al topic
                        time.sleep(0.5) 
                        if hasattr(self.server, 'producer'):
                            self.server.producer.send(CONTROL_TOPIC, {'type': 'parar', 'cp_id': self.cp_id})
                    except Exception as e:
                        print(f"[ERROR] No se pudo enviar parada inicial a Kafka: {e}")

                else:
                    # C) INICIO NORMAL
                    db.save_cp(self.server.db_path, self.cp_id, location, price=price, state='Activado')
                    self.server.register_monitor(self.cp_id, self.request, location, price)
            
            # --- CASO 2: NOTIFICACIÓN DE AVERÍA ---
            elif typ == 'averia':
                cp = self.server.cps.get(self.cp_id)
                # Solo procesamos si no estaba ya averiado
                if cp and cp.get('state') != 'Averiado':
                    print(f"[ALERT] 🔧 AVERÍA reportada por {self.cp_id}")
                    self.server.handle_averia(self.cp_id)
            
            # --- CASO 3: RECUPERACIÓN (OK) ---
            elif typ == 'ok':
                cp = self.server.cps.get(self.cp_id)
                if cp:
                    current_state = cp.get('state')
                    
                    # Solo "arreglamos" si estaba Averiado o Desconectado.
                    # IMPORTANTE: Si está 'Parado' por clima o admin, el 'OK' del health check
                    # NO debe reactivarlo automáticamente.
                    if current_state == 'Averiado' or current_state == 'Desconectado':
                        
                        self.server.set_state(self.cp_id, 'Activado')
                        print(f"[RECOVERY] El monitor {self.cp_id} reporta OK. Reactivando servicio.")
                        
                        # Avisamos al Engine para que quite su flag de error interno
                        try:
                            if hasattr(self.server, 'producer'):
                                self.server.producer.send(CONTROL_TOPIC, {'type': 'reanudar', 'cp_id': self.cp_id})
                        except Exception as e:
                            print(f"[ERROR] Fallo al enviar 'reanudar' para {self.cp_id}: {e}")

        except ConnectionRefusedError:
            # Re-lanzamos esta específica para que corte la conexión en 'handle'
            raise
        except Exception as e:
            print(f"[PROCESS] Error procesando mensaje de {self.cp_id}: {e}")

    # --- MÉTODO 'handle' TOTALMENTE REESCRITO ---
def handle(self):
        self.cp_id = None
        addr = self.client_address[0]
        print(f"[SOCKET] Connection from {addr}")

        state = 'WAIT_STX'
        message_buffer = b''
        
        try:
            while True:
                byte = self.request.recv(1)
                if not byte:
                    break

                if state == 'WAIT_STX':
                    if byte == protocol.STX:
                        state = 'IN_MESSAGE'
                        message_buffer = b'' # <--- ¡LIMPIEZA CRÍTICA!

                elif state == 'IN_MESSAGE':
                    if byte == protocol.ETX:
                        state = 'WAIT_LRC'
                    else:
                        message_buffer += byte

                elif state == 'WAIT_LRC':
                    received_lrc = byte
                    calculated_lrc = protocol.calculate_lrc(message_buffer)

                    if received_lrc == calculated_lrc:
                        try:
                            payload_str = message_buffer.decode('utf-8')
                            msg_dict = None

                            # --- LÓGICA INTELIGENTE DE DESCIFRADO ---
                            # 1. ¿Tenemos clave?
                            has_key = self.cp_id and self.server.cp_keys.get(self.cp_id)
                            
                            # 2. ¿Parece cifrado? (No empieza por '{')
                            is_encrypted_format = not payload_str.strip().startswith('{')

                            if has_key and is_encrypted_format:
                                try:
                                    # print(f"[DEBUG] Descifrando: {payload_str[:15]}...") 
                                    decrypted_json = security.decrypt_message(payload_str, self.server.cp_keys[self.cp_id])
                                    msg_dict = json.loads(decrypted_json)
                                except Exception as e:
                                    print(f"[SEC] ⚠️ Fallo al descifrar de {self.cp_id}: {e}")
                                    raise ConnectionRefusedError("Integridad criptográfica fallida")
                            else:
                                # Es texto plano (Registro o mensaje sin cifrar)
                                msg_dict = json.loads(payload_str)

                            # Procesamos el mensaje
                            self.process_message(msg_dict)
                            
                        except ConnectionRefusedError:
                            raise
                        except Exception as e:
                            print(f"[PROTO] Error lógico: {e}")
                    else:
                        print(f"[PROTO] Checksum Error!")
                    
                    # Reiniciamos máquina de estados para el siguiente mensaje
                    state = 'WAIT_STX'
                    message_buffer = b'' # <--- DOBLE SEGURIDAD
                
        except (socket.timeout, ConnectionResetError, ConnectionRefusedError):
            print(f"[SOCKET] Cerrando conexión con {self.cp_id or addr}")
        except Exception as e:
            print(f"[SOCKET] Error inesperado: {e}")
        finally:
            if self.cp_id:
                print(f"[DISCONNECT] Monitor for {self.cp_id} has disconnected.")
                self.server.set_state(self.cp_id, 'Desconectado')
class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True

    def __init__(self, server_address, handler_class, db_path, *args, **kwargs):
        super().__init__(server_address, handler_class, *args, **kwargs)
        self.db_path = db_path
        self.monitors = {}  # cp_id -> socket
        self.cps = db.load_cps(db_path)
        self.active_supplies = {}  # cp_id -> driver_id
        self.last_telemetry = {}  # cp_id -> last telemetry dict
        self.city_alerts = {}
        self.cp_keys = {}

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

    global server_ref
    server_ref = server
    print("[CENTRAL] ✅ Servidor enlazado con API Rest de Clima")

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


app = Flask(__name__)

@app.route('/api/weather', methods=['POST'])
def receive_weather_alert():
    global server_ref
    if not server_ref:
        return jsonify({"status": "error", "message": "Central no lista"}), 503

    data = request.json
    city_target = data.get('city')       # Ahora recibimos la ciudad
    accion = data.get('action')          # ALERT o RECOVER
    temp = data.get('temperature')

    if city_target:
        server_ref.city_alerts[city_target.lower()] = (accion == "ALERT")
    
    print(f"\n[REST-API] 📨 Alerta de Clima para {city_target}: {accion} ({temp}ºC)")
    
    affected_count = 0

    # Iteramos sobre todos los CPs registrados en el servidor
    # server_ref.cps es un diccionario { 'CP_1': {'location': 'Alicante', ...}, ... }
    for cp_id, cp_data in server_ref.cps.items():
        # Comparamos la ubicación (ignorando mayúsculas/minúsculas)
        cp_location = cp_data.get('location', '').lower()
        if cp_location == city_target.lower():
            
            affected_count += 1
            
            if accion == "ALERT":
                # Lógica idéntica a "parar" de la consola admin
                if cp_data.get('state') != 'Parado':
                    print(f"   ⛔ Parando {cp_id} por clima extremo...")
                    server_ref.set_state(cp_id, 'Parado')
                    try:
                        server_ref.producer.send(CONTROL_TOPIC, {'type': 'parar', 'cp_id': cp_id})
                    except Exception as e:
                        print(f"   [ERROR] Kafka: {e}")

            elif accion == "RECOVER":
                # Lógica idéntica a "reanudar"
                # Solo reanudamos si estaba Parado (no si está Averiado por otra causa)
                if cp_data.get('state') == 'Parado':
                    print(f"   ▶️  Reanudando {cp_id}...")
                    server_ref.set_state(cp_id, 'Activado')
                    try:
                        server_ref.producer.send(CONTROL_TOPIC, {'type': 'reanudar', 'cp_id': cp_id})
                    except Exception as e:
                        print(f"   [ERROR] Kafka: {e}")

    if affected_count == 0:
        return jsonify({"status": "warning", "message": f"No hay CPs en {city_target}"}), 200

    return jsonify({"status": "ok", "processed": affected_count}), 200

def run_api_server():
    
    app.run(host='0.0.0.0', port=9001, debug=False, use_reloader=False)

if __name__ == '__main__':

    main()