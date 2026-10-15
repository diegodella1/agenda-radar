# Auditoría CSS — 2026-10-15

## Incidente encontrado
El último ajuste de filtros sobrescribió static/app.css con una plantilla Jinja/HTML.
La respuesta HTTP 200 y el MIME text/css no garantizaban una hoja válida. Chromium
ignoraba las reglas y usaba Times New Roman en login y páginas internas.
El sitio público usa public.css y no tenía esta corrupción.

La revisión visual anterior correspondía al estado previo al último ajuste. Su resultado
no validaba los archivos efectivamente publicados después. Esta auditoría reemplaza esa
conclusión para la entrega corregida. También se observó un fallo DNS transitorio, pero
no explica ni sustituye la causa principal del problema de estilos.

## Corrección
Restaurado el CSS de software desde la imagen previa al ajuste, conservando navegación,
paleta, fuentes, componentes y tamaños táctiles. Reincorporadas las reglas de filtros
secundarios al archivo CSS correcto. La nueva versión de assets invalida la URL anterior.

## Prevención
- Prueba Python que rechaza Jinja/HTML dentro de app.css y public.css.
- scripts/audit-css.mjs verifica reglas cargadas, tipografía calculada, fuentes realmente
  declaradas y cargadas, fondo, altura de controles, navegación y overflow.
- Comprueba todos los desplegables abiertos. Repite a 1440, 1024, 768, 390 y 320 px.
- La prueba de demo verifica estilos aplicados y evita esperas indefinidas por fuentes.
- Los tiempos de espera son acotados y cada ruta informa PASS/FAIL.

## Cobertura local
120 comprobaciones aprobadas: 24 pantallas por cinco tamaños. Incluye sitio público,
login normal/demo, instalación, resumen, comparación, acontecimientos, detalle, tendencias,
alertas, decisiones, asistente, fuentes, criterios, cuenta, usuarios, proveedores, prompts,
operaciones y auditoría. Administrador probado con datos sintéticos en una instancia aislada;
no se emplearon credenciales ni datos administrativos de producción.
Sin errores de JavaScript ni desbordamientos. Capturas en artifacts/css-audit (no versionadas).

## Validación publicada
La imagen `agenda-radar:cssfix-b5421e4389e6` quedó desplegada en web y worker.
El servicio confirmó disponibilidad y la auditoría HTTPS aprobó 100 comprobaciones:
20 rutas por los mismos cinco tamaños, incluyendo portada, páginas públicas, accesos,
demo interna, integraciones y evidencia. Cero errores de estilos o JavaScript.
El archivo publicado usa la versión `e7656cbb4f55`.
La suite Python completa aprobó 49 pruebas, incluida la regresión de CSS.

## Reproducción
PLAYWRIGHT_MODULE debe apuntar a una instalación de Playwright, o estar disponible como paquete.
Ejecutar node scripts/audit-css.mjs con AUDIT_BASE_URL. Para el entorno local se requiere
una cuenta de prueba aislada; el script usa únicamente css-audit@example.test en 127.0.0.1.
En el dominio público utiliza una visita demo temporal y cierra la sesión al terminar.
AUDIT_SCREENSHOTS=1 activa capturas; las comprobaciones de CSS se ejecutan siempre.
Los reportes JSON se guardan en artifacts/css-audit.
