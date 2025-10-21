"""CP Monitor usando Kafka para comunicación distribuida.

El monitor envía health checks periódicos y puede simular fallos
para probar la tolerancia a fallos del sistema.
"""
import argparse
import asyncio
import signal
import random
from typing import Dict, Any
from aiokafka import AIOKafkaProducer
from kafka_utils import (
    load_config, get_producer_config, get_topics, make_msg
)


class KafkaCPMonitor:
    def __init__(self, cp_id: str, config_path: str = "kafka_config.yaml"):
        self.cp_id = cp_id
        self.config = load_config(config_path)
        self.topics_map = get_topics(self.config)
        
        # Estado del monitor
        self.running = False
        self.fault_probability = 0.02  # 2% probabilidad de fallo
        self.check_interval = 5  # segundos entre checks
        
        # Kafka components
        self.producer = None

    async def start(self):
        """Inicia los componentes de Kafka."""
        # Configurar producer
        producer_config = get_producer_config(self.config)
        self.producer = AIOKafkaProducer(**producer_config)
        
        # Iniciar producer
        await self.producer.start()
        
        print(f"CP Monitor {self.cp_id} iniciado")
        print(f"Intervalo de checks: {self.check_interval}s")
        print(f"Probabilidad de fallo: {self.fault_probability*100:.1f}%")
        
        self.running = True

    async def stop(self):
        """Detiene los componentes de Kafka."""
        self.running = False
        if self.producer:
            await self.producer.stop()
        print(f"CP Monitor {self.cp_id} detenido")

    async def run(self):
        """Loop principal que envía health checks periódicos."""
        try:
            # Crear tareas concurrentes
            tasks = [
                asyncio.create_task(self.health_loop()),
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

    async def health_loop(self):
        """Loop que envía health checks periódicos."""
        print("Iniciando monitoreo de salud...")
        
        while self.running:
            # Determinar estado de salud
            if random.random() < self.fault_probability:
                status = 'KO'
                print(f'🔴 FALLO simulado detectado en CP {self.cp_id}')
            else:
                status = 'OK'
                print(f'🟢 CP {self.cp_id} funcionando correctamente')
            
            # Enviar health check
            await self.send_health_check(status)
            
            # Esperar hasta el próximo check
            await asyncio.sleep(self.check_interval)

    async def send_health_check(self, status: str):
        """Envía un health check al central."""
        health_msg = make_msg('HEALTH', 'monitor', self.cp_id, {
            'status': status,
            'timestamp': asyncio.get_event_loop().time(),
            'check_interval': self.check_interval,
            'monitor_id': f'MONITOR-{self.cp_id}'
        })
        
        await self.send_message(self.topics_map['health'], health_msg)

    async def interactive_loop(self):
        """Maneja entrada del usuario para control manual."""
        loop = asyncio.get_running_loop()
        
        print(f"\n=== Monitor {self.cp_id} ===")
        print("Comandos disponibles:")
        print("  ok               - Enviar health check OK")
        print("  ko               - Enviar health check KO")
        print("  fault <prob>     - Cambiar probabilidad de fallo (0.0-1.0)")
        print("  interval <seg>   - Cambiar intervalo de checks")
        print("  status           - Ver configuración actual")
        print("  q                - Salir")
        
        while self.running:
            try:
                # Ejecutar input bloqueante en un executor
                line = await loop.run_in_executor(
                    None, 
                    input, 
                    f"(Monitor {self.cp_id})> "
                )
                
                command = line.strip().lower()
                parts = command.split()
                
                if command == 'q':
                    print(f'Saliendo Monitor {self.cp_id}')
                    self.running = False
                    break
                    
                elif command == 'ok':
                    await self.send_health_check('OK')
                    print("Health check OK enviado manualmente")
                    
                elif command == 'ko':
                    await self.send_health_check('KO')
                    print("Health check KO enviado manualmente")
                    
                elif command == 'status':
                    self.show_status()
                    
                elif parts[0] == 'fault' and len(parts) == 2:
                    try:
                        prob = float(parts[1])
                        if 0.0 <= prob <= 1.0:
                            self.fault_probability = prob
                            print(f"Probabilidad de fallo cambiada a {prob*100:.1f}%")
                        else:
                            print("Probabilidad debe estar entre 0.0 y 1.0")
                    except ValueError:
                        print("Probabilidad debe ser un número")
                        
                elif parts[0] == 'interval' and len(parts) == 2:
                    try:
                        interval = int(parts[1])
                        if interval > 0:
                            self.check_interval = interval
                            print(f"Intervalo cambiado a {interval} segundos")
                        else:
                            print("Intervalo debe ser mayor que 0")
                    except ValueError:
                        print("Intervalo debe ser un número entero")
                        
                elif command == 'help':
                    print("Comandos disponibles:")
                    print("  ok               - Enviar health check OK")
                    print("  ko               - Enviar health check KO")
                    print("  fault <prob>     - Cambiar probabilidad de fallo")
                    print("  interval <seg>   - Cambiar intervalo de checks")
                    print("  status           - Ver configuración actual")
                    print("  q                - Salir")
                    
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
        """Muestra el estado actual del monitor."""
        print(f"\n=== Estado Monitor {self.cp_id} ===")
        print(f"Estado: {'Activo' if self.running else 'Inactivo'}")
        print(f"Intervalo de checks: {self.check_interval} segundos")
        print(f"Probabilidad de fallo: {self.fault_probability*100:.1f}%")
        print(f"Topic de health: {self.topics_map['health']}")
        print()

    async def send_message(self, topic: str, message: Dict[str, Any]):
        """Envía un mensaje a un topic de Kafka."""
        try:
            await self.producer.send_and_wait(topic, message)
        except Exception as e:
            print(f"Error enviando mensaje a {topic}: {e}")


async def main(cp_id: str, config_path: str, fault_prob: float, interval: int):
    monitor = KafkaCPMonitor(cp_id, config_path)
    
    # Configurar parámetros iniciales
    if fault_prob is not None:
        monitor.fault_probability = fault_prob
    if interval is not None:
        monitor.check_interval = interval
    
    # Configurar manejo de señales
    def signal_handler():
        print(f"\nRecibida señal de interrupción para Monitor {cp_id}...")
        asyncio.create_task(monitor.stop())
    
    # Registrar manejadores de señales
    loop = asyncio.get_running_loop()
    for sig in [signal.SIGTERM, signal.SIGINT]:
        loop.add_signal_handler(sig, signal_handler)
    
    try:
        await monitor.start()
        await monitor.run()
        
    except Exception as e:
        print(f"Error en main: {e}")
    finally:
        await monitor.stop()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='CP Monitor con Kafka')
    parser.add_argument('--id', required=True, help='ID del CP a monitorear')
    parser.add_argument('--config', default='kafka_config.yaml',
                       help='Ruta al archivo de configuración')
    parser.add_argument('--fault-prob', type=float, 
                       help='Probabilidad de fallo (0.0-1.0, default: 0.02)')
    parser.add_argument('--interval', type=int,
                       help='Intervalo entre checks en segundos (default: 5)')
    args = parser.parse_args()
    
    try:
        asyncio.run(main(args.id, args.config, args.fault_prob, args.interval))
    except KeyboardInterrupt:
        print(f'Monitor {args.id} detenido por usuario')