# Sistema de Carga de Vehículos Eléctricos - Configuración Distribuida con Kafka

Este documento explica cómo configurar y ejecutar el sistema de carga de vehículos eléctricos en un entorno distribuido usando Apache Kafka en tres ordenadores.

## Arquitectura del Sistema

### Componentes

1. **Central**: Servidor central que maneja autorizaciones y coordina el sistema
2. **CP Engine**: Puntos de carga que se registran y envían telemetría
3. **Driver**: Clientes que solicitan autorización para cargar

### Comunicación

- **Antes**: TCP sockets directos entre componentes
- **Ahora**: Apache Kafka como broker de mensajes distribuido

### Topics de Kafka

| Topic | Descripción | Producers | Consumers |
|-------|-------------|-----------|-----------|
| `cp-register` | Registro de CPs | CP Engine | Central |
| `cp-register-ack` | Confirmación de registro | Central | CP Engine |
| `auth-request` | Solicitudes de autorización | Driver | Central |
| `auth-response` | Respuestas de autorización | Central | Driver |
| `cp-commands` | Comandos a CPs | Central | CP Engine |
| `telemetry` | Datos de telemetría | CP Engine | Central |
| `health` | Health checks | CP/Monitor | Central |

## Configuración de la Red

### Prerequisitos

- 3 ordenadores en la misma red local
- Java 8+ instalado en cada máquina
- Python 3.8+ con pip
- Acceso root/sudo en cada máquina

### Asignación de IPs (ajustar según tu red)

```
Máquina 1 (Central):    192.168.1.100
Máquina 2 (CP Engine):  192.168.1.101  
Máquina 3 (Driver/CP):  192.168.1.102
```

## Instalación y Configuración

### Paso 1: Preparar cada máquina

En **todas las máquinas**, ejecutar:

```bash
# Instalar Java si no está instalado
sudo apt update
sudo apt install default-jdk python3 python3-pip python3-venv -y

# Verificar Java
java -version
```

### Paso 2: Configurar Kafka

En **cada máquina**, ejecutar:

```bash
# Descargar los archivos del proyecto
git clone <tu-repositorio>
cd SD

# Ajustar las IPs en kafka_config.yaml según tu red
nano kafka_config.yaml

# Ejecutar setup según el número de máquina
./setup_kafka.sh 1  # En máquina 1
./setup_kafka.sh 2  # En máquina 2  
./setup_kafka.sh 3  # En máquina 3
```

### Paso 3: Iniciar servicios Kafka

En **todas las máquinas**, en orden:

```bash
# Iniciar Zookeeper (esperar 10-15 segundos entre máquinas)
sudo systemctl start zookeeper
sudo systemctl status zookeeper

# Iniciar Kafka (esperar 10-15 segundos entre máquinas)
sudo systemctl start kafka
sudo systemctl status kafka

# Habilitar para inicio automático
sudo systemctl enable zookeeper
sudo systemctl enable kafka
```

### Paso 4: Crear topics

En **cualquier máquina** (preferiblemente máquina 1):

```bash
./create_topics.sh
```

### Paso 5: Desplegar aplicaciones

#### En Máquina 1 (Central):

```bash
./deploy_app.sh central
sudo systemctl start evcharging-central
sudo systemctl enable evcharging-central
sudo systemctl status evcharging-central
```

#### En Máquina 2 (CP Engine):

```bash
./deploy_app.sh cp

# Iniciar CPs individuales
sudo systemctl start evcharging-cp@CP001
sudo systemctl start evcharging-cp@CP002
sudo systemctl enable evcharging-cp@CP001
sudo systemctl enable evcharging-cp@CP002

# Verificar estado
/opt/evcharging/manage_cps.sh status
```

#### En Máquina 3 (Driver/CP):

```bash
./deploy_app.sh driver
./deploy_app.sh cp  # Si también quiere CPs en esta máquina

# Para drivers interactivos
/opt/evcharging/start_driver.sh DRIVER001

# Para autorización simple
/opt/evcharging/request_auth.sh DRIVER001 CP001
```

## Verificación del Sistema

### Verificar Kafka

```bash
# Listar topics
/opt/kafka/bin/kafka-topics.sh --list --bootstrap-server 192.168.1.100:9092

# Monitorear mensajes (en terminal separado)
/opt/kafka/bin/kafka-console-consumer.sh \
    --bootstrap-server 192.168.1.100:9092 \
    --topic telemetry \
    --from-beginning
```

### Verificar servicios

```bash
# Estado del central
sudo systemctl status evcharging-central

# Estado de CPs
sudo systemctl status 'evcharging-cp@*'

# Logs del central
sudo journalctl -u evcharging-central -f

# Logs de CP
sudo journalctl -u evcharging-cp@CP001 -f
```

## Uso del Sistema

### Flujo típico:

1. **CPs se registran** automáticamente al iniciar
2. **Driver solicita autorización**:
   ```bash
   /opt/evcharging/start_driver.sh DRIVER001
   # En el prompt: auth CP001
   ```
3. **Central autoriza** y notifica al CP
4. **CP comienza suministro** y envía telemetría
5. **Driver recibe confirmación**

### Comandos útiles:

```bash
# Gestión de CPs
/opt/evcharging/manage_cps.sh start CP003
/opt/evcharging/manage_cps.sh stop CP001
/opt/evcharging/manage_cps.sh status

# Driver interactivo
/opt/evcharging/start_driver.sh DRIVER002

# Autorización rápida
/opt/evcharging/request_auth.sh DRIVER002 CP002
```

## Monitoreo y Logs

### Ubicaciones de logs:

- **Kafka**: `/opt/kafka/logs/`
- **Zookeeper**: `/tmp/zookeeper/zookeeper.out`
- **Central**: `sudo journalctl -u evcharging-central`
- **CPs**: `sudo journalctl -u evcharging-cp@CP001`

### Comandos de monitoreo:

```bash
# Ver topics y particiones
/opt/kafka/bin/kafka-topics.sh --describe --bootstrap-server 192.168.1.100:9092

# Consumer groups
/opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server 192.168.1.100:9092 --list

# Métricas de un consumer group
/opt/kafka/bin/kafka-consumer-groups.sh \
    --bootstrap-server 192.168.1.100:9092 \
    --describe --group central-group
```

## Troubleshooting

### Problemas comunes:

1. **Kafka no inicia**:
   - Verificar que Zookeeper esté funcionando
   - Verificar conectividad de red entre máquinas
   - Revisar logs: `sudo journalctl -u kafka`

2. **Aplicación no encuentra Kafka**:
   - Verificar IPs en `kafka_config.yaml`
   - Verificar que todos los brokers estén activos
   - Probar conectividad: `telnet 192.168.1.100 9092`

3. **CPs no se registran**:
   - Verificar que el topic `cp-register` existe
   - Verificar logs del CP: `sudo journalctl -u evcharging-cp@CP001`
   - Verificar que el central esté consumiendo

4. **Drivers no reciben respuestas**:
   - Verificar consumer group del driver
   - Verificar topic `auth-response`
   - Verificar logs del central

### Comandos de diagnóstico:

```bash
# Test de conectividad a Kafka
echo "test" | /opt/kafka/bin/kafka-console-producer.sh \
    --bootstrap-server 192.168.1.100:9092 \
    --topic test-topic

# Listar consumer groups activos
/opt/kafka/bin/kafka-consumer-groups.sh \
    --bootstrap-server 192.168.1.100:9092 \
    --list

# Verificar lag de consumers
/opt/kafka/bin/kafka-consumer-groups.sh \
    --bootstrap-server 192.168.1.100:9092 \
    --describe --all-groups
```

## Escalabilidad

### Añadir más CPs:

```bash
# En cualquier máquina con rol CP
sudo systemctl start evcharging-cp@CP004
sudo systemctl enable evcharging-cp@CP004
```

### Añadir más máquinas:

1. Instalar y configurar Kafka como broker adicional
2. Ajustar `kafka_config.yaml` en todas las máquinas
3. Reiniciar servicios para que reconozcan el nuevo broker

### Balanceado de carga:

- Kafka distribuye automáticamente los mensajes
- Consumer groups permiten múltiples instancias del central
- Particiones múltiples mejoran el throughput

## Configuración Avanzada

### Variables de entorno útiles:

```bash
export KAFKA_HEAP_OPTS="-Xmx1G -Xms1G"  # Ajustar memoria de Kafka
export KAFKA_JVM_PERFORMANCE_OPTS="-server -XX:+UseG1GC"
```

### Ajustes de red:

En `/opt/kafka/config/server.properties`:

```properties
# Aumentar timeouts para redes lentas
zookeeper.session.timeout.ms=30000
group.initial.rebalance.delay.ms=3000

# Ajustar buffers de red
socket.send.buffer.bytes=1048576
socket.receive.buffer.bytes=1048576
```

## Conclusión

Este sistema distribuido con Kafka proporciona:

- **Alta disponibilidad**: Tolerancia a fallos de máquinas individuales
- **Escalabilidad**: Fácil adición de nuevos componentes
- **Persistencia**: Los mensajes se almacenan en disco
- **Monitoreo**: Métricas detalladas de todos los componentes

Para soporte adicional, consultar los logs del sistema y la documentación oficial de Apache Kafka.