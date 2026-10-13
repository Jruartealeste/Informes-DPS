"""
Script de RECONOCIMIENTO de solo lectura: loguea en Advertys, busca en el
arbol de navegacion Entidades > Productos y saca capturas. Nunca clickea
Nuevo/Editar/Guardar/Eliminar (ver salvaguarda "Advertys es de solo
lectura" en CLAUDE.md). Objetivo: ver si el listado maestro de Productos
trae el Anunciante de cada producto, para precargar el combo Producto del
alta de OT en `ot/` sin releverlo cliente por cliente.

Uso:
    python -m modules.productos.explore
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

from tools.advertys_session import AdvertysLoginError, esperar_postback, login

SHOTS = Path("exploracion/screenshots")
SHOTS.mkdir(parents=True, exist_ok=True)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        try:
            login(page)
        except AdvertysLoginError as e:
            print(f"Login fallido: {e}")
            browser.close()
            return
        page.wait_for_timeout(2000)
        esperar_postback(page)
        page.screenshot(path=str(SHOTS / "prod_00_home.png"))
        # Expandir el grupo "Entidades" del menu lateral (solo navegacion) y listar sus nodos
        page.locator("span.dxnb-ghtext:visible", has_text="Entidades").first.click()
        esperar_postback(page)
        page.wait_for_timeout(1500)
        page.screenshot(path=str(SHOTS / "prod_01_entidades.png"))
        # Expandir carpetas del arbol (solo navegacion) hasta ver "Productos"
        for carpeta in ("Generales", "Productos"):
            page.get_by_text(carpeta, exact=True).locator("visible=true").first.click()
            esperar_postback(page)
            page.wait_for_timeout(1200)
        page.screenshot(path=str(SHOTS / "prod_03_productos.png"))
        # Entrar al listado maestro "Producto" (hoja del arbol, solo navegacion)
        page.get_by_text("Producto", exact=True).locator("visible=true").first.click()
        esperar_postback(page)
        page.wait_for_timeout(2500)
        page.screenshot(path=str(SHOTS / "prod_04_listado.png"))
        print("URL:", page.url)
        print([c.strip() for c in page.locator("td.dxgvHeader").all_inner_texts()])
        browser.close()


if __name__ == "__main__":
    main()
