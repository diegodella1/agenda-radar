# Estado de Agenda Radar — 15 de octubre de 2026

**Piloto desplegado en https://mp.diegodella.ar. Configuración de medios/proveedores a cargo del usuario; observación de 24 h automatizada.**
No se considera aprobado un piloto editorial con datos reales antes de cargar fuentes y evaluarlo.

## Entregado

- Usuario administrador `diego@diegodella.ar`, contraseña aleatoria local 0600; cambio desde
  Mi cuenta con revocación de sesiones. Roles, Argon2id, CSRF, auditoría y secretos cifrados.
- Fuentes RSS/Atom/web/manual, Google News/Trends y X opcional; validación SSRF, robots,
  ingesta con reintentos, deduplicación, correcciones, agrupamiento y revisión humana.
- Comparación propia/referencias con evidencia, pesos, cinco ventanas, snapshots, decisiones,
  cobertura propia, split/merge, exportación y configuración con preview/rollback.
- Alertas de brecha, emergentes, prioridad sin cobertura, cambio de agenda y alto impacto.
  Evidencia acumulada entre consultas; cooldown, rearme, supresión ante datos insuficientes.
- Incidencias de fuentes persistentes con recuperación y outbox exclusivo de administradores.
  Silencios y límite conjunto de seis mensajes por usuario cada doce horas.
- OpenAI opcional con estructura, citas/cifras/spans validados, reserva de presupuesto y
  fallback determinista. Publicación de prompts de respuesta exige cuatro casos sintéticos
  versionados; extracción en modo prueba no modifica entidades.
- Telegram opcional: pairing, comandos, consultas, seguimiento, silencios, outbox y reintentos.
- Backup online, checksum, rotación 7 días/4 semanas, descarga administrativa, restore aislado.
- Pausa de ingestas pendientes, diagnóstico, worker con lease/singleton y mantenimiento.
- Docker con dependencias limpias, imagen final identificada por hash de fuentes, recursos
  limitados y logs rotativos. Dependencias registradas en requirements.production.txt.
- Túnel Cloudflare propio `agenda-radar-mp`; DNS de `mp.diegodella.ar` creado. No se modificó
  el túnel compartido ni `/etc`. La propuesta systemd anterior fue reemplazada por Docker.
- Runner de disponibilidad HTTPS 24 h y evaluador de corpus editorial etiquetado.

## Evidencia

- **38 tests locales aprobados** y Ruff/mypy sin errores.
- **39 tests aprobados dentro de Docker limpio en 17,42 s**; `artifacts/docker-test-results.txt`.
- Imagen construida desde Python/PyPI; logs `artifacts/docker-build.log` y `docker-release.log`.
  Manifest de código en `deploy/release.json`; hashes de wheels en `artifacts/requirements.wheels.txt`.
- Backup/restauración de la base real actual: integridad, claves foráneas y conteos de 29 tablas
  verificados; `artifacts/restore-drill.json`. Todavía no contiene corpus piloto.
- Corpus sintético fijo: 12 documentos, precisión/recall 1,0 en ese fixture exclusivamente.
  `artifacts/corpus-evaluation.json`. No equivale a calidad editorial sobre noticias reales.
- E2E local previo: login, dashboard, decisión, 12 pantallas y móvil sin overflow.
- HTTPS público responde ready; HTTP redirige 307 a HTTPS y se envía HSTS.
- Web/worker/túnel activos con reinicio automático. Muestra puntual de memoria combinada ~156 MiB.
- Se detectó un EOF intermitente del proxy; se ajustó keepAliveTimeout a 2 s y se completó
  navegación con pausas superiores al timeout del servidor: 13 pantallas HTTPS, login,
  diagnóstico, cookie segura, móvil y logout aprobados. Ensayos anteriores archivados,
  nunca contados como 24 h aprobadas.
- Benchmark anterior: 10.000 documentos/500 eventos, p95 0,366 s para cálculo interno;
  no es medición LAN/HTTPS bajo carga. Raspberry Pi 5 ARM64 de 8 GB.

## Configuración a cargo del usuario, según su indicación

Las fuentes, RSS, redes y proveedores se cargarán desde Administración. No hay datos sintéticos
mezclados con la base real ni claves prestadas de otros proyectos. OpenAI/Telegram permanecen
apagados hasta configurar las cuentas. X es opcional.

## Límites de aceptación que no se pueden dar por aprobados anticipadamente

- Conectividad/calidad con las cuentas reales y recepción Telegram requieren su configuración.
- El ensayo 24 h debe transcurrir: consultar `artifacts/soak/status.json`; running no es aprobado.
- El corpus editorial de 150–200 documentos debe ser etiquetado por editores. El runner está
  implementado, pero los fixtures sintéticos no reemplazan esa evaluación.
- La copia externa requiere descargar un backup a otro equipo y guardar master.key por separado.
  La restauración local está probada; no se inventó un destino remoto.
- Velocidad y alto impacto son heurísticas explícitas, no modelos semánticos calibrados.
  Google News sin publisher resuelto no suma independencia; X es muestra de cuentas/listas.
- La prueba de extracción usa evidencia local; no certifica precisión con corpus real.
- UI nativa Fetch/SVG y reglas avanzadas JSON son decisiones de implementación documentadas.

Guía vigente: [Configurar y operar](docs/CONFIGURAR_Y_PROBAR.md).

## Sitio público y repositorio — 15 de octubre de 2026

Cinco páginas públicas con diseño editorial, alcance explícito, casos de uso y acceso al producto. Sin precios. La raíz conserva el dashboard autenticado. El usuario informa que cargó OpenAI; esa configuración no fue modificada por este cambio. Repositorio privado: https://github.com/diegodella1/agenda-radar.

## Demo pública editable — 15 de octubre de 2026

- Acceso demo / demo en /demo/login y desde login principal; CTA público.
- SQLite por visitante, cookies separadas, 2 h, máximo 10 visitas simultáneas.
- Escenario argentino ficticio: 7 medios, 18 acontecimientos, 103 publicaciones,
  5 alertas históricas, tendencias, decisiones y evidencias internas.
- Decisiones, cobertura, agrupamientos, fuentes, criterios, exportación, reinicio
  y lote de 10 novedades con evaluación real de alertas. Asistente determinista local.
- Sin worker demo, proveedores, claves, usuarios, backups ni operaciones externas.
- 46 tests locales aprobados; Ruff y mypy correctos. Smoke local con dos visitantes,
  11 pantallas a 1440/390/320 px, evidencia, asistente, novedades, reinicio y logout.
- El primer smoke local agotó el timeout de carga durante pruebas concurrentes;
  el recorrido completo posterior pasó con timeout de 60 s y ejecución separada.
- Plan y operación en docs/DEMO_PLAN.md y docs/DEMO.md.

- La primera prueba HTTPS detectó JavaScript antiguo servido desde caché. Se añadió
  versión por hash de contenido a CSS/JS, también en la demo y las páginas públicas.
  GitHub CI aprobó la implementación inicial; se verifica nuevamente la corrección.

- Recorrido HTTPS funcional completado tras versionar assets: ambos accesos, aislamiento,
  decisiones, evidencia, novedades, asistente, 11 pantallas en 3 tamaños, reset y logout.
  El chequeo de red identificó el beacon inyectado por Cloudflare, bloqueado por CSP antes
  de conectarse; el smoke distingue explícitamente ese bloqueo de tráfico externo real.
- CI de GitHub aprobada para el código desplegado. Ningún usuario demo ni documento
  ficticio quedó en la base de producción.


## Demo con fuentes reales — 16 de octubre de 2026

Reemplaza el escenario sintético descrito el 15 de octubre.

- Publicada imagen `agenda-radar:real-sources-v2`; web y `demo-collector` saludables.
- Horizonte Federal es el cliente ficticio; ocho medios argentinos, seis regiones,
  siete feeds YouTube y Google Trends aportan contenido real. Perfiles X/Instagram de
  los ocho medios verificados; Facebook y TikTok donde existe evidencia oficial.
- Primera carga completa: 542 publicaciones y 30 muestras de Trends. El corpus sigue
  actualizándose: noticias/Trends cada 15 minutos; YouTube/X cada 30 minutos.
- X queda pendiente de credencial exclusiva del recolector; no se inventan publicaciones.
- Catálogo y datos públicos separados de producción. El web monta snapshots en lectura;
  el recolector monta únicamente su directorio, sin secretos ni base de producción.
- 53 pruebas aprobadas, Ruff y mypy correctos. Prueba visual en seis pantallas y cinco
  anchos, prueba aislada de la imagen sin red y verificación HTTPS pública exitosas.
- Verificación pública: ocho referencias, siete canales YouTube y 503 acontecimientos.
  Primera sesión medida: 32,2 segundos en el equipo bajo carga; requiere mejorar si se
  necesita acceso inmediato. No se estableció un objetivo de latencia en este cambio.
- Operación, credencial X y rollback: `docs/DEMO.md`. Imagen anterior conservada:
  `agenda-radar:criteria-e84af9b52084`.


## Onboarding guiado de la demo — 16 de octubre de 2026

- Tutorial automático por login y pestaña: bienvenida, fuentes, criterios, comparación
  antes de publicar, radar, tendencias, evidencia real y decisiones. Omitible con botón
  o Escape; repetible desde Ver tutorial. Recargar conserva el paso; reset no lo reactiva.
- Modales con foco contenido y controles reales destacados. Navegación entre pantallas,
  adaptación móvil y movimiento reducido. El recorrido no escribe datos editoriales.
- Pantalla final «Ya está todo listo para explorar tu agenda» con verificación de fuentes
  habilitadas, configuración activa y noticias reales. Si faltan noticias muestra
  «Estamos preparando tu radar»; evita pasos de acontecimientos cuando no hay datos.
- Sin migraciones ni nuevas APIs. La ayuda anterior continúa en cuentas reales.
- 55 tests Python aprobados, Ruff/mypy correctos. Smoke de onboarding aprobado con corpus,
  sin corpus y con sessionStorage bloqueado; cuatro anchos (320/390/768/1440), teclado,
  recarga, retroceso, omisión, repetición, reinicio y login nuevo; sin escrituras del tour.
- HTTPS público: los siete pasos, cierre, datos inalterados, omisión, repetición y reset
  verificados. El último login del smoke excedió 60 s preparando el corpus; comprobación
  enfocada posterior con límite de 150 s aprobada: login 200 en 75,8 s, bienvenida automática
  tras progreso completado, omisión, recarga y logout. La demora de inicialización persiste;
  no se atribuye al tutorial ni se considera resuelta por ampliar el plazo de la prueba.
- Web desplegada con agenda-radar:onboarding-v2; health ready/healthy. Worker y recolector
  conservan real-sources-v2. Imagen previa real-sources-v2 disponible para rollback.
  Capturas en artifacts/onboarding; prueba reproducible scripts/smoke-onboarding.mjs.


## Nuevo dominio, demo ficticia e idiomas — 26 de noviembre de 2026

- Dominio: https://aradar.diegodella.ar. Túnel independiente `agenda-radar-aradar`
  (`6c2c5376-c23d-40a6-b2f5-db510d7b3117`). Base, usuarios y criterios conservados;
  OpenAI y extracción siguen apagados. Backups previos en `artifacts/deploy-20261126/`.
- Demo directa en `/demo/`, sin autenticación, corpus, base por visitante ni llamadas externas.
  Horizon Daily y todas las referencias/noticias/métricas son ficticios y están identificados.
  Incluye comparación, evidencia, decisiones, alertas, tendencias, fuentes, pesos con preview,
  asistente local y reinicio. Los cambios viven exclusivamente en el navegador.
- Guías de primera visita por sección, omitibles con botón/Escape y repetibles a voluntad.
- Inglés predeterminado y español seleccionable en sitio público, login, cuenta principal y
  demo. Preferencia compartida por cookie; textos editoriales del usuario sin traducción automática.
- Recolector retirado de Compose; sus archivos históricos se conservan sin uso.
- Validación local: demo en diez secciones, ambos idiomas, 1440/390/320 px; decisiones, fuentes,
  pesos, asistente, actualizaciones ficticias, reinicio y guías. Cero solicitudes de API o externas.
  Primera carga interactiva observada: 669 ms en una muestra local, no un SLA.
- Sitio/cuenta: 19 páginas por idioma, escritorio/móvil, sin errores de JavaScript.
- Tests específicos de demo sin base/corpus y selección/persistencia de idioma aprobados,
  así como regresiones específicas de la demo anterior y pruebas de polling de trabajos.
  Ruff y comprobación de espacios correctos. La batería completa fue interrumpida;
  no se presenta como una ejecución completa aprobada.
- Evidencias de navegador: `artifacts/showcase/` y `artifacts/i18n/`.
  La verificación pública del despliegue se registra por separado.

### Verificación pública final

- Web y worker activos con `agenda-radar:showcase-en-es-20261126`; túnel activo.
  Los tres servicios tienen reinicio `unless-stopped`. Recolector y contenedor de staging retirados.
- HTTPS `/health/ready` devuelve `ready`; `/demo/` sirve directamente la nueva demo.
- Smoke público aprobado: diez secciones, inglés/español, 1440/390/320 px, acciones locales
  y recorridos. Primera carga interactiva observada: 2125 ms (una muestra, no un SLA).
  Cero llamadas de API y cero solicitudes externas permitidas. El beacon agregado por
  Cloudflare fue bloqueado por CSP en las 50 navegaciones; la prueba verifica ese bloqueo.
- Smoke público de sitio/cuenta aprobado: 19 páginas, ambos idiomas, escritorio/móvil,
  sin errores de JavaScript. Evidencias en `artifacts/showcase-public/` y `artifacts/i18n-public/`.
- Configuración verificada dentro del contenedor: inglés predeterminado, demo estática activa,
  OpenAI y extracción desactivados, cero llamadas registradas en la última hora,
  heartbeat del worker vigente y cero fuentes en la cuenta principal (configuración conservada).

## Red team de copy, SEO y descubrimiento en asistentes — 26 de noviembre de 2026

- Auditoría y decisiones en `docs/COPY_SEO_REVIEW.md`; skills existentes copywriting/seo-audit.
- Copy público EN/ES orientado a monitoreo de medios, brechas y reuniones editoriales;
  CTA de demo directa, sin credenciales obsoletas ni resultados comerciales inventados.
- Títulos/descripciones específicos, canonical por idioma, hreflang recíprocos y enlaces
  navegables EN/ES. Sitemap con diez URLs; robots anuncia sitemap. Cloudflare conserva sus políticas.
- Definiciones y límites visibles en HTML, microdatos SoftwareApplication. Demo, cuenta y
  páginas no públicas con noindex; API excluida de rastreo, autenticación intacta.
- Corregido solapamiento del ejemplo en móvil por gap porcentual; regresión visual cubierta.
- Siete tests específicos aprobados; Ruff/diff-check correctos; 19 páginas bilingües
  escritorio/móvil aprobadas localmente. Smoke público sin JavaScript aprobado para las diez URLs,
  sitemap, robots, noindex y diseños de 1440/390/320 px. Evidencias en `artifacts/seo-public/`.
- Web/worker publicados con `agenda-radar:copy-seo-20261126`, manifiesto
  `sha256:e1a1082edff80109c453b6fde2f1ca2f1e579e63c9e780505c47e7e6524396d9`.
  HTTPS readiness devuelve `ready`. No se afirma indexación, ranking ni citas efectivas en asistentes.

## Agentes, Slack e IA empresarial — 26 de noviembre de 2026

- Implementada `/collaboration`, accesible desde la navegación: perfiles de IA, selección por
  tarea, Slack, políticas por fuente, agentes previsualizables, seguimiento y actividad. EN/ES.
- Tres agentes acotados: vigilancia con reglas existentes, briefing diario y nueva evidencia
  de historias seguidas. Decisiones humanas, responsable, silencios e historial compartido.
- Adaptadores OpenAI, Anthropic y Chat Completions compatible para servidores internos.
  Host interno autorizado por operador, conexión fijada a DNS validado, CA empresarial,
  credenciales cifradas, límites/costos y validación de salida. Sin fallback privado→nube.
- Slack Socket Mode: canales autorizados, vinculación temporal de identidad, comandos,
  menciones, botones y modal de descarte, hilos, cola durable y control de duplicados.
  Políticas verificadas antes de generar y antes de entregar; versiones corregidas cancelan
  mensajes pendientes. Reintentos del SDK desactivados para resultados ambiguos de envío.
- Migración aditiva 0002. Respaldo previo verificado:
  `data/backups/pre-release-20261126T163134.db`. Datos/configuración existentes conservados.
- Proceso separado `collaboration-worker`: IA lenta no bloquea ingestión ni recepción Slack.
  Readiness de producción verifica heartbeat de ambos workers.
- Publicado `agenda-radar:collaboration-20261126`, manifiesto
  `sha256:9879b5acd2d87215fcc9adf4beba1b5582ec52347162745d10587b41138420f0`.
  Web, worker y colaboración activos con reinicio automático; túnel activo; HTTPS ready.
- Verificación real: IA y Slack desactivados, cero perfiles/agentes activos, cero llamadas de
  modelos y cero entregas. Cuenta principal conserva cero fuentes; demo ficticia intacta.
- Navegador local: creación de perfil desactivado, reinicio de formulario y preview de agente.
  Navegador público: pantalla EN/ES en 1440/390/320 px; demo pública y sus diez secciones aprobadas.
  Evidencias en `artifacts/collaboration/`, `artifacts/collaboration-public/` y
  `artifacts/showcase-after-collaboration/`. Imagen probada sin red: migración y heartbeat correctos.
- Instalación, permisos, límites, activación y rollback en `docs/COLLABORATION.md`.
  Falta validar contra un workspace Slack y servidor empresarial reales: no se proporcionaron
  sus credenciales/endpoints. Evaluación editorial humana pendiente de un corpus representativo;
  los transportes simulados y fixtures no prueban calidad factual de modelos reales.
- Validación final: suite completa **93 aprobadas en 404,73 s**, más la prueba adicional
  de reintentos del SDK Slack aprobada. Ruff y `git diff --check` correctos. La falla de caché
  observada durante cambios simultáneos de código no se reprodujo con los archivos estables.

## Sitio público actualizado y retorno desde login — 26 de noviembre de 2026

- Inicio, Producto, Casos de uso, Acerca de y Alcance actualizados EN/ES para reflejar
  monitoreo, colaboración, tres agentes, responsables, Slack y elección de IA empresarial.
  Seis casos de uso; distinción explícita entre demo ficticia, cuenta autenticada e integraciones
  que requieren configuración. Títulos, descripciones sociales y definición estructurada actualizados.
- `/collaboration` sin sesión redirige al login; al ingresar vuelve al destino y conserva parámetros.
  Retornos externos ignorados. APIs conservan 401 JSON. Login de demo estática sin credenciales obsoletas.
- Diez tests de seguridad/acceso y ocho tests de páginas/SEO/demo aprobados. Navegador local y
  público: retorno de login correcto y destinos externos rechazados; diez URLs de idiomas verificadas
  sin JavaScript, con canonical/hreflang/sitemap y layouts 1440/390/320 px.
- Evidencias: `artifacts/product-pages-local/`, `artifacts/product-pages-public/`;
  regresión reproducible: `scripts/smoke-login-return.mjs`.
- Publicado `agenda-radar:product-pages-20261126`, manifiesto
  `sha256:a0a84274f6051fc698fa9e71c88865dc06e04bd9bfdd44a563f40bcc37898f90`.
  HTTPS readiness correcto. Sin cambios de esquema ni activación de conexiones externas.

## 2026-11-26 — Newsroom benefits page published

Replaced the public roadmap/status presentation with “For your newsroom” / “Para tu redacción”, retaining /roadmap and localized canonicals. Rewrote navigation, metadata and cross-links. The page leads with newsroom benefits, three editorial agents, a four-step Slack workflow, evidence and ownership, and optional cloud/internal AI. Demo and integration requirements remain explicit. Updated English/Spanish catalog and generated i18n assets; corrected integration panel padding.

Validation: 7 public/SEO/showcase pytest tests passed; Ruff and git diff --check passed. Browser smoke passed on production for all 10 localized public URLs at 1440/390/320 px with JavaScript disabled, including canonical/hreflang, product schema, sitemap, robots, noindex and demo links. Screenshots and report: artifacts/newsroom-public/. Initial local browser pass succeeded; repeat after padding adjustment was interrupted by preview server shutdown; final production pass verified the shipped CSS.

Published image agenda-radar:newsroom-page-20261126, manifest sha256:576376ba29f0d452ae7998dd8772c7a59996123e31a44efc0184df31f96ae599. Web, worker, collaboration and tunnel running; public /health/ready returns ready. This change presents existing agent/integration capabilities; it does not activate Slack or AI connections.
