"""
Script de exploracion (no productivo): entra a Advertys con las credenciales
de .env, navega DIRECTO por URL a "Orden Publicidad > Navegacion" y prueba
exportar a Excel para relevar las columnas reales de ese modulo.

Camino real por menu (relevado primero, ver git history de este archivo):
grupo de sidebar "Medios" (NO el nodo "Entidades > Generales > Negocios >
Medios", que tiene el mismo texto y esta mas arriba en el DOM -- un click
generico por texto matchea ese primero) > carpeta "Ordenes Publicidad" >
hoja "Navegacion" (NO "Consulta", el otro nodo hoja: esa grilla no trae
NINGUNA columna de monto, ver docstring de config.py). Una vez tenida la
URL real (ViewID=OrdenPublicidad_ListView), se navega directo por URL como
ya hacen Ordenes de Compra/Estimados/OT -- mas simple y mas estable que
repetir el click por ID de nodo del arbol en cada corrida.

Uso:
    python -m modules.ordenes_publicidad.explore
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from tools.advertys_session import AdvertysLoginError, base_url, esperar_postback, login

OUT_DIR = Path("exploracion")
OUT_DIR.mkdir(exist_ok=True)
SCREENSHOT_DIR = OUT_DIR / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)

DIRECT_URL_SUFFIX = "Default.aspx#ViewID=OrdenPublicidad_ListView&ObjectClassName=DPS_SAS_SR.Module.OrdenPublicidad"


def _abrir_combo_filtro(page) -> bool:
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


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(accept_downloads=True)

        try:
            login(page)
        except AdvertysLoginError as e:
            print(f"ERROR: {e}")
            page.screenshot(path=str(SCREENSHOT_DIR / "op_error_login.png"))
            browser.close()
            sys.exit(1)

        print("Login OK. Navegando directo a Orden Publicidad > Navegacion...")
        direct_url = f"{base_url()}{DIRECT_URL_SUFFIX}"
        page.goto(direct_url, wait_until="networkidle", timeout=30000)
        esperar_postback(page)
        page.wait_for_timeout(800)
        page.screenshot(path=str(SCREENSHOT_DIR / "op_01_listado.png"), full_page=True)
        (OUT_DIR / "op_listado.html").write_text(page.content(), encoding="utf-8")

        print("Cambiando filtro a 'Todos' para traer el historico completo...")
        if _abrir_combo_filtro(page):
            page.wait_for_timeout(500)
            item = page.get_by_text("Todos", exact=True)
            if item.count() > 0:
                item.first.click(timeout=3000)
                esperar_postback(page)
                print("Filtro seteado a 'Todos'")
            else:
                print("Aviso: no aparecio la opcion 'Todos' en el combo, sigo con el default")
                page.keyboard.press("Escape")
        else:
            print("Aviso: no se encontro el combo de Filtro, sigo con el default")
        page.wait_for_timeout(500)
        page.screenshot(path=str(SCREENSHOT_DIR / "op_02_filtro_todos.png"), full_page=True)

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
            destino = OUT_DIR / "ordenes_publicidad_export.xlsx"
            download.save_as(str(destino))
            print(f"OK: descarga guardada en {destino}")
        except Exception as e:
            print(f"ERROR al descargar: {e}")
            page.screenshot(path=str(SCREENSHOT_DIR / "op_error_export.png"), full_page=True)

        browser.close()


if __name__ == "__main__":
    main()
