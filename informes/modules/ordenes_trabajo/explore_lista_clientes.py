"""
Script de RECONOCIMIENTO de solo lectura: loguea en Advertys y saca
capturas del listado maestro "Clientes" (Entidades > Generales > Clientes
> Clientes -- ViewID=Cliente_ListView), sus dos páginas. Nunca clickea
Nuevo/Editar/Guardar/Eliminar. Ver salvaguarda "Advertys es de solo
lectura" en CLAUDE.md.

Por qué captura en vez de volcar la grilla a JSON: el id de la tabla de
DevExpress en esta vista es dinámico por sesión (ej.
`Vertical_v47_11554755_LE_v47_DXMainTable`, el numero cambia en cada
corrida) y sus filas no usan la clase `dxgvDataRow` que sí tienen otras
grillas del sistema (ver `modules/ordenes_trabajo/ingest.py` y compañía) --
un selector CSS estable no se pudo encontrar en el tiempo relevado
(2026-09-24). Leer las capturas con la tool Read es más confiable acá.

Util para relevar, cliente por cliente, el/los Anunciante(s) reales de
Advertys que corresponden a un cliente de `ot/` -- confirmado 2026-09-24
que Cliente y Anunciante NO son 1 a 1 (ej. FATE en Advertys son ~6
Anunciantes separados: "FATE S.A.I.C.I.", "FATE - AGRICOLA", etc.), asi
que `ot/`'s `Cliente.anunciantes` (tabla `cliente_anunciantes`) es 1 a N
y hay que completarlo a mano con lo que se lee acá.

Uso:
    python -m modules.ordenes_trabajo.explore_lista_clientes
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

from tools.advertys_session import AdvertysLoginError, base_url, esperar_postback, login

OUT_DIR = Path("exploracion")
SCREENSHOT_DIR = OUT_DIR / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

DIRECT_URL_SUFFIX = "Default.aspx#ViewID=Cliente_ListView&ObjectClassName=DPS_SAS_SR.Module.Cliente"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            login(page)
        except AdvertysLoginError as e:
            print(f"Login fallido: {e}")
            browser.close()
            return

        page.wait_for_timeout(1000)
        page.goto(base_url() + DIRECT_URL_SUFFIX, wait_until="networkidle", timeout=30000)
        esperar_postback(page)
        page.wait_for_timeout(1500)

        destino1 = SCREENSHOT_DIR / "ot_clientes_listview_p1.png"
        page.screenshot(path=str(destino1), full_page=True)
        print(f"-> {destino1}")

        siguiente = page.get_by_text("2", exact=True)
        if siguiente.count():
            siguiente.first.click()
            esperar_postback(page)
            page.wait_for_timeout(1500)
            destino2 = SCREENSHOT_DIR / "ot_clientes_listview_p2.png"
            page.screenshot(path=str(destino2), full_page=True)
            print(f"-> {destino2}")

        browser.close()


if __name__ == "__main__":
    main()
