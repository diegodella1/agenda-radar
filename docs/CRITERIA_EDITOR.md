# Editor visual de criterios

## Dirección UX/UI
Panel de control utilitario, dentro del sistema visual de Agenda Radar: Fira Sans,
azul para acciones, superficies claras y secciones desplegables. El elemento central
es el ajuste visual de pesos seguido de barras de comparación con datos reales.
Evaluación: impacto 3, adecuación 5, factibilidad 5, rendimiento 5,
riesgo de consistencia 3; DFII 15.

## Recorrido
1. Ajustar temas, palabras clave y multiplicadores con controles etiquetados.
2. Ajustar fuentes por nombre; internamente se conserva su ID.
3. Abrir ajustes contextuales, alertas o excepciones cuando se necesiten.
4. Comparar la versión activa con el borrador sobre las últimas 24 horas.
5. Explicar el motivo y publicar. Editar después de comparar invalida la comparación.

El borrador no altera la configuración activa. Descartarlo recupera los valores con
los que se abrió la página. Publicar usa la validación y versionado existentes.
La comparación vence a los 30 minutos y no consume IA ni envía alertas.
Los ajustes globales solo se ofrecen al superadministrador; el servidor mantiene
la verificación de permisos. Los campos no expuestos se conservan sin modificarlos.

## Interpretación
Los multiplicadores editoriales van de 0 a 5 y se combinan entre sí. 1 es neutro.
No necesitan sumar 100 y no modifican los coeficientes fijos de la prioridad.
Los pesos de referencia van de 0 a 100 por fuente. Quitar un ajuste recupera su
peso base. Los códigos geográficos corresponden al país de las fuentes; los horarios,
a la hora del análisis. Las palabras clave afectan nuevas clasificaciones.

La comparación muestra prioridad (0–100) y brecha (puntos porcentuales).
La ausencia de datos se etiqueta explícitamente. No es una simulación de alertas.
Los resultados adicionales se pueden desplegar para no dominar la pantalla.

## Verificación
scripts/smoke-criteria.mjs usa una sesión demo aislada: edición, límites,
teclado, comparación, invalidación del resultado, selección de fuentes por nombre,
publicación y persistencia, descarte y anchos 1440/768/390/320.
scripts/audit-css.mjs revisa además pantallas públicas e internas.
Las capturas se guardan en artifacts/criteria y no se versionan.

Validación local: 49 pruebas Python aprobadas y smoke del editor completo aprobado,
incluyendo persistencia exacta del borrador y descarte. Ruff y sintaxis JavaScript
verificados. La auditoría general completó 118 comprobaciones; el último menú móvil
de Auditoría venció por tiempo bajo carga del host. No se reporta esa corrida como
una auditoría completa aprobada.

Publicación: imagen agenda-radar:criteria-e84af9b52084 en mp.diegodella.ar.
El mismo smoke del editor pasó sobre HTTPS, incluyendo publicación y lectura de la
configuración en una visita demo temporal. Los criterios reales no se modificaron.
CI aprobó lint, tipos, sintaxis JavaScript, 49 pruebas y construcción del paquete.
