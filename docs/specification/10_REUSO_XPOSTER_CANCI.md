# Reutilización de XPoster y Canci/DESK — auditoría de diseño
**Repositorios privados revisados:** `diegodella1/xposter` y `diegodella1/canci`, rama `main`, 14/10/2026. Esta es una lectura de archivos README y código puntual, **no** una ejecución ni auditoría exhaustiva de dependencias/versiones, y no garantiza que cada componente funcione en tu Pi con la carga actual.

## 1. Hallazgos contrastados con código
- `xposter/README.md`: conectores RSS, web, cuentas/listas X, medios, reglas, entidades, agenda, RBAC, evidencia y SQLite local. Stack productivo actual usa Next.js, FastAPI, workers y PostgreSQL aislado: **no copiar todo** para un nuevo appliance liviano.
- `xposter/services/api/src/xposter/services/scoring.py`: calcula `novelty`, `relevance`, `source_reliability`, `confidence`, `urgency`, `diversity`, `risk_penalty`, aplicados a decisiones de **borradores**. No es el score de atención observada que necesitamos.
- `xposter/services/api/src/xposter/services/pipeline.py`: si detecta evento con el mismo `fingerprint`, devuelve antes de guardar otro evento. Esto es correcto para evitar borradores duplicados, pero insuficiente para **contar cobertura por mención y por fuente**.
- `canci/README.md`: DESK se plantea expresamente como instalación **single-tenant** y aprendizaje de decisiones del editor; incluye fuentes X/RSS/web, YouTube/radio, criterios, redacción y versionado de historial.
- `canci/PRD_PRODUCTION_READY.md`: sus gates de seguridad, autorización, backups, presupuesto de IA y tests son buena guía; el documento expresa que el software está **preproducción**, así que no presumir que todo está listo para replicar.

## 2. Matriz de reuso
| Componente | Origen | Estrategia | Cambio necesario |
|---|---|---|---|
| Canonicalización RSS/web | XPoster | portar función/test | separar documento de acontecimiento |
| X oficial con token de lectura | XPoster | adaptador opcional | entitlements, costos, salud, ventanas |
| Entidades y taxonomía | XPoster | adaptar | persistencia SQLite propia |
| Editorial rules y horarios | XPoster | extraer dominio | pesos aplicables a agendas, no borradores |
| Evidence/claim grounding | Ambos | preservar principios y utilidades | enlaces por mención + verificación post-LLM |
| Decisiones editoriales + feedback | Canci/DESK | adaptar esquema | seguir/descartar/no cubrir, no solo copy de tweet |
| Presupuestos IA y auditoría | Canci/DESK | reusar diseño/tests | integrarlo al runtime liviano |
| Next.js/frontend completo | Ambos | **no portar directo** | HTML/HTMX por límites de hardware |
| PostgreSQL/pgvector | XPoster en producción | **no portar** en MVP | SQLite JSON1/FTS5 y evaluación vectorial opcional |
| Transcripción de vivos/clip | Ambos | aplazar | M2 requiere autorización + CPU/datos |
| Publicación/redacción de X | Ambos | aplazar | producto de criterio, no publish bot |
| Scoring de borradores | XPoster | no usar como saliencia | score nuevo y explicable |

## 3. Estrategia recomendada
1. Crear repo nuevo, sin fork ciego ni copiar secretos/config producción.
2. Extraer módulos pequeños, sin dependencias de PostgreSQL/Next/worker cloud.
3. Portar fixtures/tests primero. Implementar `Document -> EventMention -> Event` antes de score.
4. Construir score de agendas desde cero; incorporar reglas de Canci como patrón de UX/versionado, no como «modelo entrenado».
5. No leer ni modificar bases productivas de XPoster/Canci durante desarrollo. Para importar historial, exportador **solo lectura**, con anonimización y validación de derechos.
6. Confirmar licencia/propiedad de los repos al distribuir software comercial; que estén bajo tu usuario no sustituye revisar dependencias de terceros.

## 4. Criterio de reuso satisfactorio
Cada módulo copiado queda cubierto por test de regresión y tiene frontera de API clara. El nuevo producto debe arrancar sin servicios anteriores conectados; cualquier integración posterior es configurable y removible.
