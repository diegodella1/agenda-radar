# Agenda Radar: guía visual editorial

## Resultado esperado
Un editor reconoce qué acontecimientos merecen atención según sus criterios y fuentes,
contrasta evidencia, registra una decisión y observa cambios. El crecimiento de publicaciones,
la conversación en X, el interés de búsqueda y la brecha de cobertura son señales distintas.
No se infiere escalada a partir de una brecha ni se inventan tendencias sin historial.

## Criterio de diseño
Aproximadamente 90% de comprensión mediante señales, gráficos y acciones visibles.
Período, unidades, fuentes, disponibilidad y estado permanecen visibles. Explicaciones en
desplegables, paneles y ayuda opcional. La dirección visual vigente es un panel de software con Fira Sans local, navegación azul
noche, controles compactos y tarjetas de señales. Ver DESIGN.md; reemplaza la estética
anterior de papel y tipografía serif. El principio de guía visual se conserva.
DFII: impacto 4 + adecuación 5 + viabilidad 5 + rendimiento 5 − riesgo 4 = 15.

## Implementación
1. Representación compartida en presentation.py, conservando algoritmo y campos API.
   Filtros por período, tema, fuente, canal y país; denominadores del universo original.
2. Resumen con seis prioridades iniciales, resto desplegable, comparación propia/referencias,
   grupos independientes, confianza explicada, ritmo observado y barras por tema.
3. Comparación con brechas centradas en cero, escala −100/+100 pp, paneles desplegables
   por acontecimiento, matriz seleccionable por medio y tabla numérica bajo demanda.
4. Detalle con ventana conservada, cobertura, comparación, evidencia agrupada por medio,
   cronología, antecedentes y decisiones con efectos explicados. Correcciones avanzadas.
5. Ayuda opcional de tres pasos, diálogo nativo con Escape y devolución de foco;
   explicaciones nativas accesibles por teclado y toque. Movimiento reducido respetado.
6. Novedades demo con antes/después y enlaces a acontecimientos afectados, sin IA adicional.
7. Validar cálculos, filtros, ausencia, aislamiento, navegación, escritorio y 390/320 px.
8. Publicar imagen verificable y actualizar repositorio privado tras pruebas.

## Interpretación de señales
Ritmo: publicaciones únicas en dos intervalos consecutivos, de hasta 120 minutos cada uno
(o media ventana si es menor). Si alguno carece de observaciones se informa historial
insuficiente. Es volumen observado, no tendencia validada ni ajuste por horario.
La prioridad mantiene la fórmula vigente (brecha, afinidad, velocidad y diversidad).
Búsquedas: últimas muestras del período, separadas y etiquetadas; no se atribuyen
automáticamente a acontecimientos ni a los filtros de tema/fuente. X depende de fuentes
configuradas y actualizadas. No se implementa autenticación de X por usuario/contraseña.
Confianza: calidad de agrupación y fuentes, nunca probabilidad de veracidad.
Datos ausentes: sin datos, no cero. Todas las barras de atención usan 0–100%.

## Aceptación
Detectar → entender → contrastar → decidir → observar cambios sin documentación externa.
La demo conserva ficción, aislamiento y efectos temporales. No se agregan servicios gráficos.

## Validación de entrega

- Suite completa: 48 pruebas aprobadas, incluyendo contrato de comparación, filtros con
  denominadores conservados, referencias, cambios demo y ausencia de datos.
- Ruff y mypy sin errores.
- Navegador: recorrido demo entre dos visitantes, aislamiento de decisiones, evidencia,
  novedades, asistente local, reinicio y cierre de sesión. Once pantallas a 1440, 390 y
  320 px, sin desbordamiento horizontal del documento.
- Ayuda: apertura/cierre por teclado, Escape y retorno del foco. Paneles nativos con
  apertura/cierre por teclado; matriz enlaza medio y conserva período.
- Semántica para lectores de pantalla: gráficos con nombres y valores, tabla con
  encabezados, diálogo con título, regiones desplazables con nombre y avisos vivos.
  No se realizó una sesión manual con software lector de pantalla ni estudio con usuarios.
- La referencia del 90% es un criterio de diseño; requiere validación con editores reales.
