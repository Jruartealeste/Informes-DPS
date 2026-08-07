# Cerrar estimados y OTs listos según Pendientes

**Objetivo:** revisar el informe de Pendientes y cerrar en Advertys los
Estimados de Costo y Órdenes de Trabajo que ya están en condiciones de
cerrarse, sin tocar nada que todavía esté bloqueado.

**Cuándo usar:** Javier pide algo como "cerrá las OTs que ya están listas"
o "revisá qué estimados se pueden finalizar según Pendientes".

**Salvaguarda:** este flujo escribe en Advertys (cambia estados reales de
negocio/facturación). El único script con permiso para eso es
`modules/ordenes_trabajo/cerrar_ot.py` (aprobado por Javier 2026-07-20/21),
con reglas duras ya bloqueadas por código: nunca "Anulado"/"Provisorio",
solo Estimado→Finalizado y OT→Cerrada. Este workflow **no** amplía ese
alcance ni cambia la granularidad de ejecución (un paso por vez, con
revisión intermedia) — solo agrega cómo armar la propuesta antes de
ejecutar.

**Tools a usar (en este orden, siempre parado en la raíz del proyecto):**

1. **Paso obligatorio, no opcional — datos al día:** si `ordenes_trabajo`,
   `estimados_costos` y `ordenes_compra` no se refrescaron en esta misma
   sesión (o Javier no confirma que ya están frescos), correr primero el
   skill `refresh-dashboard` (`python -m tools.actualizar_todo`). El
   semáforo de Pendientes sale de datos locales en `advertys.db`: con datos
   viejos se puede proponer cerrar algo que ya cambió en Advertys real, o
   al revés, no detectar algo que ya está listo. No se avanza al paso 2 sin
   esto.
2. `python -m modules.ordenes_trabajo.cerrar_ot listar-candidatos` — de
   SOLO LECTURA (nunca clickea "Editar" ni "Guardar"). Cruza el semáforo ya
   calculado por `modules/pendientes/generate_html_report.py` con un
   chequeo en vivo (`chequear_estimado_completo`, un solo login/browser
   para todos los estimados no terminales) y devuelve tres listas:
   - OT listas para `cerrar-ot` directamente (todos los estimados y OC ya
     resueltos).
   - Estimados listos para `finalizar-estimado`.
   - Estimados bloqueados, con motivo puntual.
3. **Presentarle a Javier la propuesta concreta** (qué se finalizaría, qué
   OT se cerrarían, qué queda bloqueado y por qué) y **esperar su
   confirmación explícita antes de escribir nada**. No se ejecuta ningún
   paso 4 sin ese OK — esto es lo que Javier definió como modo "proponer y
   confirmar" (no autopilot).
4. Ejecutar de a uno, revisando la salida/captura de cada paso antes de
   seguir con el siguiente (mismo criterio que ya impone `cerrar_ot.py` —
   no se cambia esta granularidad aunque el batch completo ya esté
   aprobado):
   - `python -m modules.ordenes_trabajo.cerrar_ot finalizar-estimado <numero_ot> <numero_estimado>`
     para cada estimado aprobado.
   - `python -m modules.ordenes_trabajo.cerrar_ot cerrar-ot <numero_ot>`
     recién para las OT que ya quedaron con todos los estimados en estado
     terminal (las que ya estaban listas directo, o las que lo quedaron
     tras el paso anterior).
5. Si algún paso sale bloqueado/rechazado (Advertys rechaza la transición,
   o `chequear_estimado_completo` marca un motivo), **parar y reportar el
   motivo real** — no reintentar a ciegas ni improvisar otro click. Ver la
   sección "Notas del flujo de cierre de OT" en el README para causas
   conocidas (items sin O.C., sin factura Contabilizada, desfasaje de
   imputaciones).

**Manejo de errores:**
- Si `listar-candidatos` no encuentra OT abiertas: correr el ingest de
  `ordenes_trabajo` primero (ver workflow `actualizar_informe.md`).
- Un estimado que pasa `chequear_estimado_completo` pero que Advertys
  rechaza igual al intentar `finalizar-estimado`: es el caso conocido de
  desfasaje de imputaciones (ver README) — no es una falla del script, es
  una condición necesaria-pero-no-suficiente. Se corrige a mano en
  Advertys, no con este flujo.

**Salida esperada:** un reporte final de qué se cerró, qué quedó bloqueado
(y por qué), y dónde están las capturas de cada paso
(`exploracion/screenshots/`, prefijo `ot_`/`est_`). Cualquier necesidad
fuera de Estimado→Finalizado / OT→Cerrada (reasignar OC, corregir
imputaciones) sigue siendo manual en Advertys.
