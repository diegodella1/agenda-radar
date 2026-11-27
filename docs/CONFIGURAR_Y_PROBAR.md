# Acceso, configuración y operación

Destino: **https://aradar.diegodella.ar**. Usuario: **diego@diegodella.ar**.
La contraseña inicial aleatoria está en `secrets/initial-admin.json`, archivo local 0600
ignorado por Git. Leer desde el servidor, ingresar y cambiarla en **Mi cuenta**. El cambio
revoca todas las sesiones. Eliminar el archivo inicial después de guardar la contraseña nueva.
No hay registro público abierto ni contraseña predeterminada.

## Configuración desde el administrador

Por indicación del usuario, las fuentes, redes y proveedores se cargan en la interfaz.

1. **Fuentes**: cargar fuente propia (`own`) y referencias (`reference`). Identificar grupos
   de propiedad; hacen falta dos grupos independientes para comparar. Probar cada fuente y
   verificar documentos/fechas. El piloto completo contempla 20–30 fuentes.
2. **Criterios y pesos**: ajustar temas, umbrales y reglas. Previsualizar y publicar.
   La pausa conserva ingestas pendientes y permite backups; no cancela solicitudes ya iniciadas.
3. **Proveedores**: claves opcionales de OpenAI/Telegram/X. Configurar modelos y tarifas,
   presupuestos y activar explícitamente las integraciones. Vincular Telegram con código temporal.
4. **Prompts**: probar antes de publicar. Respuestas requieren aprobar cuatro casos sintéticos
   fijos; los resultados conservan versión y hash. Extracción usa documento local en modo de prueba,
   sin modificar entidades. La aprobación automática no reemplaza evaluación editorial.
5. **Operaciones**: diagnóstico, incidencias, trabajos y backups descargables. Descargar a otro
   equipo para disponer de copia externa. Guardar `secrets/master.key` por separado.

Sin claves, la agenda funciona y el asistente devuelve evidencia determinista. No se cargan
fuentes inventadas ni se incorporan los datos de prueba a la base real.

## Despliegue actual: Docker y túnel independiente

`compose.production.yaml` define web, worker y Cloudflare con reinicio automático, límites
CPU/memoria y logs rotativos. Web escucha solo `127.0.0.1:8765`. Se usan directorios de este
proyecto; web/worker acceden únicamente a la clave del vault, no a la credencial del túnel.

Túnel propio `agenda-radar-aradar`: `6c2c5376-c23d-40a6-b2f5-db510d7b3117`.
El DNS `aradar` apunta a ese túnel. No se modifican `/etc` ni el túnel de los otros sitios.
La propuesta systemd anterior quedó reemplazada por este despliegue.

```bash
cd /home/diego/Documents/mediaparty/agenda-radar
rtk proxy docker compose -f compose.production.yaml ps
rtk proxy docker compose -f compose.production.yaml logs --tail 50 web worker tunnel
rtk proxy curl --fail https://aradar.diegodella.ar/health/ready
```

Reiniciar los servicios del proyecto:

```bash
rtk proxy bash scripts/activate-production.sh
```

Para retirar el despliegue, `docker compose -f compose.production.yaml down` detiene únicamente
este proyecto; conserva archivos de datos/secretos. Si se retira definitivamente, eliminar
solo el DNS `aradar` y el túnel `agenda-radar-aradar`. No restaurar configuraciones antiguas del túnel compartido.

## Actualizar y revertir

Antes de actualizar: backup, registrar etiqueta/ID de imagen actual y detener web/worker.
Construir imagen nueva con Dockerfile y etiqueta distinta; ejecutar tests con esa imagen,
actualizar `compose.production.yaml`, ejecutar `init` con el servicio worker y levantar servicios.
Comprobar readiness y login HTTPS. Si falla, restaurar etiqueta anterior; si hubo cambio de
esquema, restaurar backup en destino nuevo y recuperar la clave por separado antes de arrancar.
No sobrescribir una base activa con un backup.

La imagen inicial se construyó con dependencias descargadas de PyPI. La capa final incorpora
el código congelado tras QA. Etiquetas y evidencia están en `deploy/release.json` y `artifacts/`.

## Ensayo y aceptación

El servicio opcional `soak` consulta readiness HTTPS durante 24 horas:

```bash
rtk proxy docker compose -f compose.production.yaml --profile qa up -d soak
rtk proxy cat artifacts/soak/status.json
```

`status=running` y `passed=false` no indican aprobación. Solo al terminar las 24 horas sin
fallas cambia a `completed/passed=true`. Mide disponibilidad HTTP, no calidad editorial.
Para repetir, conservar evidencias previas y recrear el contenedor de ensayo.

Con fuentes cargadas, comprobar ingesta/reintentos, deduplicación, ventanas, decisiones,
cobertura propia, split/merge, configuración y rollback, presupuestos, citas y alertas reales.
Las credenciales deben validarse con las cuentas autorizadas del usuario.

Reglas implementadas: brecha, evento emergente, prioridad sin cobertura, cambio de agenda,
actualización de alto impacto y fallas de fuentes (administradores). Todas son reglas
heurísticas con umbrales editables; alto impacto significa evidencia nueva suficiente,
no una evaluación semántica certificada. Silencios y máximo conjunto de 6 avisos/12 horas.

Para medir agrupamiento con un corpus etiquetado por editores:

```bash
rtk proxy .venv/bin/python scripts/evaluate_corpus.py corpus-etiquetado.json
```

Formato de cada fila: `url`, `title`, `excerpt` opcional, `expected_cluster` y `group_name`
opcional. La ejecución usa una base temporal aislada y registra hash, precisión y recall.
`tests/fixtures/corpus.synthetic.json` sirve para comprobar el runner; no certifica rendimiento
sobre noticias reales. La calibración por franja/día requiere historial real suficiente.


El túnel usa `keepAliveTimeout: 2s`, menor que el timeout idle de Uvicorn, para evitar
reutilizar conexiones al origen que ya se cerraron. Se verificó con navegación HTTPS
y pausas entre solicitudes. Referencia: [parámetros de origen de Cloudflare](https://developers.cloudflare.com/tunnel/reference/origin-parameters/).

## Versión del 26 de noviembre de 2026

Sitio y cuenta principal bilingües (inglés por defecto, español seleccionable). La demo abre directamente en `/demo/`, sin login, noticias reales ni recolector. `DEMO_SHOWCASE=true` publica el escenario ficticio; ver [DEMO.md](DEMO.md). El despliegue activo utiliza solo web, worker y túnel. OpenAI y extracción siguen desactivados. Las fuentes y configuración de la cuenta principal se conservaron.

Rollback de esta actualización: restaurar la imagen `agenda-radar:aradar-20261126` y usar `DEMO_SHOWCASE=false` (la demo anterior requiere su corpus y recolector). No es necesario revertir esquema: esta actualización no incorpora migraciones. El backup previo queda fuera del repositorio, bajo `artifacts/deploy-20261126/`.
