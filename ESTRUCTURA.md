# 🔗 Estructura Organizada del Proyecto

El proyecto ahora está organizado en directorios específicos para facilitar el desarrollo y despliegue:

## 📂 Estructura de Directorios

```
SD/
├── 📁 local/                 # Versión TCP para desarrollo local
│   ├── central.py
│   ├── cp_engine.py  
│   ├── driver.py
│   ├── cp_monitor.py
│   ├── protocol.py
│   ├── requirements.txt
│   └── README.md
│
├── 📁 kafka/                 # Versión distribuida con Kafka
│   ├── central_kafka.py
│   ├── cp_engine_kafka.py
│   ├── driver_kafka.py
│   ├── kafka_utils.py
│   ├── kafka_config.yaml
│   ├── requirements.txt
│   └── README.md
│
├── 📁 scripts/               # Scripts de despliegue y configuración
│   ├── setup_kafka.sh
│   ├── create_topics.sh
│   ├── deploy_app.sh
│   └── README.md
│
├── 📄 IMPLEMENTATION.md       # Documentación original
├── 📄 README.md              # Este archivo
└── 📄 requirements.txt       # Dependencias generales
```

## 🎯 ¿Qué Versión Usar?

### 🏠 **Versión Local** (`local/`)
**Cuándo usar**:
- ✅ Desarrollo y pruebas
- ✅ Debugging y prototipado  
- ✅ Demos en una sola máquina
- ✅ Aprendizaje del sistema

**Ventajas**:
- Simple configuración
- Sin dependencias externas
- Fácil debugging
- Inicio rápido

### 🌐 **Versión Kafka** (`kafka/`)
**Cuándo usar**:
- ✅ Producción distribuida
- ✅ Múltiples máquinas
- ✅ Alta disponibilidad
- ✅ Escalabilidad

**Ventajas**:
- Tolerante a fallos
- Escalable horizontalmente
- Persistencia de mensajes
- Monitoreo avanzado

## 🚀 Inicio Rápido

### Para Desarrollo Local:
```bash
cd local/
python central.py &
python cp_engine.py --id CP001 &
python driver.py --id DRIVER001 --cp CP001
```

### Para Despliegue Distribuido:
```bash
# 1. Configurar Kafka (en cada máquina)
cd scripts/
./setup_kafka.sh 1  # 2, 3 según la máquina

# 2. Crear topics (una vez)
./create_topics.sh

# 3. Desplegar aplicaciones
./deploy_app.sh central  # Máquina 1
./deploy_app.sh cp       # Máquina 2  
./deploy_app.sh driver   # Máquina 3
```

## 📖 Documentación Específica

- **`local/README.md`** - Guía completa versión local
- **`kafka/README.md`** - Guía completa versión distribuida  
- **`scripts/README.md`** - Guía de despliegue automatizado

## 🔄 Migración entre Versiones

El protocolo de mensajes es **compatible** entre ambas versiones:

```python
# Mismo protocolo en ambas versiones
make_msg('AUTH_REQUEST', 'driver', 'DRIVER001', {'cp_id': 'CP001'})
```

**Diferencias**:
- **Local**: TCP sockets (`asyncio`)
- **Kafka**: Topics y producers/consumers

## 🎛️ Configuración

### Local:
- Sin configuración especial
- Solo especificar host:puerto

### Kafka:
- Editar `kafka/kafka_config.yaml`
- Configurar IPs de los brokers
- Ajustar topics según necesidades

## 📊 Comparación

| Aspecto | Local | Kafka |
|---------|-------|-------|
| **Complejidad** | 🟢 Baja | 🟡 Media |
| **Configuración** | 🟢 Mínima | 🟡 Moderada |
| **Escalabilidad** | 🔴 Limitada | 🟢 Alta |
| **Tolerancia a fallos** | 🔴 Baja | 🟢 Alta |
| **Monitoreo** | 🟡 Básico | 🟢 Avanzado |
| **Persistencia** | 🔴 No | 🟢 Sí |
| **Rendimiento** | 🟢 Local óptimo | 🟢 Distribuido óptimo |

## 🏗️ Desarrollo Recomendado

1. **Empezar con Local**: Desarrolla y prueba la lógica
2. **Migrar a Kafka**: Cuando necesites distribución
3. **Usar Scripts**: Para automatizar despliegues
4. **Mantener ambas**: Local para dev, Kafka para prod

## 🎯 Próximos Pasos

1. **Elegir versión** según tus necesidades
2. **Leer README específico** del directorio elegido
3. **Seguir guía de instalación**
4. **Probar funcionalidad básica**
5. **Escalar según sea necesario**

¡El proyecto está listo para ambos escenarios! 🚀