# Agenda Radar

## Agents, Slack and enterprise AI

The workspace includes **Agents & collaboration**: previewable vigilance, daily briefing and
follow-up agents, human decisions and ownership, Slack Socket Mode, and AI profiles for OpenAI,
Claude or an internal Ollama/vLLM-compatible server. Connections start disabled.
See [setup, data policies and pilot validation](docs/COLLABORATION.md).

Aplicación local para observar fuentes, agrupar acontecimientos, comparar cobertura propia y
referencias, registrar decisiones y consultar evidencia. Un medio por instalación.

**Acceso:** https://aradar.diegodella.ar · administrador `diego@diegodella.ar`.

[Guía vigente de acceso y operación](docs/CONFIGURAR_Y_PROBAR.md). Contraseña inicial en
`secrets/initial-admin.json` (archivo privado local); cambiar desde Mi cuenta.

**Estado:** desplegado para configuración y piloto. Consultar [STATUS.md](STATUS.md) para distinguir
pruebas verificadas, limitaciones de implementación y validaciones externas pendientes.
Plan aprobado: [12_PLAN_MVP.md](../12_PLAN_MVP.md). La instalación del medio real no precarga fuentes ni claves; la demo usa un escenario ficticio local, sin recolector ni claves. Inglés por defecto y español seleccionable en toda la interfaz.

## Inicio en un entorno nuevo de desarrollo

Requiere Python 3.12 y SQLite con FTS5. Desde esta carpeta:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
cp .env.example .env
.venv/bin/python -m agenda_radar.cli init
.venv/bin/python -m agenda_radar.cli create-admin --email editor@tu-medio.com
.venv/bin/python -m agenda_radar.cli web
```

En otra terminal, desde la misma carpeta:

```sh
.venv/bin/python -m agenda_radar.cli worker
```

Abrir `http://127.0.0.1:8765`. La contraseña se ingresa interactivamente y no aparece en
argumentos de procesos. El instalador `sh scripts/install.sh` automatiza entorno/migración;
la creación del administrador sigue siendo interactiva.

`COOKIE_SECURE=false` es exclusivamente para desarrollo HTTP en loopback. Para uso en LAN,
configurar HTTPS, `COOKIE_SECURE=true` y `APP_BASE_URL` correcto. No se instala un túnel ni
se modifican servicios existentes.

## Primer recorrido

1. Ingresar y abrir **Fuentes**. Registrar fuentes de referencia y fuente propia, indicando
   grupo editorial y fundamento de uso. Probar antes de guardar, o importar CSV.
2. Dejar worker activo o pulsar **Actualizar**. Revisar salud y última captura.
3. Abrir **Resumen**, comparar agendas y entrar a una ficha para ver todas sus publicaciones.
4. Configurar pesos/temas/reglas en **Criterios y pesos**. Previsualizar y publicar.
5. Registrar seguir/descartar, cobertura propia, o corregir agrupamiento con split/merge.
6. Configurar claves en **Proveedores** y parámetros en **Criterios y pesos**. No pegar claves
   en reglas, prompts, URLs o archivos versionados.
7. Pulsar **Vincular Telegram**, enviar el comando temporal al bot privado y activar Telegram.
8. Consultar evidencia y descargar Markdown. Un usuario lector no modifica datos; un analista
   puede exportar; un editor decide; media_admin administra criterio/equipo; superadmin opera.

Para OpenAI configurar `ai_enabled`, `ai_model`, tarifas por millón de tokens de entrada/salida
y presupuestos. Para extracción opcional: `extraction_enabled`, `extraction_model` y sus
tarifas de entrada/salida; las coincidencias ambiguas quedan pendientes de revisión humana.
El prompt debe usar el modelo con tarifa configurada. Si falta configuración,
cuota o evidencia, se devuelve una respuesta determinista con limitaciones.

Agenda propia manual: registrar publicaciones reales y declarar explícitamente la vigencia de
`manual_coverage_complete_until` (timestamp UTC) si no existe feed propio. No inferimos ausencia
por una lista manual incompleta. Datos almacenados internamente como timestamps UTC, mostrados ART.

## Proveedores

- RSS/Atom: captura HTTP limitada y conexión fijada a IP pública validada; DTD/entidades prohibidos.
- Web: robots, feed descubierto o selector CSS `options.article_selector`; solo títulos/extractos.
- Google News: evidencia capturada; enlaces de agregador sin resolver no cuentan como medio independiente.
- Google Trends: RSS exportado o CSV (`Trends`, `Tendencias` o `label`). Volumen conserva unidad propia.
- X: adaptador oficial opcional. `options.user_id` o `options.list_id`, token en Proveedores;
  señal pública separada. Sin credenciales/cuota/entitlement se informa el error.
- Telegram: Bot API por long polling, chat privado vinculado. `/agenda`, `/brechas`, `/tema`,
  `/fuentes`, `/silenciar`, `/ayuda`; botones de decisiones requieren rol editor.

El software no publica notas ni redes automáticamente. Configurar credenciales no constituye
una prueba de conectividad: verificar una operación real antes de declarar integración saludable.

## Docker

```sh
docker compose build
docker compose run --rm web python -m agenda_radar.cli init
docker compose run --rm web python -m agenda_radar.cli create-admin --email editor@tu-medio.com
docker compose up -d
```

Migraciones antes del arranque. El puerto queda en loopback. Configurar proxy HTTPS institucional
antes de usar cookies seguras desde navegador. La imagen ejecuta como usuario sin privilegios.
Construcción Docker desde registro requiere conectividad; no se modificó el daemon del equipo.

## Pruebas

```sh
.venv/bin/python -m pytest -q
.venv/bin/ruff check src tests scripts
.venv/bin/python -m mypy src/agenda_radar
```

E2E usa base separada y credenciales aleatorias:

```sh
.venv/bin/python scripts/prepare_e2e.py
DATA_DIR=artifacts/e2e/data SECRETS_DIR=artifacts/e2e/secrets COOKIE_SECURE=false APP_PORT=8876 \
  .venv/bin/python -m agenda_radar.cli web
# Otra terminal: instalar playwright de Node para pruebas o indicar módulo local disponible.
PLAYWRIGHT_MODULE=/ruta/node_modules/playwright/index.mjs node scripts/e2e.mjs
```

Capturas en `artifacts/screenshots/`. Ninguna fixture se activa en la base de uso real.
`scripts/benchmark.py` genera 10.000 documentos sintéticos en otra base. No reemplaza el piloto.

## Operación y contratos

[Operaciones y recuperación](docs/OPERATIONS.md). Health público mínimo: `/health/live` y
`/health/ready`; diagnóstico detallado y OpenAPI requieren autenticación.

API: `/api/v1/openapi.json`. Mutaciones requieren sesión, `X-Requested-With: AgendaRadar` y
`X-CSRF-Token` obtenido al ingresar. Trabajos largos devuelven `job_id`, consultable por su autor
(o superadmin). Configuración y snapshots son versionados; el rollback publica una nueva versión.

Frontend renderizado con Jinja2, CSS y Fetch nativo; gráficos SVG accesibles, sin CDN ni Node en
producción. Esta primera implementación evita depender de HTMX/Chart.js durante la instalación
offline. Tokens y claves cifrados con Fernet; contraseñas Argon2id mediante cryptography.

## Entorno de esta ejecución

La instalación desde PyPI no pudo completarse por DNS del entorno restringido. Para verificar
se copió al `.venv` aislado un conjunto de paquetes ya instalados en el equipo; no se cambiaron
sus proyectos de origen. Ese `.venv` no se distribuye. El build wheel local y sus recursos se
verificaron por separado. La imagen de producción se construyó con dependencias de PyPI
y pasó la suite completa; versiones en requirements.production.txt.

## Sitio público

Portada `/home`, acerca de `/about`, producto `/funcionalidades`, casos `/casos-de-uso` y alcance `/roadmap`. La raíz muestra el radar si hay sesión y la portada para visitantes. Sin precios. Ver [sitio público](docs/PUBLIC_SITE.md) y [especificaciones originales](docs/specification/00_LEEME.md).

## Demo pública

[Probar demo](https://aradar.diegodella.ar/demo/login): usuario `demo`, contraseña `demo`. Cliente ficticio con noticias, tendencias y perfiles reales; actualización periódica y cambios aislados por visitante. Ver [operación y límites](docs/DEMO.md) y [plan aprobado](docs/DEMO_PLAN.md).

## Demo pública

[Explorar la demo](https://aradar.diegodella.ar/demo/) sin registro: contenido ficticio, acciones locales y guías por función. [Operación de la demo](docs/DEMO.md).
