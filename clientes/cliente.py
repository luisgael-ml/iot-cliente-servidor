"""
CLIENTE 3 · Cliente de consultas (operador de planta).
Envía peticiones SQL al servidor PostgreSQL y muestra las respuestas:
consultas, altas, actualizaciones y bajas.
  python cliente.py          -> menú interactivo
  python cliente.py --demo   -> ejecuta las consultas principales sin interacción
"""
import sys

from conexiones import conectar_bd


def tabla(cur, sql, params=None):
    """Envía una consulta al servidor e imprime el resultado como tabla."""
    cur.execute(sql, params)
    columnas = [c.name for c in cur.description]
    filas = cur.fetchall()
    anchos = [max(len(str(c)), *(len(str(f[i])) for f in filas)) if filas else len(c)
              for i, c in enumerate(columnas)]
    print("  ".join(str(c).upper().ljust(a) for c, a in zip(columnas, anchos)))
    for f in filas:
        print("  ".join(str(v).ljust(a) for v, a in zip(f, anchos)))
    print(f"({len(filas)} filas)")


CONSULTAS = {
    "dispositivos": """
        SELECT d.codigo, d.nombre, d.ubicacion, d.estado, COUNT(s.id) AS sensores
        FROM dispositivos d LEFT JOIN sensores s ON s.dispositivo_id = d.id
        GROUP BY d.id ORDER BY d.codigo""",
    "ultimas": """
        SELECT dispositivo, sensor, tipo, valor, unidad, umbral_max,
               to_char(medido_en AT TIME ZONE 'America/Mexico_City', 'HH24:MI:SS') AS hora
        FROM v_ultima_lectura ORDER BY dispositivo, sensor""",
    "resumen": """
        SELECT s.codigo AS sensor, COUNT(*) AS lecturas,
               ROUND(AVG(l.valor), 2) AS promedio, MIN(l.valor) AS minimo, MAX(l.valor) AS maximo
        FROM lecturas l JOIN sensores s ON s.id = l.sensor_id
        WHERE l.medido_en > NOW() - INTERVAL '1 hour'
        GROUP BY s.codigo ORDER BY s.codigo""",
    "alertas": """
        SELECT a.id, s.codigo AS sensor, a.valor, a.umbral,
               to_char(a.creada_en AT TIME ZONE 'America/Mexico_City', 'HH24:MI:SS') AS hora
        FROM alertas a JOIN sensores s ON s.id = a.sensor_id
        WHERE NOT a.atendida ORDER BY a.creada_en DESC LIMIT 10""",
}


def demo(bd):
    with bd.cursor() as cur:
        for titulo, clave in [("Dispositivos registrados", "dispositivos"),
                              ("Última lectura de cada sensor", "ultimas"),
                              ("Resumen de la última hora", "resumen"),
                              ("Alertas pendientes (generadas por el trigger del servidor)", "alertas")]:
            print(f"\n--- {titulo} ---")
            tabla(cur, CONSULTAS[clave])


def menu(bd):
    opciones = """
1. Ver dispositivos
2. Última lectura de cada sensor
3. Resumen de la última hora (promedio, mínimo, máximo)
4. Alertas pendientes
5. Marcar alerta como atendida
6. Registrar dispositivo nuevo
7. Cambiar umbral de un sensor
8. Eliminar lecturas con más de N minutos
0. Salir"""
    while True:
        print(opciones)
        op = input("Opción: ").strip()
        try:
            with bd.cursor() as cur:
                if op in ("1", "2", "3", "4"):
                    tabla(cur, CONSULTAS[["dispositivos", "ultimas", "resumen", "alertas"][int(op) - 1]])
                elif op == "5":
                    cur.execute("UPDATE alertas SET atendida = TRUE WHERE id = %s", (int(input("ID de la alerta: ")),))
                    print("Alerta atendida." if cur.rowcount else "ID no encontrado.")
                elif op == "6":
                    cur.execute("INSERT INTO dispositivos (codigo, nombre, ubicacion) VALUES (%s, %s, %s) RETURNING id",
                                (input("Código: "), input("Nombre: "), input("Ubicación: ")))
                    print(f"Dispositivo registrado con id {cur.fetchone()[0]}.")
                elif op == "7":
                    cur.execute("UPDATE sensores SET umbral_max = %s WHERE codigo = %s",
                                (float(input("Nuevo umbral: ")), input("Código del sensor: ")))
                    print("Umbral actualizado." if cur.rowcount else "Sensor no encontrado.")
                elif op == "8":
                    cur.execute("DELETE FROM lecturas WHERE medido_en < NOW() - make_interval(mins => %s)",
                                (int(input("Minutos: ")),))
                    print(f"{cur.rowcount} lecturas eliminadas.")
                elif op == "0":
                    print("Hasta luego.")
                    return
                else:
                    print("Opción inválida.")
            bd.commit()
        except Exception as e:          # errores de SQL o de conexión no cierran el cliente
            bd.rollback()
            print(f"Error: {e}")


def main():
    bd = conectar_bd(usuario_env="DB_USER", password_env="DB_PASSWORD")
    with bd.cursor() as cur:
        cur.execute("SELECT current_user, ssl, version FROM pg_stat_ssl WHERE pid = pg_backend_pid()")
        usuario, ssl, version = cur.fetchone()
    print(f"Cliente conectado al servidor como '{usuario}'. Cifrado SSL: {'sí (' + version + ')' if ssl else 'no'}")
    demo(bd) if "--demo" in sys.argv else menu(bd)
    bd.close()


if __name__ == "__main__":
    main()
