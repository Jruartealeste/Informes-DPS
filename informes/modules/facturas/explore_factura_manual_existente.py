"""
Script de RECONOCIMIENTO de SOLO LECTURA: abre una Factura Produccion Manual
existente (vista detalle, sin "Editar") y vuelca la cabecera y la grilla de
items, para ver con que Cuenta / Sub Cuenta / % IVA se cargan los items.
No clickea Nuevo/Editar/Guardar ni ninguna Accion (Autorizar, Facturar, CAE).

Uso (parado en informes/):
    python -m modules.facturas.explore_factura_manual_existente 000500001532
"""
import sys

from playwright.sync_api import sync_playwright

from modules.facturas.explore_nueva_factura import LIST_URL_SUFFIX, OUT_DIR, shot, volcar
from tools.advertys_session import AdvertysLoginError, base_url, esperar_postback, login


def main():
    numero = sys.argv[1] if len(sys.argv) > 1 else "000500001532"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        try:
            try:
                login(page)
            except AdvertysLoginError as e:
                print(f"ERROR: {e}")
                raise SystemExit(1)
            page.goto(f"{base_url()}{LIST_URL_SUFFIX}", wait_until="networkidle", timeout=30000)
            esperar_postback(page)
            page.wait_for_timeout(800)
            celda = page.locator("tr[id*='DXDataRow'] td", has_text=numero).first
            if celda.count() == 0:
                print(f"ERROR: no se encontro la factura {numero} en el listado (filtro por defecto).")
                raise SystemExit(1)
            celda.click()  # click en la fila abre la vista detalle (modo lectura)
            esperar_postback(page)
            page.wait_for_timeout(1500)
            shot(page, f"existente_{numero}")
            volcar(page, f"existente_{numero}")
            filas = page.locator("tr[id*='DXDataRow']")
            print("Items:")
            for i in range(filas.count()):
                print("  -", filas.nth(i).inner_text().strip().replace("\n", " | ").replace("\t", " | "))
        finally:
            browser.close()


if __name__ == "__main__":
    main()
