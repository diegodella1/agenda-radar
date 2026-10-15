# Agenda Radar — documentación de implementación

**Versión:** 0.1 · **Fecha:** 14 de octubre de 2026 · **Estado:** especificación de producto, no software ya desplegado.  
**Nombre de trabajo:** Agenda Radar (renombrable). **Idioma de producto:** español, Argentina primero. **Entorno objetivo:** Raspberry Pi 5, 8 GB de RAM, ARM64, compartida con otros servicios.

## Qué estamos construyendo
Una **herramienta troncal de criterio editorial**, no un «sistema operativo editorial» ni un editor autónomo. Ayuda a un medio a medir la agenda de referencia, contrastarla con su cobertura, entender tendencias por canal y decidir qué cubrir, cuándo y en qué formato. La decisión es siempre humana. Se instala en infraestructura del medio; OpenAI se utiliza por API **cuando hace falta**, no como modelo local en la Raspberry.

## Orden recomendado de lectura
1. `01_PRD_PRODUCTO.md`: alcance, usuarios, flujos y aceptación del producto.
2. `02_ARQUITECTURA_RASPI.md`: stack, recursos, instalación y límites.
3. `03_DATOS_Y_API.md`: modelo persistente y contratos de API.
4. `04_CONECTORES_TENDENCIAS.md`: RSS, web, X, Google Trends y Google News.
5. `05_ADMINISTRACION_Y_CONFIG.md`: superadministrador, reglas, fuentes, versiones de prompts y ponderaciones.
6. `06_SCORING_AGENDAS.md`: métricas, reglas, sesgos, deduplicación y alertas.
7. `07_OPENAI_Y_TELEGRAM.md`: orquestación del LLM, seguridad y bot de Telegram.
8. `08_PLAN_DE_IMPLEMENTACION.md`: historias, dependencias, entregables y fases.
9. `09_QA_OPERACIONES.md`: pruebas, backups, seguridad, observabilidad y gates.
10. `10_REUSO_XPOSTER_CANCI.md`: reutilización y riesgos de integración.
11. `11_FUENTES_Y_DECISIONES.md`: referencias consultadas, decisiones y preguntas abiertas no bloqueantes.

## Decisiones acordadas vs propuestas
**Acordado por el promotor:** Raspberry Pi 5 8 GB; self-host; OpenAI API key; interfaz administrativa profunda; conectores RSS, web, X/listas; fuentes externas de tendencias; comparación de agendas; pesos por fuente/canal; agente Telegram proactivo y consultable; descargas Markdown.

**Propuesto técnicamente para el primer corte:** FastAPI + Python 3.12 + Jinja2/HTMX + SQLite WAL/JSON1/FTS5 + worker Python independiente + Telegram long polling + Docker Compose opcional. SQLite no es NoSQL, pero cumple el objetivo práctico de **no requerir Supabase ni un servidor de base**, y admite documentos JSON; por simplicidad y seguridad supera MongoDB en una Pi compartida. La futura compatibilidad con almacenamiento NoSQL se resuelve con repositorios/adaptadores, no con una dependencia desde hoy.

## Regla de producto
**Toda conclusión debe poder contestar**: «¿qué observaste?», «¿qué fuentes lo respaldan?», «¿cómo se calculó?», «¿qué no sabemos?» y «¿qué podría hacer un editor?». Nunca confundir importancia periodística con volumen de conversación.

## Resultado esperado del MVP
Desde una instalación limpia: crear administrador; registrar 20–30 fuentes permitidas; ingerir continuamente; agrupar publicaciones de un mismo acontecimiento sin perder ninguna; medir agenda por medio/canal; configurar criterios propios; detectar brechas; mostrar dashboard actualizado; recibir alertas por Telegram; consultar al bot con evidencia; reiniciar/restaurar sin perder datos. Si una fuente no está disponible, degradar correctamente y explicarlo.

## Lo que NO incluyen estos archivos
No incluyen un producto programado ni pruebas ejecutadas en la Raspberry real. Las tasas, latencias, disponibilidad y costos operativos que aparecen son **objetivos de validación**; requieren benchmarks contra los servicios que ya corren en tu equipo. Tampoco se presupone que una cuenta logueada en X permita extracción automatizada: se documentan alternativas legales y sus bloqueos.
