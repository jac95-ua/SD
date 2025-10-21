"""Central server usando Kafka para comunicación distribuida.

El central consume mensajes de varios topics y produce respuestas 
correspondientes, manteniendo la lógica de negocio original.
"""
import argparse
import asyncio
import signal
from typing import Dict, Any
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from kafka_utils import (
    load_config, get_consumer_config, get_producer_config,
    get_role_topics, get_topics, KafkaMessage, make_msg
)


class KafkaCentral:
    def __init__(self, config_path: str = "kafka_config.yaml"):
        self.config = load_config(config_path)
        self.topics_map = get_topics(self.config)
        
        # Estado del sistema (igual que antes)
        self.cps: Dict[str, Dict] = {}
        
        # Kafka components
        self.consumer = None
        self.producer = None
        self.running = False

    async def start(self):
        """Inicia los componentes de Kafka."""
        # Configurar consumer
        consumer_config = get_consumer_config('central', self.config)
        consumer_topics = get_role_topics('central', self.config, 'consumer')
        
        self.consumer = AIOKafkaConsumer(
            *consumer_topics,
            **consumer_config
        )
        
        # Configurar producer
        producer_config = get_producer_config(self.config)
        self.producer = AIOKafkaProducer(**producer_config)
        
        # Iniciar componentes
        await self.consumer.start()
        await self.producer.start()
        
        print(f"Central iniciado - Consumer topics: {consumer_topics}")
        print(f"Bootstrap servers: {consumer_config['bootstrap_servers']}")
        
        self.running = True

    async def stop(self):
        """Detiene los componentes de Kafka."""
        self.running = False
        if self.consumer:
            await self.consumer.stop()
        if self.producer:
            await self.producer.stop()
        print("Central detenido")

    async def run(self):
        """Loop principal que procesa mensajes de Kafka."""
        try:
            async for msg in self.consumer:
                if not self.running:
                    break
                
                await self.process_message(msg)
                
        except Exception as e:
            print(f"Error en el loop principal: {e}")
        finally:
            await self.stop()

    async def process_message(self, kafka_msg):
        """Procesa un mensaje recibido de Kafka."""
        try:
            # Extraer el mensaje
            msg = KafkaMessage.from_kafka_message(kafka_msg)
            tipo = msg.get('tipo')
            src = msg.get('source')
            id_ = msg.get('id')
            payload = msg.get('payload', {})

            print(f'RECIBIDO desde topic {kafka_msg.topic}: {tipo} de {src} id {id_} {payload}')

            # Procesar según el tipo de mensaje (lógica original)
            if tipo == 'REGISTER' and src == 'cp':
                await self.handle_cp_register(id_, payload)
                
            elif tipo == 'AUTH_REQUEST' and src == 'driver':
                await self.handle_auth_request(id_, payload)
                
            elif tipo == 'TELEMETRY' and src == 'cp':
                await self.handle_telemetry(id_, payload)
                
            elif tipo == 'HEALTH' and src in ('monitor', 'cp'):
                await self.handle_health(id_, payload)
                
            else:
                print(f"Mensaje no reconocido: {msg}")
                
        except Exception as e:
            print(f'Error procesando mensaje: {e}')

    async def handle_cp_register(self, cp_id: str, payload: Dict[str, Any]):
        """Maneja el registro de un CP."""
        # Registrar CP (lógica original)
        self.cps[cp_id] = {
            'info': payload, 
            'state': 'ACTIVADO',
            'last_seen': asyncio.get_event_loop().time()
        }
        
        # Enviar ACK via Kafka
        response = make_msg('REGISTER_ACK', 'central', cp_id, {'status': 'OK'})
        await self.send_message(self.topics_map['cp_register_ack'], response)
        
        print(f'CP registrado: {cp_id}')

    async def handle_auth_request(self, driver_id: str, payload: Dict[str, Any]):
        """Maneja request de autorización de driver."""
        cp_id = payload.get('cp_id')
        approved = False
        
        if cp_id in self.cps:
            # Política simple: aprobar si el CP existe
            approved = True
            
            # Notificar al CP vía Kafka
            start_charge_msg = make_msg('START_CHARGE', 'central', cp_id, {'driver_id': driver_id})
            await self.send_message(self.topics_map['cp_commands'], start_charge_msg)

        # Responder al driver
        response = make_msg('AUTH_RESPONSE', 'central', driver_id, {
            'approved': approved, 
            'cp_id': cp_id
        })
        await self.send_message(self.topics_map['auth_response'], response)

    async def handle_telemetry(self, cp_id: str, payload: Dict[str, Any]):
        """Maneja telemetría de CP."""
        # Actualizar estado (lógica original)
        self.cps.setdefault(cp_id, {}).setdefault('meta', {})['last_telemetry'] = payload
        self.cps[cp_id]['last_seen'] = asyncio.get_event_loop().time()
        
        print(f"TELEMETRY {cp_id}: {payload}")

    async def handle_health(self, entity_id: str, payload: Dict[str, Any]):
        """Maneja health checks."""
        status = payload.get('status')
        print(f'HEALTH {entity_id}: {status}')
        
        if status == 'KO' and entity_id in self.cps:
            # Marcar CP como averiado
            self.cps[entity_id]['state'] = 'AVERIADO'

    async def send_message(self, topic: str, message: Dict[str, Any]):
        """Envía un mensaje a un topic de Kafka."""
        try:
            await self.producer.send_and_wait(topic, message)
        except Exception as e:
            print(f"Error enviando mensaje a {topic}: {e}")

    async def status_monitor(self):
        """Monitor de estado del sistema."""
        while self.running:
            print(f"\n=== Estado del Sistema ===")
            print(f"CPs registrados: {len(self.cps)}")
            current_time = asyncio.get_event_loop().time()
            
            for cp_id, cp_info in self.cps.items():
                last_seen = cp_info.get('last_seen', 0)
                age = current_time - last_seen
                state = cp_info.get('state', 'UNKNOWN')
                print(f"  {cp_id}: {state} (hace {age:.1f}s)")
            
            await asyncio.sleep(30)  # Update every 30 seconds


async def main(config_path: str):
    central = KafkaCentral(config_path)
    
    # Configurar manejo de señales
    def signal_handler():
        print("\nRecibida señal de interrupción...")
        asyncio.create_task(central.stop())
    
    # Registrar manejadores de señales
    loop = asyncio.get_running_loop()
    for sig in [signal.SIGTERM, signal.SIGINT]:
        loop.add_signal_handler(sig, signal_handler)
    
    try:
        await central.start()
        
        # Iniciar tareas en paralelo
        tasks = [
            asyncio.create_task(central.run()),
            asyncio.create_task(central.status_monitor())
        ]
        
        # Esperar hasta que alguna tarea termine
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        
        # Cancelar tareas pendientes
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
                
    except Exception as e:
        print(f"Error en main: {e}")
    finally:
        await central.stop()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Central server con Kafka')
    parser.add_argument('--config', default='kafka_config.yaml', 
                       help='Ruta al archivo de configuración')
    args = parser.parse_args()
    
    try:
        asyncio.run(main(args.config))
    except KeyboardInterrupt:
        print('Central detenido por usuario')