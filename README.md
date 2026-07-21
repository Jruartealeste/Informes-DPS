# Pipeline Advertys → Informes dinámicos

Esqueleto funcional para armar informes que siempre reflejan los datos más
recientes que exportaste de Advertys, sin depender de que Advertys tenga una
API propia. La idea es ir sumando un módulo por vez (mismo patrón, misma
base `advertys.db`, tablas separadas) y más adelante cruzarlos entre sí.

```
Excel exportado de Advertys
        │  (modules/<modulo>/ingest.py)
        ▼
   Base local (SQLite, una tabla por módulo)
        │
        ├──► modules/<modulo>/generate_html_report.py  →  informes/informe_*.html
        └──► api.py                                       →  API local (JSON)
```

**El informe es un HTML, no un Excel.** Cada módulo genera un único archivo
`.html` autocontenido (sin CDN, sin conexión a internet) que se abre con
doble click y se imprime a PDF desde el navegador (botón "Imprimir /
Guardar PDF" en el propio informe, o Ctrl+P). Cada corrida sobreescribe el
mismo archivo — no se acumulan versiones viejas. Como la carpeta del
proyecto vive en OneDrive, alcanza con compartir el link de OneDrive al
`.html` para que se vea siempre actualizado.

**Entrypoint real: `informes/dashboard.html`.** Agrupa todos los
`informes/informe_*.html` bajo un único sidebar de navegación (estilo
dashboard, no un admin template con build — ver "Identidad visual" más
abajo). Lo genera `generate_dashboard.py` desde la raíz y también se abre
con doble click; cada informe individual sigue siendo autocontenido y
abrible suelto, el shell solo agrega navegación por encima. Todos los
`.html` que arma el pipeline (dashboard + informes) viven juntos en
`informes/` porque el sidebar los carga en un `<iframe>` por nombre de
archivo relativo — tienen que estar en la misma carpeta para que esa
referencia funcione.

Los `generate_report.py` (Excel, con `openpyxl`) siguen en el repo por si
hace falta algo puntual, pero ya no son el entregable real — no se
regeneran de forma proactiva.

## Estructura de carpetas

```
Informes/
├── db.py               # conexion SQLite compartida (get_connection())
├── common.py            # normalizar_fecha / normalizar_numero, compartidas
├── html_report.py        # shell HTML/CSS + charts SVG + tablas + dashboard_shell, compartido
├── generate_dashboard.py # genera informes/dashboard.html (sidebar + iframe sobre los informe_*.html)
├── api.py                # API de solo lectura (hoy: Ordenes de Trabajo)
├── assets/
│   └── aleste-logo.svg   # isotipo de la agencia, fuente del LOGO_SVG embebido en html_report.py
├── modules/
│   ├── ordenes_trabajo/
│   │   ├── config.py               # mapeo de columnas y rutas
│   │   ├── ingest.py                 # carga el Excel + esquema de la tabla
│   │   ├── generate_html_report.py   # genera informes/informe_dinamico.html (el informe real)
│   │   ├── generate_report.py        # genera .xlsx (legacy, no se usa mas)
│   │   ├── explore.py                # relevamiento en vivo (Playwright)
│   │   └── generar_ejemplo.py        # genera un Excel de prueba
│   ├── compras/
│   │   ├── config.py
│   │   ├── ingest.py
│   │   ├── generate_html_report.py
│   │   ├── generate_report.py
│   │   └── explore.py
│   ├── facturas/
│   │   ├── config.py
│   │   ├── ingest.py
│   │   ├── generate_html_report.py
│   │   ├── generate_report.py
│   │   └── explore.py
│   ├── estimados_costos/     # config.py, ingest.py, explore.py -- sin informe propio
│   ├── ordenes_compra/       # idem, Orden Compra Produccion -- sin informe propio
│   └── pendientes/
│       └── generate_html_report.py  # cruza ordenes_trabajo + estimados_costos + ordenes_compra_produccion
├── exploracion/          # capturas/HTML/Excel de cada relevamiento en vivo
└── informes/             # todos los .html que arma el pipeline, en una sola carpeta
    ├── dashboard.html            # entrypoint: sidebar + iframe sobre los informes (generate_dashboard.py)
    ├── informe_pendientes.html   # salida del modulo Pendientes (OT abiertas + detalle)
    ├── informe_dinamico.html     # salida del modulo Ordenes de Trabajo
    ├── informe_compras.html      # salida del modulo Compras
    ├── informe_compras_slides.html # salida del modulo Compras (formato presentacion)
    └── informe_facturas.html     # salida del modulo Facturas
```

Cada módulo nuevo se suma como una carpeta más dentro de `modules/`, con los
mismos archivos (`config.py`, `ingest.py`, `generate_html_report.py`,
`explore.py`), reutilizando `db.py`, `common.py` y `html_report.py` de la raíz.

## Módulos armados hasta ahora

| Módulo | Carpeta | Tabla en `advertys.db` | Informe |
|---|---|---|---|
| Órdenes de Trabajo | `modules/ordenes_trabajo/` | `ordenes_trabajo` | `informes/informe_dinamico.html` |
| Compras (Administración > Compras) | `modules/compras/` | `compras` | `informes/informe_compras.html` |
| Facturas (Consultas > Facturación > Facturas) | `modules/facturas/` | `facturas` | `informes/informe_facturas.html` |
| Estimados de Costo (Cuentas y Producción > Estimado Costos) | `modules/estimados_costos/` | `estimados_costos` | (sin informe propio, alimenta Pendientes) |
| Órdenes de Compra Producción (Ordenes de Compra > O.C. Producción) | `modules/ordenes_compra/` | `ordenes_compra_produccion` | (sin informe propio, alimenta Pendientes) |
| OCs Pendientes de Generar (Cuentas y Producción, shortcut) | `modules/oc_pendientes_generar/` | `oc_pendientes_generar` | (sin informe propio, alimenta Pendientes) |
| Estim.Pendientes Facturar (Cuentas y Producción, shortcut) | `modules/estimados_pendientes_facturar/` | `estimados_pendientes_facturar` | (sin informe propio, alimenta Pendientes) |
| Items pendientes de O.C. (crawl item-level, sin Excel) | `modules/ordenes_trabajo/crawl_items_pendientes.py` | `items_pendientes_oc` | (sin informe propio, alimenta Pendientes) |
| **Pendientes** (cruce OT abiertas + Estimados + OC + los 3 anteriores) | `modules/pendientes/` | *(no ingesta, cruza las 6 tablas de arriba)* | `informes/informe_pendientes.html` |

Próximo módulo: a definir (avisale a Claude Code cuál seguís usando más).

### Notas del módulo Pendientes (y sus fuentes Estimados de Costo / Órdenes de Compra)

- Objetivo: para cada Orden de Trabajo **abierta**, mostrar qué Estimados de
  Costo y qué Órdenes de Compra tiene cargados adentro — para poder revisar
  de un vistazo por qué sigue abierta. Es la primera pestaña del dashboard.
- **Cadena de vínculos** (ningún export trae las 3 cosas juntas, hay que
  cruzarlas en `modules/pendientes/generate_html_report.py`):
  `ordenes_trabajo.numero_ot` ← `estimados_costos.numero_ot` (columna directa
  del export, sin nulos) ← `ordenes_compra_produccion.numero_estimado`
  (**no** viene como columna: se parsea con regex `^(\d+)-` del texto libre
  de la columna "Estimado Costos" del export, ej.
  `"508-Realización de retratos..."` → `508`; confirmado 0 filas fuera de
  ese patrón en el relevamiento real).
- Solo se releva **Orden Compra Producción**, no "O.C. Gastos" (gasto interno
  de agencia, sin relación a OT/cliente) ni "Orden Compra Generica" (no
  expone el vínculo con el Estimado en su grilla — sería un cuarto salto sin
  columna directa).
- **El shortcut del menú lateral "Estimado Costos" (bajo "Cuentas y
  Producción") dispara por defecto un formulario de alta ("Nuevo Estimado")
  en vez de abrir el listado** — se probó una vez durante el relevamiento
  (sin guardar nada) y se descartó. Por eso `modules/estimados_costos/explore.py`
  y `modules/ordenes_compra/explore.py` navegan por **URL directa**
  (`ViewID=<Entidad>_ListView&ObjectClassName=DPS_SAS_SR.Module.<Entidad>`)
  en vez de clickear el árbol de navegación, igual que ya hacía
  `modules/ordenes_trabajo/explore.py`.
- El combo "Filtro" de estas dos vistas no es el primer `_Cb_B-1` de la
  toolbar como en Compras/Facturas: "Estimado Costos" tiene además un combo
  "Ver" (Básico/Totales) *antes* del de Filtro. Los `explore.py` de estos
  módulos ubican el combo correcto buscando el `<input>` cuyo valor actual
  es `"Mes Actual"` (el default de ambas vistas) en vez de asumir posición
  fija.
- Tercer símbolo de grado distinto en el mismo proyecto: "N° Estimado" /
  "N° OT" usan `°` (U+00B0), pero "Nº O.C." usa `º` (U+00BA, ordinal
  masculino) — mismo gotcha que Compras/Facturas, revisar bytes exactos si
  un mapeo nuevo tira `KeyError`.
- `renta_teorica`/`renta_real` (tabla `ordenes_trabajo`) son **porcentajes**
  de rentabilidad (rango real relevado: 0–158%), no montos — confirmado
  contra el detalle de OT en Advertys (se muestran con "%" en la UI). El
  informe de Pendientes los formatea como `"49.5%"`; si se suman entre OTs
  no da un número financiero con sentido (por eso el stat tile usa
  *promedio*, no suma).
- El informe es **estático** (sin el filtro de período dinámico de los otros
  módulos): "pendientes" es una foto del estado actual, no algo que tenga
  sentido recortar por rango de fechas. El drill-down por OT usa
  `<details>/<summary>` nativo de HTML (sin JS) para expandir/colapsar, con
  una regla `@media print` que fuerza todo el contenido visible al imprimir
  sin importar qué quedó colapsado en pantalla (mismo espíritu que el tope
  de 50 filas de `renderTable` en `html_report.py`).
- **Semáforo amarillo "Bloqueada para cierre" (confirmado con Javier,
  2026-07-21):** un Estimado de Costos no se puede pasar a `Finalizado` si
  (a) algún item tiene Proveedor cargado pero no tiene una Orden de Compra
  emitida, o (b) el estimado todavía tiene saldo pendiente de facturar. En
  vez de reconstruir esta lógica a mano item por item (algo que sí hay que
  hacer si se quiere chequear un estimado puntual en vivo, ver
  `modules/ordenes_trabajo/cerrar_ot.py chequear-estimado`), Advertys ya
  expone **dos vistas propias** que resuelven exactamente esto a granel:
  el shortcut **"OCs Pendientes de Generar"** (`modules/oc_pendientes_generar/`,
  ViewID=`EstimadoDetalle_ListView_OC_Pendientes`) y **"Estim.Pendientes
  Facturar"** (`modules/estimados_pendientes_facturar/`,
  ViewID=`EstimadoCostos_ListView_Pendiente_de_Facturar`), ambas bajo
  "Cuentas y Producción". Una OT queda marcada con el badge amarillo
  "Bloqueada" (tooltip con el motivo puntual) si alguno de sus estimados
  aparece en cualquiera de las dos.
  - Ninguna de las dos vistas trae una columna de item/ID estable entre
    corridas (una fila = un item o un estimado, sin identificador que
    sobreviva a que se resuelva el pendiente): por eso sus `ingest.py`
    **reemplazan la tabla entera** (`DELETE` + `INSERT`) en vez de hacer
    upsert por clave como el resto de los módulos — son snapshots de "qué
    falta ahora mismo", y un ítem/estimado que se resuelve tiene que
    desaparecer de la base local, no quedar marcado para siempre.
  - Mismo gotcha de símbolo de grado que el resto del proyecto, y esta vez
    **dentro del mismo archivo**: en el export de "Estim.Pendientes
    Facturar", "N° Estimado"/"N° OT" usan `°` (U+00B0) pero "Nº Cliente"
    usa `º` (U+00BA) — confirmado byte a byte.
  - Ninguna de las dos vistas tuvo, en el relevamiento real, un combo de
    filtro por período (ya vienen filtradas de por sí a "lo pendiente
    ahora"); si Advertys le agrega uno en el futuro y las filas parecen
    menos de las esperadas, revisar como en Facturas/Estimado Costos.
- **"OCs Pendientes de Generar" es más angosta de lo que su nombre sugiere
  (confirmado con Javier, 2026-07-21):** esa vista de Advertys solo expone
  casos en un estado YA avanzado. Prueba real: el Estimado 472 (OT 272,
  estado "Provisorio") tiene un item de rubro "SERVICIOS/PRODUCTOS DE
  TERCEROS" con Costo real de $2.400.000, sin Proveedor ni O.C. cargados
  todavía — y esa vista del sistema (que ese día tenía 4 filas en total en
  todo el sistema) no lo lista. Javier quería detectarlo antes: desde el
  momento en que a un item se le asigna un Proveedor (o incluso antes, si
  ya es tercerizado con costo real y todavía no tiene proveedor).
  - Advertys **no tiene** una vista de lista para "Items del Estimado" de
    todos los estimados a la vez (se relevó buscando en "Cuentas y
    Producción" y no existe un shortcut así) — el detalle de items solo se
    ve abriendo cada Estimado de Costos individualmente, pestaña "Items
    del Estimado".
  - Por eso se sumó `modules/ordenes_trabajo/crawl_items_pendientes.py`:
    a diferencia de todos los demás módulos, **no tiene `ingest.py`** (no
    hay Excel que parsear) — navega Advertys en vivo con Playwright,
    estimado por estimado, **solo para los estimados NO terminales de OT
    abiertas** (ver `ESTIMADO_ESTADOS_TERMINALES` en
    `modules/pendientes/generate_html_report.py`: un estimado terminal ya
    pasó el chequeo de Advertys para llegar ahí, no hace falta re-revisarlo).
    Eso acota el barrido a ~20 estimados en vez de los 500+ del sistema,
    tarda unos minutos (no segundos, es solo-lectura contra Advertys real
    con una navegación por estimado) y llena la tabla `items_pendientes_oc`
    (mismo criterio "reemplazar entera" que `oc_pendientes_generar`/
    `estimados_pendientes_facturar`, ver arriba). Marca dos motivos:
    `sin_oc` (Proveedor cargado, O.C. vacía — lo que pidió Javier) y
    `sin_proveedor` (rubro tercerizado con Costo > 0, Proveedor todavía
    vacío — señal más temprana encontrada en el relevamiento).
    Uso: `python -m modules.ordenes_trabajo.crawl_items_pendientes`.
  - `modules/pendientes/generate_html_report.py` combina esta tabla con
    `oc_pendientes_generar` (`_combinar_items_pendientes`, dedup por
    `(numero_estimado, detalle)`): el crawl cubre más temprano pero solo
    OT abiertas con estimados no-terminales; la vista del sistema cubre
    todo el histórico pero solo casos avanzados — se complementan, no se
    reemplazan.

- **Tercera causa de bloqueo, agregada 2026-07-21 (confirmado con Javier):**
  una O.C. que no está en estado `Utilizada`/`Anulada` (`OC_ESTADOS_RESUELTOS`)
  y todavía tiene `saldo > 0` también bloquea el cierre — aunque el Estimado
  ya esté en un estado terminal. Caso real que motivó el fix: OT 278, Estimado
  "Facturado manual" (ya facturado al cliente) con la O.C. #198 a SADAIC en
  "Autorizada" con $677.000 de saldo sin resolver con el proveedor. Antes de
  este fix esa OT quedaba en semáforo amarillo ("En curso") pero **no
  contaba** en ningún tile del informe (ni "Listas para cerrar" ni
  "Bloqueadas para cierre" ni "Sin estimados") — los tres tiles sumaban 22
  en vez de las 23 OT abiertas reales. Ver `saldo_oc_pendiente` /
  `_nota_oc_pendiente` en `modules/pendientes/generate_html_report.py`.
  **Antes de dar por buenos los tiles de un informe nuevo, verificar que
  las categorías mutuamente excluyentes sumen el total** — este bug pasó
  desapercibido porque cada tile individualmente parecía razonable.

### Notas del flujo de cierre de OT (`cerrar_ot.py`, `ver_imputaciones.py`)

- **Regla de negocio confirmada por Javier (2026-07-21):** un Estimado de
  Costos no se puede pasar a `Finalizado` si (a) alguno de sus items tiene
  Proveedor cargado pero no tiene una Orden de Compra vigente emitida, o
  (b) no tiene ninguna factura en estado `Contabilizada` en la pestaña
  Facturas. Una OT que tenga algún estimado en ese estado se considera
  "amarilla": abierta pero bloqueada para cerrar.
  `cerrar_ot.py` ahora chequea esto en modo lectura (`chequear_estimado_completo`,
  pestañas "Items del Estimado" → columnas `Proveedor`/`N° O.C.`, "Ordenes
  Compra" → columna `Estado` para descartar O.C. `Anulada`, "Facturas" →
  columna `Estado`) **antes** de clickear "Editar", y aborta con el motivo
  puntual en vez de intentar la transición a ciegas. Selectores de grilla
  verificados en vivo contra OT 235/Estimado 439: las grillas son
  `ASPxGridView` de DevExpress (`table[id*='DXMainTable']`, headers en
  `td[class*='dxgvHeader']` — OJO, no es la clase exacta `dxgvHeader`, esta
  instalación usa `dxgvHeader_Office2010Blue` — y filas en
  `tr[id*='DXDataRow']`, alineadas 1 a 1 por posición con el header).
  Comando de diagnóstico standalone, sin tocar nunca Editar/Guardar:
  `python -m modules.ordenes_trabajo.cerrar_ot chequear-estimado <numero_ot> <numero_estimado>`.
  **Ojo:** esta regla cubre las dos causas más comunes pero no es
  exhaustiva — es una condición necesaria, no suficiente (ver el caso real
  de desfasaje de imputaciones más abajo, que un estimado con O.C. vigente
  y factura contabilizada puede seguir bloqueado igual).
- Cuando Advertys rechaza `Estimado -> Finalizado` con el mensaje **"Los
  importes tercerizados no estan CANCELADOS"**, la causa no siempre está a
  la vista en "Items del Estimado": hay que abrir la pestaña **Imputaciones**
  del estimado (solo lectura, `python -m modules.ordenes_trabajo.ver_imputaciones
  <numero_ot> <numero_estimado>`) y mirar las filas de las cuentas
  `510010`/`510011` ("COSTO PRODUCCIÓN DE TERCEROS") — son los importes
  tercerizados que el sistema chequea, y tienen que estar compensados
  (Debe = Haber) por OC.
- **Caso real confirmado por Javier (OT 235 / Estimado 439, 2026-07-21):**
  cuando se **anula una Orden de Compra y se la reemplaza por otra** (acá,
  OC 122 anulada → reemplazada por OC 149, mismo ítem "Microfonos x 3
  Jornadas"), Advertys deja la imputación del lado venta (cuenta
  `411040-VTA SERVICIOS DE TERCEROS (OC)`) referenciando todavía la OC
  vieja (122), mientras que el lado costo (`510010`) ya quedó con la OC
  nueva (149) — es un desfasaje de sistema, no un dato mal cargado por
  el usuario. Ese desfasaje entre OC del lado venta y OC del lado costo
  parece ser lo que le impide a Advertys "cancelar" el importe tercerizado
  y bloquea la finalización del estimado.
- Este pipeline **no tiene** (ni va a agregar sin aprobación explícita)
  un script que edite imputaciones o reasigne OCs — es una corrección
  contable, no una transición de estado simple como las que
  `cerrar_ot.py` tiene permitido tocar (ver salvaguarda de solo-lectura en
  `CLAUDE.md`). La corrección de este tipo de desfasaje se hace a mano en
  Advertys.

### Notas del módulo Compras

- En Advertys el menú es "Compras (Mesa de Entrada)", bajo el grupo
  **Administracion** del árbol de navegación (no tiene URL directa, es un
  nodo de TreeView — ver `modules/compras/explore.py`). La vista real es
  `ViewID=DocumentoProveedor_ListView`.
- El Excel trae **dos columnas literalmente llamadas "Importe s/IVA"**: la
  primera siempre positiva, la segunda con signo contable (negativa en
  notas de crédito/anulaciones). Se resuelve a mano en
  `modules/compras/ingest.py` reasignando la segunda a
  `importe_sin_iva_signado` antes de aplicar el resto del mapeo.
- No hay una columna con clave única propia: "Nº Asiento" se reinicia por
  tipo/período. La clave real usada es la combinación
  `(TA, Nº Asiento, TR, Nº Referencia)`, armada como `clave_compra`.

### Notas del módulo Facturas

- En Advertys es "Facturas" bajo la carpeta **Facturacion** del grupo
  **Consultas** — también un nodo de TreeView sin URL directa, pero con un
  nivel intermedio (hay que expandir la carpeta antes de ver la hoja). Ojo:
  existen varios nodos llamados "Facturacion"/"Facturas" en el menú completo
  (Administración tiene el suyo para carga manual), por eso
  `modules/facturas/explore.py` navega por **ID exacto del árbol**, no por
  texto — ver comentarios ahí si Advertys cambia el layout del menú.
- Esta vista **no usa el filtro Abierta/Todas** de OT y Compras: tiene su
  propio combo "Filtro" con opciones Año Actual/Todos/Mes Actual (default,
  ¡solo trae el mes en curso!)/Año Anterior/Mes Anterior. Hay que ponerlo en
  "Todos" antes de exportar si se quiere el histórico completo.
- Misma clave compuesta que Compras: `(TA, Nº Asiento, TR, Nº Referencia)`
  → `clave_factura`. Pero ojo, Advertys exporta el símbolo "N°/Nº" distinto
  según el módulo (Compras usa `º` masculino, Facturas usa `°` de grados) —
  revisar bytes UTF-8 exactos si un mapeo nuevo tira `KeyError`.
- "Anunciante" y "Cliente" son cosas distintas acá (a diferencia de Órdenes
  de Trabajo, donde el anunciante es directamente el cliente): Anunciante es
  la marca/unidad de negocio, Cliente es la razón social facturada. Para
  cruces futuros, la entidad facturable real es `Cliente` + `Cuit`.

## 1. Instalar dependencias

```bash
pip install -r requirements.txt
```

## 2. Probar con datos de ejemplo (opcional, para ver que todo funciona)

```bash
python -m modules.ordenes_trabajo.generar_ejemplo             # crea un Excel de prueba
python -m modules.ordenes_trabajo.ingest sample_data/advertys_export_ejemplo.xlsx
python -m modules.ordenes_trabajo.generate_html_report         # genera informes/informe_dinamico.html
```

Borrá `advertys.db` y la carpeta `sample_data/` cuando quieras arrancar en limpio
con tus datos reales.

Todos los comandos se corren **desde la raíz del proyecto** (por eso el
`-m` con el path completo del módulo, en vez de `python archivo.py`).

## 3. Esquema real (ya verificado contra Advertys)

`modules/ordenes_trabajo/config.py` ya está ajustado contra un export real
de "Orden Trabajo" (ALESTE ADS S.A.). Las columnas que trae Advertys son:

| Excel de Advertys | Nombre interno |
|---|---|
| Nro OT | `numero_ot` (clave única) |
| Id | `id_advertys` |
| Negocio | `negocio` |
| Anunciante | `anunciante` (el "cliente") |
| Marca | `marca` |
| Producto | `producto` |
| Resumen | `resumen` |
| F.Abierta | `fecha_abierta` |
| F.Cerrada | `fecha_cerrada` |
| Abierta por... | `responsable` |
| Equipo | `equipo` |
| Estado | `estado` |
| Renta Teorica | `renta_teorica` |
| Renta Real | `renta_real` |

No hay columnas de "Monto Facturado/Presupuestado": la rentabilidad se mide
con Renta Teórica/Real. Si Advertys agrega o renombra columnas, ajustá
`COLUMN_MAP` en `modules/ordenes_trabajo/config.py` y sumalas en
`modules/ordenes_trabajo/ingest.py` (`SCHEMA`) y en `generate_html_report.py`
si las querés reflejadas en el informe.

## 4. Uso normal (con tu export real)

```bash
python -m modules.ordenes_trabajo.ingest "ruta/a/tu/export.xlsx"
python -m modules.ordenes_trabajo.generate_html_report

python -m modules.compras.ingest "ruta/a/tu/export.xlsx"
python -m modules.compras.generate_html_report

python -m modules.facturas.ingest "ruta/a/tu/export.xlsx"
python -m modules.facturas.generate_html_report

python -m modules.estimados_costos.ingest "ruta/a/tu/export.xlsx"
python -m modules.ordenes_compra.ingest "ruta/a/tu/export.xlsx"
python -m modules.oc_pendientes_generar.ingest "ruta/a/tu/export.xlsx"
python -m modules.estimados_pendientes_facturar.ingest "ruta/a/tu/export.xlsx"
python -m modules.ordenes_trabajo.crawl_items_pendientes   # sin Excel, navega Advertys en vivo (tarda unos minutos)
python -m modules.pendientes.generate_html_report   # cruza las 6 tablas de arriba, no tiene ingest propio
```

Cada vez que tengas un export nuevo, repetís esos dos comandos del módulo
que corresponda y el informe (`.html`) queda actualizado con todo lo último
— no hace falta borrar nada, los registros existentes se actualizan por su
clave única. Después abrís `informes/dashboard.html` (o el
`informes/informe_*.html` suelto) con doble click y usás el botón
"Imprimir / Guardar PDF" (o Ctrl+P) si necesitás mandárselo a un cliente.

Para que `informes/informe_pendientes.html` refleje datos frescos hace
falta que las tres tablas que cruza estén actualizadas: `ordenes_trabajo`,
`estimados_costos` y `ordenes_compra_produccion` (los tres primeros
`ingest.py` de arriba) — recién ahí correr
`python -m modules.pendientes.generate_html_report`.

`informes/dashboard.html` en sí casi nunca hace falta regenerarlo — solo
apunta por nombre de archivo a cada `informe_*.html` en esa misma carpeta,
así que una corrida normal de `ingest.py` + `generate_html_report.py` ya se
refleja solo la próxima vez que se abra. Correr `python
generate_dashboard.py` de nuevo solo hace falta si se suma o saca un
módulo del sidebar.

## 5. Consultar en vivo con la API (opcional)

```bash
python api.py
```

Deja un servidor local en `http://localhost:5000` con endpoints de solo
lectura sobre Órdenes de Trabajo (por ahora es el único módulo expuesto):

- `GET /ordenes?anunciante=...&estado=...&responsable=...&equipo=...`
- `GET /resumen/por-anunciante`
- `GET /resumen/por-mes`

> Nota técnica: usé **Flask** porque es lo que tenía disponible para probar
> este esqueleto sin acceso a internet. Si preferís FastAPI (da lo mismo
> para este caso, es más una preferencia de estilo), es un cambio chico:
> `pip install fastapi uvicorn` y reescribir `api.py` con esas librerías —
> se lo podés pedir a Claude Code directamente.

## 6. Automatizar

Mientras el export de Advertys sea manual, lo más simple es dejarte un
alias o script de una línea que corra `ingest.py` + `generate_html_report.py`
del módulo que corresponda después de exportar. Si en algún momento
Advertys permite programar el export a una carpeta fija, se puede
automatizar del todo con:

- **Windows**: Task Scheduler ejecutando un `.bat` con esos dos comandos
- **Linux/Mac**: un cron job, por ejemplo cada mañana a las 8:00

## 7. Conectar esto con Claude Code

Con este proyecto abierto como carpeta de trabajo en Claude Code, alcanza con
pedirle en lenguaje natural cosas como *"cargá el último export de Compras y
regenerá el informe"* o *"agregá una hoja al informe con el top 10 de
proveedores"* — Claude Code puede correr los scripts y editarlos directamente.

Si además querés que Claude Code consulte la base sin pasar por los scripts
(por ejemplo para responder preguntas puntuales tipo *"¿cuánto compramos
en abril?"*), podés conectar un servidor MCP de SQLite:

```bash
claude mcp add sqlite -- npx -y mcp-server-sqlite --db-path ./advertys.db
```

Con eso Claude Code puede escribir y ejecutar sus propias consultas SQL
directamente sobre `advertys.db` (que ya tiene una tabla por módulo).

## 8. Cuando esto se te quede chico

Si más de una persona necesita consultar al mismo tiempo, o el volumen crece
mucho, el único archivo que hay que tocar es `db.py`: cambiar SQLite por
Postgres es un cambio contenido (la lógica de cada `ingest.py`, `api.py` y
`generate_html_report.py` no cambia).

## Estructura de archivos compartidos

| Archivo | Qué hace |
|---|---|
| `db.py` | Conexión compartida a la base SQLite (`get_connection()`) |
| `common.py` | Normalización de fechas/números, compartida entre módulos |
| `html_report.py` | Page shell + CSS (claro/oscuro/print), stat tiles, gráficos SVG con tooltip, tablas y `dashboard_shell()` (sidebar + iframe) — usado por cada `generate_html_report.py` y por `generate_dashboard.py` |
| `generate_dashboard.py` | Genera `informes/dashboard.html`: sidebar con un ítem por módulo dado de alta, cada uno carga su `informe_*.html` (misma carpeta) en un iframe |
| `api.py` | API local de solo lectura (Flask) |

**Identidad visual:** `--brand` en `PAGE_CSS` (`html_report.py`) es el naranja
oficial de ALESTE (`#f63200`, sacado de aleste.ar — logo, barras de gráficos,
hovers/foco de inputs y botones). Es un acento sobre el fondo claro/oscuro
neutro existente, no un rediseño completo: las tablas densas necesitan ese
fondo neutro para ser legibles. Si se vuelve a tomar color de marca del sitio,
ojo que la hoja de estilos publica de WordPress trae de arrastre los colores
default del editor Gutenberg (`#3858e9`, `#1e1e1e`, `#cc1818` en
`components-badge`/`components-button`) — no son la marca real, hay que sacar
el color de una captura de pantalla del sitio renderizado, no del CSS crudo.

**Tablas largas (`DASHBOARD_JS`, función `renderTable`/`paintTable`):** toda
tabla que viene de `spec.tables` tiene buscador en vivo, headers clickeables
para ordenar y un tope de 50 filas visibles con botón "Mostrar todas". Las
filas de más quedan en el DOM con clase `row-hidden` (`display: none`) en vez
de no renderizarse — así `@media print` las vuelve a mostrar con una sola
regla CSS, sin depender de que dispare el evento JS `beforeprint` (que en
Chromium headless no dispara, aunque en un navegador de escritorio real sí).
No agregues ese tope como `.slice()` antes de construir las filas: rompe la
impresión completa.

**Filtro de período (`filter_bar_html`):** son dos `<select>` (Mes/Año) por
límite, no un `<input type="month">`. El input nativo tiene un spinner de
año que en Windows/Chrome obliga a clickear de a un año por vez — con datos
de varios años queda inutilizable (reportado por Javier). Si se vuelve a
tocar ese filtro, no volver al input nativo.

El filtro se persiste en `localStorage` por archivo (clave
`aleste-filtro:` + `location.pathname`, seteada/leída en `DASHBOARD_JS`).
Motivo: `dashboard_shell()` recarga el `<iframe>` entero (`frame.src = ...`)
cada vez que se cambia de pestaña en `dashboard.html` — sin persistencia,
volver a la pestaña de un módulo reseteaba el filtro a "todo el período"
(reportado por Javier). Si se cambia el rango de fechas que trae un export
nuevo, un filtro guardado que quede fuera de `[minPeriod, maxPeriod]` se
ignora automáticamente (se valida antes de aplicarlo) y cae al período
completo.

**Chart de comparación mes a mes / trimestre a trimestre:** tipo de chart
`"period_compare"` en el spec (`groupedBarChartSvg`/`renderPeriodCompare` en
`DASHBOARD_JS`, montado con `hr.period_compare_mount()`). Agrupa por
mes o trimestre del año, una serie por año — el año es un dato ordenado, no
categórico, así que el color es siempre `--series-1` con opacidad creciente
por año (el más reciente en opacidad plena) en vez de una paleta arcoíris.
El toggle Mensual/Trimestral repinta solo ese chart puntual (no dispara el
recálculo completo del filtro de período).
