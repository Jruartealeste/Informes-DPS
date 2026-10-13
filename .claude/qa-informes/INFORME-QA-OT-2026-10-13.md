# QA de ot/ — ciclo completo de Estimados (2026-10-13)

## Entorno y alcance
- `qa_server.py --sqlite --reset` en :8123 (Docker Desktop caído: WSL se actualizó a 3.0.3 y el motor no arrancó). Luego repetido contra Postgres local (Docker ya arriba): mismo resultado.
- Datos: 4 OT compartiendo `numero_ot_advertys=285` (5 tareas) armadas por SQL. Pruebas por HTTP con cookie de sesión + SQL; UI solo en el detalle de un Estimado GENERADO.
- **No se probó:** detalle de BORRADOR/pedido pendiente en UI, mobile, concurrencia, "Generar" más allá de crear el pedido.

## Ciclo (todo OK, verificado en base)
Crear (10,11) → agregar 12,13 / quitar 10 → pedido con fecha 2026-10-01 (422) y 1/10/2026 (303) → con pedido PENDIENTE: agregar, quitar y cargar-número dan 409, generar otra vez 422 → anular tarea del Estimado con pedido: 409 (está FINALIZADO+PARA_FACTURAR) → resolver sin número 422, con número → GENERADO y numero_estimado en el Estimado; resolver/cancelar de nuevo 409 → GENERADO: agregar/quitar/cargar/generar 409. Inexistentes: 404 en las 5 rutas. Una tarea ya en un Estimado no entra en otro (422). Título HTML escapado. OT en blanco / título en blanco / id inexistente: 422.

## Medios
- `POST /tareas/{id}/estado` y `/facturacion` (y crear/editar tarea, `/facturacion/tareas/{id}/estado`) con valor inexistente → **500**. **Corregido 2026-10-13** (`parsear_estado` → 422). Aclaración: el estado vacío = "Sin estado" (NULL) es intencional de la UI, no es bug.
- Título de Estimado de más de 300 caracteres: en Postgres da **500** (confirmado). **Corregido 2026-10-13** (422 en `estimados.py`).

## Bajos / observaciones
- `tarea_ids=23,23` (repetidos) se acepta sin error (inocuo).
- Quitar la última tarea deja un BORRADOR vacío (el alta lo rechaza, pero queda basura en el listado).
- Un Estimado puede contener tareas con estado NULL; el detalle GENERADO no muestra estado ni facturación de sus tareas.
- Abierto (feature): título de BORRADOR no editable.
