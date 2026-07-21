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
from modules.compras import config as compras_config
from modules.facturas import config as facturas_config
from modules.ordenes_trabajo import config as ot_config
from modules.pendientes import generate_html_report as pendientes_report

# (id, label, archivo_html) -- el archivo sale de config.py de cada modulo
# para no repetir el nombre a mano y quedar desincronizado si cambia.
# El basename alcanza porque dashboard.html vive en la misma carpeta informes/.
MODULOS = [
    ("pendientes", "Pendientes", os.path.basename(pendientes_report.REPORT_HTML_OUTPUT_PATH)),
    ("ordenes_trabajo", "Ordenes de Trabajo", os.path.basename(ot_config.REPORT_HTML_OUTPUT_PATH)),
    ("compras", "Compras", os.path.basename(compras_config.REPORT_HTML_OUTPUT_PATH)),
    ("facturas", "Facturas", os.path.basename(facturas_config.REPORT_HTML_OUTPUT_PATH)),
]


def main():
    html = hr.dashboard_shell(MODULOS)
    with open("informes/dashboard.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("OK: dashboard generado en informes/dashboard.html")


if __name__ == "__main__":
    main()
