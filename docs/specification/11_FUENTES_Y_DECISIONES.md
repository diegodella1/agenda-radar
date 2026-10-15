# Fuentes técnicas, decisiones y riesgos abiertos
**Consulta documental:** 14/10/2026. Estos enlaces son referencias para implementación; condiciones comerciales y APIs se deben verificar de nuevo al conectar proveedores reales.

## 1. Fuentes verificadas
- [X API Overview](https://docs.x.com/x-api/overview) — lista oficial de Posts, Lists, Trends y el acceso condicionado por plan; no extrapolar disponibilidad a tu cuenta.
- [Google Trends — exportar Trending Now](https://support.google.com/trends/answer/3076011?hl=es) — RSS y CSV en interfaz.
- [Google Trends API Alpha](https://developers.google.com/search/apis/trends) — programa por solicitud, no disponibilidad general automática.
- [Telegram Bot API](https://core.telegram.org/bots/api) — `getUpdates`, webhooks, mensajes; long polling para Pi.
- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses) — JSON Schema bajo Responses API, con validación adicional propia.
- [OpenAI API Pricing](https://developers.openai.com/api/docs/pricing) — precios por modelo/uso. No hardcodear números porque pueden cambiar.
- [Raspberry Pi 5](https://www.raspberrypi.com/products/raspberry-pi-5/) — 5 V/5 A y ventilación activa recomendada.
- Repos privados del usuario: [XPoster](https://github.com/diegodella1/xposter), [DESK/Canci](https://github.com/diegodella1/canci); utilizados exclusivamente como referencia de diseño, no se hicieron cambios ni despliegues.

## 2. Decisiones adoptadas para implementación
| Decisión | Por qué | Reversible |
|---|---|---|
| Un medio por instancia | minimiza RBAC y aislamiento en appliance | sí |
| SQLite + JSON1 + FTS5 | sin dependencias de DB externa, más robusto que TinyDB en concurrencia | sí, con adapter |
| FastAPI + HTMX | menor consumo RAM que múltiples runtimes | sí |
| Worker separado + outbox | fallos de Telegram/IA no bloquean UI | sí |
| Reglas deterministas primero | costo explicable y baja CPU | sí |
| OpenAI API configurable | BYOK, no inferencia en la Pi | sí |
| Trends RSS/CSV | camino respaldado por Google sin alpha privada | sí |
| X oficial opcional | no prometer scraping ni acceso sin API | sí |
| Prompts versionados con roles | evita cambios invisibles al razonamiento editorial | no conviene quitar |
| No autopublicar | mantiene responsabilidad humana y reduce riesgo | producto futuro separado |

## 3. Hipótesis que requieren validación
- Que 20–30 fuentes representen adecuadamente el universo que quiere observar el editor.
- Que los feed RSS externos permitan reuso comercial en cada caso.
- Que una Pi compartida pueda sostener los tiempos objetivos; hacer inventario antes del deployment.
- Que el feed de Trends permita todas las regiones/ventanas deseadas en el momento de instalación.
- Que el cliente disponga de acceso/API de X con tarifas aceptables.
- Que existan datos suficientes de la agenda propia; si no, edición manual inicial.
- Que alguna métrica propia permita recomendar un canal mejor que «el tema crece».

## 4. Preguntas abiertas no bloqueantes
1. ¿La propia agenda se define por RSS del medio, por decisiones manuales o por ambos? **Default:** ambos.
2. ¿Qué cuenta como «mis referencias» para medio local frente a medio nacional? **Default:** preset + selección manual.
3. ¿El resultado se vende como licencia, con mantenimiento o con hardware? **Default técnico:** misma imagen portable, sin billing.
4. ¿Qué presupuesto máximo de OpenAI/X? **Default:** admin configurable, IA bloqueada al alcanzar límite.
5. ¿Qué histórico importar de XPoster/Canci? **Default:** no importar hasta ver consentimiento, datos y compatibilidad.
6. ¿Cómo asignar editor a Telegram? **Default:** código de emparejamiento temporal + chat privado permitido.

## 5. Riesgos de producto, no solo técnicos
- **Sesgo de muestra:** «agenda pública» de Google Trends no sustituye representatividad social.
- **Endogeneidad:** medios que se copian elevan artificialmente visibilidad; cap por grupo y sindicación.
- **Desfase:** detectar cobertura propia ausente exige conector propio saludable.
- **Falsa certeza del lenguaje:** textos convincentes que no están respaldados; validación post-LLM.
- **Dependencia comercial:** cambios en X/Google/OpenAI alteran costos, permisos y frescura.
- **Privacidad:** autoalojar no significa que todo sea local si OpenAI y Telegram reciben datos.
- **Dispersión:** no implementar edición multimedia, CMS, social scheduling y ML training en el primer hito.
