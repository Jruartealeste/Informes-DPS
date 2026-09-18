"""
Exporta "Reporte Balance Mensual" desde Advertys: login + navegacion directa
por URL (ViewID=ReporteBalanceMensual_ListView, sin pasar por el arbol de
menu -- confirmado que funciona igual que en Estimados/OC/OT) + filtro
"Todos" + descarga.

Relevado en vivo (2026-09-16): esta vista es un agregado por cuenta x mes
(Año, Mes, Clase, Sub Clase, Rubro, Nombre, Saldo Anterior, Debe, Haber,
Neto Mes, Saldo Actual) -- NO tiene columna de Cliente/Proveedor, es
estructuralmente imposible sacarle ese detalle. El pedido de Javier de
"detalle de cliente y proveedor" se resuelve aparte, cruzando esto con el
export de Imputaciones (modules/iibb/export.py, que ya trae TODAS las
cuentas sin filtrar -- la columna "Leyenda" de esa vista trae el nombre
real del cliente/proveedor por linea de asiento).

El combo "Filtro" de esta vista viene en "Año Actual" por default (no
"Mes Actual" como Facturas/Compras/Imputaciones) -- se busca por ese valor
en vez de por ID fijo, mismo motivo que ya documento modules/iibb/export.py
(el ID de estos combos cambio de posicion mas de una vez sin aviso).

Uso:
    python -m modules.balance_mensual.export
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from tools.advertys_session import AdvertysLoginError, base_url, esperar_postback, login

OUT_DIR = Path("exploracion")
OUT_DIR.mkdir(exist_ok=True)
SCREENSHOT_DIR = OUT_DIR / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)

DESTINO = OUT_DIR / "balance_mensual_export.csv"

VIEW_URL_SUFFIX = "Default.aspx#ViewID=ReporteBalanceMensual_ListView&ObjectClassName=DPS_SAS_SR.Module.ReporteBalanceMensual"


class ExportError(RuntimeError):
    pass


def _cambiar_filtro_a_todos(page, valor_actual_esperado="Año Actual") -> None:
    inputs = page.locator("input[id$='_Cb_I']")
    combo_id = None
    for i in range(inputs.count()):
        inp = inputs.nth(i)
        try:
            valor = inp.input_value(timeout=500)
        except Exception:
            continue
        if valor.strip() == valor_actual_esperado:
            combo_id = inp.get_attribute("id")
            break

    if combo_id is None:
        page.screenshot(path=str(SCREENSHOT_DIR / "balance_export_error_filtro.png"), full_page=True)
        raise ExportError(
            f"No se encontro el combo de Filtro (ningun input muestra '{valor_actual_esperado}')."
        )

    page.locator(f"#{combo_id.replace('_Cb_I', '_Cb_B-1')}").click(timeout=3000)
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

    filtro_valor = page.locator(f"#{combo_id}").input_value()
    if filtro_valor.strip() != "Todos":
        page.screenshot(path=str(SCREENSHOT_DIR / "balance_export_error_filtro_valor.png"), full_page=True)
        raise ExportError(
            f"El filtro no quedo en 'Todos' (quedo en '{filtro_valor}'). Se corta para no exportar datos incompletos."
        )


def exportar() -> Path:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(accept_downloads=True)
        try:
            try:
                login(page)
            except AdvertysLoginError:
                page.screenshot(path=str(SCREENSHOT_DIR / "balance_export_error_login.png"))
                raise

            page.goto(base_url() + VIEW_URL_SUFFIX, wait_until="networkidle", timeout=30000)
            esperar_postback(page)
            page.wait_for_timeout(1000)

            _cambiar_filtro_a_todos(page)

            exportar_btn = page.locator('a[title="Exportar a"]')
            if exportar_btn.count() == 0:
                exportar_btn = page.get_by_text("Exportar a", exact=True)
            if exportar_btn.count() == 0:
                page.screenshot(path=str(SCREENSHOT_DIR / "balance_export_error_boton.png"), full_page=True)
                raise ExportError("No se encontro el boton 'Exportar a'.")

            exportar_btn.first.click(force=True)
            page.wait_for_timeout(600)
            page.screenshot(path=str(SCREENSHOT_DIR / "balance_export_menu_formatos.png"), full_page=True)
            opciones = page.evaluate(
                """() => [...document.querySelectorAll('span.dx-vam, a, td')]
                    .map(e => e.textContent.trim())
                    .filter(t => t && t.length < 40 && /csv|xlsx|excel|documento|popup/i.test(t))"""
            )
            print(f"Opciones visibles en 'Exportar a': {opciones}")

            try:
                with page.expect_download(timeout=30000) as download_info:
                    click_js = """() => {
                        const candidatos = [...document.querySelectorAll('span.dx-vam, a, td, div')];
                        const el = candidatos.find(e => {
                            const t = e.textContent.trim();
                            return t.length < 40 && /(Documento CSV|Documento XLSX|Documento Excel)/i.test(t);
                        });
                        if (!el) return null;
                        (el.closest('a') || el).click();
                        return el.textContent.trim();
                    }"""
                    encontrado = page.evaluate(click_js)
                    if not encontrado:
                        raise RuntimeError("No se encontro una opcion de descarga directa (Documento CSV/XLSX) en el menu de 'Exportar a'")
                    print(f"Formato elegido: {encontrado}")
                download = download_info.value
                sufijo = Path(download.suggested_filename).suffix or ".csv"
                destino = DESTINO.with_suffix(sufijo)
                download.save_as(str(destino))
            except Exception as e:
                page.screenshot(path=str(SCREENSHOT_DIR / "balance_export_error_download.png"), full_page=True)
                raise ExportError(f"Error exportando Balance Mensual: {e}") from e

            return destino
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
