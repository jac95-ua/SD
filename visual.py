
"""
EVCharging Visual Simulator (Kafka real-time)
Escucha los topics de telemetría y control para visualizar los estados de los CPs.
VERSIÓN DINÁMICA: 20 espacios reservados pero solo aparecen CPs cuando se conectan.

Uso: python3 visual_simulator.py <KAFKA_BROKER_IP:PORT>
"""

import pygame
import threading
import json
import sys
from kafka import KafkaConsumer

# ======================================
# CONFIGURACIÓN
# ======================================
if len(sys.argv) < 2:
    print("Uso: python3 visual_simulator.py <KAFKA_BROKER_IP:PORT>")
    sys.exit(1)

BROKER = sys.argv[1]
TELEMETRY_TOPIC = "telemetry_topic"
CONTROL_TOPIC = "control_topic"

# ======================================
# INTERFAZ PYGAME
# ======================================
pygame.init()
WIDTH, HEIGHT = 1024, 700
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption(f"⚡ EVCharging Real-Time Monitor (Kafka: {BROKER})")

font = pygame.font.SysFont("Arial", 22)
big_font = pygame.font.SysFont("Arial", 32, bold=True)
clock = pygame.time.Clock()

# ======================================
# ESTADOS VISUALES
# ======================================
STATE_COLORS = {
    "Activado": (0, 200, 0),
    "Suministrando": (255, 200, 0),
    "Parado": (255, 100, 0),
    "Averiado": (200, 0, 0),
    "Desconectado": (100, 100, 100),
}

# Reservamos 20 espacios (5 columnas x 4 filas)
slots = []
for row in range(4):
    for col in range(5):
        slots.append({"x": 80 + col * 180, "y": 160 + row * 120})

# Los CP aparecerán dinámicamente aquí
charging_points = {}


# ======================================
# DIBUJADO
# ======================================
def draw_scene():
    screen.fill((15, 15, 15))
    title = big_font.render("EVCharging - Estado de Puntos de Carga", True, (255, 255, 255))
    screen.blit(title, (WIDTH // 2 - 320, 40))

    # Dibujar slots vacíos
    for s in slots:
        pygame.draw.rect(screen, (80, 80, 80), (s["x"], s["y"], 150, 90), width=2, border_radius=10)

    # Dibujar los CP ocupando slots
    for i, (cp_id, cp_data) in enumerate(charging_points.items()):
        slot = slots[i]

        color = STATE_COLORS.get(cp_data["state"], (150, 150, 150))
        pygame.draw.rect(screen, color, (slot["x"], slot["y"], 150, 90), border_radius=10)

        # Nombre del CP
        screen.blit(font.render(cp_id, True, (0, 0, 0)), (slot["x"] + 50, slot["y"] + 5))
        # Estado
        screen.blit(font.render(cp_data["state"], True, (255, 255, 255)), (slot["x"] + 10, slot["y"] + 35))

        # Si está suministrando, mostramos driver + energía
        if cp_data["driver"]:
            screen.blit(font.render(f"{cp_data['driver']}", True, (255, 255, 255)),
                        (slot["x"] + 10, slot["y"] + 60))
            screen.blit(
                font.render(f"{cp_data['kwh']}kWh / {cp_data['eur']}€", True, (255, 255, 0)),
                (slot["x"] + 10, slot["y"] + 80)
            )

    pygame.display.flip()


# ======================================
# KAFKA LISTENER
# ======================================
def kafka_listener():

    try:
        consumer = KafkaConsumer(
            TELEMETRY_TOPIC,
            CONTROL_TOPIC,
            bootstrap_servers=[BROKER],
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            auto_offset_reset="latest",
            group_id="pygame_visual_monitor"
        )
    except Exception as e:
        print(f"[SIM]  No se pudo conectar a Kafka en {BROKER}. Error: {e}")
        return

    print(f"[SIM]  Escuchando mensajes Kafka en {BROKER}...")

    for msg in consumer:
        v = msg.value
        cp_id = v.get("cp_id")
        typ = v.get("type")

        if not cp_id:
            continue

        # Si es nuevo CP, lo agregamos en el siguiente slot disponible
        if cp_id not in charging_points:
            if len(charging_points) < 20:
                charging_points[cp_id] = {
                    "state": "Desconectado",
                    "driver": None,
                    "kwh": 0.0,
                    "eur": 0.0,
                }
                print(f"[SIM]  CP detectado y añadido al dashboard: {cp_id}")
            else:
                print("[SIM]  No hay más slots (máx 20)")
                continue

        # TELEMETRY
        if msg.topic == TELEMETRY_TOPIC:
            charging_points[cp_id]["state"] = "Suministrando"
            charging_points[cp_id]["driver"] = v.get("driver_id", "???")
            charging_points[cp_id]["kwh"] = round(v.get("consumo_kwh", 0.0), 2)
            charging_points[cp_id]["eur"] = round(v.get("importe_eur", 0.0), 2)
            continue

        # CONTROL (states desde CENTRAL)
        if msg.topic == CONTROL_TOPIC:

            if typ == "authorize":
                charging_points[cp_id]["state"] = "Suministrando"

            elif typ == "parar":
                charging_points[cp_id]["state"] = "Parado"

            elif typ == "reanudar":
                charging_points[cp_id]["state"] = "Activado"

            elif typ == "initial_state":
                charging_points[cp_id]["state"] = v.get("state", "Activado")

            elif typ == "ticket":
                if v.get("aborted", False):
                    charging_points[cp_id]["state"] = "Averiado"
                elif v.get("final", False):
                    charging_points[cp_id]["state"] = "Activado"
                else:
                    charging_points[cp_id]["state"] = "Desconectado"

                charging_points[cp_id]["driver"] = None
                charging_points[cp_id]["kwh"] = 0.0
                charging_points[cp_id]["eur"] = 0.0


# Hilo Kafka listener
threading.Thread(target=kafka_listener, daemon=True).start()


# ======================================
# MAIN LOOP PYGAME
# ======================================
running = True
while running:
    for ev in pygame.event.get():
        if ev.type == pygame.QUIT:
            running = False

    draw_scene()
    clock.tick(30)

pygame.quit()