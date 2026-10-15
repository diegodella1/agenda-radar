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
