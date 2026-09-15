# Actualizar un informe existente

**Para refrescar todos los módulos de una, no uno puntual:** usar
`python -m tools.actualizar_todo` en su lugar (ver skill
`refresh-dashboard`) — exporta en vivo desde Advertys y carga los 8
módulos automatizados de una sola pasada. Este workflow es para el caso
manual/puntual: un módulo a la vez.

**IIBB tiene su propio `tools/actualizar_iibb.py` (desde 2026-08-18)** —
queda fuera de `tools.actualizar_todo` porque su export es mucho más
pesado (~22.700 filas vs. cientos en el resto) y se pide actualizar con
menos frecuencia, así que se dispara aparte, a demanda (ver "Caso especial
— IIBB" más abajo).

**Objetivo:** cargar un export nuevo de Advertys en un módulo ya armado y
dejar el informe HTML actualizado con los datos más recientes.

**Cuándo usar:** Javier pide algo como "cargá el último export de Compras"
o "regenerá el informe de Facturas".

**Inputs requeridos:**
- Módulo destino (`ordenes_trabajo` | `compras` | `facturas` |
  `estimados_costos` | `ordenes_compra` | `iibb` | el que corresponda — ver
  tabla de módulos en el README)
- Ruta al archivo `.xlsx` exportado de Advertys — **excepto para `iibb`**,
  que puede autoexportarse (ver caso especial abajo).

**Caso especial — Pendientes (`modules/pendientes/`):** no tiene
`ingest.py` propio, cruza `ordenes_trabajo` + `estimados_costos` +
`ordenes_compra_produccion`. Para que quede al día hace falta correr el
`ingest.py` de esos tres módulos primero y recién después
`python -m modules.pendientes.generate_html_report` (sin paso 1 propio).

**Caso especial — IIBB (`modules/iibb/`):** el informe de IIBB no depende
solo del export de Imputaciones — también necesita `facturas`,
`ordenes_compra` y `ordenes_publicidad` frescas (para resolver
Proveedor/Monto de cada OC/OP, ver `oc_resolver.py`) y el crawl
`modules/iibb/crawl_oc_por_factura.py` corrido después de refrescar esas
tablas (para tener el N° de OC/OP de cada factura). Hasta 2026-08-18 este
caso especial solo cubría el export+ingest de Imputaciones y dejaba el
resto tal como estuviera en `advertys.db` — eso hacía que facturas con
monto deducible cargado se mostraran sin el detalle desplegable de OC/OP,
sin ningún aviso (caso real: factura 000500000556).

Por eso, si Javier pide "actualizá IIBB" sin pasar un xlsx puntual, correr
`python -m tools.actualizar_iibb` — encadena los 5 pasos en el orden que
importa (facturas/ordenes_compra/ordenes_publicidad → export+ingest de
Imputaciones → crawl de OC/OP → regenerar el informe) y al final avisa por
número de factura si alguna quedó sin detalle de OC/OP (no debería pasar
salvo que Advertys esté caído o una OC/OP referenciada todavía no exista
en `ordenes_compra`/`ordenes_publicidad`). Ver el docstring de
`tools/actualizar_iibb.py` para el detalle de cada paso.

Solo si Javier ya trae un xlsx puntual de Imputaciones (o si
`tools/actualizar_iibb.py` falla en el paso de export y hace falta
diagnosticar a mano): correr `python -m modules.iibb.export` — hace login
y descarga el export actual a `exploracion/iibb_export.xlsx` (login +
Consultas > Contabilidad > Imputaciones + filtro "Todos" + descarga, todo
vía Playwright, mismo patrón que los demás `export.py`). Usar esa ruta
como el xlsx del paso 1, y correr aparte los demás pasos de
`tools/actualizar_iibb.py` (facturas/ordenes_compra/ordenes_publicidad,
crawl, regenerar informe) para no dejar nada pendiente. El script de
export corta con `ExportError` si Advertys cambió el ID del combo de
Filtro y no logra confirmar que quedó en "Todos" (ver comentario en el
código — ya pasó una vez, el 2026-08-12, que el botón se encontraba pero
el filtro no cambiaba y el export salía silenciosamente incompleto). Si
corta así, hay que reabrir Imputaciones a mano (`python -m
modules.iibb.explore`, revisa la captura `iibb_01_listado.png`) y
actualizar el ID en `modules/iibb/export.py`.

**Tools a usar (en este orden, siempre parado en la raíz del proyecto):**

1. `python -m modules.<modulo>.ingest "<ruta al xlsx>"` — parsea el Excel y
   hace upsert en `advertys.db` (tabla `<modulo>`), por la clave única del
   módulo (ver `modules/<modulo>/config.py`).
2. `python -m modules.<modulo>.generate_html_report` — regenera
   `salida/informe_<modulo>.html`, sobrescribiendo el archivo anterior
   (no se acumulan versiones viejas).
3. `python tools/screenshot.py salida/informe_<modulo>.html <modulo> --mode all`
   — ver `workflows/verificar_informe_visual.md`. Solo hace falta si el
   HTML/CSS cambió en esta sesión; un refresh de datos puro sobre un
   informe que ya se veía bien no necesita repetir la verificación visual
   completa.

**Manejo de errores:**
- `KeyError` en `ingest.py`: Advertys puede haber cambiado nombres de
  columna, o exportar "N°" vs "Nº" con un carácter distinto al que espera
  `COLUMN_MAP` (ya pasó entre Compras y Facturas). Abrir el Excel y
  comparar contra `modules/<modulo>/config.py`.
- Conteo de filas post-ingest sospechosamente bajo: revisar que el export
  se haya hecho con el filtro de la vista en su opción más amplia — cada
  módulo tiene su propio widget de filtro, no todos usan "Abierta/Todas"
  (Facturas, por ejemplo, tiene un combo "Filtro" que por defecto trae
  solo el mes en curso).

**Salida esperada:** `salida/informe_<modulo>.html` actualizado, listo
para abrir con doble click o compartir por link de OneDrive.
