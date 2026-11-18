# Registrar una cobranza (Recibo Cliente) en Advertys

**ESCRIBE en Advertys real.** Skill: `registrar-cobranzas`. Script:
`modules/recibos/crear_recibo.py` (parado en `informes/`). Validado en vivo el
2026-11-18 con el cobro ALUAR del 16/11/26 (recibo 463).

## Entrada

PDF del cobro en Drive: `Comprobantes de cobro / <cliente> /` (carpeta
`1WV4XRLNh8LOH3aCz-uksCxgOvGIwckdr`; subcarpetas aluar, gratia, fate,
cobro gihon, infa, nordelta). Nombre: `cobro <cliente> dd.mm.aa $monto.pdf`
(el monto es el neto transferido). Un PDF de ALUAR trae: "Detalle del pago"
(una hoja por factura, con retenciones y neto) + un certificado por cada
retencion (Ganancias, IIBB PBA, SUSS, IVA).

## Pasos

1. Leer el PDF (`read_file_content` del conector de Drive) y extraer: facturas
   (`00005A00001513`), importes, certificados (numero, tipo, base, importe) y
   neto. Verificar: suma de netos = monto del nombre; suma de retenciones por
   certificado = suma por factura.
2. **Preguntar a Javier la fecha del cobro** (no tomar la de emision del PDF).
3. Mostrar el recibo armado y pedir OK explicito antes de escribir.
4. Armar el spec JSON (ejemplo: `exploracion/cobro_aluar_16.11.26.json`) y correr
   `python -m modules.recibos.crear_recibo <spec>.json --guardar`.
   Sin `--guardar` carga pero no guarda. Guarda SOLO si los totales de
   cabecera cuadran y el saldo ("Balancea") es 0.
5. Verificar en el listado Recibo Cliente (Referencias, Retenciones, Efvo.Otros).
6. Renombrar el PDF si no sigue el formato.

## Mapeos (Advertys)

| Concepto | Opcion en Advertys |
|---|---|
| Ganancias (RG 830) | `112310-RET.IMP.GCIAS.DE CLIENTES` |
| IIBB Pcia. Bs.As. | `112331-RETENCION IIBB PCIA.BS.AS.` (112330 es C.A.B.A.) |
| SUSS (RG 1784) | `112280-RETENCION SUSS CLIENTES` |
| IVA (RG 18/97) | `112320-RETENCION IVA SUFRIDAS` |
| Otros Valores | Cuenta `111218-BANCO GALICIA`, tipo `TR` Transferencia Bancaria, Debe = neto |

- Numero de retencion: dos campos = año (4 dig.) + ultimos 7 dig. del certificado.
- Numero de referencia de Otros Valores: **dejar en 0** (como el recibo 462). No
  acepta el N° de orden de pago (10 dig.: "valor incorrecto en N° Comprobante").
- Factura PDF `00005A00001513` = Advertys `000500001513` (pto vta 4 dig. + nro 8 dig.).
- Referencias canceladas se muestran con signo NEGATIVO en la cabecera.
- El spec lleva "totales" esperados: referencias (negativo), retenciones, otros.

## Gotchas (aprendidos 2026-11-18)

- El "Nuevo" de las pestanas exige Cliente y **persiste el recibo como Borrador**
  apenas se abre; por eso el script es idempotente (saltea bloques cuyo total
  ya coincide) y solo toca recibos en Borrador.
- El "Nuevo" de la barra superior y el del combo Moneda tienen el mismo texto/title;
  el script usa el de la grilla (y > 560 px).
- El recibo queda en `Borrador` (sin asiento) tras Guardar y cerrar; la
  contabilizacion no forma parte de este flujo (confirmado 2026-11-18: el 463
  paso a `Contabilizado`, asiento 110004, sin intervencion del script).
- La UI de Advertys a veces viene en ingles ("New" en vez de "Nuevo"); el script
  contempla ambos.
- Un recibo borrador de relevamiento/prueba se elimina a mano desde el listado.
