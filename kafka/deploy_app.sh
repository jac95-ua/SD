#!/bin/bash
# Script para desplegar la aplicación Python en cada máquina
# Ejecutar como: ./deploy_app.sh <machine_role>

set -e

MACHINE_ROLE=${1:-central}
APP_DIR="/opt/evcharging"
VENV_DIR="/opt/evcharging/venv"

echo "=== Desplegando aplicación para rol: $MACHINE_ROLE ==="

# Crear directorio de aplicación
sudo mkdir -p $APP_DIR
sudo chown -R $USER:$USER $APP_DIR

# Copiar archivos de la aplicación
echo "Copiando archivos de la aplicación..."
cp *.py $APP_DIR/
cp requirements.txt $APP_DIR/
cp kafka_config.yaml $APP_DIR/

# Crear entorno virtual Python
if [ ! -d "$VENV_DIR" ]; then
    echo "Creando entorno virtual Python..."
    python3 -m venv $VENV_DIR
fi

# Activar entorno virtual e instalar dependencias
echo "Instalando dependencias..."
source $VENV_DIR/bin/activate
pip install --upgrade pip
pip install -r $APP_DIR/requirements.txt

# Crear scripts de inicio según el rol
case $MACHINE_ROLE in
    central)
        create_central_service
        ;;
    cp)
        create_cp_service
        ;;
    driver)
        create_driver_scripts
        ;;
    *)
        echo "Rol no reconocido: $MACHINE_ROLE"
        echo "Roles disponibles: central, cp, driver"
        exit 1
        ;;
esac

echo "Despliegue completado para rol: $MACHINE_ROLE"

# Función para crear servicio del central
create_central_service() {
    echo "Configurando servicio del Central..."
    
    sudo tee /etc/systemd/system/evcharging-central.service > /dev/null << EOF
[Unit]
Description=EV Charging Central Server
After=kafka.service
Requires=kafka.service

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$APP_DIR
Environment=PATH=$VENV_DIR/bin
ExecStart=$VENV_DIR/bin/python central_kafka.py --config kafka_config.yaml
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    echo "Servicio creado: evcharging-central"
    echo "Para iniciar: sudo systemctl start evcharging-central"
    echo "Para habilitar: sudo systemctl enable evcharging-central"
}

# Función para crear servicio de CP
create_cp_service() {
    echo "Configurando servicio de CP Engine..."
    
    # Crear template de servicio para CPs
    sudo tee /etc/systemd/system/evcharging-cp@.service > /dev/null << EOF
[Unit]
Description=EV Charging CP Engine %i
After=kafka.service
Requires=kafka.service

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$APP_DIR
Environment=PATH=$VENV_DIR/bin
ExecStart=$VENV_DIR/bin/python cp_engine_kafka.py --id %i --config kafka_config.yaml
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    echo "Template de servicio creado: evcharging-cp@"
    echo "Para iniciar un CP: sudo systemctl start evcharging-cp@CP001"
    echo "Para habilitar: sudo systemctl enable evcharging-cp@CP001"
    
    # Crear script de utilidad para gestionar CPs
    cat > $APP_DIR/manage_cps.sh << EOF
#!/bin/bash
# Script para gestionar múltiples CPs

case \$1 in
    start)
        if [ -z "\$2" ]; then
            echo "Uso: \$0 start <cp_id>"
            exit 1
        fi
        sudo systemctl start evcharging-cp@\$2
        ;;
    stop)
        if [ -z "\$2" ]; then
            echo "Uso: \$0 stop <cp_id>"
            exit 1
        fi
        sudo systemctl stop evcharging-cp@\$2
        ;;
    status)
        if [ -z "\$2" ]; then
            sudo systemctl status 'evcharging-cp@*'
        else
            sudo systemctl status evcharging-cp@\$2
        fi
        ;;
    list)
        sudo systemctl list-units --type=service | grep evcharging-cp
        ;;
    *)
        echo "Uso: \$0 {start|stop|status|list} [cp_id]"
        echo "Ejemplos:"
        echo "  \$0 start CP001    # Iniciar CP001"
        echo "  \$0 stop CP001     # Detener CP001"
        echo "  \$0 status         # Ver estado de todos los CPs"
        echo "  \$0 status CP001   # Ver estado de CP001"
        echo "  \$0 list           # Listar todos los CPs"
        ;;
esac
EOF
    chmod +x $APP_DIR/manage_cps.sh
    echo "Script de gestión creado: $APP_DIR/manage_cps.sh"
}

# Función para crear scripts de driver
create_driver_scripts() {
    echo "Configurando scripts de Driver..."
    
    # Crear script interactivo para drivers
    cat > $APP_DIR/start_driver.sh << EOF
#!/bin/bash
# Script para iniciar un driver interactivo

if [ -z "\$1" ]; then
    echo "Uso: \$0 <driver_id>"
    echo "Ejemplo: \$0 DRIVER001"
    exit 1
fi

cd $APP_DIR
source $VENV_DIR/bin/activate
python driver_kafka.py --id \$1 --interactive --config kafka_config.yaml
EOF

    # Crear script para autorización simple
    cat > $APP_DIR/request_auth.sh << EOF
#!/bin/bash
# Script para solicitar autorización simple

if [ -z "\$1" ] || [ -z "\$2" ]; then
    echo "Uso: \$0 <driver_id> <cp_id>"
    echo "Ejemplo: \$0 DRIVER001 CP001"
    exit 1
fi

cd $APP_DIR
source $VENV_DIR/bin/activate
python driver_kafka.py --id \$1 --cp \$2 --config kafka_config.yaml
EOF

    chmod +x $APP_DIR/start_driver.sh
    chmod +x $APP_DIR/request_auth.sh
    
    echo "Scripts de driver creados:"
    echo "  $APP_DIR/start_driver.sh - Modo interactivo"
    echo "  $APP_DIR/request_auth.sh - Autorización simple"
}