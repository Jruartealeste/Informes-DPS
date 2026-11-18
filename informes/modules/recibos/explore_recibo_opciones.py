"""
RECONOCIMIENTO (no guarda nada): abre el recibo en Borrador indicado, y
releva las OPCIONES de los desplegables/buscadores que hace falta conocer
para cargar un cobro: Tipo de Retencion Sufrida, Cuenta (Galicia), Tipo de
referencia (transferencia) y la lista de "Cancelar Referencias Deudoras".
Cada dialogo se cierra con Cancelar; jamas Aceptar/Guardar. Aprobado por
Javier 2026-11-18 (recibo 463 de ALUAR, borrador creado en el relevamiento).

Uso (parado en informes/):
    python -m modules.recibos.explore_recibo_opciones 463
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from modules.recibos.explore_nuevo_recibo import (
    LIST_URL_SUFFIX, OUT_DIR, SCREENSHOT_DIR, cerrar_popup, click_visible, click_visible_debajo,
)
from tools.advertys_session import AdvertysLoginError, base_url, esperar_postback, login


def shot(page, nombre):
    destino = SCREENSHOT_DIR / f"recibo_opc_{nombre}.png"
    page.screenshot(path=str(destino), full_page=True)
    print(f"  -> {destino}")


def dialog_frame(page):
    return next((f for f in page.frames if "Dialog=true" in f.url), None)


def textos_filas(frame):
    return frame.evaluate(
        """() => [...document.querySelectorAll('tr[id*="DXDataRow"]')]
                 .map(r => r.innerText.trim().replace(/\\s*\\n\\s*/g, ' | '))"""
    )


def textos_lista_combo(page_o_frame):
    return page_o_frame.evaluate(
        """() => [...document.querySelectorAll('td.dxeListBoxItem, tr.dxeListBoxItemRow td')]
                 .filter(e => e.getBoundingClientRect().width > 0)
                 .map(e => e.innerText.trim()).filter(t => t)"""
    )


def main():
    numero = sys.argv[1] if len(sys.argv) > 1 else "463"
    res = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            try:
                login(page)
            except AdvertysLoginError as e:
                print(f"ERROR: {e}")
                raise SystemExit(1)

            page.goto(f"{base_url()}{LIST_URL_SUFFIX}", wait_until="networkidle", timeout=30000)
            esperar_postback(page)
            page.wait_for_timeout(800)
            fila = page.locator("tr[id*='DXDataRow']", has_text=numero).first
            fila.locator("img, a").nth(0).click(timeout=5000)  # icono editar de la fila
            esperar_postback(page)
            page.wait_for_timeout(1500)
            shot(page, "00_recibo_abierto")

            # --- Cancelar Referencias Deudoras (solo mirar la lista, Cancelar) ---
            print("Cancelar Referencias Deudoras (mirar, no aceptar)...")
            if click_visible(page, "Cancelar Referencias Deudoras"):
                esperar_postback(page)
                page.wait_for_timeout(1500)
                shot(page, "01_referencias_deudoras")
                fr = dialog_frame(page)
                if fr:
                    res["referencias_deudoras"] = textos_filas(fr)
                cerrar_popup(page)

            # --- Retenciones: opciones de Tipo de Retencion Sufrida ---
            print("Retenciones sufridas > Nuevo > Tipo...")
            click_visible(page, "RetencionesSufridas")
            esperar_postback(page)
            page.wait_for_timeout(800)
            if click_visible_debajo(page, "Nuevo", min_y=560):
                esperar_postback(page)
                page.wait_for_timeout(1500)
                fr = dialog_frame(page)
                if fr:
                    btn = fr.locator("td[id*='dviTipoRetencion'][id*='_B-1'], td[id*='_dropdown_DD_B-1']").first
                    if btn.count():
                        btn.click(timeout=3000)
                        page.wait_for_timeout(800)
                        res["tipos_retencion"] = textos_lista_combo(fr)
                    shot(page, "02_tipo_retencion")
                cerrar_popup(page)

            # --- Otros valores: Cuenta y Tipo de referencia ---
            print("Otros Valores > Nuevo > Cuenta / Tipo ref...")
            click_visible(page, "Otros Valores")
            esperar_postback(page)
            page.wait_for_timeout(800)
            if click_visible_debajo(page, "Nuevo", min_y=560):
                esperar_postback(page)
                page.wait_for_timeout(1500)
                fr = dialog_frame(page)
                if fr:
                    for clave, busqueda in (("cuenta_galicia", "Galicia"), ("tipo_referencia", "Transfer")):
                        botones = fr.locator("td[id$='_find_Edit_B0']")
                        idx = 0 if clave == "cuenta_galicia" else 1
                        if botones.count() <= idx:
                            continue
                        botones.nth(idx).click(timeout=3000)
                        page.wait_for_timeout(1000)
                        sub = [f for f in page.frames if "Dialog=true" in f.url and f != fr]
                        sub = sub[-1] if sub else None
                        if sub is None:
                            continue
                        campo = sub.locator("input[id$='_Ed_I']").first
                        campo.click()
                        campo.fill(busqueda)
                        campo.press("Enter")
                        page.wait_for_timeout(1200)
                        res[clave] = textos_filas(sub)
                        shot(page, f"03_{clave}")
                        click_visible(sub, "Cancelar", timeout=2000)
                        esperar_postback(page)
                        page.wait_for_timeout(500)
                cerrar_popup(page)

            destino = OUT_DIR / "recibo_opciones.json"
            destino.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"OK -> {destino}")
            print(json.dumps(res, indent=2, ensure_ascii=False)[:4000])

            print("Saliendo SIN guardar...")
            page.goto(f"{base_url()}{LIST_URL_SUFFIX}", wait_until="networkidle", timeout=30000)
        finally:
            browser.close()


if __name__ == "__main__":
    main()
