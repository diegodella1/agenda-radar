# Motor de relevancia, agendas, brechas y detección de cambios
**Principio:** medir *atención observada* y *prioridad del medio* por separado; la «brecha» es el cruce, no una verdad editorial.

## 1. Vocabulario medible
- **Documento / publicación:** nota, tweet, post, video o titular observado.
- **Acontecimiento:** un hecho específico, fechado, corroborable, agrupando N publicaciones.
- **Tema:** categoría estable (economía, elecciones, deportes).
- **Mención independiente:** publicación de grupo editorial diferente; la distribución sindicada se identifica.
- **Saliencia observada:** parte de la atención en fuentes de referencia dentro de ventana y muestra configuradas.
- **Prioridad editorial:** preferencia explícita del medio por temas, personas y criterios.
- **Agenda propia:** publicaciones/decisiones editoriales del medio (y faltantes de cobertura cuando conector está sano).
- **Señal pública:** búsquedas o conversación social; **no está en la misma unidad** que notas periodísticas.

## 2. Agrupamiento de acontecimientos
**A) Deduplicar items** por `(source_id, external_id)` o canonical URL/hash. **B) Agrupar por hecho** comparando título, tokens, entidades, tiempo y evidencia; top candidatos con FTS5; regla semántica OpenAI únicamente en pares ambiguos. **C) Mantener todas las menciones**, fechas y fuente. **D) Proveer split/merge manual** con auditoría.

No fusionar noticias distintas sobre «la economía» solo porque comparten tema. Separar `evento principal` y `actualización` cuando los hechos nuevos merezcan entidad distinta. Historias de muchos días pueden tener `parent_event_id`.

## 3. Algoritmo determinista v0.1
Para evento `e`, ventana `w`, fuente independiente `s` y momento `t`:

1. `m_s,e,w = min(1, recency_decay(max_mention_in_window))`: presencia de fuente por acontecimiento, **cap por fuente**. Si el mismo grupo editorial tiene varias fuentes, agruparlas y aplicar un tope.
2. `f_s = normalized_editor_weight(s)` entre 0 y 1; `q_s = source_quality_health_factor` (1 sano, desconocido si caído; excluido de denominador disponible, no interpretado como 0 de interés).
3. `evidence_e = Σ_{s disponibles} f_s * m_s,e,w * q_s`.
4. `attention_share_e = 100 * evidence_e / Σ_{eventos activos} evidence_event` **dentro de una selección y ventana fijas**. Registrar muestra, algoritmos y denominador. No usar porcentajes si no hay muestra mínima.
5. `velocity_e = robust_zscore(count_unique_sources_e últimas 2h vs baseline franja horaria / días comparables)`; usar heurística alternativa si historial <7 días y marcar confianza menor.
6. `editorial_affinity_e = clamp(0,1, topic_priority * entity_priority * geo_priority * schedule_priority)` con defaults 1; reportar cada multiplicador.
7. `own_share_e` se calcula sobre contenidos propios observados **o decisiones editoriales explícitas**. Si no hay cobertura propia confiable, `own_share=null`.
8. `gap_pp = attention_share_e - own_share_e` cuando ambas son distribuciones válidas de la misma cesta de acontecimientos; calcular sobre unión de eventos y normalizar ambos lados para sumar 100. Guardar `sample_quality`.

**Advertencia:** este `gap_pp` mide diferencia de atención, no porcentaje de importancia ni porcentaje de cobertura del mundo. Si el propio medio cubre menos temas, normalizar shares puede generar distorsiones: mostrar también indicadores absolutos `own_covered` y `share_of_references_covered`.

**Orden de recomendaciones:** regla verificable `candidate_priority = 0.35*normalized_gap + 0.25*editorial_affinity + 0.20*velocity + 0.20*source_diversity`; solo para ranking UI, nunca presentado como métrica empírica calibrada. Peso editable y límites 0..1. Si datos incompletos, bajar confianza y suprimir alerta en lugar de imputar ceros.

## 4. Agenda pública y canales
Google Trends RSS genera `search_trend_active`, `search_growth` o `volume_bucket` si está disponible; X puede generar `x_post_velocity`, `distinct_accounts`, `engagement` solo con permisos/entitlements. Para cada plataforma, estandarizar **dentro de esa plataforma** y mostrar en panel adyacente como señales complementarias. No sumar «1 búsqueda + 1 tweet + 1 artículo».

**Recomendación de canal** requiere dos evidencias diferentes: crecimiento del tema en ese canal y/o rendimiento histórico del contenido propio en ese canal. Si la segunda no existe, mostrar: «Está creciendo en X; todavía no tenemos datos propios suficientes para recomendar publicar allí».

## 5. Reglas de alerta — v0.1
```yaml
id: editorial_gap
when:
  gap_pp: {gte: 15}
  independent_source_count: {gte: 3}
  cluster_confidence: {gte: 0.70}
  own_source_freshness_minutes: {lte: 30}
  reference_healthy_ratio: {gte: 0.80}
actions:
  write_alert: true
  notify_telegram: true
  severity: medium
cooldown_minutes: 90
rearm_only_if_score_change: 10
```

Otras alertas: `emerging_event` (fuentes nuevas + velocidad), `priority_without_coverage`, `agenda_shift`, `source_health_failure` (solo admin), `high_impact_update` (evidencia nueva sustancial). Dedup key `rule_id:event_id:window:config_version`, supresión configurable y silencio nocturno.

## 6. Explicabilidad y confianza
Cada score devuelve `value`, `unit`, `window`, `algorithm_version`, `config_version`, `sources_used`, `sources_unavailable`, `components`, `reason`, `caveats`. Confianza combina calidad del parseo, precisión cluster, cantidad y diversidad de fuentes y salud del monitoreo. Una nota repetida por 15 dominios de un mismo propietario no debe generar una falsa certeza de 15 medios independientes.

## 7. Evals y sesgos
Construir corpus inicial de 150–200 documentos etiquetados manualmente, al menos 30–50 acontecimientos y 4 casos adversariales (mismo nombre distintos hechos, hechos con versiones, cobertura sindicada, noticia local poco popular). Evaluar pairwise cluster, falsos positivos de gap, tiempo de alerta, estabilidad ante cambios de pesos, sensibilidad al ingreso de una fuente dominante. Medir error por tipo de medio (local, nacional, especializado) para evitar sesgo de grandes cabeceras.

## 8. Pruebas con casos sintéticos
1. Cinco RSS del mismo propietario: `independent_source_count` = 1, no 5.
2. Un feed propio falla 2 h: el sistema **no** alerta «no cubrimos», marca dato insuficiente.
3. Se duplica un titular: no duplicar documento, conservar versiones.
4. X no disponible: trends X = `unavailable`; scoring de referencia sigue estable.
5. Google Trends indica aumento sin cobertura periodística: indicar «interés de búsqueda», no generar noticia ficticia.
6. Cambiar peso de un medio muestra diff y nueva versión sin modificar snapshots previos.
