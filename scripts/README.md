# Scripts de Despliegue - Sistema de Carga de Vehículos Eléctricos

Scripts para automatizar la instalación y configuración del sistema distribuido con Kafka.

## 📁 Archivos

- **`setup_kafka.sh`** - Instala y configura Kafka en cada máquina
- **`create_topics.sh`** - Crea los topics necesarios en Kafka
- **`deploy_app.sh`** - Despliega la aplicación Python según el rol

## 🚀 Proceso de Despliegue

### 1. Preparación de Máquinas

En cada una de las 3 máquinas, ejecutar:

```bash
# Actualizar sistema
sudo apt update && sudo apt upgrade -y

# Instalar Java (requerido para Kafka)
sudo apt install default-jdk -y

# Instalar Python
sudo apt install python3 python3-pip python3-venv -y

# Verificar Java
java -version
```

### 2. Instalación de Kafka

En cada máquina ejecutar con el número correspondiente:

```bash
# Máquina 1
./setup_kafka.sh 1

# Máquina 2  
./setup_kafka.sh 2

# Máquina 3
./setup_kafka.sh 3
```

### 3. Iniciar Servicios de Kafka

En cada máquina:

```bash
# Iniciar servicios
sudo systemctl start zookeeper
sudo systemctl start kafka

# Habilitar arranque automático
sudo systemctl enable zookeeper
sudo systemctl enable kafka

# Verificar estado
sudo systemctl status zookeeper
sudo systemctl status kafka
```

### 4. Crear Topics

Ejecutar **solo una vez** desde cualquier máquina:

```bash
./create_topics.sh
```

### 5. Desplegar Aplicaciones

#### Máquina 1 (Central):
```bash
./deploy_app.sh central
sudo systemctl start evcharging-central
sudo systemctl enable evcharging-central
```

#### Máquina 2 (CPs):
```bash
./deploy_app.sh cp

# Iniciar CPs específicos
sudo systemctl start evcharging-cp@CP001
sudo systemctl start evcharging-cp@CP002
sudo systemctl enable evcharging-cp@CP001
sudo systemctl enable evcharging-cp@CP002

# O usar el script de gestión
/opt/evcharging/manage_cps.sh start CP001
/opt/evcharging/manage_cps.sh start CP002
```

#### Máquina 3 (Drivers):
```bash
./deploy_app.sh driver

# Iniciar driver interactivo
/opt/evcharging/start_driver.sh DRIVER001

# O solicitar autorización simple
/opt/evcharging/request_auth.sh DRIVER001 CP001
```

## 🔧 Scripts Detallados

### `setup_kafka.sh`

**Uso**: `./setup_kafka.sh <machine_number>`

**Funciones**:
- Descarga e instala Kafka
- Configura Zookeeper para cluster de 3 nodos
- Configura broker Kafka con ID único
- Crea servicios systemd
- Configura red y puertos

**Parámetros**:
- `machine_number`: 1, 2 o 3

### `create_topics.sh`

**Funciones**:
- Crea todos los topics necesarios
- Configura particiones (3) y replicación (2)
- Verifica que los topics se crearon correctamente

**Topics creados**:
- cp-register, cp-register-ack
- auth-request, auth-response  
- cp-commands, telemetry, health

### `deploy_app.sh`

**Uso**: `./deploy_app.sh <role>`

**Roles disponibles**:
- `central`: Despliega servidor central
- `cp`: Despliega servicios para CPs
- `driver`: Despliega scripts para drivers

**Funciones**:
- Crea entorno virtual Python
- Instala dependencias
- Configura servicios systemd
- Crea scripts de utilidad

## 🎛️ Gestión de Servicios

### Comandos Básicos:

```bash
# Ver estado de todos los servicios
sudo systemctl status zookeeper kafka evcharging-*

# Ver logs
sudo journalctl -u evcharging-central -f
sudo journalctl -u evcharging-cp@CP001 -f

# Reiniciar servicios
sudo systemctl restart evcharging-central
sudo systemctl restart evcharging-cp@CP001
```

### Gestión de CPs:

```bash
# Ver todos los CPs
/opt/evcharging/manage_cps.sh list

# Ver estado de todos los CPs
/opt/evcharging/manage_cps.sh status

# Iniciar/parar CP específico
/opt/evcharging/manage_cps.sh start CP001
/opt/evcharging/manage_cps.sh stop CP001
```

## 📊 Monitoreo

### Verificar Kafka:

```bash
# Listar topics
/opt/kafka/bin/kafka-topics.sh --list --bootstrap-server localhost:9092

# Ver mensajes en tiempo real
/opt/kafka/bin/kafka-console-consumer.sh --topic telemetry --bootstrap-server localhost:9092

# Ver consumer groups
/opt/kafka/bin/kafka-consumer-groups.sh --list --bootstrap-server localhost:9092
```

### Verificar Aplicaciones:

```bash
# Logs del central
tail -f /var/log/syslog | grep evcharging-central

# Logs de CPs
tail -f /var/log/syslog | grep evcharging-cp
```

## 🚨 Troubleshooting

### Problemas Comunes:

1. **Kafka no inicia**:
   ```bash
   # Verificar logs
   sudo journalctl -u kafka -f
   # Verificar Java
   java -version
   ```

2. **Topics no se crean**:
   ```bash
   # Verificar conectividad
   telnet localhost 9092
   # Verificar Zookeeper
   sudo systemctl status zookeeper
   ```

3. **Aplicación no se conecta**:
   ```bash
   # Verificar configuración
   cat /opt/evcharging/kafka_config.yaml
   # Verificar IPs de red
   ip addr show
   ```

### Reinicio Completo:

```bash
# Parar todo
sudo systemctl stop evcharging-* kafka zookeeper

# Limpiar datos (CUIDADO: borra todo)
sudo rm -rf /tmp/kafka-logs /tmp/zookeeper

# Reiniciar servicios
sudo systemctl start zookeeper kafka evcharging-*
```

## 📋 Checklist de Despliegue

- [ ] Java instalado en todas las máquinas
- [ ] Python 3.7+ instalado en todas las máquinas  
- [ ] IPs configuradas en `kafka_config.yaml`
- [ ] Kafka instalado y configurado (3 máquinas)
- [ ] Servicios Zookeeper y Kafka iniciados (3 máquinas)
- [ ] Topics creados (una vez)
- [ ] Aplicaciones desplegadas según rol
- [ ] Servicios de aplicación iniciados
- [ ] Verificación de conectividad completa

¡Con estos scripts tendrás el sistema distribuido funcionando en minutos!