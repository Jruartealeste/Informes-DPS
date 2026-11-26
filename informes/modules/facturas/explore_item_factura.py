"""
Relevamiento del popup de ITEMS de una Factura Produccion Manual.

ESCRIBE en Advertys real (aprobado por Javier 2026-11-25, una sola vez): guarda
UNA cabecera en Borrador (cliente HORA DATA GROUP S.A., producto Varios, como
la 000500001532) porque Advertys exige la cabecera guardada para abrir el
"Nuevo" de items. Abre el popup de items, vuelca campos y opciones de los
combos y lo cierra con Cancelar (nunca Aceptar). No toca Autorizar, Facturar
ni Solicitar CAE. El Borrador queda; Javier lo elimina a mano.

Uso (parado en informes/):
    python -m modules.facturas.explore_item_factura
"""
import json

from playwright.sync_api import sync_playwright

from modules.facturas.explore_nueva_factura import LIST_URL_SUFFIX, OUT_DIR, shot, volcar
from modules.ordenes_trabajo.crear_ot import click_boton_visible, seleccionar_combo
from modules.recibos.explore_nuevo_recibo import cerrar_popup, click_visible, click_visible_debajo, seleccionar_cliente
from tools.advertys_session import AdvertysLoginError, base_url, esperar_postback, login

JS_COMBOS = """() => {
    const out = {};
    for (const t of document.querySelectorAll('table[id$="_DDD_L"], table[id*="_DDD_L_"]')) {
        const opts = [...t.querySelectorAll('td')].map(td => td.textContent.trim()).filter(x => x && x.length < 120);
        out[t.id] = [...new Set(opts)].slice(0, 300);
    }
    return out;
}"""


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        try:
            try:
                login(page)
            except AdvertysLoginError as e:
                print(f"ERROR: {e}")
                raise SystemExit(1)
            page.goto(f"{base_url()}{LIST_URL_SUFFIX}", wait_until="networkidle", timeout=30000)
            esperar_postback(page)
            page.wait_for_timeout(800)
            # mismo criterio que explore_nueva_factura: el link no tiene title, va por texto
            if not (click_visible(page, "Nuevo") or click_visible(page, "New")):
                raise SystemExit("No se encontro 'Nuevo' en el listado.")
            esperar_postback(page)
            page.wait_for_timeout(1500)

            print("cliente:", seleccionar_cliente(page, "HORA DATA"))
            esperar_postback(page)
            page.wait_for_timeout(1500)
            inp = page.locator("input[id$='_xaf_dviProductoDefault_Edit_dropdown_DD_I']").first
            iid = inp.get_attribute("id")
            page.locator(f"#{iid.replace('_DD_I', '_DD_B-1')}").click()
            page.wait_for_timeout(1500)
            opts = [t.strip() for t in page.locator(f"#{iid.replace('_DD_I', '_DD_DDD_L')} td").all_inner_texts()]
            print("  opciones Producto:", [o for o in opts if len(o) < 80])
            page.keyboard.press("Escape")
            page.wait_for_timeout(500)
            seleccionar_combo(page, "dviProductoDefault", "Comisiones")
            esperar_postback(page)
            shot(page, "item_00_cabecera")

            print("Guardando cabecera en Borrador (aprobado)...")
            if not click_boton_visible(page, "Guardar"):
                raise SystemExit("No se encontro 'Guardar'.")
            esperar_postback(page)
            page.wait_for_timeout(1500)
            shot(page, "item_01_cabecera_guardada")

            print("Abriendo 'Nuevo' de Items (sin aceptar)...")
            if not click_visible_debajo(page, "Nuevo", min_y=450):
                raise SystemExit("No se encontro el 'Nuevo' de items.")
            esperar_postback(page)
            page.wait_for_timeout(2500)
            shot(page, "item_02_popup")
            volcar(page, "item_02_popup")
            for i, fr in enumerate(page.frames):
                if "Dialog=true" in fr.url:
                    (OUT_DIR / f"factura_item_popup_{i}.html").write_text(fr.content(), encoding="utf-8")
                    # abrir cada combo para que renderice su lista y volcar opciones
                    for b in fr.locator("td[id$='_DD_B-1']").all():
                        try:
                            b.click(timeout=2000)
                            fr.wait_for_timeout(700)
                        except Exception:
                            pass
                    combos = fr.evaluate(JS_COMBOS)
                    (OUT_DIR / f"factura_item_combos_{i}.json").write_text(
                        json.dumps(combos, indent=2, ensure_ascii=False), encoding="utf-8")
                    print(f"  combos frame {i}:", {k.split('_xaf_')[-1]: len(v) for k, v in combos.items()})
            shot(page, "item_03_combos")
            cerrar_popup(page)  # SIN aceptar
            esperar_postback(page)
            shot(page, "item_04_popup_cerrado")
            print("URL del Borrador:", page.url)
        finally:
            browser.close()


if __name__ == "__main__":
    main()
