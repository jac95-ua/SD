✅ Estado del Proyecto y Hoja de Ruta (Roadmap)
1. Infraestructura de Identidad y Registro (✅ Completado)
Implementación de la autoridad de registro y autenticación inicial.

[x] Módulo EV_Registry:

    [x] Crear servidor API REST (Flask) en puerto 6000.

    [x] Base de datos SQLite para persistir identidades de CPs (ev_registry.db).

    [x] Endpoint /register que genera y devuelve un Token de acceso único.

[x] Integración en EV_Charging_Point (Monitor):

    [x] Flujo de arranque: Solicitar registro a EV_Registry antes de conectar a la Central.

    [x] Almacenamiento del Token recibido.

    [x] Inclusión del Token en el mensaje de saludo (register) hacia la Central.

[x] Autenticación en EV_Central:

    [x] Extracción del Token del mensaje inicial del Monitor.

    [x] Validación del Token contra la base de datos de EV_Registry.

    [x] Lógica de rechazo: Cerrar conexión si el token es inválido o no existe.

2. Core del Sistema (✅ Funcional)
Lógica de negocio base de carga y mensajería.

[x] Comunicación Asíncrona: Implementación de Kafka (Topics: requests, telemetry, control).

[x] Protocolo de Mensajería: Definición de trama <STX>JSON<ETX><LRC>.

[x] EV_Engine (Simulador):

[x] Simulación de carga (kWh y coste).

[x] Modo Manual (m) e Interactivo.

[x] Corrección de identidad (Argumentos de arranque CLI).

[x] EV_Driver: Cliente para solicitar cargas y visualizar progreso.

3. Seguridad Avanzada y Cifrado (🚧 Pendiente)
Siguiente paso: Proteger la comunicación con criptografía.

[ ] HTTPS/SSL en Registry: Configurar certificados para que el registro sea sobre HTTPS (actualmente es HTTP).

[ ] Intercambio de Claves (Handshake):

[ ] Central: Generar una clave simétrica (AES) tras validar el token.

[ ] Central: Enviar la clave al Monitor de forma segura.

[ ] Cifrado de Tráfico:

[ ] Implementar librería cryptography.

[ ] Encriptar payload de mensajes Socket y Kafka con la clave simétrica.

[ ] Central: Descifrar mensajes entrantes.

4. Funcionalidades Externas (🚧 Pendiente)
[ ] Módulo EV_W (Weather):

[ ] Script de consulta a OpenWeatherMap API.

[ ] Lógica de parada automática por temperatura (< 0ºC).

[ ] Front-End (Dashboard):

[ ] Web pública para visualizar estado de los cargadores.

[ ] API REST en EV_Central para alimentar el Front-end.