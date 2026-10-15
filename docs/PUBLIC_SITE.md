# Sitio público de Agenda Radar

Páginas: `/home`, `/about`, `/funcionalidades`, `/casos-de-uso`, `/roadmap`.
La raíz `/` muestra la portada a visitantes y conserva el radar para sesiones autenticadas.
El login y el pie del dashboard enlazan al sitio público. Sin precios ni registro público.

Dirección: editorial, papel claro, verde profundo y terracota; Georgia para titulares,
Trebuchet MS para texto. Comparación de agendas como pieza visual distintiva, con datos
explícitamente ficticios. DFII: impacto 4, contexto 5, viabilidad 5, rendimiento 5,
riesgo de consistencia 4; total 15. CSS separado, sin dependencias ni scripts públicos.
Navegación semántica, foco visible, enlace de salto, responsive y metadatos por página.

Las capacidades disponibles se separan de integraciones opcionales y objetivos por validar.
No se anuncian resultados de clientes, publicación automática ni login web de X disponible.

Verificación: tests de acceso público/privado y dashboard autenticado; smoke de seis rutas
con anchos 1440, 390 y 320 px, preguntas frecuentes y enlace al login.
Ejecutar `node scripts/smoke-public.mjs` con Playwright instalado y Chromium disponible.
Variables: `SMOKE_BASE_URL`, `PLAYWRIGHT_MODULE`, `CHROMIUM_PATH`.

Repositorio: https://github.com/diegodella1/agenda-radar (privado).
Especificaciones y plan originales: `docs/specification/`.
Credenciales, bases, copias y artefactos quedan fuera de Git.

Con DEMO_ENABLED activo, la portada enlaza a /demo/login. Las credenciales demo/demo
crean un escenario privado temporal, sin habilitar registro de cuentas reales.
