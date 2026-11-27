# Demo interactiva con contenido ficticio

Acceso: **https://aradar.diegodella.ar/demo/**. No requiere usuario, contraseña ni claves.
`/demo/login` también abre directamente el escenario.

## Experiencia

Horizon Daily y los cuatro medios de referencia son ficticios. Seis historias ilustran brechas
de cobertura, agenda propia, interés de búsqueda y decisiones editoriales. Noticias, extractos,
porcentajes y tendencias son ejemplos identificados como tales. No hay enlaces a artículos reales.

La demo permite comparar períodos, filtrar historias, revisar evidencia ficticia, registrar
seguir/revisar/descartar con un motivo, marcar alertas revisadas, activar referencias, modificar
pesos por tema, previsualizar y publicar prioridades, restaurar pesos y simular una nueva señal.
El asistente usa respuestas locales guionadas y reconoce preguntas fuera del escenario.
Los cálculos son ilustrativos; no sustituyen el motor editorial del espacio real.

Cada sección muestra una guía breve al visitarla por primera vez: resumen, comparación,
acontecimientos, evidencia/decisión, tendencias, alertas, historial, asistente, fuentes, criterios
e integraciones. Se puede omitir con botón o Escape y repetir desde «Guía de esta función».
Las guías no escriben decisiones. Reiniciar la demo limpia cambios, conservando guías ya vistas.

## Idiomas

Inglés por defecto, español seleccionable. `radar_lang` conserva la preferencia durante un año
para el sitio público, acceso, cuenta principal y demo. `?lang=en` y `?lang=es` permiten enlaces
directos. Las fuentes y los textos editoriales aportados por el usuario conservan su idioma original.

El catálogo de interfaz compartido está en `static/translations.json`. Después de editarlo,
ejecutar `python3 scripts/build-i18n.py` para actualizar el bundle del navegador.
La demo tiene textos pareados en `showcase.js` y `showcase-data.js`.

## Rendimiento y aislamiento

`DEMO_ENABLED=true` y `DEMO_SHOWCASE=true` montan una página ligera y módulos estáticos.
No se crea una base de datos por visitante, no se importa un corpus, no se inicia un preloader,
no se llama a APIs y no se consulta OpenAI, Google, redes ni sitios de noticias.

Las interacciones y guías vistas se conservan en `localStorage` de ese navegador, separados de
la cuenta principal. Con almacenamiento bloqueado, la sesión sigue funcionando en memoria.
No se solicitan credenciales. «Reiniciar demo» elimina las modificaciones del escenario.

El despliegue ya no incluye `demo-collector` ni monta `demo-corpus` en web/worker. Los archivos
históricos del recolector se conservan localmente y no se usan en la nueva demo.
El código anterior basado en snapshots sigue disponible con `DEMO_SHOWCASE=false` para
compatibilidad y pruebas; no es el modo publicado.

## Validación

- `tests/test_showcase.py`: demo sin migraciones ni lecturas de corpus; idiomas y persistencia.
- `scripts/smoke-showcase.mjs`: ambos idiomas, diez secciones, 1440/390/320 px, guías,
  decisiones, pesos, fuentes, señal simulada, asistente, reinicio, cero APIs y tráfico externo.
- `scripts/smoke-i18n.mjs`: 19 páginas públicas y administrativas, ambos idiomas, escritorio/móvil.
- `scripts/serve-showcase.py`: servidor local aislado con cuenta de prueba y datos temporales.

Las evidencias locales se guardan en `artifacts/showcase/`, `artifacts/i18n/` y
`artifacts/deploy-20261126/`. La validación publicada usa carpetas separadas.
