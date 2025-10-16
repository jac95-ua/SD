# Guía de implementación para EVCharging (MVP en Python)

Este repositorio contiene un MVP mínimo para la práctica EVCharging usando Python y
asyncio con mensajes JSON por línea (newline-delimited JSON) sobre TCP.

Archivos creados:

- `protocol.py`: helpers para enviar/recibir mensajes JSON por streams asincrónicos.
- `central.py`: servidor CENTRAL que acepta `REGISTER` de CPs y `AUTH_REQUEST` de drivers.
- `cp_engine.py`: CP Engine que se registra en CENTRAL y envía `TELEMETRY` cuando suministra.
- `cp_monitor.py`: Monitor simple que envía `HEALTH` periódicamente.
- `driver.py`: Cliente Driver que solicita autorización para un CP.

Contrato mínimo de mensajes (JSON por línea)

Campos comunes:
- `tipo`: REGISTER | REGISTER_ACK | AUTH_REQUEST | AUTH_RESPONSE | START_CHARGE | STOP_CHARGE | TELEMETRY | HEALTH | ERROR
- `source`: "central" | "cp" | "driver" | "monitor"
- `id`: identificador del emisor (CP o Driver)
- `payload`: objeto con campos específicos

Ejemplos:

CP registra:
```
{"tipo":"REGISTER","source":"cp","id":"CP-01","payload":{"location":"Demo","price_kwh":0.25}}
```

Driver solicita autorización:
```
{"tipo":"AUTH_REQUEST","source":"driver","id":"DR-01","payload":{"cp_id":"CP-01"}}
```

Telemetry:
```
{"tipo":"TELEMETRY","source":"cp","id":"CP-01","payload":{"kw":7.2,"amount":0.9,"state":"Suministrando"}}
```

Cómo ejecutar el MVP localmente (ejemplo simple)

1. Abrir 3 terminales.

Terminal 1 — CENTRAL:

```bash
python3 central.py --host 0.0.0.0 --port 9000
```

Terminal 2 — CP Engine:

```bash
python3 cp_engine.py --id CP-01 --host 127.0.0.1 --port 9000
```

Terminal 3 — Driver:

```bash
python3 driver.py --id DR-01 --cp CP-01 --host 127.0.0.1 --port 9000
```

Observa cómo el Central responde al registro, el Driver recibe la `AUTH_RESPONSE` y el
CP empieza a enviar `TELEMETRY` cuando recibe `START_CHARGE`.

Notas y siguientes pasos recomendados

- Este MVP usa JSON por línea para facilitar depuración; para producción podrías usar
  framing con <STX><DATA><ETX><LRC> o migrar a Kafka para desacoplar componentes.
- Añadir persistencia (SQLite) para almacenar CPs y sesiones.
- Añadir reconexiones y manejo de fallos más robusto.
- Crear pruebas unitarias con `pytest` y ejemplos de Docker/Docker Compose para despliegue.

Si quieres, puedo:
- Adaptar este MVP para usar Kafka (con `docker-compose` y `aiokafka`).
- Añadir persistencia y un CLI para el Central.
- Modularizar y documentar la API de mensajes más en detalle.
