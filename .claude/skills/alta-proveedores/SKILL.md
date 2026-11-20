---
name: alta-proveedores
description: Use when Javier pide dar de alta un proveedor nuevo en Advertys a partir de su constancia de inscripción ARCA/AFIP (PDF). Dispara con frases como "dá de alta este proveedor", "cargá el proveedor de esta constancia", "alta de proveedor", "creá el proveedor URBANIA". Lee la constancia, arma los datos, pregunta lo que falta (retención de Ganancias, tipo de proveedor, condición de pago, cuenta a imputar) recomendando opciones según la actividad, corre primero en modo prueba y pide OK explícito antes de guardar. ESCRIBE en Advertys real. No es alta de cliente/anunciante ni de OT.
argument-hint: [ruta-o-nombre-de-la-constancia.pdf]
---

## Qué hace

Da de alta un Proveedor en Advertys (Entidades > Generales > Proveedores >
Proveedor) corriendo `modules/proveedores/crear_proveedor.py` con los datos de
la constancia de inscripción. Fuente de verdad completa:
[workflows/alta_proveedor.md](../../../informes/workflows/alta_proveedor.md) —
si algo acá y el workflow difieren, gana el workflow (releerlo).

Escribe en Advertys real (no hay ambiente de prueba): **nunca guardar sin OK
explícito de Javier para esa corrida**; una autorización anterior no vale para
la siguiente.

## Pasos

1. **Leer la constancia.** La tool `Read` no renderiza PDFs acá (falta
   `pdftoppm`): extraer el texto con `pypdf` (`python` por ruta completa, ver
   `informes/CLAUDE.md`). Sacar razón social, CUIT, domicilio fiscal
   (calle, localidad, CP, provincia), condición de IVA, si está inscripto en
   Ganancias y la actividad principal. Verificar la vigencia de la constancia.
2. **Mostrar los datos a Javier** en una tabla corta.
3. **Preguntar y recomendar** (con `AskUserQuestion` si conviene):
   - *Retención Ganancia*: ¿retiene? ¿enajenación? ¿locación de obras y
     servicios? (NO RETENER / ENAJENACION / LOCACION DE OBRAS Y SERVICIOS /
     ALQUILERES / INTERESES / MONOTRIBUTO / FACTURAS M - GANANCIAS). Recomendar
     según la actividad (ej. comercio de bienes → ENAJENACION; servicios →
     LOCACION DE OBRAS Y SERVICIOS).
   - *Tipo Proveedor* (AGENCIA / MEDIOS / PRODUCCION / VARIOS) y *Condición
     Pago*: recomendar según la actividad. **La Condición de Pago es
     obligatoria** (Advertys rechaza el Guardar sin ella): no hay "sin
     condición".
   - *Cuenta a imputar*: opcional. Preguntar si la necesita; base
     `GASTOS VARIOS` (cuenta "GASTOS VARIOS (PART)"). Si no la quiere,
     recomendar una afín a la actividad.
   - SUSS = "No Retener" salvo que Javier diga otra cosa. Grupo Proveedor e
     IIBB se desestiman (no se tocan).
4. **Modo prueba** (parado en `informes/`, sin `--guardar`):
   `python -m modules.proveedores.crear_proveedor "<razón social>" "<cuit>" --direccion ... --cp ... --localidad ... --provincia ... --tipo-proveedor ... --retencion-ganancia ... [--condicion-pago ...] [--cuenta ...]`
   Completa el formulario y cierra sin guardar. Leer las capturas
   `exploracion/screenshots/crear_proveedor_*.png` y mostrar un resumen.
5. **Pedir OK explícito** y repetir el mismo comando con `--guardar`.
6. **Reportar** el N° de proveedor leído del formulario (no asumido) y revisar
   `crear_proveedor_guardado.png`.

## Notas

- Si el script avisa que el CUIT ya existe, no forzar: avisarle a Javier.
- Si una opción no matchea un combo, el error lista las opciones válidas.
- El click en `Guardar` todavía no se probó contra Advertys real (ver "Estado
  de verificación" en el workflow): revisar con cuidado la primera corrida y
  documentar cualquier hallazgo en el workflow.
- Nunca ampliar el alcance a editar/inhabilitar proveedores existentes ni a
  cargar CBU, contactos o IIBB.
