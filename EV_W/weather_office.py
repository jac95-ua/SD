import time
import requests
import sys

# Configuración: Alicante (Universidad)
LAT = 38.38
LON = -0.51
UMBRAL_TEMPERATURA = 20.0  # Si baja de 10 grados, paramos cargas (puesto alto para probar)
INTERVALO = 5 # Segundos entre consultas

def obtener_clima():
    """Consulta la API pública de Open-Meteo"""
    url = f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&current_weather=true"
    try:
        respuesta = requests.get(url)
        datos = respuesta.json()
        temperatura = datos['current_weather']['temperature']
        return temperatura
    except Exception as e:
        print(f"[ERROR] No se pudo conectar con el servicio de clima: {e}")
        return None

def main():
    print(f"🌦️  Iniciando EV_Weather Office (Ubicación: {LAT}, {LON})")
    print(f"❄️  Umbral de corte: < {UMBRAL_TEMPERATURA}ºC")
    
    estado_anterior = "NORMAL"

    while True:
        temp_actual = obtener_clima()
        
        if temp_actual is not None:
            sys.stdout.write(f"\r[CLIMA] Temperatura actual en Alicante: {temp_actual}ºC  ")
            sys.stdout.flush()

            # Lógica de decisión
            if temp_actual < UMBRAL_TEMPERATURA:
                if estado_anterior != "ALERTA":
                    print("\n🔴 [ALERTA] ¡Temperatura muy baja! Enviando orden de PARADA a Central...")
                    # AQUI CONECTAREMOS CON CENTRAL (PENDIENTE)
                    estado_anterior = "ALERTA"
            else:
                if estado_anterior != "NORMAL":
                    print("\n🟢 [INFO] Temperatura normalizada. Enviando orden de REANUDAR a Central...")
                    # AQUI CONECTAREMOS CON CENTRAL (PENDIENTE)
                    estado_anterior = "NORMAL"
        
        time.sleep(INTERVALO)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Weather Office cerrado.")