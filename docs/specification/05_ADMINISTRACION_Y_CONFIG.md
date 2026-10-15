# Panel de administración, configuración y gobernanza editorial

## 1. Separación de responsabilidades
**Superadministrador (instalación):** usuarios iniciales, proveedor OpenAI, Telegram token, secretos cifrados, selector de modelos, presupuesto y límites, cadencia global, estado de workers, replays, backups, políticas de retención, prompts del sistema, actualizaciones y auditoría.

**Administrador editorial (medio):** fuentes, grupos de medios, temas, entidades, pesos, canales, criterios, horarios, prompt de tono editorial (sin poder eliminar controles globales), alertas, integrantes del equipo, configuración de agenda propia y correcciones de agrupamiento.

**Editor:** consulta, decisiones sobre fichas, seguir/descartar, marcar cubierto, corrección de acontecimiento y solicitar briefing. Sin cambios de secretos ni límites globales.

## 2. Editor de fuentes
Formulario: `nombre`, `tipo`, `URL/ID`, `canal`, `país`, `grupo editorial`, `referencia|propia|pública`, `peso [0,100]`, `frecuencia`, `etiquetas`, `términos que incluir/excluir`, `condiciones de uso comprobadas`, `enabled`. Previsualización antes de guardar, test HTTP/parseo, salud y última descarga. Hacer cambio masivo y CSV import/export de fuentes.

**No confundir fuente con canal:** La Nación es fuente; web es canal. Un canal puede incluir múltiples fuentes; una organización puede tener fuentes en web/X/YouTube. Grupo de independencia se configura aparte.

## 3. Motor de criterios
Los criterios se construyen con: prioridad de temas, figuras, instituciones y geografía; relevancia especial por día/franja horaria; cobertura deseada por sección; exclusiones explícitas; penalizaciones (riesgo/legal/duplicación); reglas duras y blandas. Cada regla lleva `scope`, autor, fecha de vigencia, motivo y estado `draft/tested/active/retired`.

**Tipos de reglas:**
- `hard_exclude` (solo razones explicables, nunca ocultar evidencia original de la base);
- `priority_boost` (multiplicador con límites);
- `require_review` (contenido sensible/controvertido);
- `quiet_hours` (no envía push fuera de ventana salvo alta severidad autorizada);
- `channel_affinity` (cuando existe analítica propia autorizada);
- `independence_cap` (máximo aporte por grupo propietario);
- `notification_threshold` (mínimo cambio y confianza para Telegram).

## 4. Pesos — interfaz y modelo
Se habilita una grilla simple y una vista avanzada. Escalas 0–100 y normalización interna transparente.

```yaml
config_version: 3
reference_sources:
  medio_a: 80
  medio_b: 65
  medio_c: 40
source_groups:
  grupo_editorial_a: {max_share: 0.20}
channels:
  web: 100
  rss: 100        # vehículo de distribución; evita doble cuenta con web
  x: 45
  google_news: 30
  google_trends: 35  # señal pública; no se suma como cobertura periodística
editorial_priorities:
  economia: 1.4
  politica_local: 1.3
  deporte: 0.5
alerts:
  minimum_gap_pp: 15
  minimum_independent_sources: 3
  minimum_confidence: 0.70
  cooldown_minutes: 90
  quiet_hours: ['23:00', '07:00']
```

**Muy importante:** los pesos de canales no se suman indiscriminadamente. RSS y web suelen representar el mismo artículo; Google Trends pertenece a otra dimensión. El panel bloquea configuraciones conceptualmente inválidas y muestra advertencias.

## 5. Editor de prompts
- Propósitos versionados `extract_event`, `disambiguate`, `explain_score`, `answer_telegram`, `format_recommendation`, `daily_brief`.
- Texto del sistema protegido por superadmin; instrucciones editoriales del medio se agregan en un bloque subordinado.
- Campos `template`, `input_schema`, `output_schema`, `model`, `temperature/reasoning si disponible`, `max_tokens`, `context_policy`, `active_version`, `last_tested_at`, `test_result`, `cost_per_test`.
- `Guardar borrador` ≠ `Publicar`; el admin ejecuta tests con corpus fijo, obtiene diff de outputs y estimación de costo, luego publica. Rollback inmediato.
- Nunca sustituir determinísticamente evidencia con un prompt. Documentos de fuentes entran como **datos no confiables**; ignorar instrucciones contenidas en ellos.

## 6. Preview y seguridad de cambios
Todo cambio de pesos muestra re-score sobre las últimas 24 h: eventos suben/bajan, alertas que se dispararían, falsos positivos conocidos y estimación de API. Aprobación explícita activa una nueva versión; conservar snapshot anterior. Para cambios peligrosos, confirmar desde contraseña/sesión reciente. Registrar `who/when/what/before/after/why`.

## 7. UX inicial
Al inicio ofrecer preset `Generalista nacional`, `Local/regional`, `Vertical temático`, y `En blanco`. Los presets solo prellenan valores; no se presentan como recomendaciones infalibles. Añadir pantalla `Calidad de fuentes` con health y cobertura muestral antes del gráfico de agenda.

## 8. Administración de costos
Presupuestos mensual y diario en USD, límites de llamadas por job, alertas 50/80/100%, opción `pausar AI` y `solo análisis determinista`. Los límites operativos se hacen en backend, bajo mutex/transacción; no depender de la buena voluntad del modelo. Historial por operación, tokens in/out, estimado y proveedor. Una clave puede verificarse con prueba pequeña sin mostrarla a ningún usuario.
