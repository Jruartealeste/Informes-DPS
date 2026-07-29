# OTs — app de tareas del equipo + vínculo a facturación

Reemplaza el Google Sheet compartido donde ~10 personas del equipo (diseño,
producción, redacción, estrategia) cargan tareas por cliente. Hoy ese Sheet
no tiene ningún vínculo real a las Órdenes de Trabajo de Advertys ni a las
facturas emitidas — el estado de facturación es texto libre
("FACTURADO"/"PARA FACTURAR"/etc.) sin número de factura asociado. Esta app
cierra ese gap: cada tarea se vincula a una OT real, y más adelante
(Fase 2) al número de factura que la cubre.

Proyecto hermano de `Informes/` (mismo repo, misma agencia — ALESTE ADS
S.A.), pero de otra categoría de sistema: `Informes/` es scripts +
HTML estático corridos a demanda por un solo operador; esto es una
**aplicación web multiusuario** con servidor persistente, base de datos y
login. Por eso vive en su propia carpeta con su propio `CLAUDE.md`, en vez
de sumarse al pipeline de informes.

## Estado actual

Todavía no hay código — este documento es el punto de partida. El primer
trabajo real es el modelo de datos + CRUD de tareas (ver "Roadmap" abajo).

## Alcance: dos fases

**Fase 1 (la que se construye ahora):** app donde el equipo carga y edita
tareas. Cada tarea se vincula a una OT real de Advertys (nunca texto libre
suelto — se valida contra datos ya sincronizados, no contra Advertys en
vivo). Estados de tarea y de facturación normalizados. Login con Google
OAuth restringido a `@aleste.ar` (la agencia ya tiene Google Workspace
pago).

**Fase 2 (fuera de alcance por ahora, no empezar sin decisión explícita):**
facturación semi-automática — seleccionar tareas/OT terminadas → aprobación
humana → Advertys crea la factura en BORRADOR → revisión humana → recién
ahí se solicita el CAE (paso fiscal sin retorno) → se captura el número de
factura resultante y se vincula a la(s) tarea(s) que la originaron. Esto
implica escribir en Advertys (hoy de solo lectura en todo el proyecto
`Informes/`, salvo la excepción puntual y muy acotada de
`modules/ordenes_trabajo/cerrar_ot.py`, aprobada explícitamente por
Javier). Antes de tocar una sola línea de esto hace falta: (a) relevar en
modo lectura el formulario "Nueva Factura" de Advertys (todavía no se hizo
nunca) y (b) aprobación explícita de Javier antes de cualquier click que
cree o edite algo ahí.

## Stack

- **Backend:** FastAPI.
- **Base de datos:** PostgreSQL, vía SQLAlchemy 2.x + Alembic para
  migraciones.
- **Frontend:** Jinja2 + HTMX, sin build de JS (HTMX vendorizado local, sin
  CDN). El caso de uso es CRUD + filtros + formularios con autocompletado —
  no justifica el costo de mantenimiento de una SPA para un equipo no
  técnico.
- **Auth:** Google OAuth (Authlib), validando el claim `hd` del id_token
  contra `aleste.ar` del lado del servidor (no alcanza con mirar el sufijo
  del email). Sesión en cookie httponly firmada — no se exponen tokens al
  cliente.

## Arquitectura / estructura de carpetas (a crear)

```
app/
├── main.py            # instancia FastAPI, monta routers y SessionMiddleware
├── config.py           # settings vía env: DATABASE_URL, GOOGLE_CLIENT_ID/SECRET, SYNC_TOKEN, SESSION_SECRET
├── db.py                # engine/session de SQLAlchemy
├── models.py             # ORM: ver "Modelo de datos" abajo
├── schemas.py             # Pydantic
├── auth.py                # OAuth Google + validación de dominio + dependencias require_user/require_role
├── routers/
│   ├── tareas.py           # /, /tareas, /tareas/{id}, /tareas/partial
│   ├── clientes.py          # /clientes/{cliente_id}
│   ├── facturacion.py        # /facturacion/listas (cola de "listas para facturar", semilla de Fase 2)
│   ├── ordenes_trabajo.py     # /api/ordenes-trabajo/buscar (autocompletar OT)
│   ├── sync.py                 # /api/sync/ordenes-trabajo, /api/sync/facturas
│   └── auth_routes.py           # /auth/login, /auth/callback, /auth/logout
├── templates/                    # Jinja2
└── static/                        # HTMX vendorizado, CSS propio
migrations/                         # Alembic
scripts/
└── migrar_sheet.py                 # migración one-off del Google Sheet real
tests/
```

## Modelo de datos

Enums (normalizan los valores reales del Sheet, typos incluidos):

- `estado_tarea`: PARA_INICIAR, EN_PROCESO, PAUSADO, PENDIENTE_OK (normaliza
  el typo real "PENDIETE OK" además de "PENDIENTE OK"), FINALIZADO,
  APROBADO.
- `estado_facturacion`: SIN_FACTURAR (default), PARA_FACTURAR,
  FALTA_OK_CLIENTE, FACTURADO, NO_CORRESPONDE.
- `rol_usuario`: MIEMBRO, APROBADOR_FACTURACION (modelado ya, sin uso hasta
  Fase 2), ADMIN.

Tablas:

- `usuarios` — id, email (único), nombre, rol, activo, ultimo_login.
- `clientes` — id, nombre, `anunciante_advertys` (alias hacia
  `ordenes_trabajo_espejo.anunciante`; el nombre de cuenta interno no
  siempre coincide 1:1 con el de Advertys).
- `tipos_tarea` — catálogo (diseño, redaccion, produccion, estrategia,
  campania, gestion, mant_web, pautas_medios, otro) — en el Sheet
  "TIPO DE TAREA" es multivalor separado por coma.
- `tareas` — id, cliente_id, `numero_ot` (nullable, FK a
  `ordenes_trabajo_espejo`), `ot_ambigua` (texto crudo cuando no resuelve a
  una OT real, ej. "4086/4110"), fecha_pedido, detalle, pedido_por,
  link_drive, presupuestado, estado_tarea, estado_facturacion,
  `numero_factura`/`cae` (nullable, placeholders de Fase 2),
  `fila_sheet_original` (trazabilidad de la migración), creado_por_id,
  timestamps.
- `tarea_tipos_tarea` / `tarea_responsables` — N:M ("RESPONSABLES" en el
  Sheet también es multivalor, separado por "/"; `tarea_responsables`
  incluye `nombre_libre` como fallback cuando no matchea a un usuario real).
- `tareas_historial` — auditoría de cambios de campo (10 personas editando
  lo mismo).
- `ordenes_trabajo_espejo` — espejo de solo lectura de la tabla
  `ordenes_trabajo` de `Informes/advertys.db`, poblado únicamente por sync
  (upsert por `numero_ot`).
- `facturas_espejo` — opcional en Fase 1, deja el terreno listo para
  Fase 2.
- `sync_log` — auditoría de cada sync recibido.

## Relación con `Informes/` y con Advertys

- Esta app nunca habla directo con Advertys. Todo lo que sabe de OT viene
  de `ordenes_trabajo_espejo`, sincronizada desde `Informes/advertys.db`.
- El único cambio que este proyecto le suma al pipeline padre es un script
  chico ahí (`Informes/modules/sync_tareas_app/push.py`, a construir): lee
  `ordenes_trabajo` con `db.get_connection()` y hace `POST` autenticado
  (bearer token separado en `SYNC_TOKEN`, no OAuth de usuario) a
  `/api/sync/ordenes-trabajo` acá. Se corre a mano después de un
  `ingest.py`, igual de manual que el resto del pipeline hoy.
- Las credenciales de Advertys (`.env` de `Informes/`) no se copian ni se
  usan en este proyecto.

## Quirks conocidos del Google Sheet real (relevado 2026-07-23)

- **Typos reales en "ESTADO"**: aparece "PENDIETE OK" (sic) además de
  "PENDIENTE OK" — reconocer ambos en la migración.
- **"OT" no siempre es un número limpio**: valores como "4086/4110" (dos OT
  en una tarea) o vacío. Si no resuelve a una OT real en
  `ordenes_trabajo_espejo`, guardar el texto crudo en `ot_ambigua` y
  flaggear para revisión manual — nunca descartar ni adivinar.
- **"TIPO DE TAREA" y "RESPONSABLES" son multivalor** en una sola celda
  (coma y "/" respectivamente).
- **Columna "OT DPS"**: casi siempre vacía, propósito legacy no claro — se
  descarta en la migración.
- **"FACTURACION" es texto libre sin número de factura** — es exactamente
  el gap que esta app viene a cerrar; no asumir que "FACTURADO" implica que
  existe un número recuperable en algún lado del Sheet (no existe).

## Decisión pendiente (confirmar con Javier antes de ejecutar)

Hosting de la app (hoy no hay infraestructura propia más allá de Google
Workspace): evaluar Render.com/Railway.app (deploy simple, Postgres
administrado, ~USD 5–20/mes) vs. Google Cloud Run + Cloud SQL (mismo
ecosistema que Workspace, más pasos de setup). No desplegar nada sin su OK
explícito.

## Roadmap inmediato

1. Modelo de datos (`models.py` + primera migración de Alembic) y CRUD
   básico de tareas, sin auth todavía (para poder probar rápido).
2. Auth con Google OAuth restringido a `@aleste.ar`.
3. `scripts/migrar_sheet.py` en modo dry-run contra el Sheet real, revisar
   el CSV de filas flaggeadas con Javier antes de `--commit`.
4. Sync `ordenes_trabajo` ↔ `ordenes_trabajo_espejo` (script en
   `Informes/` + endpoint acá).
5. UI: vista unificada filtrable, vista por cliente, alta/edición de tarea
   con autocompletado de OT, vista `/facturacion/listas`.
6. Elegir y confirmar hosting con Javier, desplegar.
