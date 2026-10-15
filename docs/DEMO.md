# Demo pública editable

Acceso: https://mp.diegodella.ar/demo/login — usuario `demo`, contraseña `demo`.
También se puede usar esa combinación desde el login principal. No es una cuenta de producción.

## Datos y recorrido

Escenario `argentina-v1`: 7 medios ficticios (1 propio y 6 referencias independientes),
18 acontecimientos y 103 publicaciones distribuidas entre cinco ventanas. Incluye 5 alertas
históricas explícitamente ficticias, 3 tendencias, decisiones y evidencia interna navegable.
El reloj editorial se fija al inicio de cada visita. El motor real calcula comparaciones;
la consulta local no llama a OpenAI. Los antecedentes son ilustrativos, no mediciones reales.

Comparar agendas → abrir Transporte urbano → revisar evidencia → registrar decisión →
Simular novedades → revisar alertas → consultar «transporte» → reiniciar el escenario.
El lote agrega 10 publicaciones una sola vez y evalúa las reglas sobre esos datos.
Cambiar criterios o agrupamientos puede modificar el resultado; reiniciar restaura el fixture.

## Aislamiento y límites

Aplicación montada en `/demo` con una base SQLite independiente por visita y directorio
aleatorio `data/demo/visit-<hash>`. La plantilla se genera con código versionado; no se copia
la base real. Cookies propias limitadas a `/demo`; todas las mutaciones usan CSRF.
No hay acceso a usuarios, secretos, backups, operaciones, contraseña ni vinculación Telegram.
La lista de rutas permitidas se aplica en backend. Las pruebas de fuentes son simuladas.
Importaciones masivas/manuales y carga de archivos no están habilitadas en la demo.

No se inicia el worker normal ni se usan clientes externos. La configuración global de
proveedores está bloqueada. Los cambios de fuentes/criterios, exportaciones y decisiones
pertenecen únicamente a la base de la visita.

Duración: 2 horas reales, máximo 10 sesiones, 30 fuentes por visita, 250 mutaciones antes
de pedir reinicio y 20 solicitudes válidas de login por minuto en el conjunto de la demo.
Limpieza cada 10 minutos y al atender solicitudes; logout elimina la visita. Al reiniciar
el servidor se eliminan las visitas anteriores y se requiere ingresar nuevamente.
Una única instancia web administra las visitas; no habilitar múltiples workers Uvicorn
sin implementar primero un registro de sesiones compartido.

## Operación y rollback

`DEMO_ENABLED` es false por defecto en el código y true en el Compose de producción.
`DEMO_DIR`, `DEMO_MAX_SESSIONS` y `DEMO_SESSION_SECONDS` controlan almacenamiento y capacidad.
Para desactivar: `DEMO_ENABLED=false docker compose -f compose.production.yaml up -d web`.
No requiere migración de la base de producción. Los datos temporales están ignorados por Git
y no forman parte del backup SQLite del medio real. No configurar el worker sobre DEMO_DIR.

## Verificación

`pytest tests/test_demo.py`: aislamiento, producción intacta, cinco ventanas, evidencia,
novedades idempotentes, reset, permisos, ausencia de tráfico externo/secrets, CSRF, capacidad,
vencimiento, limpieza y configuración. `scripts/smoke-demo.mjs` recorre la interfaz con dos
navegadores y tres anchos; usa `PLAYWRIGHT_MODULE`, `CHROMIUM_PATH` y `SMOKE_BASE_URL`.

### Guía visual editorial
El resumen muestra seis prioridades y permite desplegar el resto. Incluye ritmo de
publicaciones en intervalos comparables, cobertura propia/referencias, grupos y confianza.
Las primeras seis historias tienen una publicación previa para contrastar el ritmo actual.
Las novedades muestran participación de referencia antes/después y enlaces a dos
acontecimientos afectados. Todos estos datos siguen siendo ficticios.
Ver [criterio y validación visual](VISUAL_EDITORIAL_PLAN.md).
