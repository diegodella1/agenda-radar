# Diseño: panel de monitoreo

## Dirección vigente
Desde 2026-10-15, por pedido del usuario, Agenda Radar adopta una interfaz de software.
El criterio editorial permanece en los datos y las decisiones; la presentación usa un
espacio de trabajo, navegación con iconos, barra de herramientas y tarjetas de señales.
Esta dirección reemplaza la estética anterior de papel, serif y titulares de revista.

Propósito: reconocer señales, contrastar evidencia y registrar decisiones rápidamente.
Tono: herramienta profesional de monitoreo. Ancla: navegación azul noche y tarjetas con
ritmo de publicaciones y atención comparada. DFII: impacto 4 + adecuación 5 + viabilidad 5
+ rendimiento 5 − riesgo 4 = 15.

## Skills aplicadas
- ui-ux-pro-max: consulta de sistema de diseño y guías de navegación/accesibilidad.
- frontend-design: dirección visual, jerarquía, consistencia y componentes funcionales.
Se adoptan la tipografía funcional y las guías de interacción. No se incorporan sugerencias
ajenas al producto como personalización comercial, testimonios ni efectos luminosos.

## Sistema visual
- Fira Sans 400/600, alojada localmente bajo SIL Open Font License; sin peticiones externas.
- Fondo #f3f6fb, paneles blancos, texto #18283f, secundario #53647b.
- Navegación #122139, acción y referencia #2356c7, cobertura propia #ad4819.
- Bordes suaves, radios 7–16 px, sombras discretas, espaciado de 4/8 px.
- Encabezados compactos sans serif; números tabulares para comparar métricas.
- SVG lineales consistentes de 24 px; iconos decorativos ocultos a lectores de pantalla.
- Estados acompañados por texto; datos ausentes nunca se convierten en cero.
- Transiciones de color de 160 ms, anuladas con movimiento reducido.

## Interacción
Navegación lateral en escritorio y menú desplegable explícito en móvil. El botón anuncia
estado expandido y Escape cierra y devuelve foco. Sin JavaScript la navegación queda visible.
Objetivos táctiles de al menos 44 px en navegación, botones y formularios.
Resumen de selección junto al período visible; filtros secundarios en Más filtros y
etiquetas de filtros activos siempre visibles. Acceso al criterio limitado a roles autorizados.
Ayuda opcional, paneles nativos y evidencia conservan su comportamiento.
Login y páginas públicas comparten tipografía, controles y lenguaje visual.
No hay cambios al algoritmo, permisos, integraciones ni aislamiento demo.

## Validación
Comprobar recorrido demo completo, menú móvil por toque/teclado y retorno de foco,
contraste, fuentes locales, estados de cobertura y ausencia de desbordamiento.
Revisar páginas públicas y once pantallas de aplicación a 1440, 390 y 320 px,
además de 768/1024 para transiciones de la barra lateral y grillas.
Ver también [guía visual editorial](VISUAL_EDITORIAL_PLAN.md).

### Resultado de validación
48 pruebas aprobadas. Recorrido de aplicación probado en once pantallas y cinco anchos
(1440, 1024, 768, 390 y 320); sitio público en seis rutas y tres anchos.
Menú móvil y ayuda verificados con teclado, Escape y retorno de foco.
Contrastes principales medidos: texto 14,85:1; secundario 5,58:1; azul sobre blanco 6,51:1;
navegación secundaria 9,41:1; estado de cobertura 5,62:1.
Fuentes locales incluidas también en el paquete Python, con su licencia.

### Verificación pública de esta entrega
La nueva imagen está desplegada y /health/ready responde correctamente. La suite local
y CI aprobaron. La comprobación integral por HTTPS quedó incompleta: Chromium agotó
el tiempo al capturar una página y al esperar una navegación; un intento posterior
se interrumpió tras aproximadamente cinco minutos sin resultado final. No se declara
aprobado ese recorrido remoto. Las capturas locales y el recorrido local en cinco
tamaños sí fueron revisados. El script admite SMOKE_SCREENSHOTS=0 para separar
la comprobación funcional de las capturas en equipos con recursos limitados.

### Corrección posterior de CSS
La auditoría encontró app.css sobrescrito con una plantilla durante el último ajuste.
Se restauró y se incorporaron pruebas de contenido y estilos calculados. El sitio público
no estaba afectado. Ver [causa, corrección y cobertura](CSS_AUDIT.md).
