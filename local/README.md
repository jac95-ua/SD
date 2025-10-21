# Versión Local - Sistema de Carga de Vehículos Eléctricos

Esta es la versión original del sistema que funciona en una sola máquina usando conexiones TCP directas.

## 📁 Archivos

- **`central.py`** - Servidor central que maneja registros y autorizaciones
- **`cp_engine.py`** - Motor de punto de carga (CP) que se registra y envía telemetría
- **`driver.py`** - Cliente conductor que solicita autorización para cargar
- **`cp_monitor.py`** - Monitor de salud de puntos de carga
- **`protocol.py`** - Funciones de protocolo para comunicación TCP

## 🚀 Uso Rápido

### 1. Iniciar el servidor central:
```bash
python central.py --host 0.0.0.0 --port 9000
```

### 2. Iniciar un punto de carga:
```bash
python cp_engine.py --id CP001 --host localhost --port 9000
```

### 3. Solicitar autorización (en otra terminal):
```bash
python driver.py --id DRIVER001 --cp CP001 --host localhost --port 9000
```

### 4. Monitorear un CP (opcional):
```bash
python cp_monitor.py --id CP001 --host localhost --port 9000
```

## ✅ Ventajas de la Versión Local

- **Simplicidad**: Fácil de configurar y probar
- **Desarrollo**: Ideal para desarrollo y debugging
- **Pruebas**: Perfecto para pruebas unitarias y de integración
- **Aprendizaje**: Excelente para entender el flujo del sistema

## 🔧 Configuración

No requiere instalación adicional más allá de Python 3.7+:

```bash
# Solo usar la biblioteca estándar
pip install -r ../requirements.txt  # Opcional, solo para desarrollo
```

## 📊 Flujo de Comunicación

```
Driver ──► Central ──► CP Engine
  │         │           │
  │         │           ▼
  │         │       Telemetría
  │         │           │
  │         ◄───────────┘
  │         │
  ▼         ▼
Auth Response
```

## 🎯 Casos de Uso

- Desarrollo y testing local
- Demos y presentaciones
- Validación de lógica de negocio
- Prototipado rápido
- Debugging de problemas

Esta versión es perfecta para entender el funcionamiento básico antes de pasar a la versión distribuida con Kafka.