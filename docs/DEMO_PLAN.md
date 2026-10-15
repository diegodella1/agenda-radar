# Demo editable de Agenda Radar

Implementación aprobada: acceso demo / demo en /demo, bases independientes por visitante,
sin datos ni secretos reales. Redacción argentina ficticia: un medio propio, seis referencias,
18 acontecimientos, unas 100 publicaciones, alertas, tendencias y decisiones.

Cada sesión dura dos horas; diez simultáneas. Limpieza cada diez minutos y al iniciar.
El reloj editorial queda fijado al inicio para mantener las cinco ventanas pobladas durante
la visita; las fechas se regeneran para cada visitante. La sesión expira con el reloj real.

Permite comparar, filtrar, revisar evidencias internas, decidir, reconocer alertas, registrar
cobertura, corregir agrupamientos, editar fuentes y criterios, exportar y reiniciar.
Simular novedades aplica un lote local una sola vez y recalcula indicadores y alertas.
El asistente usa búsqueda local determinista; ninguna función llama a proveedores externos.
No hay administración de usuarios, secretos, operaciones, backups ni cambio de contraseña.

Pruebas: aislamiento entre visitantes y producción, cookies/CSRF, vencimiento, reinicio,
capacidad, prohibiciones backend, cero tráfico externo, corpus, recorrido web móvil/escritorio.
Publicar en mp.diegodella.ar y subir al repositorio privado, con DEMO_ENABLED como interruptor.
