"""
Script de exploracion (no productivo): entra a Advertys con las credenciales
de .env, navega Administracion > Compras y prueba exportar a Excel para
relevar las columnas reales de ese modulo.

A diferencia de Orden Trabajo, "Compras" no tiene una URL directa con
ObjectClassName: es un nodo del arbol de navegacion (TreeView) que dispara
un postback via JS al hacer click. Por eso navegamos clickeando el menu
en vez de ir directo a una URL.

Uso:
    python explore_compras.py
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
    """Busca un nodo del menu por su texto visible o su atributo title y le hace click via JS
    (evita problemas de visibilidad/scroll dentro del arbol colapsable de DevExpress)."""
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
            page.screenshot(path=str(SCREENSHOT_DIR / "compras_error_login.png"))
            browser.close()
            sys.exit(1)

        print(f"Login OK. URL actual: {page.url}")
        page.screenshot(path=str(SCREENSHOT_DIR / "compras_01_menu.png"), full_page=True)

        print("Expandiendo grupo 'Administracion' del menu...")
        if not click_por_texto_o_title(page, "Administracion"):
            print("Aviso: no se encontro el grupo 'Administracion' por texto exacto, sigo igual.")
        page.wait_for_timeout(800)
        page.screenshot(path=str(SCREENSHOT_DIR / "compras_02_admin_expandido.png"), full_page=True)

        print("Haciendo click en 'Compras'...")
        if not click_por_texto_o_title(page, "Compras"):
            print("ERROR: no se encontro el nodo 'Compras' en el menu.")
            (OUT_DIR / "compras_menu.html").write_text(page.content(), encoding="utf-8")
            page.screenshot(path=str(SCREENSHOT_DIR / "compras_error_menu.png"), full_page=True)
            browser.close()
            sys.exit(1)
        esperar_postback(page)
        print(f"URL tras click en Compras: {page.url}")
        page.screenshot(path=str(SCREENSHOT_DIR / "compras_03_listado.png"), full_page=True)
        (OUT_DIR / "compras_listado.html").write_text(page.content(), encoding="utf-8")

        print("Intentando cambiar filtro a 'Todas' (si existe en esta vista)...")
        filtro_btn = page.locator('td[id$="_Cb_B-1"]').first
        if filtro_btn.count() > 0:
            filtro_btn.click()
            page.wait_for_timeout(800)
            page.screenshot(path=str(SCREENSHOT_DIR / "compras_04_filtro_abierto.png"), full_page=True)
            todas_item = page.get_by_text("Todas", exact=True).first
            try:
                todas_item.click(timeout=5000)
            except Exception:
                page.evaluate(
                    """() => {
                        const els = [...document.querySelectorAll('td, div, span, li')];
                        const el = els.find(e => e.textContent.trim() === 'Todas');
                        if (el) el.click();
                    }"""
                )
            esperar_postback(page)
            page.screenshot(path=str(SCREENSHOT_DIR / "compras_05_filtro_todas.png"), full_page=True)
            (OUT_DIR / "compras_filtro_todas.html").write_text(page.content(), encoding="utf-8")
        else:
            print("Aviso: no se encontro el boton de filtro habitual; sigo sin cambiarlo.")

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
            destino = OUT_DIR / "compras_export.xlsx"
            download.save_as(str(destino))
            print(f"OK: descarga guardada en {destino}")
        except Exception as e:
            print(f"ERROR al descargar: {e}")
            page.screenshot(path=str(SCREENSHOT_DIR / "compras_error_export.png"), full_page=True)

        browser.close()


if __name__ == "__main__":
    main()
