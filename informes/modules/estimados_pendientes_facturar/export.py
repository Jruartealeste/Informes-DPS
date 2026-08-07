"""
Exporta el listado de "Estim.Pendientes Facturar" desde Advertys: login +
navegar DIRECTO por URL + descarga XLSX (esta vista no tiene combo de
filtro por periodo, ya viene pre-filtrada a "lo pendiente ahora" -- ver
explore.py). Version productiva de explore.py: mismos selectores ya
verificados contra Advertys real, sin las capturas de debug intermedias
(solo se guarda una si algo falla, para diagnostico).

Uso:
    python -m modules.estimados_pendientes_facturar.export
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from tools.advertys_session import AdvertysLoginError, base_url, esperar_postback, login

OUT_DIR = Path("exploracion")
OUT_DIR.mkdir(exist_ok=True)
SCREENSHOT_DIR = OUT_DIR / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)

DESTINO = OUT_DIR / "estimados_pendientes_facturar_export.xlsx"

DIRECT_URL_SUFFIX = "Default.aspx#ViewID=EstimadoCostos_ListView_Pendiente_de_Facturar&ObjectClassName=DPS_SAS_SR.Module.EstimadoCostos"


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
                page.screenshot(path=str(SCREENSHOT_DIR / "estimados_pendientes_facturar_export_error_login.png"))
                raise

            direct_url = f"{base_url()}{DIRECT_URL_SUFFIX}"
            page.goto(direct_url, wait_until="networkidle", timeout=30000)
            esperar_postback(page)
            page.wait_for_timeout(800)

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
                download.save_as(str(DESTINO))
            except Exception as e:
                page.screenshot(path=str(SCREENSHOT_DIR / "estimados_pendientes_facturar_export_error_download.png"), full_page=True)
                raise ExportError(f"Error exportando Estim.Pendientes Facturar: {e}") from e

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
