"""Driver client usando Kafka para comunicación distribuida.

El driver solicita autorización via Kafka y escucha la respuesta,
manteniendo la funcionalidad original.
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


class KafkaDriver:
    def __init__(self, driver_id: str, config_path: str = "kafka_config.yaml"):
        self.driver_id = driver_id
        self.config = load_config(config_path)
        self.topics_map = get_topics(self.config)
        
        # Estado del driver
        self.authorized = False
        self.current_cp = None
        
        # Kafka components
        self.consumer = None
        self.producer = None
        self.running = False

    async def start(self):
        """Inicia los componentes de Kafka."""
        # Configurar consumer con group específico para este driver
        consumer_config = get_consumer_config('driver', self.config, self.driver_id)
        consumer_topics = get_role_topics('driver', self.config, 'consumer')
        
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
        
        print(f"Driver {self.driver_id} iniciado")
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
        print(f"Driver {self.driver_id} detenido")

    async def request_auth(self, cp_id: str):
        """Solicita autorización para cargar en un CP específico."""
        auth_msg = make_msg('AUTH_REQUEST', 'driver', self.driver_id, {
            'cp_id': cp_id,
            'timestamp': asyncio.get_event_loop().time()
        })
        
        await self.send_message(self.topics_map['auth_request'], auth_msg)
        print(f"Solicitud de autorización enviada para CP {cp_id}")
        self.current_cp = cp_id

    async def run(self):
        """Loop principal que procesa mensajes."""
        try:
            # Crear tareas concurrentes
            tasks = [
                asyncio.create_task(self.message_loop()),
                asyncio.create_task(self.interactive_loop())
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

            # Solo procesar mensajes dirigidos a este driver
            if id_ != self.driver_id:
                return

            if tipo == 'AUTH_RESPONSE' and src == 'central':
                approved = payload.get('approved')
                cp_id = payload.get('cp_id')
                
                if approved:
                    self.authorized = True
                    print(f'✅ Autorización APROBADA para CP {cp_id}')
                    print('Puede comenzar la carga')
                else:
                    self.authorized = False
                    print(f'❌ Autorización DENEGADA para CP {cp_id}')
                
            elif tipo == 'SESSION_FINISHED' and src == 'central':
                # Ticket final recibido
                ticket = payload
                print(f"🎫 Ticket recibido para sesión {ticket.get('session_id')}: energía={ticket.get('energy_kwh')} kWh, importe={ticket.get('amount')}")
                    
            else:
                print(f'Mensaje no reconocido para driver: {msg}')
                
        except Exception as e:
            print(f'Error procesando mensaje: {e}')

    async def interactive_loop(self):
        """Maneja entrada del usuario para solicitar autorizaciones."""
        loop = asyncio.get_running_loop()
        
        print(f"\n=== Driver {self.driver_id} ===")
        print("Comandos disponibles:")
        print("  auth <cp_id> - Solicitar autorización para un CP")
        print("  status       - Ver estado actual")
        print("  q            - Salir")
        
        while self.running:
            try:
                # Ejecutar input bloqueante en un executor
                line = await loop.run_in_executor(
                    None, 
                    input, 
                    f"(Driver {self.driver_id})> "
                )
                
                command = line.strip().lower()
                
                if command == 'q':
                    print(f'Saliendo Driver {self.driver_id}')
                    self.running = False
                    break
                    
                elif command == 'status':
                    self.show_status()
                    
                elif command.startswith('auth '):
                    parts = command.split()
                    if len(parts) >= 2:
                        cp_id = parts[1]
                        await self.request_auth(cp_id)
                    else:
                        print("Uso: auth <cp_id>")
                        
                elif command == 'help':
                    print("Comandos disponibles:")
                    print("  auth <cp_id> - Solicitar autorización para un CP")
                    print("  status       - Ver estado actual")
                    print("  q            - Salir")
                    
                else:
                    print(f"Comando no reconocido: {command}")
                    print("Escriba 'help' para ver comandos disponibles")
                    
            except EOFError:
                # No hay entrada disponible (modo batch)
                await asyncio.sleep(1)
            except Exception as e:
                print(f"Error en interactive_loop: {e}")
                await asyncio.sleep(1)

    def show_status(self):
        """Muestra el estado actual del driver."""
        print(f"\n=== Estado Driver {self.driver_id} ===")
        print(f"Autorizado: {'Sí' if self.authorized else 'No'}")
        print(f"CP actual: {self.current_cp or 'Ninguno'}")
        print(f"Estado: {'Conectado' if self.running else 'Desconectado'}")
        print()

    async def send_message(self, topic: str, message: Dict[str, Any]):
        """Envía un mensaje a un topic de Kafka."""
        try:
            await self.producer.send_and_wait(topic, message)
        except Exception as e:
            print(f"Error enviando mensaje a {topic}: {e}")


async def run_driver_simple(driver_id: str, cp_id: str, config_path: str):
    """Versión simplificada para ejecutar una sola solicitud de autorización."""
    driver = KafkaDriver(driver_id, config_path)
    
    try:
        await driver.start()
        await driver.request_auth(cp_id)
        
        # Esperar respuesta por un tiempo limitado
        timeout = 10  # segundos
        start_time = asyncio.get_event_loop().time()
        
        async for msg in driver.consumer:
            await driver.process_message(msg)
            
            # Salir si se recibió respuesta o se agotó el tiempo
            if driver.authorized or (asyncio.get_event_loop().time() - start_time) > timeout:
                break
                
        if not driver.authorized and (asyncio.get_event_loop().time() - start_time) > timeout:
            print("Timeout esperando respuesta de autorización")
            
    finally:
        await driver.stop()


async def main(driver_id: str, cp_id: str, config_path: str, interactive: bool):
    if interactive:
        # Modo interactivo
        driver = KafkaDriver(driver_id, config_path)
        
        # Configurar manejo de señales
        def signal_handler():
            print(f"\nRecibida señal de interrupción para Driver {driver_id}...")
            asyncio.create_task(driver.stop())
        
        # Registrar manejadores de señales
        loop = asyncio.get_running_loop()
        for sig in [signal.SIGTERM, signal.SIGINT]:
            loop.add_signal_handler(sig, signal_handler)
        
        try:
            await driver.start()
            await driver.run()
            
        except Exception as e:
            print(f"Error en main: {e}")
        finally:
            await driver.stop()
    else:
        # Modo simple (una sola solicitud)
        await run_driver_simple(driver_id, cp_id, config_path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Driver client con Kafka')
    parser.add_argument('--id', required=True, help='ID único del driver')
    parser.add_argument('--cp', help='ID del CP para autorización (modo simple)')
    parser.add_argument('--config', default='kafka_config.yaml',
                       help='Ruta al archivo de configuración')
    parser.add_argument('--interactive', action='store_true',
                       help='Modo interactivo (por defecto si no se especifica --cp)')
    args = parser.parse_args()
    
    # Determinar modo
    interactive = args.interactive or args.cp is None
    
    if not interactive and not args.cp:
        print("Error: Debe especificar --cp para modo simple o --interactive")
        exit(1)
    
    try:
        asyncio.run(main(args.id, args.cp, args.config, interactive))
    except KeyboardInterrupt:
        print(f'Driver {args.id} detenido por usuario')