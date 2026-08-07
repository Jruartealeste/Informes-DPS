"""
Exporta el listado de Facturas desde Advertys: login + navegar (Consultas >
Facturacion > Facturas, por ID exacto de arbol) + filtro "Todos" + descarga
XLSX. Version productiva de explore.py: mismos selectores ya verificados
contra Advertys real, sin las capturas de debug intermedias (solo se
guarda una si algo falla, para diagnostico).

Uso:
    python -m modules.facturas.export
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from tools.advertys_session import AdvertysLoginError, esperar_postback, login

OUT_DIR = Path("exploracion")
OUT_DIR.mkdir(exist_ok=True)
SCREENSHOT_DIR = OUT_DIR / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)

DESTINO = OUT_DIR / "facturas_export.xlsx"

# Hay mas de un nodo "Facturacion"/"Facturas" en el menu (Administracion
# tiene su propia "Facturacion" para carga manual) -- se navega por ID
# exacto del arbol, no por texto. Ver modules/facturas/explore.py.
FACTURACION_ID = "Vertical_NC_NB_ITC3i0_TL_N0"
FACTURAS_ID = "Vertical_NC_NB_ITC3i0_TL_N0_0"


class ExportError(RuntimeError):
    pass


def _click_por_texto_o_title(page, texto) -> bool:
    click_js = """(texto) => {
        const candidatos = [...document.querySelectorAll('[title], span, div')];
        const el = candidatos.find(e =>
            (e.getAttribute && e.getAttribute('title') && e.getAttribute('title').trim().startsWith(texto)) ||
            e.textContent.trim() === texto
        );
        if (!el) return false;
        el.click();
        return true;
    }"""
    return page.evaluate(click_js, texto)


def exportar() -> Path:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(accept_downloads=True)
        try:
            try:
                login(page)
            except AdvertysLoginError:
                page.screenshot(path=str(SCREENSHOT_DIR / "facturas_export_error_login.png"))
                raise

            _click_por_texto_o_title(page, "Consultas")
            page.wait_for_timeout(800)

            try:
                page.locator(f"#{FACTURACION_ID}").click(timeout=10000)
            except Exception as e:
                page.screenshot(path=str(SCREENSHOT_DIR / "facturas_export_error_menu.png"), full_page=True)
                raise ExportError(f"No se pudo clickear la carpeta Facturacion por ID: {e}") from e
            page.wait_for_timeout(800)

            try:
                page.locator(f"#{FACTURAS_ID}").click(timeout=10000)
            except Exception as e:
                page.screenshot(path=str(SCREENSHOT_DIR / "facturas_export_error_menu.png"), full_page=True)
                raise ExportError(f"No se pudo clickear el nodo Facturas por ID: {e}") from e
            esperar_postback(page)

            filtro_btn = page.locator("#Vertical_TB_Menu_ITCNT9_xaf_a2_Cb_B-1")
            if filtro_btn.count() > 0:
                filtro_btn.click()
                page.wait_for_timeout(800)
                todos_item = page.get_by_text("Todos", exact=True).first
                try:
                    todos_item.click(timeout=5000)
                except Exception:
                    page.evaluate(
                        """() => {
                            const els = [...document.querySelectorAll('td, div, span, li')];
                            const el = els.find(e => e.textContent.trim() === 'Todos');
                            if (el) el.click();
                        }"""
                    )
                esperar_postback(page)

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
                page.screenshot(path=str(SCREENSHOT_DIR / "facturas_export_error_download.png"), full_page=True)
                raise ExportError(f"Error exportando Facturas: {e}") from e

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
