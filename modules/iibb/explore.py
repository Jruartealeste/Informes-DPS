"""
Script de exploracion (no productivo): entra a Advertys con las credenciales
de .env, navega Consultas > Contabilidad > Imputaciones y exporta a Excel.

Igual que Facturas, "Contabilidad" es un nodo del arbol de navegacion sin
URL directa, con un nivel intermedio (primero expandir "Contabilidad" antes
de clickear el nodo hoja "Imputaciones").

El filtro de esta vista es un combo de toolbar "Filtro" con opciones Año
Actual/Todos/Mes Actual (default)/Año Anterior/Mes Anterior -- mismo patron
que Facturas/Compras. Hay que ponerlo en "Todos" antes de exportar, si no
el export solo trae el mes en curso (relevado 2026-07-23: "Mes Actual" trae
~600 filas contra ~22700 de "Todos").

Uso:
    python -m modules.iibb.explore
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
            page.screenshot(path=str(SCREENSHOT_DIR / "iibb_error_login.png"))
            browser.close()
            sys.exit(1)

        print(f"Login OK. URL actual: {page.url}")
        page.wait_for_timeout(1200)

        print("Expandiendo grupo 'Consultas' del menu...")
        if not click_por_texto_o_title(page, "Consultas"):
            print("Aviso: no se encontro el grupo 'Consultas' por texto exacto, sigo igual.")
        page.wait_for_timeout(800)

        # Mismo patron que modules/facturas/explore.py: navegar por ID exacto
        # del arbol, no por texto (hay mas de un nodo "Contabilidad" en el
        # menu -- Administracion tiene el suyo, separado del de Consultas).
        # Relevado 2026-07-23: grupo "Consultas" (ITC3i0) > carpeta
        # "Contabilidad" (N1) > hoja "Imputaciones" (N1_1).
        CONTABILIDAD_ID = "Vertical_NC_NB_ITC3i0_TL_N1"
        IMPUTACIONES_ID = "Vertical_NC_NB_ITC3i0_TL_N1_1"

        print("Expandiendo carpeta 'Contabilidad' (dentro de Consultas, por ID)...")
        try:
            page.locator(f"#{CONTABILIDAD_ID}").click(timeout=10000)
        except Exception as e:
            print(f"ERROR: no se pudo clickear la carpeta Contabilidad por ID: {e}")
            (OUT_DIR / "iibb_menu.html").write_text(page.content(), encoding="utf-8")
            page.screenshot(path=str(SCREENSHOT_DIR / "iibb_error_menu.png"), full_page=True)
            browser.close()
            sys.exit(1)
        page.wait_for_timeout(800)

        print("Haciendo click en 'Imputaciones' (por ID)...")
        try:
            page.locator(f"#{IMPUTACIONES_ID}").click(timeout=10000)
        except Exception as e:
            print(f"ERROR: no se pudo clickear el nodo Imputaciones por ID: {e}")
            (OUT_DIR / "iibb_menu.html").write_text(page.content(), encoding="utf-8")
            page.screenshot(path=str(SCREENSHOT_DIR / "iibb_error_menu.png"), full_page=True)
            browser.close()
            sys.exit(1)
        esperar_postback(page)
        print(f"URL tras click en Imputaciones: {page.url}")
        page.screenshot(path=str(SCREENSHOT_DIR / "iibb_01_listado.png"), full_page=True)

        print("Cambiando filtro a 'Todos'...")
        filtro_btn = page.locator('#Vertical_TB_Menu_ITCNT6_xaf_a3_Cb_B-1')
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
            page.screenshot(path=str(SCREENSHOT_DIR / "iibb_02_filtro_todos.png"), full_page=True)
        else:
            print("Aviso: no se encontro el combo de Filtro esperado (ID puede haber cambiado); sigo sin cambiarlo.")

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
            with page.expect_download(timeout=30000) as download_info:
                encontrado = page.evaluate(click_js, "Documento XLSX")
                if not encontrado:
                    raise RuntimeError("No se encontro el item 'Documento XLSX' en el DOM")
            download = download_info.value
            destino = OUT_DIR / "iibb_export.xlsx"
            download.save_as(str(destino))
            print(f"OK: descarga guardada en {destino}")
        except Exception as e:
            print(f"ERROR al descargar: {e}")
            page.screenshot(path=str(SCREENSHOT_DIR / "iibb_error_export.png"), full_page=True)

        browser.close()


if __name__ == "__main__":
    main()
