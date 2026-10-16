# Informe QA ot/ — 2026-10-16 (b): alta de OT con Claude

## Entorno y alcance
- Server descartable `ot/tools/qa_server.py` en `:8123` sobre Postgres local
  `ot-qa-pg`, ahora en **127.0.0.1:15433** (antes 54329: Windows reservó el
  rango 54269–54368 y Docker no podía publicar el puerto; ver Bajos).
- Flujo probado de punta a punta: pedido desde OT internas en el navegador →
  aviso en Solicitudes → `informes/modules/ordenes_trabajo/procesar_solicitudes.py`
  (`listar`, `procesar --simular`, `descartar`) por HTTP real contra `:8123` →
  verificación en la base y en la app.
- **No se probó:** la creación real en Advertys (`--simular` reemplaza a
  `crear_ot` por `SIM-<id>`), ni la API contra prod (los endpoints nuevos
  todavía no están desplegados). La falla de red se simuló forzando
  `resolver_api` a fallar con un wrapper (scratchpad), no cortando la red.

## Altos
_(ninguno)_

## Medios — corregidos en esta pasada
- **ñ rota en la salida del script** ("Dise�o de piezas"): la consola de
  Windows usa cp1252 y Javier aprueba leyendo esa salida. Corregido:
  `stdout`/`stderr` en UTF-8 en `main()`.
- **`listar` no marcaba "YA CREADA"** cuando la corrida que creó la OT usó
  `--simular`: había dos logs (`.jsonl` y `.sim.jsonl`) y `listar` leía el
  otro. Corregido: un solo log, separado por URL (y `--simular` solo existe
  en `procesar` y solo contra localhost).

## Bajos — corregidos
- Panel "Generar OT en Advertys" en OT internas decía "arma un pedido para
  correr `crear_ot.py` a mano": ahora dice que se carga corriendo el alta
  con Claude.
- Puerto del Postgres de QA movido a 15433 (fuera del rango dinámico de
  Windows, 49152+). `levantar-entorno.sh` recrea el contenedor si tiene otro
  puerto, sin tocar el volumen.
- Había un `qa_server.py --sqlite` del 14/10 todavía escuchando en `:8123`
  con código viejo; se cerró. Si `preview_start` falla con "solo se permite
  un uso de cada dirección", buscar el PID en `netstat -ano`.

## Simplificación
| Elemento | Decisión |
|---|---|
| Comando manual en cada pedido | Ya plegado en `<details>` "Alternativa manual" (no compite con el aviso de Claude) |
| Botón Copiar | Ya es ícono solo con aria-label |
| Texto del aviso | Se deja visible (no `info-tip`): es la instrucción principal de la pantalla |

## Lo que funcionó bien
- Pedido con 2 OT internas → aviso "Pedido creado, pero todavía no está en
  Advertys" + card resaltada; con 1 pendiente cambia a "1 pedido todavía no
  está…"; sin pendientes no aparece.
- `procesar --ids 2`: OT `SIM-2` propagada a 4161 y 4162, la #1 intacta;
  reintento del mismo id → "SALTEADA".
- Falla de vinculación después de crear → `listar` marca "YA CREADA", el
  reintento solo vincula (no crea de nuevo).
- Pedido cancelado después de crear → `listar` avisa ATENCION con el número,
  `procesar` da 404 explícito, `descartar` lo saca del aviso.
- Token inválido → 401 claro; `--simular` contra `--prod` → rechazado.
- Suite `pytest`: 147 en verde.
