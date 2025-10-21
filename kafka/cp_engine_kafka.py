"""CP Engine usando Kafka para comunicación distribuida.

El CP Engine se registra via Kafka, envía telemetría y escucha comandos
del central, manteniendo la funcionalidad original.
"""
import argparse
import asyncio
import signal
import random
from typing import Dict, Any
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from kafka_utils import (
    load_config, get_consumer_config, get_producer_config,
    get_role_topics, get_topics, KafkaMessage, make_msg
)


class KafkaCPEngine:
    def __init__(self, cp_id: str, config_path: str = "kafka_config.yaml"):
        self.cp_id = cp_id
        self.config = load_config(config_path)
        self.topics_map = get_topics(self.config)
        
        # Estado del CP (igual que antes)
        self.suministrando = False
        self.registered = False
        
        # Kafka components
        self.consumer = None
        self.producer = None
        self.running = False

    async def start(self):
        """Inicia los componentes de Kafka."""
        # Configurar consumer con group específico para este CP
        consumer_config = get_consumer_config('cp_engine', self.config, self.cp_id)
        consumer_topics = get_role_topics('cp_engine', self.config, 'consumer')
        
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
        
        print(f"CP Engine {self.cp_id} iniciado")
        print(f"Consumer topics: {consumer_topics}")
        print(f"Consumer group: {consumer_config['group_id']}")
        
        self.running = True

    async def stop(self):
        """Detiene los componentes de Kafka."""
        self.running = False
        if self.consumer:
            await self.consumer.stop()
        if self.producer:
            await self.producer.stop()
        print(f"CP Engine {self.cp_id} detenido")

    async def register(self):
        """Registra el CP con el central."""
        register_msg = make_msg('REGISTER', 'cp', self.cp_id, {
            'location': 'Demo Location',
            'price_kwh': 0.25,
            'max_power': 22.0
        })
        
        await self.send_message(self.topics_map['cp_register'], register_msg)
        print(f"Registro enviado para CP {self.cp_id}")

    async def run(self):
        """Loop principal que procesa mensajes y envía telemetría."""
        try:
            # Registrarse al inicio
            await self.register()
            
            # Crear tareas concurrentes
            tasks = [
                asyncio.create_task(self.message_loop()),
                asyncio.create_task(self.telemetry_loop()),
                asyncio.create_task(self.stdin_loop())
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
            print(f"Error en run: {e}")
        finally:
            await self.stop()

    async def message_loop(self):
        """Loop para procesar mensajes de Kafka."""
        async for msg in self.consumer:
            if not self.running:
                break
                
            await self.process_message(msg)

    async def process_message(self, kafka_msg):
        """Procesa un mensaje recibido de Kafka."""
        try:
            msg = KafkaMessage.from_kafka_message(kafka_msg)
            tipo = msg.get('tipo')
            src = msg.get('source')
            id_ = msg.get('id')
            payload = msg.get('payload', {})

            print(f'RECIBIDO desde topic {kafka_msg.topic}: {tipo} de {src} para {id_}')

            # Solo procesar mensajes dirigidos a este CP
            if id_ != self.cp_id:
                return

            if tipo == 'REGISTER_ACK' and src == 'central':
                status = payload.get('status')
                if status == 'OK':
                    self.registered = True
                    print(f'CP {self.cp_id} registrado exitosamente')
                else:
                    print(f'Error en registro: {payload}')
                    
            elif tipo == 'START_CHARGE' and src == 'central':
                driver_id = payload.get('driver_id')
                print(f'Iniciando carga para driver {driver_id}')
                self.suministrando = True
                
            elif tipo == 'STOP_CHARGE' and src == 'central':
                print('Parando carga por orden del central')
                self.suministrando = False
                
            else:
                print(f'Mensaje no reconocido para CP: {msg}')
                
        except Exception as e:
            print(f'Error procesando mensaje: {e}')

    async def telemetry_loop(self):
        """Envía telemetría cada segundo cuando está suministrando."""
        while self.running:
            if self.suministrando and self.registered:
                # Generar datos de telemetría (lógica original)
                kw = round(random.uniform(3.0, 22.0), 2)
                amount = round(kw * 0.25, 2)
                
                telemetry_msg = make_msg('TELEMETRY', 'cp', self.cp_id, {
                    'kw': kw,
                    'amount': amount,
                    'state': 'Suministrando',
                    'timestamp': asyncio.get_event_loop().time()
                })
                
                await self.send_message(self.topics_map['telemetry'], telemetry_msg)
                
            await asyncio.sleep(1)

    async def stdin_loop(self):
        """Maneja entrada del usuario para control manual."""
        loop = asyncio.get_running_loop()
        
        while self.running:
            try:
                # Ejecutar input bloqueante en un executor
                line = await loop.run_in_executor(
                    None, 
                    input, 
                    f"(CP {self.cp_id}) Enter=toggle suministro, h=health, q=salir> "
                )
                
                if line.strip().lower() == 'q':
                    print(f'Saliendo CP Engine {self.cp_id}')
                    self.running = False
                    break
                elif line.strip().lower() == 'h':
                    # Enviar health check
                    await self.send_health_check()
                else:
                    # Toggle suministro
                    self.suministrando = not self.suministrando
                    state = "suministrando" if self.suministrando else "disponible"
                    print(f'CP {self.cp_id} estado: {state}')
                    
            except EOFError:
                # No hay entrada disponible (modo batch)
                await asyncio.sleep(1)
            except Exception as e:
                print(f"Error en stdin_loop: {e}")
                await asyncio.sleep(1)

    async def send_health_check(self):
        """Envía un health check."""
        # Simular ocasionalmente problemas
        status = 'OK' if random.random() > 0.1 else 'KO'
        
        health_msg = make_msg('HEALTH', 'cp', self.cp_id, {
            'status': status,
            'timestamp': asyncio.get_event_loop().time()
        })
        
        await self.send_message(self.topics_map['health'], health_msg)
        print(f'Health check enviado: {status}')

    async def send_message(self, topic: str, message: Dict[str, Any]):
        """Envía un mensaje a un topic de Kafka."""
        try:
            await self.producer.send_and_wait(topic, message)
        except Exception as e:
            print(f"Error enviando mensaje a {topic}: {e}")


async def main(cp_id: str, config_path: str):
    cp_engine = KafkaCPEngine(cp_id, config_path)
    
    # Configurar manejo de señales
    def signal_handler():
        print(f"\nRecibida señal de interrupción para CP {cp_id}...")
        asyncio.create_task(cp_engine.stop())
    
    # Registrar manejadores de señales
    loop = asyncio.get_running_loop()
    for sig in [signal.SIGTERM, signal.SIGINT]:
        loop.add_signal_handler(sig, signal_handler)
    
    try:
        await cp_engine.start()
        await cp_engine.run()
        
    except Exception as e:
        print(f"Error en main: {e}")
    finally:
        await cp_engine.stop()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='CP Engine con Kafka')
    parser.add_argument('--id', required=True, help='ID único del CP')
    parser.add_argument('--config', default='kafka_config.yaml',
                       help='Ruta al archivo de configuración')
    args = parser.parse_args()
    
    try:
        asyncio.run(main(args.id, args.config))
    except KeyboardInterrupt:
        print(f'CP Engine {args.id} detenido por usuario')