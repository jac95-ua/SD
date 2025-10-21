#!/bin/bash
# Script para configurar e instalar Kafka en los tres ordenadores
# Ejecutar como: ./setup_kafka.sh <machine_number>

set -e

MACHINE_NUM=${1:-1}
KAFKA_VERSION="2.13-3.6.0"
KAFKA_DIR="/opt/kafka"
KAFKA_CONFIG_DIR="$KAFKA_DIR/config"

echo "=== Configurando Kafka en máquina $MACHINE_NUM ==="

# Verificar que se proporcionó el número de máquina
if [[ ! "$MACHINE_NUM" =~ ^[1-3]$ ]]; then
    echo "Error: Número de máquina debe ser 1, 2 o 3"
    echo "Uso: $0 <machine_number>"
    exit 1
fi

# Configurar IPs según el número de máquina (ajustar según tu red)
case $MACHINE_NUM in
    1)
        BROKER_ID=1
        ADVERTISED_HOST="192.168.1.100"
        ;;
    2)
        BROKER_ID=2
        ADVERTISED_HOST="192.168.1.101"
        ;;
    3)
        BROKER_ID=3
        ADVERTISED_HOST="192.168.1.102"
        ;;
esac

echo "Configurando broker ID: $BROKER_ID en host: $ADVERTISED_HOST"

# Descargar e instalar Kafka si no existe
if [ ! -d "$KAFKA_DIR" ]; then
    echo "Descargando e instalando Kafka..."
    sudo mkdir -p /opt
    cd /tmp
    
    if [ ! -f "kafka_$KAFKA_VERSION.tgz" ]; then
        wget "https://downloads.apache.org/kafka/3.6.0/kafka_$KAFKA_VERSION.tgz"
    fi
    
    sudo tar -xzf "kafka_$KAFKA_VERSION.tgz" -C /opt/
    sudo mv "/opt/kafka_$KAFKA_VERSION" "$KAFKA_DIR"
    sudo chown -R $USER:$USER "$KAFKA_DIR"
    
    echo "Kafka instalado en $KAFKA_DIR"
else
    echo "Kafka ya está instalado en $KAFKA_DIR"
fi

# Configurar Zookeeper
echo "Configurando Zookeeper..."
cat > "$KAFKA_CONFIG_DIR/zookeeper.properties" << EOF
# Configuración de Zookeeper para cluster de 3 nodos
dataDir=/tmp/zookeeper
clientPort=2181
maxClientCnxns=0
admin.enableServer=false

# Configuración del cluster
initLimit=5
syncLimit=2

# Servidores del cluster
server.1=192.168.1.100:2888:3888
server.2=192.168.1.101:2888:3888
server.3=192.168.1.102:2888:3888
EOF

# Crear directorio de datos de Zookeeper y archivo myid
sudo mkdir -p /tmp/zookeeper
echo "$BROKER_ID" | sudo tee /tmp/zookeeper/myid

# Configurar Kafka
echo "Configurando Kafka server..."
cat > "$KAFKA_CONFIG_DIR/server.properties" << EOF
# Configuración del broker Kafka
broker.id=$BROKER_ID
listeners=PLAINTEXT://0.0.0.0:9092
advertised.listeners=PLAINTEXT://$ADVERTISED_HOST:9092

# Configuración de red
socket.send.buffer.bytes=102400
socket.receive.buffer.bytes=102400
socket.request.max.bytes=104857600

# Configuración de logs
log.dirs=/tmp/kafka-logs
num.network.threads=3
num.io.threads=8
num.partitions=3
num.recovery.threads.per.data.dir=1

# Configuración de Zookeeper
zookeeper.connect=192.168.1.100:2181,192.168.1.101:2181,192.168.1.102:2181
zookeeper.connection.timeout.ms=18000

# Configuración de replicación
default.replication.factor=2
min.insync.replicas=2

# Configuración de retención
log.retention.hours=168
log.segment.bytes=1073741824
log.retention.check.interval.ms=300000

# Configuración de limpieza
log.cleanup.policy=delete
EOF

# Crear directorios de logs
sudo mkdir -p /tmp/kafka-logs
sudo chown -R $USER:$USER /tmp/kafka-logs

# Crear servicios systemd
echo "Creando servicios systemd..."

# Servicio Zookeeper
sudo tee /etc/systemd/system/zookeeper.service > /dev/null << EOF
[Unit]
Description=Apache Zookeeper server
Documentation=http://zookeeper.apache.org
Requires=network.target remote-fs.target
After=network.target remote-fs.target

[Service]
Type=forking
User=$USER
Group=$USER
Environment=JAVA_HOME=/usr/lib/jvm/default-java
ExecStart=$KAFKA_DIR/bin/zookeeper-server-start.sh -daemon $KAFKA_CONFIG_DIR/zookeeper.properties
ExecStop=$KAFKA_DIR/bin/zookeeper-server-stop.sh
Restart=on-abnormal

[Install]
WantedBy=multi-user.target
EOF

# Servicio Kafka
sudo tee /etc/systemd/system/kafka.service > /dev/null << EOF
[Unit]
Description=Apache Kafka server
Documentation=http://kafka.apache.org/documentation.html
Requires=zookeeper.service
After=zookeeper.service

[Service]
Type=forking
User=$USER
Group=$USER
Environment=JAVA_HOME=/usr/lib/jvm/default-java
ExecStart=$KAFKA_DIR/bin/kafka-server-start.sh -daemon $KAFKA_CONFIG_DIR/server.properties
ExecStop=$KAFKA_DIR/bin/kafka-server-stop.sh
Restart=on-abnormal

[Install]
WantedBy=multi-user.target
EOF

# Recargar systemd
sudo systemctl daemon-reload

echo "=== Configuración completada ==="
echo "Para iniciar los servicios:"
echo "  sudo systemctl start zookeeper"
echo "  sudo systemctl start kafka"
echo ""
echo "Para habilitarlos al inicio:"
echo "  sudo systemctl enable zookeeper"
echo "  sudo systemctl enable kafka"
echo ""
echo "Para verificar el estado:"
echo "  sudo systemctl status zookeeper"
echo "  sudo systemctl status kafka"