"""
Script de exploracion (no productivo): entra a Advertys con las credenciales
de .env, navega DIRECTO por URL a "Estim.Pendientes Facturar" (shortcut del
menu "Cuentas y Produccion") y exporta a Excel.

Mismo motivo que modules/estimados_costos/explore.py para navegar por URL
directa en vez de clickear el shortcut del menu lateral.

Esta vista no tuvo, en el relevamiento real (2026-07-21), un combo de
filtro por periodo -- ya viene filtrada de por si a "lo pendiente ahora".

Uso:
    python -m modules.estimados_pendientes_facturar.explore
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

URL = os.environ.get("ADVERTYS_URL")
USER = os.environ.get("ADVERTYS_USER")
PASSWORD = os.environ.get("ADVERTYS_PASSWORD")

OUT_DIR = Path("exploracion")
OUT_DIR.mkdir(exist_ok=True)
SCREENSHOT_DIR = OUT_DIR / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)


def esperar_postback(page, timeout=25000):
    try:
        page.wait_for_selector(".dxlpLoadingDiv", state="visible", timeout=3000)
    except Exception:
        pass
    try:
        page.wait_for_selector(".dxlpLoadingDiv", state="hidden", timeout=timeout)
    except Exception:
        pass
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass


def main():
    if not URL or not USER or not PASSWORD:
        print("ERROR: completa ADVERTYS_URL, ADVERTYS_USER y ADVERTYS_PASSWORD en .env")
        sys.exit(1)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(accept_downloads=True)

        print(f"Abriendo {URL}")
        page.goto(URL, wait_until="networkidle", timeout=30000)

        user_input = page.locator('input[id$="xaf_dviUserName_Edit_I"]')
        pass_input = page.locator('input[id$="xaf_dviPassword_Edit_I"]')
        user_input.wait_for(state="visible", timeout=15000)
        user_input.click()
        user_input.fill(USER)
        pass_input.click()
        pass_input.fill(PASSWORD)
        pass_input.press("Enter")
        esperar_postback(page)

        if "Login.aspx" in page.url:
            login_link = page.locator('a[title="Iniciar sesión"], a[title="Iniciar sesion"]')
            if login_link.count() > 0:
                login_link.first.click(force=True, timeout=10000)
                esperar_postback(page)

        if "Login.aspx" in page.url:
            print("ERROR: no se pudo hacer login. Revisa usuario/contraseña en .env")
            page.screenshot(path=str(SCREENSHOT_DIR / "estim_pendientes_error_login.png"))
            browser.close()
            sys.exit(1)

        print("Login OK. Navegando directo a 'Estim.Pendientes Facturar'...")
        base_url = URL.split("Login.aspx")[0]
        direct_url = f"{base_url}Default.aspx#ViewID=EstimadoCostos_ListView_Pendiente_de_Facturar&ObjectClassName=DPS_SAS_SR.Module.EstimadoCostos"
        page.goto(direct_url, wait_until="networkidle", timeout=30000)
        esperar_postback(page)
        page.wait_for_timeout(800)
        page.screenshot(path=str(SCREENSHOT_DIR / "estim_pendientes_01_listado.png"), full_page=True)

        print("Exportando a XLSX...")
        click_js = """(texto) => {
            const spans = [...document.querySelectorAll('span.dx-vam')];
            const span = spans.find(s => s.textContent.trim() === texto);
            if (!span) return false;
            const anchor = span.closest('a');
            if (!anchor) return false;
            anchor.click();
            return true;
        }"""
        try:
            with page.expect_download(timeout=20000) as download_info:
                encontrado = page.evaluate(click_js, "Documento XLSX")
                if not encontrado:
                    raise RuntimeError("No se encontro el item 'Documento XLSX' en el DOM")
            download = download_info.value
            destino = OUT_DIR / "estimados_pendientes_facturar_export.xlsx"
            download.save_as(str(destino))
            print(f"OK: descarga guardada en {destino}")
        except Exception as e:
            print(f"ERROR al descargar: {e}")
            page.screenshot(path=str(SCREENSHOT_DIR / "estim_pendientes_error_export.png"), full_page=True)

        browser.close()


if __name__ == "__main__":
    main()
