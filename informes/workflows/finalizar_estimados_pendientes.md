# Finalizar estimados listos según Estimados Pendientes

**Objetivo:** revisar el informe de Estimados Pendientes y pasar a
`Finalizado` en Advertys los Estimados de Costo que ya están facturados y
con sus Órdenes de Compra cruzadas, sin tocar nada que todavía esté
bloqueado.

**Cómo se diferencia de `cerrar_pendientes.md`:** ese workflow parte de las
OT **abiertas** (informe de Pendientes) y además cierra la OT una vez que
sus estimados quedan resueltos. Este workflow parte de TODOS los estimados
no terminales (informe de Estimados Pendientes, `modules/estimados_pendientes/`),
de cualquier OT — abierta o cerrada — y **solo** finaliza estimados, nunca
cierra una OT. Cubre el caso confirmado por Javier (2026-09-09): un
estimado que quedó "Facturado manual" colgado de una OT que ya se cerró,
sin el click final a `Finalizado`.

**Cuándo usar:** Javier pide algo como "revisá qué estimados se pueden
pasar a Finalizado" o "probá el flujo de cierre de estimados".

**Salvaguarda:** este flujo escribe en Advertys (cambia el estado real de
un estimado). El único script con permiso para eso sigue siendo
`modules/ordenes_trabajo/cerrar_ot.py` (mismas reglas duras ya aprobadas
por Javier 2026-07-20/21): nunca "Anulado"/"Provisorio", solo
Estimado→Finalizado. Este workflow no amplía ese alcance ni la
granularidad de ejecución (un estimado por vez, con revisión intermedia).

**Tools a usar (en este orden, siempre parado en la raíz del proyecto,
`informes/`):**

1. **Paso obligatorio, no opcional — datos al día:** si `estimados_costos`,
   `ordenes_compra`, `oc_pendientes_generar`, `estimados_pendientes_facturar`
   y `ordenes_trabajo` no se refrescaron en esta misma sesión, correr
   primero el skill `refresh-dashboard`. El semáforo sale de datos locales
   en `advertys.db`.
2. `python -m modules.ordenes_trabajo.cerrar_ot listar-candidatos-estimados`
   — de SOLO LECTURA (nunca clickea "Editar" ni "Guardar"). Parte del
   semáforo local de `modules/estimados_pendientes/generate_html_report.py`
   (todos los estimados no terminales marcados "Listo para Finalizado":
   facturados, sin items sin O.C., sin O.C. con saldo pendiente) y corre
   `chequear_estimado_completo` en vivo (un solo login/browser) para
   confirmarlo contra Advertys antes de proponer nada. Devuelve:
   - Estimados no evaluables (su OT tiene más de 20 estimados cargados —
     la grilla pagina, revisar a mano).
   - Estimados LISTOS para `finalizar-estimado`.
   - Estimados BLOQUEADOS en el chequeo en vivo, con motivo puntual (puede
     pasar aunque el semáforo local haya dado verde — ver "Notas del flujo
     de cierre de OT" en el README, ej. desfasaje de imputaciones).
3. **Presentarle a Javier la propuesta concreta** (qué estimados se
   finalizarían, de qué OT — marcando si esa OT ya está Cerrada — y qué
   quedó bloqueado y por qué) y **esperar su confirmación explícita antes
   de escribir nada**. No se ejecuta ningún paso 4 sin ese OK.
4. Ejecutar de a uno, revisando la captura de cada paso antes de seguir con
   el siguiente:
   - `python -m modules.ordenes_trabajo.cerrar_ot finalizar-estimado <numero_ot> <numero_estimado>`
     para cada estimado aprobado.
5. Si algún paso sale bloqueado/rechazado, **parar y reportar el motivo
   real** — no reintentar a ciegas. Ver "Notas del flujo de cierre de OT"
   en el README (causas conocidas: items sin O.C., desfasaje de
   imputaciones).

**Manejo de errores:**
- Si `listar-candidatos-estimados` no encuentra estimados: correr el
  ingest de `estimados_costos` primero.
- Un estimado que pasa el chequeo en vivo pero que Advertys rechaza igual
  al `finalizar-estimado`: mismo caso conocido de desfasaje de
  imputaciones documentado en el README — se corrige a mano en Advertys,
  no con este flujo.

**Salida esperada:** un reporte final de qué estimados se finalizaron, qué
quedó bloqueado (y por qué), y dónde están las capturas de cada paso
(`exploracion/screenshots/`, prefijo `est_`). Este workflow nunca cierra
una OT — si de paso se quiere revisar si alguna OT quedó lista para
cerrar, correr `cerrar_pendientes.md` por separado.
