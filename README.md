# SD
Actúa como un programador experto en Python especializado en sistemas distribuidos, sockets TCP y Apache Kafka. Mi objetivo es crear un proyecto de simulación de una red de carga de vehículos eléctricos (EVCharging) basado en los siguientes requisitos estrictos. El lenguaje de desarrollo DEBE ser Python.

## 1. Objetivo del Proyecto

Simular un sistema de gestión en tiempo real para una red de puntos de recarga (CPs) de vehículos eléctricos. El sistema consta de 4 componentes principales que deben desarrollarse: `EV_Central`, `EV_CP_M` (Monitor), `EV_CP_E` (Engine) y `EV_Driver`.

## 2. Tecnologías Obligatorias

1.  **Python:** Todo el código de los 4 componentes debe estar en Python.
2.  **Apache Kafka:** DEBE usarse como el gestor de colas y streaming de eventos (Streaming & QM). Se usará para casi toda la comunicación principal (peticiones de conductores, telemetría de CPs, autorizaciones).
3.  **Sockets TCP:** DEBEN usarse *específicamente* para la comunicación de registro, autenticación y envío de estados de "Avería" o "Desconexión" entre el monitor del CP (`EV_CP_M`) y la central (`EV_Central`).
4.  **Base de Datos/Ficheros:** `EV_Central` necesita persistir el estado y registro de los CPs (puede ser SQLite o ficheros).

## 3. Arquitectura de Despliegue (Crítico)

El sistema DEBE estar diseñado para un despliegue distribuido en **al menos 3 máquinas (PCs) distintas**. La arquitectura de despliegue mínima es:

* **PC 1 (IP1):** Ejecutará una o más instancias de `EV_Driver`.
* **PC 2 (IP2):** Ejecutará `EV_Central` y el broker de **KAFKA**.
* **PC 3 (IP3):** Ejecutará una o más instancias de `EV_CP` (cada instancia incluye un `EV_CP_M` y un `EV_CP_E`).

## 4. Descripción de Componentes a Desarrollar

### Componente 1: EV_Central (El Cerebro)

* **Nombre ejecutable:** `EV_Central`
* **Argumentos de entrada:** `<Puerto_escucha_Sockets> <IP:Puerto_Kafka_Broker> [IP:Puerto_BBDD]`
* **Responsabilidades:**
    1.  **Servidor de Sockets (Concurrente):** Debe levantar un servidor de sockets TCP en el `<Puerto_escucha_Sockets>` para recibir conexiones *únicamente* de los `EV_CP_M`. Gestionará:
        * **Registro/Autenticación:** Recibe el ID y ubicación del CP desde `EV_CP_M`. Lo valida contra la BBDD.
        * **Recepción de Averías:** Recibe mensajes de avería desde `EV_CP_M`.
        * **Detección de Desconexión:** Si el socket con un `EV_CP_M` se rompe, marca ese CP como "Desconectado" (GRIS).
    2.  **Cliente/Consumidor Kafka:** Se conecta al broker de Kafka para:
        * Consumir peticiones de recarga del topic `requests_topic` (enviadas por `EV_Driver`).
        * Consumir telemetría (consumo, importe) del topic `telemetry_topic` (enviada por `EV_CP_E`).
        * Producir autorizaciones/denegaciones en `control_topic` (para `EV_CP_E` y `EV_Driver`).
        * Producir comandos (Parar/Reanudar) en `control_topic`.
    3.  **Panel de Monitorización (Dashboard):** Muestra en la consola (en tiempo real) el estado de todos los CPs registrados. Cada CP debe mostrar:
        * ID, Ubicación, Precio.
        * **Estado (con color):**
            * `Activado` (VERDE): Listo.
            * `Parado` (NARANJA): "Out of Order" (parado por la central).
            * `Suministrando` (VERDE): Muestra `Driver ID`, `Consumo (kWh)` e `Importe (€)` en tiempo real.
            * `Averiado` (ROJO): Reportado por `EV_CP_M`.
            * `Desconectado` (GRIS): Socket con `EV_CP_M` perdido.
    4.  **Lógica de Negocio:**
        * Valida si un CP está `Activado` antes de autorizar una recarga.
        * Envía el "ticket" final al `EV_Driver` (vía Kafka) al terminar el suministro.
    5.  **Comandos de Admin (por teclado):** Permitir al operador de CENTRAL enviar comandos de "Parar" (pone el CP en NARANJA) o "Reanudar" (pone en VERDE) a un CP específico vía Kafka.

---

### Componente 2: EV_CP_M (El Monitor de Salud)

* **Nombre ejecutable:** `EV_CP_M` (Monitor)
* **Argumentos de entrada:** `<IP:Puerto_EV_CP_E> <IP:Puerto_EV_Central> <ID_CP>`
* **Responsabilidades:**
    1.  **Cliente de Sockets (hacia Central):**
        * Al arrancar, se conecta vía socket a `EV_Central` (`<IP:Puerto_EV_Central>`).
        * Envía un mensaje de autenticación/registro con su `<ID_CP>` y ubicación (puedes hardcodear la ubicación o pasarla como arg).
        * Mantiene esta conexión de socket abierta (modo "heartbeat") para que `EV_Central` sepa que está vivo.
    2.  **Comunicación con su Engine (Local):**
        * Se conecta al `EV_CP_E` local (`<IP:Puerto_EV_CP_E>`), (esta comunicación puede ser un socket local simple o cualquier IPC).
        * Cada segundo, le envía un mensaje de "health check".
    3.  **Gestión de Averías:**
        * Si el `EV_CP_E` local *no responde* o responde `KO` al health check, `EV_CP_M` DEBE enviar inmediatamente un mensaje de **AVERÍA** a `EV_Central` a través de su conexión de **socket** principal.
        * Si el `EV_CP_E` se recupera, `EV_CP_M` envía un mensaje de "OK" a `EV_Central` por el socket.

---

### Componente 3: EV_CP_E (El Suministrador)

* **Nombre ejecutable:** `EV_CP_E` (Engine)
* **Argumentos de entrada:** `<IP:Puerto_Kafka_Broker>`
* **Responsabilidades:**
    1.  **Cliente/Consumidor Kafka:**
        * Se conecta al broker de Kafka.
        * Se suscribe a un topic de control (`control_topic` o uno específico para su ID) para recibir órdenes de `EV_Central` (ej. "INICIAR_SUMINISTRO", "PARAR", "REANUDAR").
    2.  **Comunicación con su Monitor (Local):**
        * Abre un puerto (ej. en `<IP:Puerto_EV_CP_E>`) para recibir "health checks" de su `EV_CP_M` asociado.
        * Debe tener una opción (ej. pulsar una tecla) para **simular una avería**, haciendo que deje de responder o responda `KO` a su `EV_CP_M`.
    3.  **Lógica de Suministro:**
        * Cuando recibe la orden "INICIAR_SUMINISTRO" (vía Kafka) de `EV_Central`:
            * Pasa a estado "Suministrando".
            * **Simula la recarga:** Cada segundo, incrementa el consumo (kWh) y el importe (€).
            * **Envía Telemetría (Kafka):** Cada segundo, envía un mensaje al `telemetry_topic` de Kafka con `{ "cp_id": <ID_CP>, "driver_id": <Driver_ID>, "consumo_kwh": X, "importe_eur": Y }`.
        * El suministro finaliza por una orden de "FIN_SUMINISTRO" (simulada por el Driver o por tiempo) o si recibe "PARAR" de la Central.
        * Al finalizar, envía un mensaje final de telemetría y vuelve a estado `Activado`.

---

### Componente 4: EV_Driver (El Cliente)

* **Nombre ejecutable:** `EV_Driver`
* **Argumentos de entrada:** `<IP:Puerto_Kafka_Broker> <ID_Cliente>`
* **Responsabilidades:**
    1.  **Cliente/Productor Kafka:**
        * Se conecta al broker de Kafka.
        * Produce peticiones de recarga en `requests_topic`. Mensaje: `{ "driver_id": <ID_Cliente>, "cp_id_solicitado": <ID_CP> }`.
        * Consume mensajes de `control_topic` (o un topic de notificaciones) para ver el estado de su petición (Autorizada, Denegada) y el "ticket" final.
        * Opcionalmente, consume `telemetry_topic` para ver en tiempo real *su propia* recarga.
    2.  **Lógica de Peticiones (Fichero):**
        * Debe poder leer un fichero de texto local (ej. `requests.txt`) que contiene una lista de IDs de CPs donde quiere recargar (uno por línea).
        * Envía la primera petición a `EV_Central` (vía Kafka).
        * Espera a que el suministro **concluya** (recibiendo el "ticket" final).
        * Espera **4 segundos** adicionales.
        * Envía la siguiente petición del fichero.
        * Repite hasta que el fichero se acabe.

## 5. Resumen de Flujos de Comunicación

* **Arranque CP:**
    1.  `EV_CP_M` arranca.
    2.  `EV_CP_M` -> (Socket TCP) -> `EV_Central`: "Hola, soy CP-01, estoy en C/Italia 5. Estoy OK."
    3.  `EV_Central` lo añade al panel como "Activado" (VERDE).

* **Petición de Carga:**
    1.  `EV_Driver` -> (Kafka: `requests_topic`) -> `EV_Central`: "Soy Driver-23, quiero cargar en CP-01."
    2.  `EV_Central` comprueba que CP-01 está "Activado".
    3.  `EV_Central` -> (Kafka: `control_topic`) -> `EV_CP_E` (CP-01): "Autorizado. Inicia suministro para Driver-23."
    4.  `EV_Central` -> (Kafka: `control_topic`) -> `EV_Driver`: "Autorizado. Conecte su vehículo."

* **Durante la Carga:**
    1.  `EV_CP_E` (CP-01) -> (Kafka: `telemetry_topic`) -> `EV_Central`: "{ cp_id: CP-01, driver_id: 23, consumo_kwh: 1.5, ... }" (cada segundo)
    2.  `EV_Central` actualiza el panel (muestra consumo 1.5 kWh en CP-01).

* **Fallo de Engine:**
    1.  Operador pulsa tecla de "fallo" en `EV_CP_E` (CP-01).
    2.  `EV_CP_M` (CP-01) envía "health check" a `EV_CP_E` (CP-01).
    3.  `EV_CP_E` (CP-01) responde `KO` (o no responde).
    4.  `EV_CP_M` (CP-01) -> (Socket TCP) -> `EV_Central`: "¡AVERÍA en CP-01!"
    5.  `EV_Central` actualiza el panel de CP-01 a "Averiado" (ROJO) y finaliza el suministro si lo había.

* **Fallo de Monitor (Desconexión):**
    1.  Proceso `EV_CP_M` (CP-01) muere (Ctrl+C).
    2.  `EV_Central` detecta que el socket TCP con `EV_CP_M` (CP-01) se ha cerrado.
    3.  `EV_Central` actualiza el panel de CP-01 a "Desconectado" (GRIS).

## Tarea para Copilot

Genera una estructura de proyecto en Python y el código base para estos 4 componentes. Asegúrate de incluir:
1.  La estructura de carpetas (ej. `/EV_Central`, `/EV_Charging_Point`, `/EV_Driver`).
2.  El código Python para `EV_Central` (con el servidor de sockets concurrente y el cliente Kafka).
3.  El código Python para `EV_CP_M` (con el cliente socket).
4.  El código Python para `EV_CP_E` (con el cliente Kafka y la simulación de avería).
5.  El código Python para `EV_Driver` (con el cliente Kafka y la lógica de lectura de fichero).
6.  Un `requirements.txt` (que incluya `kafka-python`).
7.  Un `docker-compose.yml` básico para facilitar el despliegue de **Kafka** y Zookeeper.
