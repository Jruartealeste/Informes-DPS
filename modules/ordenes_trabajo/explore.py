"""
Script de exploracion (no productivo): entra a Advertys con las credenciales
de .env, navega hasta "Orden Trabajo" y prueba exportar a Excel para
confirmar que el flujo de automatizacion es viable.

Uso:
    python explore_advertys.py
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
            page.screenshot(path=str(OUT_DIR / "error_login.png"))
            browser.close()
            sys.exit(1)

        print(f"Login OK. URL actual: {page.url}")

        base_url = URL.split("Login.aspx")[0]
        direct_url = f"{base_url}Default.aspx#ViewID=OrdenTrabajo_ListView&ObjectClassName=DPS_SAS_SR.Module.OrdenTrabajo"
        print(f"Probando navegacion directa: {direct_url}")
        page.goto(direct_url, wait_until="networkidle", timeout=30000)
        esperar_postback(page)
        page.screenshot(path=str(OUT_DIR / "03_directo.png"), full_page=True)
        (OUT_DIR / "directo.html").write_text(page.content(), encoding="utf-8")
        print(f"URL tras navegacion directa: {page.url}")
        page.screenshot(path=str(OUT_DIR / "03_orden_trabajo.png"), full_page=True)
        print(f"URL tras click: {page.url}")

        # Guardar el HTML para poder revisar la estructura de la grilla
        (OUT_DIR / "orden_trabajo.html").write_text(page.content(), encoding="utf-8")

        print("Cambiando filtro a 'Todas' para traer el historico completo...")
        filtro_btn = page.locator('td[id$="_Cb_B-1"]').first
        filtro_btn.click()
        page.wait_for_timeout(800)
        page.screenshot(path=str(OUT_DIR / "04_filtro_abierto.png"), full_page=True)
        (OUT_DIR / "filtro_abierto.html").write_text(page.content(), encoding="utf-8")

        todas_item = page.get_by_text("Todas", exact=True).first
        try:
            todas_item.click(timeout=5000)
        except Exception:
            page.evaluate(
                """() => {
                    const els = [...document.querySelectorAll('td, div, span, li')];
                    const el = els.find(e => e.textContent.trim() === 'Todas');
                    if (el) el.click();
                }"""
            )
        esperar_postback(page)
        page.screenshot(path=str(OUT_DIR / "05_filtro_todas.png"), full_page=True)
        (OUT_DIR / "filtro_todas.html").write_text(page.content(), encoding="utf-8")

        print("Exportando a XLSX (click nativo por texto del item, sin requerir visibilidad)...")
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
            destino = OUT_DIR / "orden_trabajo_export.xlsx"
            download.save_as(str(destino))
            print(f"OK: descarga guardada en {destino}")
        except Exception as e:
            print(f"ERROR al descargar: {e}")
            page.screenshot(path=str(OUT_DIR / "error_export.png"), full_page=True)

        browser.close()


if __name__ == "__main__":
    main()
