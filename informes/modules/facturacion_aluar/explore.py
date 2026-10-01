"""
Exploracion puntual (no productiva, se borra o se reemplaza por
crawl_facturas_relacionadas.py una vez confirmado el selector real): abrir
una factura Producción (FP) conocida que fue cancelada (000500000555) y su
cancelación (000500000017) para encontrar dónde vive el campo "Factura
Relacionada" en el detalle de Advertys. Solo lectura -- no clickea
Nuevo/Editar/Guardar.

Uso:
    python -m modules.facturacion_aluar.explore_relacionada
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from tools.advertys_session import AdvertysLoginError, esperar_postback, login, base_url

OUT_DIR = Path("exploracion")
SCREENSHOT_DIR = OUT_DIR / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


def ir_a_factura(page, numero_referencia: str) -> bool:
    direct_url = f"{base_url()}Default.aspx#ViewID=DPS_Factura_ListView&ObjectClassName=DPS_SAS_SR.Module.DPS_Factura"
    page.goto(direct_url, wait_until="networkidle", timeout=30000)
    esperar_postback(page)
    page.wait_for_timeout(800)

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
            page.wait_for_timeout(500)
            item = page.get_by_text("Todos", exact=True)
            if item.count() > 0:
                item.first.click(timeout=3000)
                esperar_postback(page)
            break

    search_inputs = page.locator("input[id$='_Ed_I']")
    encontrado = False
    for i in range(search_inputs.count()):
        inp = search_inputs.nth(i)
        try:
            valor = inp.input_value(timeout=500)
        except Exception:
            continue
        if valor.strip() == "Texto a buscar...":
            inp.click()
            inp.fill(str(numero_referencia))
            inp.press("Enter")
            encontrado = True
            break
    if not encontrado:
        raise RuntimeError("No se encontro el buscador")
    esperar_postback(page)
    page.wait_for_timeout(800)

    fila = page.get_by_text(str(numero_referencia), exact=True)
    if fila.count() == 0:
        return False
    fila.first.click(timeout=5000)
    esperar_postback(page)
    page.wait_for_timeout(800)
    return True


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(accept_downloads=True)
        try:
            login(page)
        except AdvertysLoginError as e:
            print(f"ERROR: {e}")
            sys.exit(1)

        for numero in ["000500000015"]:
            print(f"\n=== Factura {numero} ===")
            if not ir_a_factura(page, numero):
                print("  no encontrada")
                continue
            page.screenshot(path=str(SCREENSHOT_DIR / f"aluar_relacionada_{numero}_detalle.png"), full_page=True)

            # Listar todas las pestañas visibles del detalle
            tabs = page.locator("[role='tab'], .dxtc-tab, td.dxtc-tab")
            nombres = []
            for i in range(tabs.count()):
                try:
                    t = tabs.nth(i).inner_text().strip()
                    if t:
                        nombres.append(t)
                except Exception:
                    continue
            print("  pestañas encontradas:", nombres)

            texto = page.inner_text("body")
            idx = texto.lower().find("relacionad")
            if idx == -1:
                print("  'relacionad' NO aparece en el texto visible de la pestaña actual")
            else:
                print("  match 'relacionad':", repr(texto[max(0, idx-60):idx+120]))

        browser.close()


if __name__ == "__main__":
    main()
