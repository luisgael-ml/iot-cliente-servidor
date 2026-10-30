"""Conexiones compartidas por los clientes: PostgreSQL (servidor de BD) y RabbitMQ."""
import os
import time

import pika
import psycopg

COLA = "lecturas"   # cola durable donde los sensores publican sus lecturas


def conectar_bd(usuario_env="DB_USER", password_env="DB_PASSWORD", intentos=30):
    """Abre una conexión cifrada (SSL) con el servidor PostgreSQL, reintentando mientras arranca."""
    params = dict(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "iotanalytics"),
        user=os.getenv(usuario_env, "postgres"),
        password=os.environ[password_env],          # la contraseña nunca está en el código
        sslmode=os.getenv("DB_SSLMODE", "require"),
    )
    for i in range(1, intentos + 1):
        try:
            return psycopg.connect(**params)
        except psycopg.OperationalError as e:
            if i == intentos:
                raise
            print(f"Esperando a PostgreSQL ({i}/{intentos}): {str(e).strip()}")
            time.sleep(2)


def conectar_rabbitmq(intentos=30):
    """Abre una conexión con RabbitMQ y declara la cola durable de lecturas."""
    credenciales = pika.PlainCredentials(os.getenv("MQ_USER", "guest"), os.getenv("MQ_PASSWORD", "guest"))
    params = pika.ConnectionParameters(host=os.getenv("MQ_HOST", "localhost"), credentials=credenciales,
                                       heartbeat=60)
    for i in range(1, intentos + 1):
        try:
            conexion = pika.BlockingConnection(params)
            canal = conexion.channel()
            canal.queue_declare(queue=COLA, durable=True)   # la cola sobrevive a un reinicio
            return conexion, canal
        except pika.exceptions.AMQPConnectionError:
            if i == intentos:
                raise
            print(f"Esperando a RabbitMQ ({i}/{intentos})")
            time.sleep(2)
