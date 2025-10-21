# Versión Kafka - Sistema Distribuido de Carga de Vehículos Eléctricos

Esta es la versión distribuida del sistema que funciona en múltiples máquinas usando Apache Kafka como sistema de mensajería.

## 📁 Archivos

- **`central_kafka.py`** - Servidor central distribuido usando Kafka
- **`cp_engine_kafka.py`** - Motor de CP distribuido usando Kafka
- **`driver_kafka.py`** - Cliente conductor distribuido usando Kafka
- **`kafka_utils.py`** - Utilidades y helpers para Kafka
- **`kafka_config.yaml`** - Configuración del cluster de Kafka

## 🏗️ Arquitectura Distribuida

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Máquina 1     │    │   Máquina 2     │    │   Máquina 3     │
│   192.168.1.100 │    │   192.168.1.101 │    │   192.168.1.102 │
├─────────────────┤    ├─────────────────┤    ├─────────────────┤
│ Kafka Broker 1  │◄──►│ Kafka Broker 2  │◄──►│ Kafka Broker 3  │
│ Zookeeper 1     │    │ Zookeeper 2     │    │ Zookeeper 3     │
│                 │    │                 │    │                 │
│ Central Server  │    │ CP Engines      │    │ Drivers         │
│                 │    │ (CP001, CP002)  │    │ CP Engines      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🚀 Configuración Inicial

### 1. Configurar IPs en `kafka_config.yaml`:
```yaml
kafka:
  bootstrap_servers:
    - "192.168.1.100:9092"  # Tu máquina 1
    - "192.168.1.101:9092"  # Tu máquina 2  
    - "192.168.1.102:9092"  # Tu máquina 3
```

### 2. Instalar dependencias:
```bash
pip install -r ../requirements.txt
```

## 🎯 Uso del Sistema

### Servidor Central (Máquina 1):
```bash
python central_kafka.py --config kafka_config.yaml
```

### Punto de Carga (Máquina 2):
```bash
python cp_engine_kafka.py --id CP001 --config kafka_config.yaml
```

### Driver Interactivo (Máquina 3):
```bash
python driver_kafka.py --id DRIVER001 --interactive --config kafka_config.yaml
```

### Driver Simple (una solicitud):
```bash
python driver_kafka.py --id DRIVER001 --cp CP001 --config kafka_config.yaml
```

## 📨 Topics de Kafka

- **`cp-register`** - Registro de puntos de carga
- **`cp-register-ack`** - Confirmaciones de registro
- **`auth-request`** - Solicitudes de autorización
- **`auth-response`** - Respuestas de autorización
- **`cp-commands`** - Comandos del central a CPs
- **`telemetry`** - Datos de telemetría de CPs
- **`health`** - Health checks y estado

## ✅ Ventajas de la Versión Kafka

- **🌐 Distribuido**: Funciona en múltiples máquinas
- **📈 Escalable**: Fácil añadir más componentes
- **🛡️ Tolerante a fallos**: Continúa funcionando si una máquina falla
- **💾 Persistente**: Los mensajes se guardan en disco
- **📊 Monitoreable**: Métricas detalladas disponibles
- **🔄 Asíncrono**: Comunicación no bloqueante
- **⚡ Alto rendimiento**: Maneja miles de mensajes por segundo

## 🔧 Comandos Útiles

### Verificar topics:
```bash
kafka-topics.sh --list --bootstrap-server localhost:9092
```

### Monitorear mensajes:
```bash
kafka-console-consumer.sh --topic telemetry --bootstrap-server localhost:9092
```

### Ver estado del cluster:
```bash
kafka-broker-api-versions.sh --bootstrap-server localhost:9092
```

## 🎛️ Configuración Avanzada

### Consumer Groups:
- **Central**: `central-group`
- **CP Engine**: `cp-{cp_id}-group`
- **Driver**: `driver-{driver_id}-group`

### Replicación:
- **Factor de replicación**: 2
- **Particiones por topic**: 3
- **Min in-sync replicas**: 2

## 🚨 Troubleshooting

### Verificar conectividad:
```bash
telnet 192.168.1.100 9092
```

### Ver logs de Kafka:
```bash
tail -f /tmp/kafka-logs/server.log
```

### Reiniciar servicios:
```bash
sudo systemctl restart kafka zookeeper
```

Esta versión es ideal para entornos de producción y sistemas que requieren alta disponibilidad y escalabilidad.