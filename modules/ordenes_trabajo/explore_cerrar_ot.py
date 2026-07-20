"""
Script de RECONOCIMIENTO (no productivo, no escribe nada en Advertys):
navega hasta la OT indicada, entra en modo edicion y saca capturas de
cada pantalla del flujo de cierre (ver workflow acordado con Javier
2026-07-20), para relevar los selectores exactos antes de escribir el
script que efectivamente cambia estados y guarda.

Este script NO clickea ningun "Guardar" ni cambia ningun combo de
estado -- solo navega y entra en modo edicion para poder screenshotear
la UI real. Ver salvaguarda "Advertys es de solo lectura" en CLAUDE.md.

Uso:
    python -m modules.ordenes_trabajo.explore_cerrar_ot <numero_ot>
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

OUT_DIR = Path("exploracion") / "cerrar_ot"
OUT_DIR.mkdir(parents=True, exist_ok=True)

NUMERO_OT = sys.argv[1] if len(sys.argv) > 1 else "235"


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


def buscar_texto(page, texto):
    """El buscador 'Texto a buscar...' de Advertys es un ASPxTextBox con
    NullText: el placeholder es el VALUE real del input hasta que se
    escribe algo, no un atributo placeholder de HTML. Por eso se ubica
    por el value actual en vez de por placeholder."""
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
            shot(page, "00_error_login")
            browser.close()
            sys.exit(1)

        print(f"Login OK. Navegando a Orden Trabajo (listado)...")
        base_url = URL.split("Login.aspx")[0]
        direct_url = f"{base_url}Default.aspx#ViewID=OrdenTrabajo_ListView&ObjectClassName=DPS_SAS_SR.Module.OrdenTrabajo"
        page.goto(direct_url, wait_until="networkidle", timeout=30000)
        esperar_postback(page)
        page.wait_for_timeout(800)
        shot(page, "01_listado_ot")

        print("Cambiando filtro a 'Todas'...")
        if abrir_combo_filtro(page):
            page.wait_for_timeout(500)
            item = page.get_by_text("Todas", exact=True)
            if item.count() > 0:
                item.first.click(timeout=3000)
                esperar_postback(page)
                print("Filtro seteado a 'Todas'")
            else:
                print("Aviso: no aparecio 'Todas' en el combo")
                page.keyboard.press("Escape")
        else:
            print("Aviso: no se encontro el combo de filtro")
        page.wait_for_timeout(500)
        shot(page, "02_listado_ot_filtro_todas")

        print(f"Buscando OT {NUMERO_OT} con el buscador 'Texto a buscar...'...")
        if buscar_texto(page, NUMERO_OT):
            esperar_postback(page)
            page.wait_for_timeout(800)
            print("Busqueda enviada")
        else:
            print("Aviso: no se encontro el buscador (input con value 'Texto a buscar...')")
        shot(page, "03_busqueda_ot")

        print(f"Intentando abrir la fila de la OT {NUMERO_OT}...")
        celda_nro_ot = page.locator("td").filter(has_text=str(NUMERO_OT))
        fila = page.get_by_text(str(NUMERO_OT), exact=True)
        if fila.count() > 0:
            fila.first.click(timeout=5000)
            esperar_postback(page)
            page.wait_for_timeout(800)
            shot(page, "04_ot_detalle")
        else:
            print(f"AVISO: no se encontro texto '{NUMERO_OT}' clickeable en la grilla. Revisar captura 03.")
            browser.close()
            return

        print("Buscando pestana 'Estimados Costo' (sub-grilla de la OT) en modo VISTA, antes de editar...")
        tab = page.get_by_text("Estimados Costo", exact=True)
        if tab.count() > 0:
            tab.first.click(timeout=5000)
            esperar_postback(page)
            page.wait_for_timeout(800)
            shot(page, "06_ot_tab_estimados_vista")
        else:
            print("AVISO: no se encontro la pestana 'Estimados Costo' con texto exacto en modo vista.")

        print("Entrando en modo edicion de la OT (para ver el boton 'Cambiar estado a: Cerrada')...")
        editar_btn = page.get_by_text("Editar", exact=True)
        if editar_btn.count() > 0:
            editar_btn.first.click(timeout=5000)
            esperar_postback(page)
            page.wait_for_timeout(800)
            shot(page, "07_ot_modo_edicion")
        else:
            print("AVISO: no se encontro boton 'Editar' por texto exacto. Revisar captura 04 para ubicarlo a mano.")

        print("Cancelando edicion de la OT (no tocamos su estado en este reconocimiento)...")
        cancelar_btn = page.get_by_text("Cancelar", exact=True)
        if cancelar_btn.count() > 0:
            cancelar_btn.first.click(timeout=5000)
            esperar_postback(page)
            page.wait_for_timeout(800)

        numero_estimado = sys.argv[2] if len(sys.argv) > 2 else None
        if numero_estimado:
            print(f"Volviendo a la pestana 'Estimados Costo' para abrir el estimado {numero_estimado}...")
            tab = page.get_by_text("Estimados Costo", exact=True)
            if tab.count() > 0:
                tab.first.click(timeout=5000)
                esperar_postback(page)
                page.wait_for_timeout(800)

            fila_est = page.get_by_text(str(numero_estimado), exact=True)
            if fila_est.count() > 0:
                fila_est.first.click(timeout=5000)
                esperar_postback(page)
                page.wait_for_timeout(800)
                shot(page, "08_estimado_detalle")

                print("Entrando en modo edicion del estimado...")
                editar_est = page.get_by_text("Editar", exact=True)
                if editar_est.count() > 0:
                    editar_est.first.click(timeout=5000)
                    esperar_postback(page)
                    page.wait_for_timeout(800)
                    shot(page, "09_estimado_modo_edicion")
                else:
                    print("AVISO: no se encontro boton 'Editar' en el detalle del estimado.")
            else:
                print(f"AVISO: no se encontro el estimado {numero_estimado} en la grilla. Revisar captura 06.")

        print("Reconocimiento terminado. No se guardo ni cambio ningun dato (no se clickeo 'Cerrada'/'Finalizado' ni 'Guardar').")
        browser.close()


if __name__ == "__main__":
    main()
