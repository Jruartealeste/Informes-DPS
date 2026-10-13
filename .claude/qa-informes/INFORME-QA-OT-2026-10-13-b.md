# QA de ot/ — concurrencia, Facturación y sync (2026-10-13, parte 2)

## Entorno y alcance
`qa_server.py --reset` sobre **Postgres local en Docker** (:8123). Dos sesiones (cookies A y B) por HTTP, SQL después de cada paso, una captura de `/facturacion`.
**No se probó:** concurrencia real simultánea (carreras de milisegundos; solo "vista vieja" de un formulario abierto), UI del drawer con dos navegadores, mobile, Gmail, `Quitar` en cola de Facturación, volumen.

## Altos
- **Último que guarda gana, en silencio y con campos de otro** (`PATCH /tareas/{id}`, `tareas.py:~425`). A y B abren la tarea 5. A guarda detalle y responsable; B guarda después con su vista vieja y pisa ambos (detalle y responsable de A perdidos, 200). Peor: A marca la tarea FACTURADO por `/facturacion`; B guarda su drawer viejo y la deja otra vez en PARA_FACTURAR. No hay versión ni `actualizado_en` para detectarlo. Sin `estado_facturacion` en el body, el PATCH la resetea a SIN_FACTURAR.
- **La regla "facturadas no se anulan" se saltea** con `PATCH ... estado_tarea=ANULADA` y con `POST /tareas/{id}/estado estado_tarea=ANULADA` (tarea FACTURADO → ANULADA, 200). Solo `/anular` la aplica.

## Medios
- **Sync: un registro inválido tumba el lote con 500 y no queda en `sync_log`** (`sync.py`: el `commit` está fuera del `try`). Casos: `numero_ot` repetido en el lote (UniqueViolation), `numero_ot` >20, `estado` >40, `negocio` >80 (StringDataRightTruncation). Quedan 0 filas del lote y sin auditoría del fallo.
- **Sync acepta `numero_ot` vacío** (`""` queda como clave en `ordenes_trabajo_espejo`).
- **Facturación acepta cualquier tarea por POST directo**: una sin Estimado (id 1) pasó a FACTURADO; una PARA_INICIAR (12) también. La cola solo filtra la vista.
- **Un Estimado BORRADOR aparece en la cola** de Facturación (el texto dice que Advertys factura por Estimado ya existente) — decidir si es intencional.

## Bajos
- `/facturacion/tareas/{id}/estado` con id inexistente → 200 sin hacer nada.
- Sync: upsert pisa con NULL los campos que el registro no manda (esperable si Informes envía el registro completo).
- Con Estimado, la tarea no se anula (409): correcto y coherente con el informe anterior.

## Funcionó bien
Sync: 401 sin token, token malo o esquema distinto; upsert por `numero_ot` sin duplicar; lista vacía 200; 422 para cuerpo no-lista, JSON roto, falta `numero_ot`, fecha mala. Facturación: transiciones PARA_FACTURAR→FACTURADO y →NO_CORRESPONDE, contador y kicker coherentes (5→3 pendientes), valor inexistente 422, pantalla sin errores (captura OK).

## Seguimiento
Los dos Altos quedaron corregidos el mismo día (control de versión en el PATCH + `puede_anular` en `/estado` y PATCH), verificados contra Postgres y en la UI real (aviso 409 con el drawer abierto; guardado normal sin falsos conflictos). Los Medios siguen abiertos.
Los dos Medios del sync también quedaron corregidos (ver `hallazgos-conocidos.md`); verificados contra Postgres.
