"""
Genera el shell de dashboard (sidebar + iframe) que agrupa todos los
informe_<modulo>.html en una sola pagina navegable. No regenera los
informes en si -- corre despues de generar cada informe_<modulo>.html con
su propio 'python -m modules.<modulo>.generate_html_report'.

Cada modulo nuevo que se sume (ver workflows/relevar_modulo_nuevo.md) tiene
que agregarse a MODULOS aca.

Uso:
    python generate_dashboard.py
"""
import os

import html_report as hr
from modules.cobranza_proveedores import config as cobranza_proveedores_config
from modules.compras import config as compras_config
from modules.estado_resultados import config as estado_resultados_config
from modules.estimados_pendientes import generate_html_report as estimados_pendientes_report
from modules.facturacion_aluar import config as facturacion_aluar_config
from modules.facturas import config as facturas_config
from modules.iibb import config as iibb_config
from modules.ordenes_trabajo import config as ot_config
from modules.pendientes import generate_html_report as pendientes_report

# (id, label, archivo_html, grupo) -- el archivo sale de config.py de cada
# modulo para no repetir el nombre a mano y quedar desincronizado si cambia.
# El basename alcanza porque dashboard.html vive en la misma carpeta salida/.
# `grupo` arma las secciones del sidebar, en el orden en que aparecen aca;
# modulo nuevo: sumarlo junto a los de su grupo y darle icono en
# html_report.NAV_ICONS.
G_OT = "Seguimiento de OT"
G_COMPRAS = "Compras y proveedores"
G_FACT = "Facturación"
G_RES = "Resultados"

MODULOS = [
    ("pendientes", "Pendientes", os.path.basename(pendientes_report.REPORT_HTML_OUTPUT_PATH), G_OT),
    ("estimados_pendientes", "Estimados pendientes", os.path.basename(estimados_pendientes_report.REPORT_HTML_OUTPUT_PATH), G_OT),
    ("ordenes_trabajo", "Órdenes de trabajo", os.path.basename(ot_config.REPORT_HTML_OUTPUT_PATH), G_OT),
    ("compras", "Compras", os.path.basename(compras_config.REPORT_HTML_OUTPUT_PATH), G_COMPRAS),
    ("cobranza_proveedores", "Cobranza x proveedores", os.path.basename(cobranza_proveedores_config.REPORT_HTML_OUTPUT_PATH), G_COMPRAS),
    ("iibb", "IIBB (recupero OC/OP)", os.path.basename(iibb_config.REPORT_HTML_OUTPUT_PATH), G_COMPRAS),
    ("facturas", "Facturas", os.path.basename(facturas_config.REPORT_HTML_OUTPUT_PATH), G_FACT),
    ("facturacion_aluar", "Facturación ALUAR", os.path.basename(facturacion_aluar_config.REPORT_HTML_OUTPUT_PATH), G_FACT),
    ("estado_resultados", "Estado de resultados", os.path.basename(estado_resultados_config.REPORT_HTML_OUTPUT_PATH), G_RES),
]


def main():
    html = hr.dashboard_shell(MODULOS)
    with open("salida/dashboard.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("OK: dashboard generado en salida/dashboard.html")


if __name__ == "__main__":
    main()
