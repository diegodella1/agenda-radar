# Plan de construcción — historias ejecutables
**Objetivo:** producir un sistema en funcionamiento, medible y instalable en la Raspberry compartida, no una demo estática.

## 0. Reglas para agente de programación/Codex
1. Crear repo separado `agenda-radar`; **no sobrescribir** XPoster/Canci ni afectar servicios actuales en Raspi sin autorización explícita.
2. Leer los PRD y los repos originales antes de portar código; citar archivo/commit cuando se reutilice.
3. Construir por historias con tests; actualizar migraciones, README y changelog.
4. Nunca afirmar que un conector externo funciona sin una prueba real autorizada; usar fixtures en CI.
5. No inventar tokens/API keys, no ejecutar credenciales de producción ni modificar tunnel/routers sin autorización.
6. Toda etapa debe poder arrancar en x86_64 y ARM64 con datos sintéticos, y continuar sin OpenAI/X.
7. Marcar historias `TODO`, `IN_PROGRESS`, `BLOCKED_EXTERNAL`, `DONE_VERIFIED`. Una UI bonita no cuenta como funcionalidad sin backend y datos.
8. Entregar checklist y evidencia de test en cada PR; no publicar automáticamente.

## Fase 0 — bootstrap (P0)
- **AR-001** Estructura repo, Python/FastAPI, Jinja/HTMX, config tipada, lint/test/mypy, scripts ARM64.
- **AR-002** SQLite/FTS5/Alembic, modelos, índices, WAL y datos sintéticos. Criterio: migración arriba/abajo, búsquedas FTS, backup y restore con integridad.
- **AR-003** Usuarios, roles, sesión, CSRF y bootstrap; superadmin y media_admin diferenciados. Criterio: endpoints mutantes no autorizados devuelven 403.
- **AR-004** Workers con tabla jobs, lease e idempotencia. Criterio: restart no duplica items ni pierde trabajos.

## Fase 1 — capturar y agrupar (P0)
- **AR-010** CRUD RSS y agregación propia/reference, actualización manual, lectura real y salud.
- **AR-011** Web públicamente permitido con discover RSS + allowlist y SSRF/robots guard.
- **AR-012** Canonicalización, dedupe documento y versionado de cambios.
- **AR-013** Extracción de entidad/tema via heurística + OpenAI condicional, con schema.
- **AR-014** Agrupación de acontecimientos sin borrar menciones; split/merge humano.
- **AR-015** Ficha de evento con timelines, URLs y fuente independiente.

**Gate 1:** 20 feeds válidos procesados, un evento con 5 menciones de distintas fuentes visible, reintento idempotente, error de feed diagnosticable.

## Fase 2 — agenda y motor editorial (P0)
- **AR-020** Fuentes/grupos/temas/entidades/pesos con validaciones y export JSON.
- **AR-021** Scoring por componente + versiones/config snapshot.
- **AR-022** Agenda propia (RSS propio o carga manual) y referencia comparables.
- **AR-023** Dashboard con 1/6/24/72 h, delta, detalle, salud y gráficas.
- **AR-024** Motor de brecha con supresión por datos faltantes y métricas de confianza.
- **AR-025** Preview, rollback y auditoría de config.

**Gate 2:** variar pesos cambia score como se espera; referencia/propia se compara sobre misma cesta; fuente propia caída impide alerta falsa.

## Fase 3 — tendencias, bot y OpenAI (P0/P1)
- **AR-030** Google Trends RSS/CSV, Google News RSS; atribución, freshness y controles de proveedor.
- **AR-031** API client OpenAI parametrizable, Structured Outputs, presupuestos y evals.
- **AR-032** Editor de prompts con versionado, test, publicación, rollback.
- **AR-033** Telegram pairing/lista blanca, `/agenda`, `/brechas`, `/tema`, `/fuentes`, preguntas naturales.
- **AR-034** Motor de alertas + outbox + cooldown + silencio + auditoría.
- **AR-035** X con API oficial, detrás de feature flag. Si no hay entitlement, demostrar degradación; no bloquear release.

**Gate 3:** alerta real controlada por regla llega a chat autorizado; consulta devuelve links guardados; un chat desconocido no obtiene datos; OpenAI deshabilitado no rompe métricas.

## Fase 4 — hardening y piloto
- **AR-040** Pruebas E2E en Pi 5 bajo carga real de otros servicios (sin tocarlos), memoria, CPU, I/O, temperatura, coste de tokens.
- **AR-041** Backup a volumen externo y restore drill; retention y rotación de logs.
- **AR-042** Controles legales/privacidad de conectores, CSRF/SSRF, secret redaction.
- **AR-043** Corpus editorial de evaluación: clusters, brechas, errores IA.
- **AR-044** Instalador one-shot verificable + manual 15 minutos + healthchecks y soporte.
- **AR-045** Piloto con 1 medio, 1 administrador y 2 editores; registrar falsos positivos y decisiones tomadas.

**Gate 4:** aceptación funcional `09_QA_OPERACIONES.md` y evidencia de instalación/recuperación real. No declarar «production-ready» por tests simulados solamente.

## Dependencias clave
`AR-002 -> AR-010/012 -> AR-014 -> AR-021 -> AR-022/024 -> AR-034 -> AR-033`.
`AR-003 -> AR-020/032 -> AR-025`. `AR-030` en paralelo a fase 2. `AR-035` opcional según entitlements.

## Backlog explícito fuera del MVP
Analítica propia de YouTube, conectores CMS, recomendaciones de video basadas en conversiones, audio/radio en vivo, generación de clips, multi-instancia gestionada, appliance comercial y facturación. Diseño de interfaces de plugin desde el principio, pero sin construir todo.

## Alcance para Media Party
Si se presenta un prototipo previo a financiación: demo con 10–20 medios autorizados; evento agrupado; score explicado; delta propio/ref; alerta Telegram y consulta con evidencia. Incluir claramente qué es real (ingesta y medición) y qué está simulado (fixtures). La documentación y planes comerciales son distintos del software terminado.
