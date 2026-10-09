# QA ot/ — proceso de creación de Estimados (2026-10-09)

## Entorno y alcance
- Server descartable `:8123` (`ot/tools/qa_server.py`) sobre Postgres Docker `ot-qa-pg`, datos del seed (ALUAR). Sin cambios de modelo/migraciones respecto de HEAD.
- Probado, con consulta SQL después de cada paso: armar Estimado desde `/estimados/nuevo?ot_advertys=260` (validación cliente + POST), detalle, agregar/quitar tareas, "Generar Estimado en Advertys" (solicitud + comando), resolver/cancelar solicitud, "Cargar número", estados BORRADOR/GENERADO, validaciones 404/409/422 por POST directo, interacción con anular tarea y con `/facturacion`, desborde mobile a 375px.
- **No se probó:** Estimado con tareas de dos OT internas hermanas (el seed no trae hermanas), el listado `/estimados` con muchos registros, botón "Armar Estimado" desde el detalle de OT, modo claro, impresión, y la corrida real de `crear_estimado.py` (nunca desde QA).

## Altos
1. **Comando `crear_estimado.py` sin escapar** (`ot/app/viewmodels.py:209-223`, `_comando_crear_estimado`). El título va entre comillas dobles sin escapar y las fechas sin comillas. Con `fecha_solicitada = $HOME\`id\`` el comando generado queda `--fecha-solicitada $HOME\`id\``, y `a"b'c` rompe el quoting. En PowerShell, `"...$(cmd)..."` ejecuta dentro del título. Es el mismo bug que `_comando_crear_ot` ya corrigió con `_arg_shell` (ver hallazgos-conocidos). El comando se pega en una terminal con credenciales de Advertys cargadas. Arreglo: usar `_arg_shell` para título, OT y fechas.

## Medios
2. **`cargar-numero` con pedido PENDIENTE** (`estimados.py:255`): no chequea `solicitud_alta_id`. Reproducido: pedido pendiente en Estimado 1, `cargar-numero 777` → 303, Estimado GENERADO con 777 y la solicitud sigue PENDIENTE. Después "Cargar número 888" en `/estimados/solicitudes` pisa el 777 en silencio (base: `numero_estimado=888`). Mismo patrón que el bug de OT corregido el 2026-10-07 (asignar-lote). Esperado: 409 mientras haya pedido PENDIENTE.
3. **Tarea ANULADA sigue dentro del Estimado y en Facturación.** Anulé la tarea 12 (en Estimado GENERADO): sigue en el detalle y en `/facturacion`. Además `_tareas_candidatas` no excluye ANULADA, así que una tarea anulada se ofrece para armar un Estimado nuevo. Decidir con Javier si anular una tarea la saca del Estimado (si está en BORRADOR) y de las candidatas.
4. **Fechas del pedido sin validar** (`generar_estimado_en_advertys`): texto libre. Más de 10 caracteres → **500** (`StringDataRightTruncation`, `varchar(10)`); lo que cabe en 10 se guarda aunque no sea una fecha (`$HOME`, `ab"c`). Esperado: 422 si no es D/M/AAAA. El form debería usar `type="date"` o `pattern`.

## Bajos
5. `tarea_ids` no numérico (`abc`) → 500 en `POST /estimados` y `POST /estimados/{id}/agregar` (`int()` sin capturar, `estimados.py:190` y `:233`). Esperado 422.
6. Se puede generar un pedido de alta para un Estimado **sin tareas** (quitar todas y generar → 303). Un Estimado vacío no tiene sentido en la cola de Facturación.
7. Se puede agregar/quitar tareas de un Estimado BORRADOR **con pedido PENDIENTE**; el comando ya copiado no cambia pero el resumen sí. Menor, el comando solo usa título y OT.
8. No hay forma de editar el título de un Estimado BORRADOR (ni ruta ni UI); un error de tipeo obliga a rehacer el Estimado.
9. Texto del detalle: `abrir el Estimado ).` con espacio antes del paréntesis (`estimados/detalle.html`, sin número de Estimado interpolado cuando está en BORRADOR).
10. La validación "tildá al menos una tarea" es un `alert()` nativo, no un aviso en la página (ya anotado en `ot/CLAUDE.md`).

## Lo que funcionó bien
- Alta por la interfaz: título obligatorio (nativo), aviso sin tareas, Estimado BORRADOR con exactamente las tareas tildadas (base: `estimados` 1 fila, `tareas.estimado_id` correcto, sin duplicados).
- 422 en servidor: sin tareas, título en blanco, tarea ya en otro Estimado, tarea inexistente, tarea de otra OT de sistema. 404 en ids inexistentes y 400 sin `ot_advertys`.
- Agregar/quitar: quitar una tarea ajena es no-op, agregar vacío no hace nada, agregar de otra OT de sistema → 422.
- Pedido: crea `solicitudes_alta_estimado` PENDIENTE, rechaza el segundo pedido (422), resolver propaga número y GENERADO, resolver/cancelar dos veces → 409, cancelar libera el Estimado (`solicitud_alta_id` NULL, solicitud borrada), todo GENERADO queda de solo lectura (409 en agregar/quitar/generar/cargar).
- Mobile 375px: `scrollWidth` 371 en las 5 pantallas de estimados, sin desborde.

## Estado de correcciones (2026-10-09)
Corregidos 1–7 y 9 (sin commit aún), verificados con `ot/tests/test_estimados.py` (7 casos nuevos, suite 78 en verde) y repetidos contra el server de QA. Sin tocar: 8 (título no editable, es una feature) y 10 (`alert()` nativo). Decisión tomada sin consultar: una tarea ANULADA deja de ser candidata y sale de la cola de Facturación; si ya está dentro de un Estimado sigue apareciendo en su detalle.
