"""
RECONOCIMIENTO (no escribe nada): en el formulario "Nuevo" de Proveedor abre
el popup de Direccion (lapiz) y el buscador de Cuenta a imputar (pestana
Parametros), los fotografia y vuelca el HTML de su iframe; cierra sin guardar.
Aprobado por Javier el 2026-11-19 junto con explore_nuevo_proveedor.py.

Uso (parado en informes/):
    python -m modules.proveedores.explore_popups_proveedor
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from tools.advertys_session import AdvertysLoginError, base_url, esperar_postback, login

OUT_DIR = Path("exploracion")
SHOTS = OUT_DIR / "screenshots"
SHOTS.mkdir(parents=True, exist_ok=True)
URL = "Default.aspx#ViewID=Proveedor_ListView&ObjectClassName=DPS_SAS_SR.Module.Proveedor"


def shot(page, nombre):
    page.screenshot(path=str(SHOTS / f"{nombre}.png"), full_page=True)
    print(f"  -> {nombre}.png")


def volcar_popup(page, nombre):
    page.wait_for_timeout(1500)
    shot(page, nombre)
    for f in page.frames:
        if "Dialog=true" in f.url:
            (OUT_DIR / f"{nombre}_frame.html").write_text(f.content(), encoding="utf-8")
            print(f"  frame -> {nombre}_frame.html")
            return f
    print("  (sin iframe Dialog=true)")
    return None


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 1000})
        try:
            try:
                login(page)
            except AdvertysLoginError as e:
                print(f"ERROR: {e}")
                sys.exit(1)
            page.goto(base_url() + URL, wait_until="networkidle", timeout=30000)
            esperar_postback(page)
            page.locator('a[title="Nuevo"], span:has-text("Nuevo")').first.click()
            esperar_postback(page)
            page.wait_for_timeout(1500)

            print("Popup Direccion (lapiz)...")
            page.locator("td[id$='_xaf_dviDatosGenerales_Edit_B0']").first.click(timeout=8000)
            fr = volcar_popup(page, "prov_popup_direccion")
            if fr is not None:
                fr.get_by_text("Cancelar", exact=True).first.click(timeout=5000)  # cierra sin aceptar
            esperar_postback(page)
            page.wait_for_timeout(800)

            print("Buscador Cuenta a imputar...")
            page.get_by_text("Parámetros", exact=True).locator("visible=true").last.click(timeout=8000)
            esperar_postback(page)
            page.wait_for_timeout(800)
            btn = page.locator("td[id$='_xaf_dviCuenta_Edit_find_Edit_B0']")
            print(f"  botones lupa: {btn.count()}")
            if btn.count():
                btn.first.click(timeout=8000)
                volcar_popup(page, "prov_popup_cuenta")
        finally:
            browser.close()


if __name__ == "__main__":
    main()
