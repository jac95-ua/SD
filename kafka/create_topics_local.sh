#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Creando topics en Kafka (localhost:9092) ..."

topics=(
  cp-register
  cp-register-ack
  auth-request
  auth-response
  cp-commands
  telemetry
  health
  session-finished
)

# Detectar comando de compose disponible
COMPOSE_CMD=()
if docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD=(docker compose -f "$ROOT_DIR/docker-compose.yml")
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD=(docker-compose -f "$ROOT_DIR/docker-compose.yml")
elif command -v podman-compose >/dev/null 2>&1; then
  COMPOSE_CMD=(podman-compose -f "$ROOT_DIR/docker-compose.yml")
else
  echo "Error: no se encontró 'docker compose', 'docker-compose' ni 'podman-compose' en PATH" >&2
  exit 1
fi

# Dentro del contenedor intentaremos varios nombres/rutas para kafka-topics
KAFKA_CMD_TRIES=("kafka-topics.sh" "kafka-topics" "/opt/bitnami/kafka/bin/kafka-topics.sh" "/opt/confluent/bin/kafka-topics" "/usr/bin/kafka-topics" )

for t in "${topics[@]}"; do
  echo "Creando topic: $t"
  # Construir comando que pruebe varios posibles ejecutables dentro del contenedor
  CMD=
  CMD+='for c in '
  for cmd in "${KAFKA_CMD_TRIES[@]}"; do
    CMD+="'$cmd' ";
  done
  CMD+='; do '
  CMD+='if command -v "$c" >/dev/null 2>&1 || [ -x "$c" ]; then '
  CMD+='  "$c" --create --bootstrap-server localhost:9092 --topic "'"$t"'" --partitions 1 --replication-factor 1 && exit 0; '
  CMD+='fi; '
  CMD+='done; exit 0'

  "${COMPOSE_CMD[@]}" exec -T kafka bash -lc "$CMD" || true
done

echo "Topics creados (si ya existían el comando los ignoró)."
