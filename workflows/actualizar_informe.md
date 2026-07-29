# Actualizar un informe existente

**Para refrescar todos los módulos de una, no uno puntual:** usar
`python -m tools.actualizar_todo` en su lugar (ver skill
`refresh-dashboard`) — exporta en vivo desde Advertys y carga los 7
módulos automatizados de una sola pasada. Este workflow es para el caso
manual/puntual: un módulo a la vez, con un Excel que Javier ya tiene a
mano (incluye siempre a IIBB, que quedó deliberadamente fuera de la
automatización).

**Objetivo:** cargar un export nuevo de Advertys en un módulo ya armado y
dejar el informe HTML actualizado con los datos más recientes.

**Cuándo usar:** Javier pide algo como "cargá el último export de Compras"
o "regenerá el informe de Facturas".

**Inputs requeridos:**
- Módulo destino (`ordenes_trabajo` | `compras` | `facturas` |
  `estimados_costos` | `ordenes_compra` | el que corresponda — ver tabla de
  módulos en el README)
- Ruta al archivo `.xlsx` exportado de Advertys

**Caso especial — Pendientes (`modules/pendientes/`):** no tiene
`ingest.py` propio, cruza `ordenes_trabajo` + `estimados_costos` +
`ordenes_compra_produccion`. Para que quede al día hace falta correr el
`ingest.py` de esos tres módulos primero y recién después
`python -m modules.pendientes.generate_html_report` (sin paso 1 propio).

**Tools a usar (en este orden, siempre parado en la raíz del proyecto):**

1. `python -m modules.<modulo>.ingest "<ruta al xlsx>"` — parsea el Excel y
   hace upsert en `advertys.db` (tabla `<modulo>`), por la clave única del
   módulo (ver `modules/<modulo>/config.py`).
2. `python -m modules.<modulo>.generate_html_report` — regenera
   `informes/informe_<modulo>.html`, sobrescribiendo el archivo anterior
   (no se acumulan versiones viejas).
3. `python tools/screenshot.py informes/informe_<modulo>.html <modulo> --mode all`
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

**Salida esperada:** `informes/informe_<modulo>.html` actualizado, listo
para abrir con doble click o compartir por link de OneDrive.
