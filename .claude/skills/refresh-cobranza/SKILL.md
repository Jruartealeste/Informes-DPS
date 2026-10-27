---
name: refresh-cobranza
description: Use when Javier pide actualizar o refrescar el informe de Cobranza x Proveedores (la cadena recibos → referencias canceladas → OC/OP de cada factura → facturas de compra de cada orden), o se queja de que "tarda 70 minutos". Ej: "actualizá cobranza por proveedor", "refrescá el informe de cobranzas", "¿por qué tarda tanto cobranza?", "corré la cobranza completa". Es la cadena que refresh-dashboard deja afuera a propósito; no usar para IIBB (tools.actualizar_iibb) ni para el resto de los informes (refresh-dashboard).
argument-hint: (sin argumentos, o un modo: incremental | completo | legacy)
---

## Qué hace

`tools/actualizar_cobranza.py` encadena, en este orden (cada paso lee lo que
dejó el anterior):

0. `facturas`, `ordenes_compra`, `ordenes_publicidad` — export + ingest
   (desde 2026-10-27, siempre: **todo refresh baja los exports nuevos que
   necesita**, pedido de Javier). `--sin-previos` lo saltea, solo si esos
   tres se bajaron recién en la misma sesión (ej. se corrió antes
   `tools.actualizar_iibb` para refrescar también Facturación ALUAR).
1. `recibos` — export + ingest de la cabecera.
2. `modules.recibos.crawl_referencias_canceladas` — qué facturas cancela
   cada recibo de la ventana de 2 meses.
3. `modules.cobranza_proveedores.crawl_oc_por_factura` — OC/OP de cada
   factura cobrada.
4. `modules.cobranza_proveedores.crawl_facturas_compra_por_oc` — facturas de
   compra de cada OC/OP.
5. Regenera `salida/informe_cobranza_proveedores.html` y el dashboard.

Los pasos 2–4 navegan Advertys con Playwright (solo lectura) y son los que
cuestan el tiempo.

Si Javier pide cobranza **y** Facturación ALUAR juntas: correr primero
`python -m tools.actualizar_iibb` (baja facturas/OC/OP + Imputaciones y
refresca ALUAR) y después `python -m tools.actualizar_cobranza --sin-previos`,
para no descargar dos veces los mismos exports.

## Modos (implementados el 2026-10-13)

Parado en `informes/` (no en la raíz del repo), con el Python completo
(`/c/Users/javie/AppData/Local/Programs/Python/Python312/python.exe`):

| Comando | Cuándo | Qué hace |
|---|---|---|
| `-m tools.actualizar_cobranza` | uso normal | **Incremental**: solo visita lo nuevo o cambiado. Medido 2026-10-13: ~200 s en total (la mayor parte son los ~7 recibos de la última semana, que se revisitan siempre). |
| `... --completo` | sospecha de dato viejo, o después de tocar un crawl | Ignora la caché y revisita todo (con upsert, no borra antes). |
| `... --legacy` | si algo del modo nuevo se ve raro | La corrida vieja tal cual: borra y recrawlea todo, de a uno. ~70 min (medido 2026-09-30). Se mantiene a propósito como red de seguridad. |
| `... --workers N` | junto a cualquiera de los anteriores | N navegadores en paralelo (cada uno con su login). Validado el 2026-10-13 que 3 sesiones simultáneas dan los mismos datos, pero rinde poco (~1.3x): el límite es el servidor. Dejar el default en 1 salvo una corrida `--completo`. |

## Qué se re-visita en modo incremental y por qué

La caché (`crawl_cache`) recuerda qué se crawleó y con qué "firma" de
cabecera (estado/importes). El cierre contable de mes (día 15–20 del mes
siguiente; el código usa el 20, el más conservador) hace que un recibo o
factura de un mes cerrado ya no cambie:

- **Recibos y facturas de mes cerrado ya en caché: congelados.**
- Recibos de los últimos 7 días: siempre se revisitan (se editan/anulan).
- Cambió la firma de cabecera, o la factura no tiene OC/OP resuelta: se revisita.
- **OC/OP: la fecha de la orden NO congela.** Una orden vieja puede recibir
  una factura de compra nueva; manda la firma (estado, saldo, comprado,
  pagado) y que no tenga factura de compra resuelta.

## Cómo leer el resultado

Al final hay un resumen por paso: ítems visitados vs. salteados por caché,
errores y tiempo. Qué mirar:

- **Visitó casi todo en una corrida normal** → la caché está vacía o se
  invalidó; esperable solo la primera vez o con `--completo`.
- **Un paso falla** → se saltean los siguientes (dependen de su salida) pero
  el informe se regenera igual con lo que haya en `advertys.db`. Leer la
  línea `ERROR <paso>`; si es de login o de sesión rota, reintentar; si es
  un ítem puntual, `--completo` sobre ese paso.
- **Un número del informe no coincide con Advertys** → probar `--completo`
  antes de asumir bug; si persiste, `--legacy` para descartar un error del
  modo nuevo, y avisarle a Javier.

## Después de correr

Avisarle a Javier cuánto tardó y cuántos ítems se revisitaron. Si hubo
cambios de CSS/layout en la sesión, verificar con el skill `verificar-visual`.
Si algo del flujo cambió (flags, regla de cierre), actualizar este skill y
`workflows/actualizar_informe.md`.
