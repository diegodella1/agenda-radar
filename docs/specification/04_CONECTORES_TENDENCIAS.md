# Conectores y tendencias — matriz de factibilidad
**Principio:** no basar el éxito del MVP en extracción frágil de plataformas cerradas.

## 1. Contrato de conector
`validate(config)`, `poll(cursor,since,limit)`, `normalize(raw)->Document|TrendSample`, `health()`, `rate_limit_info()`. Campos obligatorios: plataforma, método de captura, permiso, timestamp, país, métrica/unidad, enlace original. Cada fuente posee activación, intervalo, timeout, prioridad, grupo propietario, etiquetas, presupuesto y manejo de errores. Reintentos con backoff/jitter; `ETag`, `If-Modified-Since` si se soporta.

## 2. Matriz
| Fuente | Camino inicial | Estado | Riesgo / condición |
|---|---|---|---|
| RSS/Atom propios y medios de referencia | `feedparser` + HTTP | P0 recomendado | permiso/atribución por medio; respetar términos |
| Páginas web públicas | primero descubrir feed; fallback extractor allowlisted | P0 condicionado | robots/ToS, SSRF, JS dinámico, límite 2 MB |
| Google News | feeds RSS de secciones/búsquedas si funcionan; URLs parametrizables | P0 condicionado | servicio no es API contractual con SLA; redirecciones y estructura cambiante |
| Google Trends — Trending Now | exportación **RSS** oficial desde interfaz; CSV manual como backup | P0 recomendado | datos de interés relativo, no audiencia total; atribuir a Google |
| Google Trends API | acceso alpha solo si la cuenta es aceptada | P2 / opt-in | no asumir acceso general |
| X listas/cuentas | X API v2 oficial cuando haya plan/credenciales | P1 condicionado | costos/cuotas; actividad visible depende de plan |
| X Trends | endpoint de Trends oficial sujeto a disponibilidad y plan | P1 condicionado | no disponible sin acceso y presupuesto; no simular |
| X sesión logueada/scraping | **No requerido / no por defecto** | Fuera de MVP | sesiones privadas, anti-bot, términos, alto mantenimiento; nunca recolectar cookies |
| YouTube (externo) | canal RSS y metadata/analítica permitida | P1 | historial y métricas requieren permisos/capacidad API |
| Webhooks/manual | URL, CSV, JSON importado por administrador | P0 | indicar origen manual y frescura |

**Punto clave:** «abrir la cuenta X logueada en un navegador» no convierte su contenido en una fuente contractual de datos. No diseñar login automático, extracción de cookies, CAPTCHA bypass o automatización de una sesión personal como dependencia crítica. El panel podrá mostrar enlaces y permitir importación manual etiquetada cuando falte API. Un conector de navegador asistido solo se evaluaría con autorización y revisión legal específicas; nunca como promesa de cobertura estable.

## 3. Google Trends
La ayuda oficial confirma que **Trending Now permite exportar RSS y CSV**. Flujo propuesto: administrador elige Argentina / ventana / categoría -> pega o configura URL del feed RSS exportado -> validar esquema -> ingestión periódica -> `trend_samples` con `provider=google_trends`, geografía, etiqueta, inicio y volumen si el feed lo incluye. Los datos expresan aumento de interés de búsqueda, no número de artículos, no relevancia periodística.

La API de Google Trends documentada para 2026 está en programa alpha por solicitud, así que no se requiere para aprobar el MVP. Si deja de funcionar RSS, pasar a importación de CSV sin romper scoring de referencias. Mostrar aviso de freshness.

## 4. Google News
Se ofrece como señal editorial pública secundaria. Preferir RSS de resultados o secciones que el usuario configure, verificar que se entrega efectivamente en región/idioma y almacenar URL original y fuente de publicación. Google News reagrupa noticias que también pueden estar en feeds propios; evitar contarlas como «otro medio independiente». Deduplicar por canonicalización. No extrapolar su ranking como audiencia.

## 5. X
Los docs oficiales X API v2 incluyen posts, listas y trends, pero endpoints concretos, métricas, condiciones comerciales y cuotas pueden variar: **verificar en la cuenta del cliente antes de prometer una función**. Implementar adaptador desactivable que informa `no_credentials`, `quota_exhausted`, `not_entitled`, `healthy`. Sin token, el sistema sigue operativo con fuentes RSS/web/Trends y reporta X como no medido.

Algunos contenidos de X son reproducciones del mismo link: ponderar la repetición social distinta a la cobertura periodística original. Normalizar métricas por canal y disponibilidad. Guardar IDs/URLs/metadatos de acuerdo con condiciones de proveedor; retención/redifusión con revisión legal.

## 6. Página de administración de conectores
Por cada fuente: nombre, tipo, URL/id, referencia/propia/pública, grupo editorial, prioridad 0..100, confiabilidad declarada, cadencia, país, tags, último fetch, antigüedad, cantidad de elementos, costo aproximado, TOS/legal gate, activar/pausar/forzar prueba. Debe existir `Test source` sin guardar y `Preview 10 items`.

Los conectores deben conservar tres relojes: `published_at` (lo que afirma la fuente), `observed_at` (cuándo lo vimos) y `ingested_at` (cuándo quedó en DB); la «primera fuente» siempre significa la primera **observada por nuestro universo**.

## 7. Detección de errores y degradación
- Feed vacío 1 hora: degraded, no señal de ausencia.
- 429/quota: stop hasta reset y alerta admin sin reintentos agresivos.
- 403/401: credencial/restricción; pausar.
- `robots`/ToS prohíben: rechazar activación.
- Loop URLs o variantes: canonical host + path + parámetros allowlist + hashes.
- Dos fuentes con mismo propietario: mismo `independence_group`.
- Etiqueta de tendencia inesperada/no relacionada: conservar como señal pública, no fusionar automáticamente con evento no probado.

## 8. Contratos de licencia y privacidad
Citar URLs, almacenar extracto permitido y metadatos; no archivar notas completas ni audios sin autorización. Documentar origen, base legal y retención. El panel debe poder eliminar fuente y datos asociados según política. Identidades de lectores/autores y comentarios sociales merecen minimización.
