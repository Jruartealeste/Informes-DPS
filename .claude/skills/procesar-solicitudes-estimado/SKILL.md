---
name: procesar-solicitudes-estimado
description: Busca las solicitudes de alta de Estimado de Costo PENDIENTES que el equipo armó en la app ot/ (botón "Generar Estimado en Advertys"), las crea en Advertys real con crear_estimado.py previo OK explícito de Javier, y carga el número de Estimado resultante en la app. Usar cuando Javier pide "generá los estimados pendientes", "procesá las solicitudes de estimado", "dá de alta en Advertys los estimados de la app". No es para OT (eso es procesar-solicitudes-ot) ni para finalizar estimados existentes.
---

# Procesar solicitudes de alta de Estimado

Misma mecánica que `procesar-solicitudes-ot`, con el script
`informes/modules/estimados_costos/procesar_solicitudes.py` y la API
`/api/sync/solicitudes-alta-estimado` de `ot/` (token `OT_SYNC_TOKEN` del `.env`
de la raíz). Solo crea el **encabezado** del Estimado (OT, título, fechas);
los ítems de costo se cargan a mano en Advertys.

Crear un Estimado en Advertys es real y no se deshace sin borrarlo a mano. El
script solo procesa los ids que le pasás con `--ids`, y tienen que ser los que
Javier aprobó **en esta conversación, después de ver los datos**.

Parado en `informes/`, Python: `/c/Users/javie/AppData/Local/Programs/Python/Python312/python.exe`. Destino `--prod` salvo que Javier diga otra cosa.

```bash
python -m modules.estimados_costos.procesar_solicitudes listar --prod
python -m modules.estimados_costos.procesar_solicitudes procesar --prod --ids 5,6
# Estimado creado cuyo pedido ya no existe, después de que Javier decidió:
python -m modules.estimados_costos.procesar_solicitudes descartar --prod --ids 5
```

1. **Listar.** Si no hay pendientes, decilo y terminá.
2. **Pedir OK por id** mostrando OT de sistema, título, fechas y tareas.
   Si pide cambiar un dato: se cancela el pedido en la app y se arma otro.
3. **Procesar** solo los ids aprobados. Por cada uno: crea el Estimado
   (`crear_estimado`), anota el número en
   `informes/salida/solicitudes_alta_estimado.jsonl` y lo resuelve en la app.
4. **Reportar** el resumen que imprime el script.

**Si falla `crear_estimado`, NO reintentar:** el alta pudo salir bien. Mirar la
captura `exploracion/screenshots/crear_est_<ot>_03_guardado.png` y la grilla de
la OT en Advertys (ver `workflows/crear_estimado.md`). Si falla solo el resolver
en la app, volver a correr `procesar` con ese id: no crea otro, solo vincula.
Un 404/409 al resolver deja un Estimado sin vincular: avisar a Javier con el
número, y cuando decida, `descartar`.
