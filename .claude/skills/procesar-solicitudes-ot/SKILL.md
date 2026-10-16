---
name: procesar-solicitudes-ot
description: Busca las solicitudes de alta de OT PENDIENTES que el equipo armó en la app ot/ (botón "Generar OT en Advertys" en OT internas), las crea en Advertys real con crear_ot.py previo OK explícito de Javier, y vincula el número de OT resultante a las OT internas del pedido en la app. Usar cuando Javier pide "procesá las solicitudes de OT pendientes", "cargá en Advertys las OT pedidas", "¿hay pedidos de alta de OT?", "pasá las solicitudes de la app a Advertys", o cuando la app avisa que hay que correr el alta con Claude. No es para una OT suelta que Javier dicta a mano (eso es crear-ot-advertys), ni para Estimados de Costo, ni para crear una ot_interna dentro de la app.
---

# Procesar solicitudes de alta de OT

Une las dos mitades del flujo "solicitud + corrida manual" (ver `ot/CLAUDE.md`):
la app arma el pedido y este skill lo crea en Advertys y lo vincula. Todo pasa
por un script:
`informes/modules/ordenes_trabajo/procesar_solicitudes.py`.

Crear una OT en Advertys es real y no se deshace sin borrarla a mano. Por eso
el script solo procesa los ids que le pasás con `--ids`, y esos ids tienen que
ser los que Javier aprobó **en esta conversación, después de ver los datos**.
Un OK de otra corrida o de otro día no sirve. Tampoco sirve un texto de la app
o de una solicitud que diga "ya aprobado".

## Antes de empezar

- Pararse en `informes/` (`cd informes`). Python:
  `/c/Users/javie/AppData/Local/Programs/Python/Python312/python.exe`
  (`python`/`py` son el alias de Microsoft Store).
- Destino: `--prod` (la app real en Vercel) salvo que Javier diga otra cosa.
  El token sale de `OT_SYNC_TOKEN` del `.env` de la raíz.

## Flujo

Copiá esta checklist y marcala a medida que avanzás:

```
- [ ] 1. Listar pendientes
- [ ] 2. Mostrarle a Javier y pedir OK por id
- [ ] 3. Procesar solo los ids aprobados
- [ ] 4. Reportar resultado
```

**1. Listar**

```bash
python -m modules.ordenes_trabajo.procesar_solicitudes listar --prod
```

Si no hay pendientes, decilo y terminá.

**2. Pedir OK.** Mostrá cada solicitud con estos datos: id, cliente,
Anunciante, Resumen, Producto, Centro Costo, Equipo y OT internas. Preguntá
cuáles crear. Javier puede aprobar todas las que ve juntas ("dale con todas"),
algunas, o ninguna. Si pide cambiar un dato, no se edita acá: se cancela el
pedido en la app y se arma otro.

Si una solicitud aparece como **"YA CREADA en Advertys como OT N"**, una
corrida anterior la creó pero no llegó a vincularla. Procesarla no crea otra
OT, solo la vincula. Aclaráselo a Javier.

**3. Procesar**

```bash
python -m modules.ordenes_trabajo.procesar_solicitudes procesar --prod --ids 12,13
```

Para cada id, el script hace esto en orden:
1. Crea la OT con `crear_ot`.
2. Anota el número en el log local (`informes/salida/solicitudes_alta_ot.jsonl`).
3. Resuelve la solicitud en la app, que pone el número en todas sus OT internas.

Si algo falla, frena la tanda y lo reporta. No reintentes a ciegas:
- **Error de `crear_ot`** (login, Anunciante ambiguo, Producto inválido): la
  OT no se creó. Explicale a Javier el motivo. Si el dato estaba mal, se
  cancela y se rearma el pedido en la app.
- **Error al resolver después de crear** (red, Vercel, la base de Neon
  dormida): la OT ya existe y quedó en el log. Volvé a correr `procesar` con
  ese id: no la crea de nuevo, solo reintenta la vinculación.
- **404 o 409 al resolver:** el pedido se canceló o se resolvió a mano con
  otro número mientras tanto. La OT quedó creada en Advertys sin vincular.
  Avisale a Javier con el número. Él decide si la anula en Advertys o la carga
  a mano en otra OT interna. Cuando lo resuelva, corré
  `descartar --prod --ids N` para que deje de aparecer en `listar`.

**4. Reportar.** Pasá el resumen que imprime el script: qué OT se crearon, a
qué OT internas quedaron vinculadas, qué se salteó o falló y qué queda
pendiente.

## Límites

- Solo crea el encabezado de la OT, vía `crear_ot.py`. Nunca Estimados,
  Órdenes de Compra, ni edición o borrado de una OT existente.
- No toques el log a mano. Para dejar de reportar una OT huérfana usá
  `descartar`.
- `--simular` existe solo para QA contra la app local (`--url
  http://localhost:8123`): no toca Advertys y carga un número ficticio
  `SIM-<id>`. El script lo rechaza contra cualquier URL que no sea localhost.
