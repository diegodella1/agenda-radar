# PRD — Agenda Radar
**ID:** AR-PRD-001 · **Versión:** 0.1 · **Responsable:** Product owner · **Fecha:** 2026-10-14

## 1. Problema y tesis
La mesa editorial observa decenas de sitios, periodistas y plataformas, pero no dispone de una medición reproducible de **qué cubren los medios elegidos, qué cubrimos nosotros y qué crece entre el público**. La saturación informativa induce decisiones por intuición, notoriedad de una fuente o simple cantidad de publicaciones. El producto no debe «elegir noticias por el editor»; debe aportar una comparación verificable y recomendaciones controlables.

**Hipótesis:** la combinación de fuentes seleccionadas, cronología por acontecimiento, normalización de relevancia, agenda propia y notificaciones oportunas permite descubrir oportunidades de cobertura útiles sin aumentar la carga editorial.

**No prometemos:** una medición universal de «importancia objetiva», acceso garantizado a datos de X, conocimiento de la audiencia sin integrar analítica propia, ni producción/publicación automática.

## 2. Público y roles
- **Superadministrador de instalación:** operación y seguridad global, credenciales de proveedores, límites/costos, motores, versiones de prompts, mantenimiento, auditoría.
- **Administrador del medio:** criterios editoriales, fuentes, temas, entidades, pesos, agenda propia, umbrales, canales y destinatarios de alertas.
- **Editor/a:** consume tablero; crea y corrige acontecimientos; acepta/descarta recomendaciones; registra decisiones; consulta al asistente.
- **Analista:** compara cobertura y exporta informes, sin alterar reglas críticas.
- **Lector/a:** acceso de solo lectura a vistas habilitadas.

Instalación inicial: **un medio por despliegue**. La existencia de superadministrador no implica multiempresa. Más adelante se puede soportar múltiples medios sobre infraestructura distinta; evitar complejidad multitenant prematura.

## 3. Jobs to be done
1. «Quiero saber qué temas crecieron desde la última reunión de pauta, y quién los instaló».
2. «Quiero comparar mis prioridades con las de estos 12 medios sin tratar a cada uno como equivalente».
3. «Quiero que me muestres qué temas no publicamos y por qué el sistema cree que importan».
4. «Quiero entender en qué plataformas surge un tema y si **a mi medio** le convendría producir una nota, tweet, clip o video».
5. «Quiero que Telegram me avise solamente de cambios relevantes y que me conteste con enlaces».
6. «Quiero que la infraestructura, los datos, las reglas y las decisiones editoriales sigan bajo nuestro control».

## 4. Experiencias críticas (MVP)
**F1: onboarding administrativo.** En la primera visita se crea admin; se carga clave OpenAI en backend; se selecciona zona horaria; se crean fuentes de referencia y fuente propia; se definen pesos con plantilla editable; se prueba Telegram. Hay modo sin OpenAI: ingestión, conteo y scoring determinista siguen funcionando.

**F2: tablero de agenda.** Inicio con período 1 h / 6 h / 24 h / 72 h / 7 d, filtros por tema, fuente, canal y geografía. Mostrar acontecimientos ordenados por *saliencia observada*, *prioridad editorial* y *brecha*; variación respecto a ventana previa, número de medios independientes, antigüedad de dato, cobertura propia y confianza del agrupamiento. Debe poderse abrir cada acontecimiento y ver **todas las menciones originales**.

**F3: ficha de acontecimiento.** Línea de tiempo, primera fuente observada (no afirmar primera publicación mundial), URLs, titulares, tratamiento/tópicos, variantes/posibles coincidencias, score explicado, fuentes faltantes, incertidumbre y acciones «seguir», «descartar», «marcar cubierto», «solicitar análisis». Un editor puede dividir o fusionar acontecimientos con auditoría y recalcular.

**F4: comparación.** Vista propia / referencias / búsquedas públicas. Diferencia en puntos de **distribución de atención** dentro del conjunto monitoreado; nunca comparar directamente unidades incompatibles como búsquedas, tweets y notas. Permitir matrices fuente×acontecimiento y mapa de cambios.

**F5: tendencias por canal.** Comparar variación interna de cada plataforma (no magnitudes absolutas entre plataformas); mostrar estado de conector, cobertura muestral, retraso y fuente del indicador. «Aceleración en X» se muestra solo si el acceso al proveedor realmente permite medirla.

**F6: Telegram.** Alerta preventiva con razón, enlaces, canal afectado, disponibilidad de datos y botón/link hacia ficha. Comandos `/agenda`, `/brechas`, `/tema <consulta>`, `/fuentes`, `/ayuda` y consultas libres acotadas a datos guardados.

**F7: reglas y prompts versionados.** Ajustes con *preview* sobre datos reales anteriores, activar/publicar, rollback y auditoría. Separar puntuación determinista de explicaciones generadas por IA.

## 5. Funcionalidades y prioridad
| ID | Necesidad verificable | MVP | Después |
|---|---|---:|---|
| P-01 | RSS/Atom y Google News RSS elegibles | Sí | — |
| P-02 | Web público permitido, fetch controlado, canonical URL | Sí | — |
| P-03 | Fuentes X con adaptador oficial y modo sin credenciales | Condicional | cuotas específicas y trends |
| P-04 | Google Trends Trending Now RSS, importación CSV | Sí | API alpha si acceso |
| P-05 | Agrupación evento/menciones con revisión manual | Sí | semántica más robusta |
| P-06 | Entidades, temas, vocabulario y regiones | Sí | taxonomías avanzadas |
| P-07 | Tres agendas, historial 1/6/24/72 h | Sí | benchmarking largo plazo |
| P-08 | Saliencia, prioridad propia, brecha, confianza | Sí | calibración longitudinal |
| P-09 | Pesos por fuente, canal, tema y horario | Sí | escenarios comparativos |
| P-10 | Dashboard, tablas, líneas y drill-down | Sí | cohortes, reportes especiales |
| P-11 | Telegram saliente/entrante con lista permitida | Sí | grupos/equipos |
| P-12 | OpenAI estructurado para interpretación + QA | Sí | aprendizaje asistido |
| P-13 | Roles, auditoría, backups, límites de costos | Sí | SSO empresarial |
| P-14 | Lectura de analytics propios de YouTube/X | No | M1, APIs autorizadas |
| P-15 | Clips automáticos y publicación/redacción CMS | No | M2 con aprobación |
| P-16 | Radios, TV y transcripción continua | No | M2, hardware/costo aparte |

## 6. Reglas funcionales transversales
- Una publicación puede pertenecer a un acontecimiento; el acontecimiento contiene N publicaciones. Deduplicar **la misma publicación** por URL/ID/hash, **no borrar la cobertura repetida de medios distintos**.
- Cada dato registra `observed_at`, `published_at` (si existe), `ingested_at`, fuente, método de captura, legalidad/permiso y estado de frescura.
- Una alerta no se envía por «ausencia de cobertura propia» si el conector propio está caído o tiene cobertura incompleta.
- El sistema distingue *señal externa*, *decisión editorial* y *recomendación*. Las recomendaciones no actúan por sí solas.
- La configuración de tono afecta los resúmenes y las explicaciones; **no cambia silenciosamente el dato numérico observado**.
- Sin acceso válido a una red social, el dashboard indica «no disponible» y no simula tendencias.

## 7. Pantallas y navegación
**Trabajo editorial:** `Resumen`, `Agenda comparada`, `Acontecimientos`, `Tendencias`, `Alertas`, `Historial/decisiones`.

**Administración de medio:** `Fuentes`, `Referencias`, `Criterios`, `Pesos`, `Agenda propia`, `Reglas`, `Alertas`, `Equipo`, `Calidad de datos`.

**Administración global:** `Instalación`, `Proveedores y secretos`, `Modelos y presupuestos`, `Prompts`, `Conectores`, `Jobs`, `Auditoría`, `Backups`, `Actualizaciones`.

## 8. Métricas
**Producto:** uso semanal por editor; brechas revisadas; recomendaciones aceptadas/descartadas; decisiones registradas; tiempo desde primera mención capturada hasta alerta; tasa de falsas alarmas y fatiga de notificaciones.

**Calidad:** precisión de agrupación (pairwise precision ≥0,90 en corpus etiquetado), recall de agrupación ≥0,80 (objetivos piloto); evidencia válida en respuestas ≥99%; al menos 95% de fichas con fuente y hora; tasas por conector, duplicados y datos faltantes.

**Operación:** p95 API dashboard <1,5 s con corpus objetivo en LAN; 95% de feeds saludables actualizados dentro de 15 min; alertas emitidas <2 min desde el cálculo relevante; sin pérdida en reinicios. Son targets, NO resultados medidos.

## 9. Casos extremos
Ruptura de RSS; titulares ambiguos; cronología de eventos que se prolongan días; mismo artículo sindicado a 12 sitios; contenido corregido; hechos contradictorios; fuentes copiándose entre sí; manipulación coordinada; tema importante pero pequeño; evento publicado primero en fuente que no monitoreamos; credenciales caducadas; API sin presupuesto; reinicio de Raspi; DB ocupada por otro worker; horarios mixtos UTC/ART.

## 10. Fuera de alcance y restricciones
No publicación automática, no scraping de sesiones privadas, no bypass de paywalls ni CAPTCHA, no compra/venta de datos privados, no replica íntegra de contenidos sin derecho. No «fine-tuning» automático del modelo por notas o estilo en el MVP: el ajuste editorial se logra por reglas, ejemplos seleccionados, recuperación y decisiones de los editores.

## 11. Criterio de éxito del MVP
Un editor carga 20 feeds, define 3 temas y 5 medios de referencia, observa al menos 5 eventos con múltiples menciones reales, comprueba una brecha con URLs, recibe una alerta real por Telegram, pregunta por qué ocurrió y obtiene una respuesta fundamentada. Tras reiniciar la Pi, conserva fuentes, menciones, scores, reglas y decisiones. Completar con integraciones reales y QA de `09_QA_OPERACIONES.md`.
