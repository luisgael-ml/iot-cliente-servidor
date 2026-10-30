"""
CLIENTE 2 · Consumidor de RabbitMQ (servicio de ingesta).
Lee las lecturas de la cola, las agrupa en lotes y las guarda en PostgreSQL
dentro de una transacción. Solo confirma (ACK) los mensajes después del COMMIT.
"""
import json
import os
import time

from conexiones import COLA, conectar_bd, conectar_rabbitmq

TAM_LOTE = int(os.getenv("TAM_LOTE", "100"))   # máximo de mensajes por lote
ESPERA = float(os.getenv("ESPERA_LOTE", "1"))  # segundos máximos antes de guardar un lote incompleto

SQL_INSERT = """
    INSERT INTO lecturas (mensaje_id, sensor_id, valor, medido_en)
    SELECT %(mensaje_id)s, s.id, %(valor)s, %(medido_en)s
    FROM sensores s WHERE s.codigo = %(sensor)s
    ON CONFLICT (mensaje_id) DO NOTHING      -- si el mensaje ya se guardó, se ignora
"""


def guardar_lote(bd, lote):
    """Guarda el lote completo en una sola transacción. Devuelve las filas insertadas."""
    with bd.transaction():                   # COMMIT al salir; ROLLBACK si hay error
        with bd.cursor() as cur:
            cur.executemany(SQL_INSERT, lote)
            return cur.rowcount


def main():
    bd = conectar_bd(usuario_env="DB_USER", password_env="DB_PASSWORD")
    conexion, canal = conectar_rabbitmq()
    canal.basic_qos(prefetch_count=TAM_LOTE * 2)    # cuántos mensajes recibe sin confirmar
    print(f"Consumidor listo. Lotes de hasta {TAM_LOTE} mensajes o {ESPERA}s.")

    lote, ultima_etiqueta, total, inicio_lote = [], None, 0, 0.0
    for metodo, _props, cuerpo in canal.consume(COLA, inactivity_timeout=ESPERA):
        if metodo is not None:
            if not lote:
                inicio_lote = time.time()
            lote.append(json.loads(cuerpo))
            ultima_etiqueta = metodo.delivery_tag
        # Guarda cuando el lote se llena o cuando ya pasó el tiempo máximo de espera
        if lote and (len(lote) >= TAM_LOTE or time.time() - inicio_lote >= ESPERA):
            insertadas = guardar_lote(bd, lote)
            canal.basic_ack(delivery_tag=ultima_etiqueta, multiple=True)   # ACK múltiple tras el COMMIT
            total += insertadas
            print(f"Lote guardado: {len(lote)} mensajes, {insertadas} insertados (total: {total})")
            lote = []


if __name__ == "__main__":
    main()
