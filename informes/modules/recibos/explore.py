"""
Script de exploracion (no productivo): entra a Advertys con las credenciales
de .env, navega Administracion > Recibo Cliente y releva:

1. Si el listado exporta a Excel en bloque, y que columnas trae (busca si ya
   viene ahi la referencia a la factura cancelada, lo que evitaria el paso 2).
2. Si NO viene la referencia en el listado: abre el primer recibo real y
   releva la pestana "Referencias Canceladas" -- que columnas trae, si esa
   grilla interna tiene su propio export, y el formato de la referencia a la
   factura (para poder cruzar con facturas.clave_factura).

Es el primer paso de relevar_modulo_nuevo.md para el modulo nuevo
"Cobranza x Factura Venta x Factura Compra" (pedido de Javier, 2026-08-04):
la pieza que falta es justamente el lado "Recibo Cliente", los otros dos
saltos (factura -> N de OC, y detalle de la OC) ya existen en
modules/iibb/crawl_oc_por_factura.py y modules/ordenes_compra.

SOLO LECTURA: login, navegacion entre vistas, expandir un recibo para verlo,
exportacion. Ningun click apunta a "Nuevo/Editar/Guardar/Eliminar" -- ver
salvaguarda en informes/CLAUDE.md.

Uso:
    python -m modules.recibos.explore
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


def click_por_texto_o_title(page, texto) -> bool:
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


def click_boton_visible(page, texto, timeout=5000):
    candidatos = page.get_by_text(texto, exact=True)
    for i in range(candidatos.count()):
        cand = candidatos.nth(i)
        try:
            if cand.is_visible():
                cand.click(timeout=timeout)
                return True
        except Exception:
            continue
    return False


def leer_grid_visible(page):
    """Lee la grilla ASPxGridView actualmente visible (headers + filas),
    mismo patron que modules/iibb/crawl_oc_por_factura.leer_grid_visible."""
    tablas = page.locator("table[id*='DXMainTable']")
    tabla = None
    for i in range(tablas.count()):
        candidata = tablas.nth(i)
        try:
            if candidata.is_visible():
                tabla = candidata
                break
        except Exception:
            continue
    if tabla is None:
        return [], []

    headers_loc = tabla.locator("td[class*='dxgvHeader']")
    headers = [headers_loc.nth(i).inner_text().strip() for i in range(headers_loc.count())]
    if not headers:
        return [], []

    filas_loc = tabla.locator("tr[id*='DXDataRow']")
    filas = []
    for i in range(filas_loc.count()):
        celdas = filas_loc.nth(i).locator("td")
        n = celdas.count()
        fila = {nombre: (celdas.nth(j).inner_text().strip() if j < n else "") for j, nombre in enumerate(headers)}
        filas.append(fila)
    return headers, filas


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
            page.screenshot(path=str(SCREENSHOT_DIR / "recibos_error_login.png"))
            browser.close()
            sys.exit(1)

        print(f"Login OK. URL actual: {page.url}")
        page.screenshot(path=str(SCREENSHOT_DIR / "recibos_01_menu.png"), full_page=True)

        print("Expandiendo grupo 'Administracion' del menu...")
        if not click_por_texto_o_title(page, "Administracion"):
            print("Aviso: no se encontro el grupo 'Administracion' por texto exacto, sigo igual.")
        page.wait_for_timeout(800)
        page.screenshot(path=str(SCREENSHOT_DIR / "recibos_02_admin_expandido.png"), full_page=True)

        print("Haciendo click en 'Recibo Cliente'...")
        if not click_por_texto_o_title(page, "Recibo Cliente"):
            print("ERROR: no se encontro el nodo 'Recibo Cliente' en el menu.")
            (OUT_DIR / "recibos_menu.html").write_text(page.content(), encoding="utf-8")
            page.screenshot(path=str(SCREENSHOT_DIR / "recibos_error_menu.png"), full_page=True)
            browser.close()
            sys.exit(1)
        esperar_postback(page)
        print(f"URL tras click en Recibo Cliente: {page.url}")
        page.screenshot(path=str(SCREENSHOT_DIR / "recibos_03_listado.png"), full_page=True)
        (OUT_DIR / "recibos_listado.html").write_text(page.content(), encoding="utf-8")

        print("Intentando cambiar filtro a la opcion mas amplia (si existe en esta vista)...")
        filtro_btn = page.locator('td[id$="_Cb_B-1"]').first
        if filtro_btn.count() > 0:
            filtro_btn.click()
            page.wait_for_timeout(800)
            page.screenshot(path=str(SCREENSHOT_DIR / "recibos_04_filtro_abierto.png"), full_page=True)
            (OUT_DIR / "recibos_filtro_opciones.html").write_text(page.content(), encoding="utf-8")
            encontrado = False
            for opcion in ("Todos", "Todas", "Año Actual", "Ano Actual"):
                item = page.get_by_text(opcion, exact=True).first
                if item.count() > 0:
                    try:
                        item.click(timeout=3000)
                        encontrado = True
                        print(f"  -> filtro puesto en '{opcion}'")
                        break
                    except Exception:
                        continue
            if not encontrado:
                print("  Aviso: no se encontro una opcion de filtro amplia conocida; reviso el HTML volcado.")
                page.keyboard.press("Escape")
            esperar_postback(page)
            page.screenshot(path=str(SCREENSHOT_DIR / "recibos_05_filtro_aplicado.png"), full_page=True)
            (OUT_DIR / "recibos_filtro_aplicado.html").write_text(page.content(), encoding="utf-8")
        else:
            print("Aviso: no se encontro el boton de filtro habitual; sigo sin cambiarlo.")

        print("Intentando exportar el LISTADO a XLSX (para ver si trae la referencia a la factura)...")
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
            with page.expect_download(timeout=15000) as download_info:
                encontrado = page.evaluate(click_js, "Documento XLSX")
                if not encontrado:
                    raise RuntimeError("No se encontro el item 'Documento XLSX' en el DOM")
            download = download_info.value
            destino = OUT_DIR / "recibos_export.xlsx"
            download.save_as(str(destino))
            print(f"OK: export del listado guardado en {destino}")
        except Exception as e:
            print(f"Aviso: no se pudo exportar el listado (puede que este modulo no tenga export de grilla): {e}")
            page.screenshot(path=str(SCREENSHOT_DIR / "recibos_error_export_listado.png"), full_page=True)

        print("Abriendo el primer recibo del listado (solo lectura, para ver la pestana 'Referencias Canceladas')...")
        filas_loc = page.locator("tr[id*='DXDataRow']")
        if filas_loc.count() == 0:
            print("ERROR: no hay filas visibles en el listado, no se puede abrir un recibo de ejemplo.")
            browser.close()
            sys.exit(1)
        try:
            filas_loc.first.click(timeout=5000)
            esperar_postback(page)
        except Exception as e:
            print(f"ERROR al abrir el primer recibo: {e}")
            page.screenshot(path=str(SCREENSHOT_DIR / "recibos_error_abrir_recibo.png"), full_page=True)
            browser.close()
            sys.exit(1)

        print(f"URL del recibo abierto: {page.url}")
        page.screenshot(path=str(SCREENSHOT_DIR / "recibos_06_detalle_recibo.png"), full_page=True)
        (OUT_DIR / "recibos_detalle_recibo.html").write_text(page.content(), encoding="utf-8")

        print("Buscando la pestana 'Referencias Canceladas'...")
        if not click_boton_visible(page, "Referencias Canceladas"):
            print("ERROR: no se encontro una pestana/boton visible con texto exacto 'Referencias Canceladas'.")
            print("Reviso recibos_detalle_recibo.html a mano para ver el nombre real de la pestana.")
            browser.close()
            sys.exit(1)
        esperar_postback(page)
        page.wait_for_timeout(600)
        page.screenshot(path=str(SCREENSHOT_DIR / "recibos_07_referencias_canceladas.png"), full_page=True)
        (OUT_DIR / "recibos_referencias_canceladas.html").write_text(page.content(), encoding="utf-8")

        headers, filas = leer_grid_visible(page)
        print(f"Columnas de 'Referencias Canceladas': {headers}")
        print(f"Filas relevadas en este recibo de ejemplo: {len(filas)}")
        for fila in filas[:5]:
            print(f"  {fila}")

        print("Buscando si esta sub-grilla tiene su propio export (boton XLSX dentro de la pestana)...")
        tiene_export_propio = page.locator('span.dx-vam:has-text("XLSX")').count() > 0
        print(f"  -> boton con texto 'XLSX' visible en esta vista: {tiene_export_propio}")

        browser.close()
        print("\nListo. Revisar en exploracion/: recibos_listado.html, recibos_export.xlsx (si se genero),")
        print("recibos_detalle_recibo.html, recibos_referencias_canceladas.html, y las screenshots recibos_0*.")


if __name__ == "__main__":
    main()
