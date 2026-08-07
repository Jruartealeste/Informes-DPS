"""
Configuracion del modulo de cruce "Cobranza x Factura Venta x Factura Compra"
(pedido de Javier, 2026-08-04).

No tiene ingest propio (igual que modules/pendientes): cruza tablas que ya
cargan otros modulos --

    recibos                  <- modules/recibos/ingest.py (cabecera)
    referencias_canceladas   <- modules/recibos/crawl_referencias_canceladas.py
    facturas                 <- modules/facturas/ingest.py
    items_factura_oc_cobranza <- modules/cobranza_proveedores/crawl_oc_por_factura.py
    ordenes_compra_produccion <- modules/ordenes_compra/ingest.py

Cadena de vinculos (Cobrado -> Facturado -> Detalle de lo Facturado):
    recibos.numero_recibo
        -> referencias_canceladas.numero_recibo (1 recibo cancela N referencias)
        -> facturas por (tipo_referencia, numero_referencia) -- desambiguado
           por monto cuando hay mas de una factura candidata con el mismo
           N Referencia (ver generate_html_report.py, caso real documentado
           en modules/iibb: mismo N Referencia usado por una factura
           Produccion TA=FP y una Medios TA=FM a la vez)
        -> items_factura_oc_cobranza.numero_oc (via crawl_oc_por_factura.py)
        -> ordenes_compra_produccion.numero_oc (proveedor, saldo, estado)

Ventana: ultimos 2 meses (rolling, recalculada en cada corrida). Empezo en
6 meses (mismo criterio que modules/iibb) pero se acorto a 2 el mismo dia
(Javier, 2026-08-04): con 71 recibos en la ventana de 6 meses el crawl de
modules/recibos/crawl_referencias_canceladas.py no habia terminado despues
de varios minutos -- cada recibo es mas caro de crawlear que cada factura
en IIBB (hay que volver al listado y re-buscar por cada uno, ver docstring
de ese script). 2 meses alcanza para el uso operativo real ("que pago
ahora con lo que acabo de cobrar") sin que el crawl se vuelva impracticable.
"""

VENTANA_MESES = 2

REPORT_HTML_OUTPUT_PATH = "salida/informe_cobranza_proveedores.html"
