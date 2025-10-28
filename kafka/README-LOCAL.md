# Pruebas locales con Docker Compose

Este documento explica cómo levantar un broker Kafka local (single-node) usando
Docker Compose y cómo crear los topics necesarios para la práctica.

Requisitos
- Docker y Docker Compose instalados en la máquina.
- En el directorio `kafka/` del repositorio.

Pasos rápidos

1) Levantar Zookeeper + Kafka

```bash
cd kafka
docker compose up -d
```

2) Verificar que los contenedores están en marcha

```bash
docker compose ps
docker compose logs -f kafka
```

3) Crear topics (hay un script de ayuda `create_topics_local.sh`)

```bash
chmod +x create_topics_local.sh
./create_topics_local.sh
```

El script creará los topics: cp-register, cp-register-ack, auth-request, auth-response, cp-commands, telemetry, health.

4) Configura los scripts de Python para usar `kafka_config.local.yaml` (parámetro `--config kafka_config.local.yaml`) o edita `kafka_config.yaml` para apuntar a `localhost:9092`.

5) Instala dependencias de Python (recomendado en virtualenv)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

6) Ejecutar componentes (en terminales separadas)

Central:
```bash
python3 central_kafka.py --config kafka_config.local.yaml
```

CP Engine:
```bash
python3 cp_engine_kafka.py --id CP-01 --config kafka_config.local.yaml
```

CP Monitor:
```bash
python3 cp_monitor_kafka.py --id CP-01 --config kafka_config.local.yaml
```

Driver (modo simple):
```bash
python3 driver_kafka.py --id DR-01 --cp CP-01 --config kafka_config.local.yaml
```

Ver mensajes en consola mediante `docker` (opcional):

```bash
docker compose exec kafka kafka-console-consumer.sh --topic telemetry --bootstrap-server localhost:9092 --from-beginning
```

Apagar el stack

```bash
docker compose down
```
