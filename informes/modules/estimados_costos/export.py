"""
Exporta el listado de Estimado Costos desde Advertys: login + navegar
DIRECTO por URL (el shortcut del menu lateral abre un formulario de alta
en vez del listado, ver explore.py) + filtro "Todos" + descarga XLSX.
Version productiva de explore.py: mismos selectores ya verificados contra
Advertys real, sin las capturas de debug intermedias (solo se guarda una
si algo falla, para diagnostico).

Uso:
    python -m modules.estimados_costos.export
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from tools.advertys_session import AdvertysLoginError, base_url, esperar_postback, login

OUT_DIR = Path("exploracion")
OUT_DIR.mkdir(exist_ok=True)
SCREENSHOT_DIR = OUT_DIR / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)

DESTINO = OUT_DIR / "estimados_costos_export.xlsx"

DIRECT_URL_SUFFIX = "Default.aspx#ViewID=EstimadoCostos_ListView&ObjectClassName=DPS_SAS_SR.Module.EstimadoCostos"


class ExportError(RuntimeError):
    pass


def _abrir_combo_filtro(page) -> bool:
    """Encuentra el input cuyo valor actual es 'Mes Actual' (el filtro
    default de esta vista) y clickea su boton de combo asociado -- esta
    vista tiene ademas un combo 'Ver' (Basico/Totales) antes en la toolbar,
    por eso no se puede asumir el primer '_Cb_B-1' de la pagina."""
    inputs = page.locator("input[id$='_Cb_I']")
    for i in range(inputs.count()):
        inp = inputs.nth(i)
        try:
            valor = inp.input_value(timeout=500)
        except Exception:
            continue
        if valor.strip() == "Mes Actual":
            btn_id = inp.get_attribute("id").replace("_Cb_I", "_Cb_B-1")
            page.locator(f"#{btn_id}").click(timeout=3000)
            return True
    return False


def exportar() -> Path:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(accept_downloads=True)
        try:
            try:
                login(page)
            except AdvertysLoginError:
                page.screenshot(path=str(SCREENSHOT_DIR / "estimados_costos_export_error_login.png"))
                raise

            direct_url = f"{base_url()}{DIRECT_URL_SUFFIX}"
            page.goto(direct_url, wait_until="networkidle", timeout=30000)
            esperar_postback(page)
            page.wait_for_timeout(800)

            if _abrir_combo_filtro(page):
                page.wait_for_timeout(500)
                item = page.get_by_text("Todos", exact=True)
                if item.count() > 0:
                    item.first.click(timeout=3000)
                    esperar_postback(page)
                else:
                    page.keyboard.press("Escape")
            page.wait_for_timeout(500)

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
                page.screenshot(path=str(SCREENSHOT_DIR / "estimados_costos_export_error_download.png"), full_page=True)
                raise ExportError(f"Error exportando Estimado Costos: {e}") from e

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
