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
        ├──► modules/<modulo>/generate_html_report.py  →  informe_*.html
        └──► api.py                                       →  API local (JSON)
```

**El informe es un HTML, no un Excel.** Cada módulo genera un único archivo
`.html` autocontenido (sin CDN, sin conexión a internet) que se abre con
doble click y se imprime a PDF desde el navegador (botón "Imprimir /
Guardar PDF" en el propio informe, o Ctrl+P). Cada corrida sobreescribe el
mismo archivo — no se acumulan versiones viejas. Como la carpeta del
proyecto vive en OneDrive, alcanza con compartir el link de OneDrive al
`.html` para que se vea siempre actualizado.

Los `generate_report.py` (Excel, con `openpyxl`) siguen en el repo por si
hace falta algo puntual, pero ya no son el entregable real — no se
regeneran de forma proactiva.

## Estructura de carpetas

```
Informes/
├── db.py               # conexion SQLite compartida (get_connection())
├── common.py            # normalizar_fecha / normalizar_numero, compartidas
├── html_report.py        # shell HTML/CSS + charts SVG + tablas, compartido
├── api.py                # API de solo lectura (hoy: Ordenes de Trabajo)
├── assets/
│   └── aleste-logo.svg   # isotipo de la agencia, fuente del LOGO_SVG embebido en html_report.py
├── modules/
│   ├── ordenes_trabajo/
│   │   ├── config.py               # mapeo de columnas y rutas
│   │   ├── ingest.py                 # carga el Excel + esquema de la tabla
│   │   ├── generate_html_report.py   # genera informe_dinamico.html (el informe real)
│   │   ├── generate_report.py        # genera .xlsx (legacy, no se usa mas)
│   │   ├── explore.py                # relevamiento en vivo (Playwright)
│   │   └── generar_ejemplo.py        # genera un Excel de prueba
│   ├── compras/
│   │   ├── config.py
│   │   ├── ingest.py
│   │   ├── generate_html_report.py
│   │   ├── generate_report.py
│   │   └── explore.py
│   └── facturas/
│       ├── config.py
│       ├── ingest.py
│       ├── generate_html_report.py
│       ├── generate_report.py
│       └── explore.py
├── exploracion/          # capturas/HTML/Excel de cada relevamiento en vivo
├── informe_dinamico.html # salida del modulo Ordenes de Trabajo
├── informe_compras.html  # salida del modulo Compras
└── informe_facturas.html # salida del modulo Facturas
```

Cada módulo nuevo se suma como una carpeta más dentro de `modules/`, con los
mismos archivos (`config.py`, `ingest.py`, `generate_html_report.py`,
`explore.py`), reutilizando `db.py`, `common.py` y `html_report.py` de la raíz.

## Módulos armados hasta ahora

| Módulo | Carpeta | Tabla en `advertys.db` | Informe |
|---|---|---|---|
| Órdenes de Trabajo | `modules/ordenes_trabajo/` | `ordenes_trabajo` | `informe_dinamico.html` |
| Compras (Administración > Compras) | `modules/compras/` | `compras` | `informe_compras.html` |
| Facturas (Consultas > Facturación > Facturas) | `modules/facturas/` | `facturas` | `informe_facturas.html` |

Próximo módulo: a definir (avisale a Claude Code cuál seguís usando más).

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
python -m modules.ordenes_trabajo.generate_html_report         # genera informe_dinamico.html
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
```

Cada vez que tengas un export nuevo, repetís esos dos comandos del módulo
que corresponda y el informe (`.html`) queda actualizado con todo lo último
— no hace falta borrar nada, los registros existentes se actualizan por su
clave única. Después abrís el `.html` con doble click y usás el botón
"Imprimir / Guardar PDF" (o Ctrl+P) si necesitás mandárselo a un cliente.

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
| `html_report.py` | Page shell + CSS (claro/oscuro/print), stat tiles, gráficos SVG con tooltip y tablas — usado por cada `generate_html_report.py` |
| `api.py` | API local de solo lectura (Flask) |
