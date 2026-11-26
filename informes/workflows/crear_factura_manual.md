# Crear una Factura Producción Manual (en Borrador) en Advertys

**ESCRIBE en Advertys real** (solo con `--guardar`). Skill:
`crear-factura-manual-produccion`. Script: `modules/facturas/crear_factura_manual.py`
(parado en `informes/`). Relevado el 2026-11-25. La carga de ítems con `--guardar`
todavía no tiene una corrida real validada: en la primera, revisar el Borrador a mano.

## Alcance

- Solo **Producción** (`FacturaProduccionManual`, Administración > Facturación >
  Producción > Factura Manual). Medios / Representante son otros objetos.
- Solo facturas de **servicios reales prestados**. El script rechaza un neto total
  menor a $10.000 (`NETO_MINIMO`), sin override: no se arman comprobantes nominales
  ni facturas pensadas para anularse con NC.
- El script deja la factura en **Borrador** (sin número ni CAE). **Nunca** clickea
  Autorizar, Facturar, Solicitar CAE ni Clona Comprobante: eso lo hace Javier a mano.

## Pasos

1. Juntar con Javier: cliente, producto, título (opcional), condición de pago
   (opcional) y por ítem: cuenta, detalle, cantidad, precio unitario **sin IVA**,
   alícuota de IVA y tipo de facturación (opcional). Preguntar qué servicio se factura
   si no está claro.
2. Armar el spec JSON en `exploracion/factura_manual_<cliente>_<dd.mm.aa>.json`
   (formato en el docstring del script).
3. Correr en **modo prueba**:
   `python -m modules.facturas.crear_factura_manual <spec>.json`
   Valida el spec y el neto, abre el formulario, elige cliente y producto, y no guarda.
4. Mostrar la factura armada (cliente, producto, ítems, neto, IVA y total) y **pedir
   OK explícito**. Una autorización anterior no vale para la factura siguiente.
5. Correr con `--guardar`. El script guarda la cabecera, carga cada ítem (verifica
   que el neto que calcula Advertys coincida con el del spec), guarda y relee la
   grilla. Informa el ObjectKey y el link al Borrador.
6. Reportar a Javier el link y recordarle que la autorización y el CAE son pasos suyos.

## Mapeos (Advertys)

| Campo | Valores relevados |
|---|---|
| Cuenta (ítem) | `411010-FEE`, `411020-SERVICIO AGENCIA PRODUCCION`, `411030-VTA SERVICIOS PROPIOS`, `411035-VTA X DIFERENCIA DE SERV 3EROS`, `411038-MARK UP PRODUCCION`, `411040-VTA SERVICIOS DE TERCEROS (OC)`, `411050-BONIFICACIONES PRODUCCION` |
| % IVA | `21,00` (default), `10,50`, `27,00`, `5,00`, `2,50` |
| Sub Cuenta | deshabilitada, la completa Advertys |
| Tipo Facturación | AGENCIA, CREATIVIDAD, DIGITAL, DERECHOS, CONTENT & EVENTOS COVERAGES, … (lista con scroll virtual: el script tipea para filtrar) |
| Anunciante | por defecto el mismo nombre que el cliente; spec `anunciante` para otro |
| Producto | depende del **anunciante** (HORA DATA GROUP S.A. → `Varios`; TWDC → `Comisiones`) |

## Gotchas (2026-11-25)

- El listado de **Consultas > Facturación > Facturas** (`DPS_Factura`) es solo de
  consulta: no tiene "Nuevo".
- **Producto es obligatorio** y la cabecera tiene que estar **guardada** para abrir el
  "Nuevo" de ítems. Si se toca "Nuevo" sin Producto, falla la validación y no se
  guarda nada.
- Al elegir Cliente, Advertys **autocompleta Anunciante con el primero asociado**
  (HORA DATA → TWDC), y eso cambia los Productos disponibles. El script fija el
  Anunciante explícitamente (por defecto, igual al cliente) y lo verifica.
- El link "Nuevo" del listado no tiene `title`; se busca por texto.
- `type()` carácter por carácter se corta con el postback (el Título quedaba "P"). Se
  usa `fill()` + Tab y se relee el valor.
- El popup de búsqueda de Cliente a veces no abre a la primera; el script reintenta.
- Si el script corta después de guardar la cabecera, queda un Borrador a medias
  (informa el ObjectKey). Borrarlo es decisión de Javier; no relanzar a ciegas porque
  crearía otro.
- Borrador de relevamiento ObjectKey 310 (HORA DATA, quedó con anunciante TWDC /
  producto Comisiones por el gotcha de arriba, sin ítems): lo elimina Javier a mano.
