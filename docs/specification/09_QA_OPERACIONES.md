# Calidad, seguridad, operaciones y criterios de aceptación

## 1. Estructura de tests
- **Unitarios:** canonicalización, scoring, grupos independientes, interpretación de reglas, umbrales, ventanas, parsing, CSRF y RBAC.
- **Integración:** SQLite file real, migraciones, workers concurrentes, fixture RSS/Trends, OpenAI falso con JSON estructurado, Telegram falso y cuota 429.
- **E2E:** administración -> fuente -> evento -> agenda -> alerta -> pregunta -> decisión -> backup/restore.
- **Contrato:** esquema OpenAPI, versión de prompts, formato de respuesta del bot, idempotencia jobs.
- **Seguridad:** IP privadas/SSRF, redirects, XSS de titulares, prompt injection en RSS, cookies, secretos en logs, acceso Telegram no autorizado.
- **Hardware:** contenedor ARM64, cold boot, reinicios por caída de energía simulada, 24 h soak en Pi con otros servicios, estado térmico y RAM.

## 2. Matriz de aceptación por escenarios
| ID | Prueba | Resultado esperado |
|---|---|---|
| QA-01 | Instalar en Pi 5 de prueba sin Supabase | los 2 servicios arrancan, health ok |
| QA-02 | Cargar 20 RSS con 2 corruptos | 18 fuentes visibles, 2 degradadas y logs |
| QA-03 | Misma nota en 3 URLs | 3 documentos si fuentes distintas, 1 acontecimiento, 3 menciones |
| QA-04 | Sindicación en 4 medios del mismo grupo | conteo independiente 1 |
| QA-05 | 2 noticias con mismo nombre propio y hechos distintos | cluster separados o revisión humana clara |
| QA-06 | Fuente propia sin actualizar | brecha no confiable y alerta suprimida |
| QA-07 | Reconfigurar peso medio A | preview + versionado + rollback exacto |
| QA-08 | Google Trends RSS disponible | feed real parseado con atribución |
| QA-09 | X sin acceso | app continúa y vista indica «no disponible» |
| QA-10 | Telegram ID desconocido | denegación sin filtrar contenido |
| QA-11 | Alerta disparada 3 veces en 20 min | 1 aviso y historial de supresión |
| QA-12 | Pregunta sobre evento existente | respuestas con IDs/URLs presentes en DB |
| QA-13 | Pregunta sobre evento ausente | incertidumbre reconocida, sin invención |
| QA-14 | OpenAI 429 / presupuesto alcanzado | se bloquea IA, tablero/scoring disponibles |
| QA-15 | Caída/restart worker mientras ingiere | no pierde documento ni duplica job |
| QA-16 | Backup online y restaurar otra DB | checksum + auditoría + data íntegra |
| QA-17 | RSS con prompt injection textual | contenido ignorado como instrucción |
| QA-18 | URL RSS apunta a 127.0.0.1 o 169.254.x.x | rechazo y registro de seguridad |
| QA-19 | Fuentes usan distintas TZ | serie temporal coherente en UTC/ART |
| QA-20 | API con editor intenta cambiar prompt sistema | 403 y auditoría |

## 3. Objetivos de performance (no verificados todavía)
- Dashboard 24h con 30 fuentes y 10.000 documentos: respuesta p95 <1,5 s en LAN.
- Memoria Agenda Radar <1,5 GB RSS (excluyendo SO y otros servicios); medir en Pi real, ajustar si el hardware disponible exige menos.
- Ingestión de 95% RSS saludables en <15 min de ventana programada.
- Máximo 1 extracción costosa simultánea y 3 descargas paralelas al iniciar.
- 95% de alertas válidas entregadas <2 min después de completar scoring, si Telegram está disponible.
- Tras reinicio, DB íntegra y worker retoma de cursor.

## 4. Playbook operacional
**Daily:** revisar fuentes degradadas, cuota de OpenAI, tamaño DB/disco, temperatura, alertas fallidas, backlogs y latencia.

**Backup:** snapshot consistente diario de SQLite con API backup, cifrado opcional de archivo, copia fuera de la Raspberry/SSD, retención 7 diarios + 4 semanales; restore drill semanal en destino separado. No copiar `.db` abierto a mano ignorando WAL. Resguardar secretos cifrados por separado y documentar recuperación de clave.

**Pausas:** toggle RUN global, toggle IA, toggle Telegram, toggle de conector y modo lectura; no detener todo por una sola API caída.

**Reprocesado:** `jobs` fallidos -> DLQ con motivo -> replay con `idempotency_key`; no ocultar errores sistemáticos. Admin recibe aviso resumido si más del 20% de fuentes falla.

**Versiones:** migraciones semánticas, rollback probado, backups previos, changelog; no reemplazar DB por nueva en deploy.

## 5. Requisitos legales/editoriales
Datos de medios con links y atribución. Respetar robots, términos y derechos de autor; almacenar lo mínimo posible. No transcribir/capturar contenidos privados sin licencia. Contar con mecanismos de exportar y borrar datos, política de retención y registro del fundamento de recolección. Transparencia frente al editor acerca de qué se envía a OpenAI y qué se comunica por Telegram. Revisar contratos antes de venderlo a terceros.

## 6. Go/No-go de piloto
**GO** solo si QA-01 a QA-20 completados según disponibilidad real y decisiones `BLOCKED_EXTERNAL` explícitas sin engañar al usuario; sin fallas de seguridad críticas; backups restaurados; fuentes/tendencias etiquetadas; IA acotada por budget; bot restringido. Si no hay X pago, piloto puede proceder mostrando disponibilidad «sin X». Si no hay feed Trends operativo, continuar con CSV manual, explicar limitación.

## 7. Checklist de entrega
`README`, `.env.example`, `compose.yaml`, migraciones, fixtures, test report, health endpoints, manual admin, matriz legal por fuente, copia/restore, 2 usuarios de prueba sin claves por defecto, presupuesto mensual, lista de integraciones habilitadas y pendientes.
