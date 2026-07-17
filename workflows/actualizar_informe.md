# Actualizar un informe existente

**Objetivo:** cargar un export nuevo de Advertys en un módulo ya armado y
dejar el informe HTML actualizado con los datos más recientes.

**Cuándo usar:** Javier pide algo como "cargá el último export de Compras"
o "regenerá el informe de Facturas".

**Inputs requeridos:**
- Módulo destino (`ordenes_trabajo` | `compras` | `facturas` | el que
  corresponda — ver tabla de módulos en el README)
- Ruta al archivo `.xlsx` exportado de Advertys

**Tools a usar (en este orden, siempre parado en la raíz del proyecto):**

1. `python -m modules.<modulo>.ingest "<ruta al xlsx>"` — parsea el Excel y
   hace upsert en `advertys.db` (tabla `<modulo>`), por la clave única del
   módulo (ver `modules/<modulo>/config.py`).
2. `python -m modules.<modulo>.generate_html_report` — regenera
   `informe_<modulo>.html` en la raíz, sobrescribiendo el archivo anterior
   (no se acumulan versiones viejas).
3. `python tools/screenshot.py informe_<modulo>.html <modulo> --mode all`
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

**Salida esperada:** `informe_<modulo>.html` actualizado en la raíz,
listo para abrir con doble click o compartir por link de OneDrive.
