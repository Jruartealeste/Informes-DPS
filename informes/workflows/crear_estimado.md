# Crear (dar de alta) el encabezado de un Estimado de Costo en Advertys

**Objetivo:** correr `modules/estimados_costos/crear_estimado.py` para crear
el encabezado de un Estimado de Costo dentro de una OT que ya existe en
Advertys. Solo el encabezado (Título, Fecha Solicitada, Fecha Análisis). Los
ítems del estimado (líneas de costo/proveedor) NO se automatizan: se cargan
a mano en Advertys.

**Cuándo usar:** Javier pide "creá un estimado", "entrá a la OT y dale a
Nuevo Estimado", o la app `ot/` tiene una solicitud de alta de estimado
(`solicitudes_alta_estimado`). Para modificar o finalizar un estimado
existente es otro flujo (`finalizar_estimados_pendientes.md`).

**Salvaguarda:** escribe en Advertys real y no se deshace sin borrar a mano.
Antes de cada corrida, confirmar con Javier, en esa conversación: número de
OT y título. Una autorización anterior no vale para la siguiente corrida. No
inventar el título: preguntarlo (Javier suele usar el Resumen de la OT).

**Datos:**
- OT: número de una OT existente.
- Título: obligatorio (la app `ot/` también lo exige antes de pedir el alta).
- Fechas: opcionales. Sin ellas, Advertys deja la Fecha Solicitada en hoy y
  la Fecha Análisis vacía. `--fecha-analisis D/M/AAAA` si hace falta.

**Pasos (parado en `informes/`):**
1. Confirmar OT + título con Javier.
2. `python -m modules.estimados_costos.crear_estimado <ot> "<titulo>" [--fecha-analisis D/M/AAAA]`
   Hace login, abre la OT, pestaña "Estimados Costo", "Nuevo Estimado",
   completa el popup, clickea "Aceptar" y detecta el N° nuevo comparando la
   columna N° de la grilla antes y después (el popup no lo muestra). Nunca
   clickea nada más que "Nuevo Estimado" y "Aceptar".
3. Revisar las capturas `exploracion/screenshots/crear_est_<ot>_*.png`
   (`00_antes`, `02_completado`, `03_guardado`).
4. Reportar el N° de Estimado. Hoy el N° se carga a mano en la app `ot/`
   (`Estimado.numero_estimado`); los ítems de costo, a mano en Advertys.

**Desde la app `ot/`:** usar el skill `procesar-solicitudes-estimado`
(`modules.estimados_costos.procesar_solicitudes`): crea el Estimado y carga el
número en la solicitud solo. Si el Estimado ya existe en Advertys y la solicitud
quedó pendiente: `procesar_solicitudes vincular --prod --ids N --numero X` (no
toca Advertys). Corriendo `crear_estimado.py` a mano, `--solicitud N` hace lo
mismo al terminar bien.

**Si el script informa error, NO reintentar:** el alta puede haber salido
bien y reintentar crea un duplicado. Mirar primero la captura
`03_guardado` y la grilla de la OT en Advertys.

**Gotchas conocidos:**
- *Falso error "no se pudo identificar el Estimado nuevo"* (2026-10-30,
  OT 303 / Estimado 589): el estimado se creó bien, pero `leer_numeros_estimado`
  leía la celda 0 de cada fila, que es el checkbox (vacía). Corregido: toma
  la primera celda numérica de las primeras 5.
- OT con 20 o más estimados: la grilla pagina de a 20 y el nuevo puede caer
  en la página 2+; el script lo avisa en el mensaje de error.
- Login lento: Advertys tarda 10-15 s en responder; `tools/advertys_session.py`
  espera hasta 30 s. No usar copias locales de `login` sin esa espera
  (`cerrar_ot.py` tenía una y fallaba en falso; ahora usa la compartida).
- El grid se repinta de forma asincrónica tras el "Aceptar": el script
  reintenta hasta 10 s antes de darse por vencido.
