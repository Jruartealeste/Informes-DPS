"""
Exporta el listado de Imputaciones (IIBB) desde Advertys: login + navegar
(Consultas > Contabilidad > Imputaciones, por ID exacto de arbol) + filtro
"Todos" + descarga XLSX. Version productiva de explore.py: mismos selectores
ya verificados contra Advertys real, sin las capturas de debug intermedias
(solo se guarda una si algo falla, para diagnostico).

A diferencia de los otros 8 modulos automatizados, este NO esta sumado a
`tools/actualizar_todo.py` (ver README seccion 6): el export de Imputaciones
es mucho mas pesado (~22.700 filas vs. cientos en el resto). Se corre aparte,
a pedido, cuando se pide actualizar IIBB puntualmente -- ver skill
actualizar-informe / workflows/actualizar_informe.md.

Uso:
    python -m modules.iibb.export
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from tools.advertys_session import AdvertysLoginError, esperar_postback, login

OUT_DIR = Path("exploracion")
OUT_DIR.mkdir(exist_ok=True)
SCREENSHOT_DIR = OUT_DIR / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)

DESTINO = OUT_DIR / "iibb_export.xlsx"

# Hay mas de un nodo "Contabilidad" en el menu (Administracion tiene el
# suyo, separado del de Consultas) -- se navega por ID exacto del arbol, no
# por texto. Ver modules/iibb/explore.py (relevado 2026-07-23).
CONTABILIDAD_ID = "Vertical_NC_NB_ITC3i0_TL_N1"
IMPUTACIONES_ID = "Vertical_NC_NB_ITC3i0_TL_N1_1"


class ExportError(RuntimeError):
    pass


def _cambiar_filtro_a_todos(page) -> None:
    """Busca el combo de Filtro por el VALOR actual ('Mes Actual', el
    default de esta vista) en vez de por un ID fijo -- ese ID ya cambio
    dos veces sin aviso (2026-08-12 y 2026-08-19), asi que hardcodear un
    tercero se romperia igual la proxima vez que Advertys reordene la
    toolbar. Cambia el combo a 'Todos' y verifica que haya quedado ahi
    antes de exportar (ver ExportError abajo: este filtro ya dio un falso
    OK una vez -- el boton se encontro pero el combo quedo en "Mes Actual"
    y el export salio con 291 filas en vez de ~22.700, sin ningun error
    visible)."""
    inputs = page.locator("input[id$='_Cb_I']")
    combo_id = None
    for i in range(inputs.count()):
        inp = inputs.nth(i)
        try:
            valor = inp.input_value(timeout=500)
        except Exception:
            continue
        if valor.strip() == "Mes Actual":
            combo_id = inp.get_attribute("id")
            break

    if combo_id is None:
        page.screenshot(path=str(SCREENSHOT_DIR / "iibb_export_error_filtro.png"), full_page=True)
        raise ExportError(
            "No se encontro el combo de Filtro (ningun input muestra 'Mes Actual'). "
            "Sin filtro en 'Todos' el export solo trae el mes en curso, asi que se "
            "corta acá en vez de exportar datos incompletos en silencio."
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
        page.screenshot(path=str(SCREENSHOT_DIR / "iibb_export_error_filtro_valor.png"), full_page=True)
        raise ExportError(
            f"El filtro no quedo en 'Todos' (quedo en '{filtro_valor}'). "
            "Exportar así traeria datos incompletos, así que se corta acá."
        )


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
                page.screenshot(path=str(SCREENSHOT_DIR / "iibb_export_error_login.png"))
                raise

            _click_por_texto_o_title(page, "Consultas")
            page.wait_for_timeout(800)

            try:
                page.locator(f"#{CONTABILIDAD_ID}").click(timeout=10000)
            except Exception as e:
                page.screenshot(path=str(SCREENSHOT_DIR / "iibb_export_error_menu.png"), full_page=True)
                raise ExportError(f"No se pudo clickear la carpeta Contabilidad por ID: {e}") from e
            page.wait_for_timeout(800)

            try:
                page.locator(f"#{IMPUTACIONES_ID}").click(timeout=10000)
            except Exception as e:
                page.screenshot(path=str(SCREENSHOT_DIR / "iibb_export_error_menu.png"), full_page=True)
                raise ExportError(f"No se pudo clickear el nodo Imputaciones por ID: {e}") from e
            esperar_postback(page)

            # Filtro de vista: Advertys trae "Mes Actual" por default. Sin
            # cambiarlo a "Todos" el export trae ~300 filas en vez de
            # ~22.700 (relevado 2026-07-23). El ID de este combo cambio DOS
            # veces sin aviso (de "_a3_" a "_a5_" el 2026-08-12, y de nuevo
            # el 2026-08-19 -- confirmado en vivo, ExportError real en
            # produccion), probablemente por otro item de toolbar que corre
            # el indice cada vez. Un tercer ID hardcodeado se rompería
            # igual la proxima vez, asi que se busca el combo por su VALOR
            # actual ("Mes Actual") en vez de por ID -- mismo patron ya
            # probado en modules/iibb/crawl_oc_por_factura.abrir_combo_filtro().
            _cambiar_filtro_a_todos(page)

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
                with page.expect_download(timeout=30000) as download_info:
                    encontrado = page.evaluate(click_js, "Documento XLSX")
                    if not encontrado:
                        raise RuntimeError("No se encontro el item 'Documento XLSX' en el DOM")
                download = download_info.value
                download.save_as(str(DESTINO))
            except Exception as e:
                page.screenshot(path=str(SCREENSHOT_DIR / "iibb_export_error_download.png"), full_page=True)
                raise ExportError(f"Error exportando Imputaciones (IIBB): {e}") from e

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
