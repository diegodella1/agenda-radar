# Operación

## Arranque y actualización

Ejecutar `init` antes de web/worker. Nunca iniciar migraciones desde una petición web.
Antes de actualizar: backup online + checksum; detener solo los procesos Agenda Radar;
instalar dependencias, migrar, iniciar y consultar `/health/ready`.
Ante fallo, restaurar backup a destino separado y usar la versión de código anterior.
No usar downgrade destructivo como estrategia de recuperación de datos.

## Backups

`python -m agenda_radar.cli backup /destino-externo/agenda-FECHA.db`.
SQLite backup API, integridad y checksum SHA-256. Restaurar con
`python -m agenda_radar.cli restore BACKUP NUEVO_DESTINO`.
Nunca sobrescribe base activa ni destino existente. Guardar `secrets/master.key`
por separado, cifrado con el mecanismo institucional; sin esa clave no se recuperan
los tokens cifrados. Las contraseñas son hashes Argon2id.
El volumen Docker por defecto no constituye una copia fuera del dispositivo.
El worker programa backup diario y retiene 7 diarios + 4 semanales de sus archivos
automáticos. Para piloto conectar almacenamiento externo como BACKUP_DIR. Ejecutar restore drill semanal antes de retirar copias antiguas.

## Diagnóstico

`/health/live`: proceso web. `/health/ready`: migración y heartbeat worker.
`/api/v1/admin/health`: detalle autenticado. Panel Operaciones: trabajos y reintentos.
No registrar cuerpos completos de proveedores ni URLs que contengan tokens.
Conector caído no equivale a falta de noticias. Reintentar desde fuente o job fallido.

## Instalación LAN

Por defecto bind loopback; usar reverse proxy HTTPS institucional para LAN/VPN.
`COOKIE_SECURE=true` en HTTPS. No publicar HTTP autenticado directamente a internet.
No modificar routers, túneles o servicios ajenos durante desarrollo.

## Validación externa

Falta validar 20 feeds autorizados del medio piloto, cuentas proveedoras y entrega Telegram.
La suite usa fixtures separados y nunca habilita fuentes reales ni envía mensajes a terceros.
El gate de piloto exige 24 h en Raspberry, evaluación editorial humana y restore externo.
