import time
import requests
import sys

# --- CONFIGURACIÓN ---
# URL de la Central (ajusta la IP si despliegas en máquinas distintas)
CENTRAL_API_URL = "http://localhost:9001/api/weather" 

# Umbral de temperatura (Puesto en 20 para probar fácilmente, el enunciado pide 0)
UMBRAL_TEMPERATURA = 30.0 
INTERVALO = 4  # Según enunciado: cada 4 segundos

# Lista de ciudades (Simulación de configuración manual/fichero)
# Puedes añadir más aquí manualmente.
CIUDADES = [
    {"nombre": "Alicante", "lat": 38.38, "lon": -0.51, "estado": "NORMAL"},
    {"nombre": "Madrid",   "lat": 40.41, "lon": -3.70,  "estado": "NORMAL"},
    {"nombre": "Oslo",     "lat": 59.91, "lon": 10.75,  "estado": "NORMAL"} # Para probar frío
]

def obtener_clima(lat, lon):
    """Consulta la API pública de Open-Meteo"""
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
    try:
        respuesta = requests.get(url, timeout=2)
        respuesta.raise_for_status()
        datos = respuesta.json()
        return datos['current_weather']['temperature']
    except Exception as e:
        print(f"[ERROR] Fallo consultando clima: {e}")
        return None

def notificar_central(ciudad, accion, temperatura):
    """Envía la alerta o recuperación a EV_Central"""
    payload = {
        "city": ciudad,
        "action": accion,      # "ALERT" (parar) o "RECOVER" (reanudar)
        "temperature": temperatura
    }
    try:
        requests.post(CENTRAL_API_URL, json=payload, timeout=2)
        print(f"   -> 📨 Notificación enviada a Central: {accion} para {ciudad}")
    except requests.exceptions.ConnectionError:
        print(f"   -> ❌ Error: No se puede conectar con EV_Central en {CENTRAL_API_URL}")
    except Exception as e:
        print(f"   -> ❌ Error enviando notificación: {e}")

def main():
    print(f"🌦️  Iniciando EV_Weather Office")
    print(f"📋  Ciudades vigiladas: {[c['nombre'] for c in CIUDADES]}")
    print(f"❄️  Umbral de alerta: < {UMBRAL_TEMPERATURA}ºC")
    print(f"📡  Conectando a Central en: {CENTRAL_API_URL}")
    print("-" * 50)

    while True:
        for ciudad in CIUDADES:
            nombre = ciudad["nombre"]
            temp_actual = obtener_clima(ciudad["lat"], ciudad["lon"])
            
            if temp_actual is None:
                continue

            # Mostramos info en una sola línea que se actualiza (o línea nueva)
            print(f"[CLIMA] {nombre}: {temp_actual}ºC ", end="")

            # --- LÓGICA DE DECISIÓN ---
            if temp_actual < UMBRAL_TEMPERATURA:
                print("🔴 ¡BAJA TEMPERATURA!", end="")
                # Si antes estaba bien, avisamos para PARAR
                if ciudad["estado"] != "ALERTA":
                    print("\n⚠️  Cambiando estado a ALERTA...")
                    notificar_central(nombre, "ALERT", temp_actual)
                    ciudad["estado"] = "ALERTA"
                else:
                    print("", end="\r") # Limpiar línea visualmente

            else:
                print("🟢 Normal", end="")
                # Si antes estaba en alerta, avisamos para REANUDAR
                if ciudad["estado"] != "NORMAL":
                    print("\n✅  Temperatura recuperada. Volviendo a NORMAL...")
                    notificar_central(nombre, "RECOVER", temp_actual)
                    ciudad["estado"] = "NORMAL"
                else:
                    print("", end="\r")
        
        # Espera para cumplir el ciclo de 4 segundos
        time.sleep(INTERVALO)
        # Un pequeño salto de línea para separar iteraciones si hubo logs
        # print() 

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Weather Office cerrado.")