# Agenda Radar: construcción del MVP funcional

Plan aprobado el 15 de octubre de 2026. Referencia de alcance; los resultados reales se registran en `agenda-radar/STATUS.md`.

## 1. Producto y resultado esperado

Los 12 documentos originales describen una herramienta para ayudar a una mesa editorial a decidir qué cubrir mediante comparación de agendas, tendencias y evidencia verificable. Al aprobar este plan todavía no había software.

Entrega acordada: piloto completo para un medio, configurable, instalado en Raspberry Pi 5 compartida. X opcional. Medio piloto por seleccionar.

Recorrido obligatorio: configurar fuentes → ingerir publicaciones → agrupar acontecimientos → comparar cobertura → detectar brechas → alertar por Telegram → responder con evidencia → registrar decisión editorial → exportar informe.

“100% funcional” significa completar ese recorrido con integraciones reales, permisos efectivos, recuperación ante fallos y pruebas en hardware objetivo. No significa disponibilidad garantizada de proveedores externos.

## 2. Arquitectura y decisiones

- Python 3.12, FastAPI, Pydantic, SQLAlchemy y Alembic; Jinja2/HTMX con Chart.js local; SQLite WAL/FTS5; procesos separados web y worker.
- Docker Compose principal; systemd como alternativa documentada. Proyecto independiente `agenda-radar` dentro del workspace; conservar documentos originales.
- XPoster/Canci aportan patrones. Reutilizar código solo tras inspección de módulo, dependencias y pruebas; no son requisito del runtime.
- Separar documento original de observaciones por conectores. RSS y Google News no duplican una misma nota; diferentes medios mantienen sus menciones.
- Aporte por grupo editorial: máximo aporte ponderado del grupo por acontecimiento como límite inicial.
- Cobertura propia: publicaciones detectadas o registros manuales explícitos. Seguir, descartar o planificar no equivale a publicar.
- Agenda sin denominador válido: `own_share` y `gap_pp` nulos; mostrar cobertura absoluta y motivo.
- Prioridad editorial: conservar multiplicadores; normalizar su producto p mediante p/(1+p) para ranking.
- Distinguir consulta exitosa, antigüedad de publicaciones y fallas de captura. Feed sin novedades no implica caída.
- Snapshots inmutables con ventana, muestra, configuración y algoritmo. Preview/rollback no reescriben historia.
- Outbox durable y deduplicación local; no prometer entrega Telegram exactamente una vez ante respuestas ambiguas.

## 3. Entregas verificables

1. **Base operativa:** proyecto, migraciones, configuración, sesiones, cinco roles, CSRF, auditoría, jobs con leases y recuperación, bootstrap de un uso. Cierre: instalación limpia, permisos probados y recuperación idempotente.
2. **Captura real:** RSS/Atom, descubrimiento de feeds, web permitida con selectores configurables, importación manual, normalización/versiones y salud. Cierre: 20 feeds válidos, errores aislados, reingesta idempotente.
3. **Acontecimientos:** FTS5, similitud de títulos/entidades/tiempo, IA opcional para ambiguos, ficha con menciones, split/merge auditado; proteger correcciones humanas. Cierre: múltiples fuentes reales agrupadas sin fusionar hechos distintos por compartir nombre/tema.
4. **Agendas y administración:** scoring explicable, agenda propia, brechas, ventanas 1/6/24/72 h y 7 d, filtros, matriz fuente×evento, decisiones, criterios/pesos, preview/publicación/rollback y Markdown. Cierre: pesos producen diferencias verificables; conector propio caído suprime falsas alertas.
5. **Tendencias e IA:** Google News, Trends RSS/CSV, X opcional, consultas fundamentadas, prompts versionados y presupuestos. Cierre: unidades separadas, citas guardadas, scoring independiente de IA.
6. **Telegram y alertas:** pairing temporal, chats privados, comandos documentados, preguntas libres, seguir/descartar, silencios, cooldown, outbox. Cierre: alerta y consulta reales; usuarios desconocidos sin acceso.
7. **Operación y piloto:** instalación, backup/restore, retención, mantenimiento, observabilidad, ARM64 y piloto editorial. Cierre: restauración y 24 h en Pi compartida dentro de objetivos medidos.

Cada entrega incluye backend, interfaz utilizable, pruebas y documentación. Estados: TODO, IN_PROGRESS, BLOCKED_EXTERNAL, DONE_VERIFIED.

Interfaz: navegación editorial/administrativa del PRD; carga, vacío, error y degradación. Gráficos con período, muestra y fecha. Google Trends RSS con CSV alternativo; Google News no cuenta como otro medio independiente.

IA: Responses API, Pydantic y Structured Outputs; gestionar rechazo/respuesta incompleta. Verificar citas contra contexto y renderizar cifras desde backend. Estructura válida no garantiza veracidad.

Telegram: long polling, receptor único, cursor persistido; consultas costosas mediante jobs.

## 4. Datos, contratos y controles

Adoptar entidades y `/api/v1` de los documentos originales. Completar observaciones de captura, sesiones, versiones completas de configuración, pairing y reservas de presupuesto; `ingested_at`, procedencia, medio original y relaciones entre acontecimientos.

Una asignación activa de evento por documento; conservar reasignaciones. Endpoints para probar fuentes, actualizar, importar/exportar, cobertura propia, usuarios y Markdown. Trabajos largos devuelven ID consultable. Métricas incluyen unidad, ventana, muestra, frescura, componentes, limitaciones y versiones.

Seguridad: Argon2id, sesiones revocables, autorización backend, CSRF, escape HTML, SSRF por redirección, límite de descarga. Secretos cifrados con clave externa a SQLite; nunca devueltos ni registrados. Reserva presupuestaria transaccional antes de IA, conciliación posterior. Modelos/tarifas configurables; configuración inválida bloquea IA.

Instalación: comprobar entorno → configurar almacenamiento/secretos → migrar → crear administrador → iniciar → comprobar salud. Backup previo a actualización y recuperación documentada.

## 5. Pruebas y aceptación

- Unitarias: deduplicación, independencia, ventanas, scoring, reglas, permisos, silencios.
- Integración: SQLite real, migraciones, concurrencia, leases vencidos, outbox, presupuestos, 401/429/timeout.
- E2E navegador: onboarding, fuente, evento, comparación, configuración, decisión y exportación.
- Seguridad: SSRF, XSS, CSRF, escalamiento de roles, secretos y prompt injection.
- Corpus editorial: 150–200 documentos etiquetados; precisión pairwise ≥0,90 y recall ≥0,80; separar calibración/evaluación.
- QA-01 a QA-20 de `09_QA_OPERACIONES.md` con evidencia real y bloqueos externos explícitos.
- Administrador y dos editores completan recorrido sin tocar SQLite; cinco eventos multifuente, uno con cinco fuentes; brecha comprobable y explicación con links.
- Presupuesto agotado, X ausente y Telegram caído degradan correctamente. Reinicio conserva datos; restore produce instancia utilizable.
- Pi: dashboard p95 <1,5 s / 10.000 documentos; memoria ≤1,5 GB; 95% feeds sanos dentro de 15 min; 95% alertas válidas <2 min con Telegram disponible.

Defaults: un medio; español argentino; UTC/ART; agenda propia RSS/manual; 90 días de retención; tres descargas y una llamada IA simultáneas; USD 1/día y USD 20/mes configurables.

Fuera: autopublicación, CMS, clips, transcripción, multitenancy y billing. Medio, fuentes autorizadas, credenciales OpenAI/Telegram, Pi y destino externo de backups requeridos para aceptación final. Su ausencia no bloquea desarrollo local, pero impide declarar piloto terminado. X sin acceso no bloquea entrega.

## Referencias oficiales verificadas al planificar

- https://support.google.com/trends/answer/3076011?hl=es
- https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses
- https://core.telegram.org/bots/api#getupdates


## Actualización de ejecución — acceso público y configuración

Destino confirmado por el usuario: `https://mp.diegodella.ar`. Núcleo preparado para
configurar y probar; el plan completo continúa abierto. Alta inicial web con código de
un solo uso, diagnóstico y pausa efectiva de trabajos pendientes implementados.
Validación actual: 28 tests, Ruff/mypy, E2E general, readiness real de web/worker y
configuración Cloudflare. No se activó DNS/túnel/systemd: `/etc` queda fuera del sandbox.

Referencia de continuación: [Configurar y probar](agenda-radar/docs/CONFIGURAR_Y_PROBAR.md).
Evidencia, pendientes de alcance y aceptación editorial: [STATUS](agenda-radar/STATUS.md).


## Ejecución ampliada — 15 de octubre de 2026

- Confirmado por el usuario: medios/RSS/redes/proveedores se cargarán en Administración.
- Administrador creado: diego@diegodella.ar; contraseña privada local, cambio y revocación de sesiones.
- Implementadas alertas especializadas, incidencias administrativas, evidencia acumulada,
  descarga de backups y corpus fijo para pruebas de prompts de respuesta.
- Build Docker limpio y suite completa dentro del contenedor; backup/restore real aislado aprobado.
- DNS y túnel independiente creados. Web/worker/túnel activos; HTTPS readiness y E2E público aprobados.
- Se añade redirección HTTP→HTTPS/HSTS antes del cierre final.
- La observación de disponibilidad de 24 horas queda automatizada; no se declara concluida antes de transcurrir.
- Corpus editorial, proveedores reales y copia externa dependen de configuración/validación del usuario.

Ver estado vigente y evidencias en agenda-radar/STATUS.md y guía de acceso en
agenda-radar/docs/CONFIGURAR_Y_PROBAR.md. No usar la propuesta anterior de modificar el túnel compartido.

Cierre de despliegue: imagen `pilot-762a80ce0e77`, 39 tests Docker aprobados; HTTPS/HSTS y
redirección HTTP verificadas. E2E público completo aprobado tras ajustar keepalive del túnel.
El ensayo final de 24 horas se inicia después de ese ajuste y conserva resultados en artifacts/soak.
