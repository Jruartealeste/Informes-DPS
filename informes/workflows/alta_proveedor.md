# Alta de Proveedor en Advertys

Skill: `alta-proveedores`. Script: `modules/proveedores/crear_proveedor.py`.
Escribe en Advertys real (Entidades > Generales > Proveedores > Proveedor) —
mismo nivel de cuidado que `crear_ot.py`/`crear_estimado.py`: nunca guardar
sin OK explícito de Javier **para esa corrida**.

## Entrada

Constancia de inscripción ARCA (PDF, ej. en `Downloads`). La tool `Read` no
renderiza PDFs en esta máquina (falta `pdftoppm`); extraer el texto con
`pypdf` (`pypdf.PdfReader(path).pages[0].extract_text()`). La constancia da:
razón social, CUIT, forma jurídica, domicilio fiscal (calle, localidad, CP,
provincia), impuestos registrados (IVA, Ganancias, etc.) y actividad
principal. **No trae** teléfono, mail ni contacto — no se cargan.

## Qué se carga y de dónde sale (decisiones de Javier, 2026-11-19)

| Pestaña / campo | Origen |
|---|---|
| Nombre | Razón social de la constancia |
| Dirección (popup Datos Generales: dirección, CP, localidad, provincia, país) | Domicilio fiscal de la constancia; país ARGENTINA (obligatorio) |
| Grupo Proveedor | Desestimado (queda N / D) |
| Datos Impositivos: Tipo IVA, Tipo Documento = CUIT, CUIT | Constancia (solo dígitos) |
| Ganancias: "Es Inscripto Ganancias" | Constancia (viene tildado por defecto) |
| Ganancias: Retención Ganancia | **Preguntar al usuario**: ¿retiene?, ¿enajenación? ¿locación de obras y servicios? (opciones: ALQUILERES, ENAJENACION, FACTURAS M - GANANCIAS, INTERESES, LOCACION DE OBRAS Y SERVICIOS, MONOTRIBUTO, NO RETENER) |
| SUSS | "No Retener" por defecto |
| IIBB | Desestimado |
| Parámetros: Tipo Proveedor (AGENCIA/MEDIOS/PRODUCCION/VARIOS) y Condición Pago | **Preguntar al usuario**, recomendando según la actividad del proveedor |
| Parámetros: Cuenta a imputar | Opcional: preguntar si la necesita. Base: `GASTOS VARIOS (PART)`; si no, recomendar una cuenta afín a la actividad |

## Pasos

1. Extraer los datos de la constancia y mostrárselos a Javier en una tabla.
2. Preguntar lo que falta (Retención Ganancia, Tipo Proveedor, Condición Pago,
   Cuenta) con recomendación según la actividad.
3. Parado en `informes/`, correr **sin** `--guardar` (modo prueba: completa el
   formulario, saca una captura por pestaña en `exploracion/screenshots/
   crear_proveedor_*.png` y cierra sin guardar). Leer las capturas.
4. Pedir OK explícito y recién ahí repetir el mismo comando con `--guardar`.
5. Reportar el N° de proveedor leído del formulario tras Guardar.

```
python -m modules.proveedores.crear_proveedor "<razón social>" "<cuit>" \
  --direccion "<calle y nro>" --cp <cp> --localidad "<localidad>" --provincia "<provincia>" \
  --tipo-proveedor <AGENCIA|MEDIOS|PRODUCCION|VARIOS> --retencion-ganancia "<opción>" \
  [--condicion-pago "<opción>"] [--cuenta "<texto>"] [--suss "No Retener"] \
  [--tipo-iva "IVA Responsable Inscripto"] [--no-inscripto-ganancias] [--guardar]
```

## Quirks relevados

- Anti-duplicado: antes de abrir "Nuevo" busca el CUIT en el listado y corta si
  ya existe. El listado filtra "Habilitados": un proveedor inhabilitado no se
  detecta, revisar a mano si hay dudas.
- Provincia/combos: el match es sin distinguir mayúsculas (Advertys las lista
  en MAYÚSCULAS: BUENOS AIRES, CAPITAL FEDERAL…). Si no matchea, el error
  lista las opciones.
- País es un lookup anidado (popup dentro del popup de Dirección); si queda
  vacío el popup no cierra ("Dato obligatorio") y el script corta con captura.
- La pestaña "Parámetros" comparte nombre con un nodo del menú lateral: el
  script usa el último elemento visible con ese texto.
- Los combos de Advertys cargan la lista por callback y muestran unas ~9
  opciones por vez (virtual scroll): las opciones de Condición Pago de abajo
  pueden estar incompletas (relevadas: 10 DIAS FF, 15 DIAS FECHA FACTURA,
  30 % ANT.SALDO CONTRA ENTREGA, 30 DIAS SIN DPP, 45 DIAS FECHA FACTURA,
  45 DIAS SIN DPP, 60 DIAS FECHA FACTURA, 7 DIAS FECHA FACTURA).
- La barra del formulario tiene "Obtener Datos Afip Proveedor" (Advertys puede
  traer los datos de ARCA por su cuenta). No se usa: el script carga desde la
  constancia que pasa Javier.

## Primer Guardar real (2026-11-19): Condición de Pago es OBLIGATORIA

El primer `--guardar` (URBANIA) fue rechazado por Advertys con "Falta:
Condicion de Pago" y el script lo reportó como OK porque el N° de proveedor se
autoasigna al abrir "Nuevo" (no prueba que se guardó). Corregido: el script
ahora detecta el cartel "Problemas fueron detectados" tras Guardar y corta con
error, y `--condicion-pago` es argumento obligatorio. Preguntarle siempre al
usuario la condición de pago (no hay "sin condición").

## Estado de verificación

Verificado de punta a punta contra Advertys real el 2026-11-19 con URBANIA
S.A.C.I.F.I.C. (proveedor 00413, CUIT 30-52167595-7): modo prueba, rechazo
por Condición de Pago faltante (detectado), y alta exitosa con
`--condicion-pago CONTADO`. Aun así, revisar siempre
`crear_proveedor_guardado.png` tras un `--guardar`: el éxito se infiere por la
ausencia del cartel de validación, no por el N° (que se asigna antes de guardar).

Nota sobre combos: las listas tienen virtual-scroll; el script las recorre
scrolleando, por eso opciones como `CONTADO` (que no aparecían entre las
primeras 9) sí se encuentran.
