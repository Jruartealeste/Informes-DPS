---
name: cargar-items-estimado
description: Lee el Google Sheet de items que el equipo vinculó a un Estimado en la app ot/ y carga esos items en el Estimado de Costo en Advertys real (rubro Servicios Propios, artículo similar, cantidad y precio), previo OK explícito de Javier. Usar cuando Javier pide "cargá los items del estimado 599", "pasá el sheet al estimado", "creá los items del estimado en Advertys". No crea el encabezado del Estimado (eso es procesar-solicitudes-estimado) ni finaliza estimados.
---

# Cargar los items de un Estimado desde su Google Sheet

El equipo pega el link del sheet (siempre el mismo diseño) en el detalle del
Estimado de la app `ot/`: pestaña, fila inicial y modo de precio. Este skill lo
lee con el conector de Google Drive y lo carga en Advertys con
`informes/modules/estimados_costos/cargar_items_estimado.py`.

Cargar items escribe en Advertys real (cambia el estado del Estimado a
Provisorio y crea un item por fila). No se deshace sin borrar a mano. Solo se
carga con el OK de Javier **en esta conversación, después de ver la tabla**.

Parado en `informes/`, Python: `/c/Users/javie/AppData/Local/Programs/Python/Python312/python.exe`.

## Flujo

```
- [ ] 1. Listar estimados con sheet
- [ ] 2. Leer el sheet y armar la tabla de items
- [ ] 3. Mostrar a Javier y pedir OK
- [ ] 4. Cargar en Advertys
- [ ] 5. Reportar
```

**1.** `python -m modules.estimados_costos.estimados_con_sheet --prod`. Si no hay
el Estimado pedido, es que le falta el link del sheet o el número de Advertys.

**2.** Leer el sheet con `read_file_content` del conector de Drive (el id es el
tramo `/d/<ID>/` del link). Tomar la pestaña indicada desde la fila inicial
(diseño: **B** título, **C** artículo del tarifario, **D** cantidad, **E**
precio, que es el total de la línea). Cortar en la primera fila sin título o en
"Subtotal". Armar un JSON `[{"titulo","articulo","cantidad","precio"}]` en el
scratchpad. Verificar que la suma de E coincida con el subtotal del sheet.

**3.** Mostrar la tabla (título, artículo, cantidad, unitario, total) y el modo
de precio. `cantidad` = cantidad D × unitario E÷D; `total` = cantidad 1 y
precio E. Si Javier cambia un dato, se corrige el JSON; no hay edición en la app.

**4.**

```bash
python -m modules.estimados_costos.cargar_items_estimado <ot> <estimado> <items.json> --modo <cantidad|total>
```

`--modo` es el del sheet (lo imprime `estimados_con_sheet`: "modo de precio: total"
-> `--modo total`). Qué hace el script (regla de Javier, 2026-11-10):
1. Pasa el Estimado a **Provisorio** y espera a ver "Provisorio" en el campo Estado
   (el postback tarda; sin esa espera "Nuevo" no aparece en la grilla).
2. Por cada item, en la pestaña **Items del Estimado**: "Nuevo" -> popup -> "Aceptar"
   -> **"Guardar" del Estimado después de CADA item** (obligatorio, no solo al final).
3. Al final "Guardar y cerrar".

**Retomar tras un fallo a mitad:** los items ya guardados persisten. Mirar la captura
`est_items_cargar_<n>_guardado.png` (grilla y Suma) y volver a correr solo con los
items que faltan (JSON con el resto de la lista); el script detecta que ya está
Provisorio y sigue. No reenviar la lista completa: duplicaría.

Rubro fijo "SERVICIOS PROPIOS Y TARIFARIO". El artículo se busca por la columna C
y se elige la coincidencia exacta; sin coincidencia exacta usa "Otros" (avisa).
Antes de cada "Aceptar" el script verifica que el Total del popup sea igual a E.

**5.** Reportar los items cargados, avisos de artículo y el Sub Total final del
Estimado (captura `exploracion/screenshots/est_items_cargar_<n>_100_guardado.png`).

## Si falla

**No reintentar a ciegas:** pueden quedar items ya cargados. Mirar el Estimado en
Advertys antes de volver a correr (un reintento duplicaría los ya guardados).
