# Arquitectura y deployment — Raspberry Pi 5 (8 GB)
**Decisión:** self-host sencillo, sin Supabase, sin obligación de nube propia; OpenAI queda como servicio externo por API.

## 1. Topología
```text
  RSS / Web permitida / Google News / Trends RSS / X(API opcional)
                             |
                     workers de ingesta
                  fetch -> parse -> normalizar
                             |
          SQLite WAL + JSON1 + FTS5   <---> archivo de auditoría
                   |         |               |
          cluster de eventos   motor de reglas/scoring
                   |         |               |
                FastAPI (REST + vistas HTML)
                    |                |
           Dashboard LAN        Bot Telegram (long polling)
                                      |
                               OpenAI Responses API
                             (solo al solicitarlo)
```

**Un solo backend Python** aporta API, HTML (Jinja2 + HTMX), auth, repositorios y servicios. **Dos procesos** separados: `web` y `worker` (ingestión, scoring, scheduled jobs y bot). Evitar Redis, RabbitMQ, Elasticsearch, MongoDB y Node runtime permanente. Para gráficos Chart.js/uPlot estáticos vendorizados; no depender de CDN al usar LAN.

## 2. Stack propuesto
| Capa | Propuesta | Motivo |
|---|---|---|
| OS | Raspberry Pi OS 64-bit, actualizado | ARM64 estable |
| Runtime | Python 3.12, virtualenv o contenedores ARM64 | menos dependencias y fácil debug |
| App | FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic | tipos, OpenAPI, migraciones |
| UI | HTML/Jinja2 + HTMX, CSS propio, charts | evita build server Next permanente |
| DB | SQLite 3 WAL, índices, JSON1 y FTS5 | archivo portable, sin servicio extra |
| Jobs | tabla `jobs` + worker tick/lease con reintentos; APScheduler opcional dentro del worker | sin broker, recuperable |
| Fetch | httpx, feedparser, selectolax/bs4, robots checks | RSS + páginas allowlisted |
| IA | OpenAI SDK, Responses API, Structured Outputs, configuración por operación | no inferencia local |
| Bot | python-telegram-bot con getUpdates/long polling | no abrir puerto externo |
| Logs | JSON rotativo + métricas en DB | operación autónoma |
| Contenedores | Docker Compose de 2 servicios, volúmenes locales | despliegue repetible; compatible con Pi |

**Nota de almacenamiento:** SQLite es SQL, no NoSQL. JSON1 permite campos flexibles y evita un clúster Mongo. Abstraer `StoragePort` para migrar solo si hay un problema probado. Evitar usar DB en microSD: preferir SSD y backups fuera del disco.

## 3. Límites iniciales de hardware
- Pi 5 / 8 GB **compartida** con otros servicios. Realizar inventario de RAM/CPU/espacio antes de desplegar. Memoria objetivo inicial de Agenda Radar **≤1,5 GB RSS** (web + worker + cachés; excluir otros servicios), límite duro ajustable según disponibilidad real. No realizar procesamiento pesado de video.
- 20–30 fuentes RSS/web, actualización 5–15 min con jitter; 1–2 conectores de tendencias cada 15–30 min; X únicamente según cuota real y costo.
- Límite de concurrencia de fetch 3–5; IA 1–2 solicitudes simultáneas; máximo 1 lote de clusterización caro por vez.
- Discos: retener 90 días metadata/menciones en MVP; por defecto almacenar extractos breves autorizados y URLs, no copiar artículos completos.
- Fuente 5V/5A y ventilación activa recomendadas para ejecución continua; conexión Ethernet preferible. Sin acceso directo desde internet.

## 4. Ciclo de datos
`FETCH -> PARSED -> STORED -> ENRICHED -> CLUSTERED -> SCORED -> ALERT_EVALUATED -> UI/TELEGRAM`.
Cada etapa es **idempotente**, registra `job_id`, estado, latencia, error y reintentos. Nunca borrar un input original por fallo de IA. Diferenciar datos «raw» de correcciones humanas.

## 5. Concurrencia SQLite
Configurar `PRAGMA journal_mode=WAL`, `busy_timeout=5000`, `foreign_keys=ON`; conexiones cortas y transacciones pequeñas. Una única cola de escritura serializada en worker; API escribe bajo transacciones cortas. No colocar DB en NFS. Asegurar checkpoints WAL, `VACUUM` en mantenimiento y backup por API online de SQLite para evitar snapshots inconsistentes.

## 6. Servicios y seguridad
- `web`: FastAPI con un único proceso/worker; bind `127.0.0.1` o LAN protegida; reverse proxy solo si hace falta.
- `worker`: CLI Python que ingiere y calcula, bot Telegram long polling con `chat_id` permitidos. Elegir un solo consumidor de getUpdates.
- `data/`: DB, archivos temporales, logs. `secrets/`: clave OpenAI/X/Telegram, permisos 0600, fuera de Git.
- Primer arranque requiere bootstrap admin en consola o token temporal de un solo uso; no credenciales por defecto.
- TLS remoto solo a través de túnel/VPN con autenticación fuerte; preferir Tailscale/Cloudflare Access ya existente; jamás abrir SQLite ni puerto 8000 a internet.
- SSRF: bloquear IPs privadas/loopback/link-local, esquemas inseguros, redirecciones hacia rangos internos, DNS rebinding; limitar tamaño HTTP, descargas y tiempo de respuesta.

## 7. Variables de configuración indicativas
```dotenv
APP_ENV=production
APP_BIND=127.0.0.1
APP_PORT=8765
DATA_DIR=/var/lib/agenda-radar
DATABASE_URL=sqlite:////var/lib/agenda-radar/agenda.db
APP_TIMEZONE=America/Argentina/Buenos_Aires
OPENAI_API_KEY= # nunca en el frontend ni en Git
OPENAI_MODEL_EXTRACT= # identificador validado en cuenta al instalar
OPENAI_MODEL_EXPLAIN= # identificador validado en cuenta al instalar
OPENAI_DAILY_BUDGET_USD=1.00
OPENAI_MONTHLY_BUDGET_USD=20.00
TELEGRAM_BOT_TOKEN=
TELEGRAM_ALLOWED_CHAT_IDS=
FETCH_CONCURRENCY=3
API_MAX_CONCURRENT_LLM=1
NO_EXTERNAL_PUBLISHING=true
```

El nombre de modelo **se configura y prueba**, no se hardcodea para evitar dependencia de disponibilidad/retirada o precios. Los presupuestos son defaults de prueba, no predicción de costos.

## 8. Mecanismo de instalación
`git clone`/copia de código -> `docker compose build` ARM64 -> configurar `.env` -> iniciar `web` y `worker` -> `alembic upgrade head` -> crear admin -> chequeo de salud -> registrar feeds -> Telegram pairing. Documentar modo bare-metal por si Docker existente está cargado.

El repositorio a crear debe incluir `compose.yaml`, Dockerfile multi-stage ARM64, `.env.example`, script `install.sh` idempotente, `backup.sh`, `restore.sh`, `healthcheck.sh`, service manifest/systemd si no Docker y prueba de smoke. **No hay scripts ejecutables en este paquete de especificaciones**.

## 9. Health y degradación
- `/health/live`: proceso responde.
- `/health/ready`: DB, migraciones, loop de worker y acceso a disco.
- `/health/connectors`: edad del último fetch, cuotas, errores, fuentes pausadas.
- Sin OpenAI: ingesta/scoring/filtros disponibles; resúmenes IA deshabilitados con mensaje claro.
- Sin Telegram: dashboard disponible, alertas quedan en outbox y se envían al restaurar, sujetas a vencimiento.
- Sin X: marcar `unavailable`; nunca completar con datos inventados.
- Sin conectividad: acceso al historial; retomar con backoff e idempotencia.

## 10. Escalabilidad
No escalar antes de encontrar un cuello de botella medido. La frontera natural al crecer es separar la base (Postgres o un motor document-oriented si se justifica), workers y distribución; conservar API y dominio editorial. El modo appliance para vender hardware debe reutilizar exactamente la misma imagen de instalación y backups.
