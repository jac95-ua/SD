#!/bin/bash
# Script para crear topics de Kafka necesarios para el sistema
# Ejecutar después de que todos los brokers estén funcionando

set -e

KAFKA_DIR="/opt/kafka"
BOOTSTRAP_SERVERS="192.168.1.100:9092,192.168.1.101:9092,192.168.1.102:9092"

echo "=== Creando topics de Kafka ==="

# Función para crear un topic
create_topic() {
    local topic_name=$1
    local partitions=${2:-3}
    local replication=${3:-2}
    
    echo "Creando topic: $topic_name (particiones: $partitions, replicación: $replication)"
    
    $KAFKA_DIR/bin/kafka-topics.sh \
        --create \
        --bootstrap-server $BOOTSTRAP_SERVERS \
        --topic $topic_name \
        --partitions $partitions \
        --replication-factor $replication \
        --if-not-exists
}

# Crear todos los topics necesarios
create_topic "cp-register" 3 2
create_topic "cp-register-ack" 3 2
create_topic "auth-request" 3 2
create_topic "auth-response" 3 2
create_topic "cp-commands" 3 2
create_topic "telemetry" 3 2
create_topic "health" 3 2

echo ""
echo "=== Listando topics creados ==="
$KAFKA_DIR/bin/kafka-topics.sh \
    --list \
    --bootstrap-server $BOOTSTRAP_SERVERS

echo ""
echo "=== Detalles de los topics ==="
$KAFKA_DIR/bin/kafka-topics.sh \
    --describe \
    --bootstrap-server $BOOTSTRAP_SERVERS

echo ""
echo "Topics creados exitosamente!"