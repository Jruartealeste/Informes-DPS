"""
Script de RECONOCIMIENTO (solo lectura, no escribe nada en Advertys):
navega hasta un Estimado de Costos puntual (en modo VISTA, sin entrar a
Editar) y abre la pestana 'Imputaciones' para revisar por que Advertys
rechaza la transicion a 'Finalizado' con el mensaje "Los importes
tercerizados no estan CANCELADOS".

No clickea 'Editar', 'Guardar' ni ningun boton de 'Cambiar estado a: X'.
Ver salvaguarda "Advertys es de solo lectura" en CLAUDE.md.

Uso:
    python -m modules.ordenes_trabajo.ver_imputaciones <numero_ot> <numero_estimado>
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

OUT_DIR = Path("exploracion") / "screenshots"
OUT_DIR.mkdir(parents=True, exist_ok=True)


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


def shot(page, nombre):
    destino = OUT_DIR / f"{nombre}.png"
    page.screenshot(path=str(destino), full_page=True)
    print(f"  -> {destino}")


def click_texto_visible(page, texto, timeout=5000):
    """Clickea el primer elemento VISIBLE con este texto exacto (evita
    matchear items ocultos del menu lateral con el mismo texto)."""
    candidatos = page.get_by_text(texto, exact=True)
    n = candidatos.count()
    for i in range(n):
        cand = candidatos.nth(i)
        try:
            if cand.is_visible():
                cand.click(timeout=timeout)
                return True
        except Exception:
            continue
    return False


def buscar_texto(page, texto):
    inputs = page.locator("input[id$='_Ed_I']")
    for i in range(inputs.count()):
        inp = inputs.nth(i)
        try:
            valor = inp.input_value(timeout=500)
        except Exception:
            continue
        if valor.strip() == "Texto a buscar...":
            inp.click()
            inp.fill(str(texto))
            inp.press("Enter")
            return True
    return False


def abrir_combo_filtro(page):
    inputs = page.locator("input[id$='_Cb_I']")
    for i in range(inputs.count()):
        inp = inputs.nth(i)
        try:
            valor = inp.input_value(timeout=500)
        except Exception:
            continue
        if valor.strip() in ("Mes Actual", "Abiertas"):
            btn_id = inp.get_attribute("id").replace("_Cb_I", "_Cb_B-1")
            page.locator(f"#{btn_id}").click(timeout=3000)
            return True
    return False


def login(page):
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
        shot(page, "00_error_login_imputaciones")
        sys.exit(1)
    print("Login OK.")


def ir_a_ot(page, numero_ot):
    base_url = URL.split("Login.aspx")[0]
    direct_url = f"{base_url}Default.aspx#ViewID=OrdenTrabajo_ListView&ObjectClassName=DPS_SAS_SR.Module.OrdenTrabajo"
    page.goto(direct_url, wait_until="networkidle", timeout=30000)
    esperar_postback(page)
    page.wait_for_timeout(800)

    if abrir_combo_filtro(page):
        page.wait_for_timeout(500)
        item = page.get_by_text("Todas", exact=True)
        if item.count() > 0:
            item.first.click(timeout=3000)
            esperar_postback(page)
        else:
            page.keyboard.press("Escape")
        page.wait_for_timeout(500)

    if not buscar_texto(page, numero_ot):
        raise RuntimeError("No se encontro el buscador 'Texto a buscar...'")
    esperar_postback(page)
    page.wait_for_timeout(800)

    fila = page.get_by_text(str(numero_ot), exact=True)
    if fila.count() == 0:
        raise RuntimeError(f"No se encontro la OT {numero_ot} en la grilla")
    fila.first.click(timeout=5000)
    esperar_postback(page)
    page.wait_for_timeout(800)


def ver_imputaciones(numero_ot, numero_estimado):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(accept_downloads=True)
        login(page)

        print(f"Navegando a OT {numero_ot} > Estimados Costo > {numero_estimado} (modo vista)...")
        ir_a_ot(page, numero_ot)
        if not click_texto_visible(page, "Estimados Costo"):
            raise RuntimeError("No se encontro la pestana 'Estimados Costo'")
        esperar_postback(page)
        page.wait_for_timeout(800)

        fila_est = page.get_by_text(str(numero_estimado), exact=True)
        if fila_est.count() == 0:
            raise RuntimeError(f"No se encontro el estimado {numero_estimado} en la grilla")
        fila_est.first.click(timeout=5000)
        esperar_postback(page)
        page.wait_for_timeout(800)
        shot(page, f"est_{numero_estimado}_imp_00_detalle")

        for pestana, tag in (
            ("Facturas", "02_facturas"),
            ("Ordenes Compra", "03_ordenes_compra"),
            ("Imputaciones", "01_imputaciones"),
        ):
            print(f"  Abriendo pestana '{pestana}' (solo lectura)...")
            if not click_texto_visible(page, pestana):
                print(f"  AVISO: no se encontro la pestana '{pestana}' visible, sigo con la siguiente.")
                continue
            esperar_postback(page)
            page.wait_for_timeout(800)
            shot(page, f"est_{numero_estimado}_imp_{tag}")

        print("Reconocimiento terminado. No se clickeo 'Editar' ni 'Guardar'.")
        browser.close()


def main():
    if not URL or not USER or not PASSWORD:
        print("ERROR: completa ADVERTYS_URL, ADVERTYS_USER y ADVERTYS_PASSWORD en .env")
        sys.exit(1)
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    ver_imputaciones(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    main()
