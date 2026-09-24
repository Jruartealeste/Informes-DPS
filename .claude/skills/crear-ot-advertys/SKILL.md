---
name: crear-ot-advertys
description: Use when Javier pide crear, dar de alta, o generar una OT (Orden de Trabajo) nueva en Advertys — incluye "OT de prueba" contra Advertys real. Dispara con frases como "creá una OT en Advertys", "dale de alta una OT nueva", "generá una OT para <cliente>", "necesito una OT de prueba en Advertys", "alta de OT". No confundir con crear una ot_interna dentro de la app ot/ (eso no toca Advertys, ver ot/CLAUDE.md) — si no queda claro cuál de las dos quiere, preguntar. Corre modules/ordenes_trabajo/crear_ot.py, que escribe en Advertys real (no reversible sin borrar a mano), así que siempre junta Anunciante/Resumen/Producto/Centro Costo y pide confirmación explícita de Javier antes de cada corrida — una autorización anterior no vale para la siguiente.
argument-hint: [anunciante] [resumen] [producto] [centro_costo] [--equipo]
---

## Qué hace

Da de alta el encabezado de una OT nueva en Advertys corriendo
`modules/ordenes_trabajo/crear_ot.py`. Fuente de verdad completa:
[workflows/crear_ot.md](../../../informes/workflows/crear_ot.md) — si algo
acá y el workflow difieren, gana el workflow (releerlo).

Este flujo escribe en Advertys real — mismo nivel de cuidado que
`cerrar_ot.py`/`crear_estimado.py`. **Nunca correr el script sin que Javier
confirme explícitamente, para esa corrida puntual, los 4 datos: Anunciante,
Resumen, Producto, Centro Costo** (Equipo es opcional). Si pide "una OT de
prueba" sin más detalle, no inventar valores — preguntarle con qué datos
quiere probar.

## Diferencia con crear una OT interna en `ot/`

Si el pedido es sobre la app `ot/` (crear una `ot_interna`, que es 100%
interna y nunca toca Advertys), este skill no aplica — ver `ot/CLAUDE.md`.
Ante la ambigüedad de "creá una OT de prueba" sin más contexto, preguntar
primero cuál de las dos quiere.

## Pasos

1. Confirmar con Javier: Anunciante, Resumen, Producto, Centro Costo, y
   Equipo si aplica (Centro Costo es un combo fijo de 4 valores: ver el
   workflow). No asumir ninguno.
2. Parado en `informes/` (`cd informes` primero si la sesión arrancó en la
   raíz del repo):
   `python -m modules.ordenes_trabajo.crear_ot "<anunciante>" "<resumen>" "<producto>" "<centro_costo>" [--equipo "<equipo>"]`
3. Reportar el número de OT resultante (leído del campo del formulario, no
   asumido) y recordarle a Javier que si era de prueba, la anula/borra él
   mismo en Advertys cuando quiera.

## Notas

- `python`/`py` en esta terminal apuntan al alias de Microsoft Store — si
  falla, usar la ruta completa indicada en `informes/CLAUDE.md`.
- Producto es un catálogo por Anunciante, relevado a mano y parcial (ver el
  workflow) — si el Anunciante no está relevado todavía, avisar que el
  script no puede validar el valor de antemano.
- Nunca ampliar el alcance a Estimados de Costo, Órdenes de Compra, o
  edición/borrado de una OT existente.
