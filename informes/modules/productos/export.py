"""
Exporta el listado maestro de Productos desde Advertys (Entidades >
Generales > Productos > Producto): login + navegar DIRECTO por URL +
descarga XLSX. Solo lectura -- no cambia el filtro: se deja el default
"Habilitados", que es lo que Advertys ofrece en el combo Producto del alta
de OT (un producto deshabilitado no se puede elegir ahi).

Uso:
    python -m modules.productos.export
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from tools.advertys_session import AdvertysLoginError, base_url, esperar_postback, login

OUT_DIR = Path("exploracion")
OUT_DIR.mkdir(exist_ok=True)
SCREENSHOT_DIR = OUT_DIR / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)

DESTINO = OUT_DIR / "productos_export.xlsx"

DIRECT_URL_SUFFIX = "Default.aspx#ViewID=Producto_ListView&ObjectClassName=DPS_SAS_SR.Module.Producto"


class ExportError(RuntimeError):
    pass


def exportar() -> Path:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(accept_downloads=True)
        try:
            try:
                login(page)
            except AdvertysLoginError:
                page.screenshot(path=str(SCREENSHOT_DIR / "productos_export_error_login.png"))
                raise

            page.goto(f"{base_url()}{DIRECT_URL_SUFFIX}", wait_until="networkidle", timeout=30000)
            esperar_postback(page)
            page.wait_for_timeout(1500)

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
                    if not page.evaluate(click_js, "Documento XLSX"):
                        raise RuntimeError("No se encontro el item 'Documento XLSX' en el DOM")
                download_info.value.save_as(str(DESTINO))
            except Exception as e:
                page.screenshot(path=str(SCREENSHOT_DIR / "productos_export_error_download.png"), full_page=True)
                raise ExportError(f"Error exportando Productos: {e}") from e

            return DESTINO
        finally:
            browser.close()


def main():
    try:
        destino = exportar()
    except (AdvertysLoginError, ExportError) as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    print(f"OK: descarga guardada en {destino}")


if __name__ == "__main__":
    main()
