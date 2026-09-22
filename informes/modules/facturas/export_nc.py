"""
Exporta las Notas de Credito automaticas de Ventas desde Advertys, una por
segmento (produccion/medios/representante). A diferencia de "Facturas"
(Consultas > Facturacion), estas NO son ObjectClassName=DPS_Factura -- viven
como ListViews propios bajo Administracion > Facturacion > <Segmento> >
"N.Credito Automatica", por eso el export de Facturas con filtro "Todos"
nunca las trae. Ver la nota "Notas de Credito de Ventas" en README.md.

Navega DIRECTO por URL (mismo criterio que estimados_costos/export.py) en
vez de clickear el arbol de Administracion: ese arbol tiene, al lado del
listado real, un shortcut "Quick create" que abre un formulario de alta
vacio para el mismo ObjectClassName -- clickear el nodo equivocado ahi
aterriza en un alta, no en un listado (ver explore_nc_ventas.py, descartado).

Uso:
    python -m modules.facturas.export_nc --segmento produccion
    python -m modules.facturas.export_nc --segmento medios
    python -m modules.facturas.export_nc --segmento representante
"""
import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from tools.advertys_session import AdvertysLoginError, base_url, esperar_postback, login
from . import config

OUT_DIR = Path("exploracion")
OUT_DIR.mkdir(exist_ok=True)
SCREENSHOT_DIR = OUT_DIR / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)


class ExportError(RuntimeError):
    pass


def _abrir_combo_filtro(page) -> bool:
    """Mismo criterio que estimados_costos/export.py: busca el input cuyo
    valor actual es 'Mes Actual' (default de esta vista) y clickea su boton
    de combo asociado, en vez de asumir el primer '_Cb_B-1' de la pagina."""
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


def exportar(segmento: str) -> Path:
    if segmento not in config.NC_SEGMENTOS:
        raise ExportError(f"segmento desconocido '{segmento}'. Opciones: {list(config.NC_SEGMENTOS)}")

    object_class = config.NC_SEGMENTOS[segmento]["object_class"]
    destino = OUT_DIR / f"facturas_nc_{segmento}_export.xlsx"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(accept_downloads=True)
        try:
            try:
                login(page)
            except AdvertysLoginError:
                page.screenshot(path=str(SCREENSHOT_DIR / f"facturas_nc_{segmento}_export_error_login.png"))
                raise

            direct_url = f"{base_url()}Default.aspx#ViewID={object_class}_ListView&ObjectClassName=DPS_SAS_SR.Module.{object_class}"
            page.goto(direct_url, wait_until="networkidle", timeout=30000)
            esperar_postback(page)
            page.wait_for_timeout(800)

            if _abrir_combo_filtro(page):
                page.wait_for_timeout(500)
                # Esta vista usa "Todas" (femenino, por "Nota Credito
                # Automatica"), a diferencia del "Todos" de Facturas/Compras.
                item = page.get_by_text("Todas", exact=True)
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
                download.save_as(str(destino))
            except Exception as e:
                page.screenshot(path=str(SCREENSHOT_DIR / f"facturas_nc_{segmento}_export_error_download.png"), full_page=True)
                raise ExportError(f"Error exportando NC {segmento}: {e}") from e

            return destino
        finally:
            browser.close()


def main():
    parser = argparse.ArgumentParser(description="Exporta Notas de Credito automaticas de Ventas (Advertys)")
    parser.add_argument("--segmento", required=True, choices=list(config.NC_SEGMENTOS))
    args = parser.parse_args()

    try:
        destino = exportar(args.segmento)
    except (AdvertysLoginError, ExportError) as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    print(f"OK: descarga guardada en {destino}")


if __name__ == "__main__":
    main()
