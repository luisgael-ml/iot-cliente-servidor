"""
CLIENTE 1 · Simulador de sensores IoT (productor).
Cada segundo genera una lectura por sensor y la publica en RabbitMQ como JSON.
No conoce la base de datos: solo envía mensajes a la cola.
"""
import json
import os
import random
import time
import uuid
from datetime import datetime, timezone

import pika

from conexiones import COLA, conectar_rabbitmq

# sensor -> (valor base, variación, probabilidad de pico que supera el umbral)
SENSORES = {
    "PRE03-TEMP": (70, 3, 0.04), "PRE03-VIB": (4.5, 0.6, 0.04), "PRE03-ENE": (22, 2, 0.03),
    "TOR01-TEMP": (65, 3, 0.04), "TOR01-VIB": (3.8, 0.5, 0.04), "TOR01-ENE": (18, 2, 0.03),
    "EMB02-TEMP": (60, 3, 0.04), "EMB02-VIB": (3.0, 0.4, 0.04), "EMB02-ENE": (14, 2, 0.03),
}


def generar(codigo):
    base, variacion, prob_pico = SENSORES[codigo]
    valor = random.gauss(base, variacion)
    if random.random() < prob_pico:
        valor = base * 1.35                      # pico anómalo para probar las alertas
    return {
        "mensaje_id": str(uuid.uuid4()),
        "sensor": codigo,
        "valor": round(valor, 2),
        "medido_en": datetime.now(timezone.utc).isoformat(),
    }


def main():
    intervalo = float(os.getenv("INTERVALO", "1"))
    duracion = int(os.getenv("DURACION", "0"))   # 0 = sin límite
    conexion, canal = conectar_rabbitmq()
    print(f"Simulador conectado a RabbitMQ. Publicando en la cola '{COLA}' cada {intervalo}s...")
    inicio, enviados = time.time(), 0
    try:
        while duracion == 0 or time.time() - inicio < duracion:
            for codigo in SENSORES:
                lectura = generar(codigo)
                canal.basic_publish(
                    exchange="", routing_key=COLA, body=json.dumps(lectura),
                    properties=pika.BasicProperties(delivery_mode=2, content_type="application/json"),
                )
                enviados += 1
            print(f"-> {enviados} lecturas publicadas (última: {lectura['sensor']} = {lectura['valor']})")
            time.sleep(intervalo)
    finally:
        conexion.close()
        print(f"Simulador detenido. Total publicado: {enviados}")


if __name__ == "__main__":
    main()
