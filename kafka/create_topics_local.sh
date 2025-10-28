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
)

for t in "${topics[@]}"; do
  echo "Creando topic: $t"
  docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T kafka kafka-topics.sh --create --bootstrap-server localhost:9092 --topic "$t" --partitions 1 --replication-factor 1 || true
done

echo "Topics creados (si ya existían el comando los ignoró)."
