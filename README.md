# IoT Analytics Dashboard — Sistema cliente-servidor

Sistema de base de datos con arquitectura cliente-servidor para datos de sensores IoT:
**PostgreSQL** (servidor), **RabbitMQ** (intermediario), clientes en **Python** y **Grafana** (visualización), todo con **Docker**.

## Componentes
| Servicio | Rol | Acceso |
|---|---|---|
| postgres | Servidor de base de datos (SSL) | localhost:5434 |
| rabbitmq | Intermediario de mensajes | http://localhost:15673 (guest/guest) |
| simulador | Cliente: publica lecturas de 9 sensores | — |
| consumidor | Cliente: guarda las lecturas por lotes | — |
| cliente | Cliente: consultas del operador | `docker compose run --rm cliente` |
| grafana | Cliente: dashboard en tiempo real | http://localhost:3001 (admin/admin) |

## Ejecución
```bash
docker compose up -d --build                         # servidor, RabbitMQ, simulador, consumidor y Grafana
docker compose run --rm cliente python cliente.py --demo   # consultas principales
docker compose run --rm cliente                      # menú interactivo
docker compose logs consumidor                       # lotes guardados
docker compose down                                  # detener todo
```

## Seguridad
- Conexiones a PostgreSQL cifradas con SSL (`sslmode=require`).
- Un usuario por cliente con permisos mínimos: `ingesta` (solo inserta), `operador` (consulta y administra), `grafana_ro` (solo lectura).
- Lecturas con `mensaje_id` único: un mensaje reenviado por RabbitMQ no se guarda dos veces.
