"""
Relevamiento en vivo (solo navegacion, sin guardar nada) del detalle de un
Estimado de Costo: abre la OT, la pestana "Estimados Costo", entra al
estimado, vuelca captura + texto de botones/pestanas/campos, y abre la
pestana "Items". Base para `cargar_items_estimado.py`.

Uso (parado en informes/):
    python -m modules.estimados_costos.explore_items_estimado <numero_ot> <numero_estimado>
"""
import json
import sys

from playwright.sync_api import sync_playwright

from modules.estimados_costos.crear_estimado import (
    OUT_DIR,
    click_boton_visible,
    ir_a_ot,
    shot,
)
from tools.advertys_session import esperar_postback, login


def volcar(page, nombre):
    shot(page, nombre)
    datos = page.evaluate(
        """() => {
          const vis = e => !!(e.offsetWidth || e.offsetHeight);
          const t = s => [...document.querySelectorAll(s)].filter(vis);
          return {
            links_title: t('a[title]').map(e => e.getAttribute('title')).slice(0, 80),
            tabs: t('li.dxtc-tab, td.dxtc-tab, [id*="_pg_AT"]').map(e => e.innerText.trim()).filter(Boolean).slice(0, 40),
            inputs: t('input[id]').map(e => [e.id, e.value]).slice(0, 60),
            frames: [...document.querySelectorAll('iframe')].map(f => f.src || f.name),
          };
        }"""
    )
    (OUT_DIR / f"{nombre}.json").write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(datos, ensure_ascii=False)[:1500])


def main():
    numero_ot, numero_estimado = sys.argv[1], sys.argv[2]
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 1000})
        try:
            login(page)
            ir_a_ot(page, numero_ot)
            click_boton_visible(page, "Estimados Costo")
            esperar_postback(page)
            page.wait_for_timeout(1000)
            fila = page.get_by_text(str(numero_estimado), exact=True)
            print("coincidencias del N° en la grilla:", fila.count())
            fila.first.click(timeout=5000)
            esperar_postback(page)
            page.wait_for_timeout(1500)
            volcar(page, f"est_items_{numero_estimado}_01_detalle")
            if "--editar" in sys.argv:
                # Autorizado por Javier (2026-11-03) sobre el Estimado 599.
                page.locator('a[title="Editar"]').first.click(timeout=5000)
                esperar_postback(page)
                page.wait_for_timeout(1500)
                volcar(page, f"est_items_{numero_estimado}_02_editar")
                if "--provisorio" in sys.argv:
                    click_boton_visible(page, "Provisorio")
                    esperar_postback(page)
                    page.wait_for_timeout(1500)
                    volcar(page, f"est_items_{numero_estimado}_03_provisorio")
                    if "--nuevo" in sys.argv:
                        click_boton_visible(page, "Nuevo")
                        esperar_postback(page)
                        page.wait_for_timeout(2000)
                        shot(page, f"est_items_{numero_estimado}_04_nuevo_item")
                        for f in page.frames:
                            try:
                                campos = f.evaluate(
                                    """() => [...document.querySelectorAll('input[id],textarea[id],select[id]')]
                                      .filter(e => e.offsetWidth).map(e => [e.id, e.value])"""
                                )
                                etiquetas = f.evaluate("() => document.body.innerText.slice(0, 1500)")
                            except Exception:
                                continue
                            if campos:
                                print("FRAME", f.url[:120], len(campos))
                                for c in campos: print("  ", c)
                                print("  TEXTO:", etiquetas.replace("\n", " | ")[:900])
                        if "--combos" in sys.argv:
                            for sufijo in ("RubroProduccion", "Articulo"):
                                dlg = next(f for f in page.frames if "Dialog=true" in f.url)
                                if sufijo == "Articulo":
                                    shot(page, "est_items_599_05b_tras_rubro")
                                    print("IDS Articulo:", dlg.evaluate(
                                        "() => [...document.querySelectorAll('[id*=dviArticulo]')].map(e => e.id + '|' + e.tagName + '|' + (e.value||''))"
                                    ))
                                    dlg.locator("td[id$='_xaf_dviArticulo_Edit_find_Edit_B0']").first.click()
                                    page.wait_for_timeout(2000)
                                    shot(page, "est_items_599_06_popup_articulo")
                                    pop = next(f for f in page.frames if "ActionID=" in f.url)
                                    for q in ("Adaptación 1/2 página", "Adaptación", "Original 1 página",
                                              "Diseñador", "otros", "varios"):
                                        box = pop.locator("input[id$='_Ed_I']").first
                                        box.click()
                                        box.fill(q)
                                        box.press("Enter")
                                        page.wait_for_timeout(1500)
                                        filas = pop.locator("tr[id*='DXDataRow']")
                                        print(f"BUSQ {q!r}: {filas.count()} filas")
                                        for i in range(min(filas.count(), 25)):
                                            print("   ROW", filas.nth(i).inner_text().replace("\n", " | ").replace("\t", " "))
                                    break
                                inp = dlg.locator(f"input[id$='xaf_dvi{sufijo}_Edit_dropdown_DD_I']")
                                btn_id = inp.get_attribute("id").replace("_DD_I", "_DD_B-1")
                                dlg.locator(f"#{btn_id}").click()
                                page.wait_for_timeout(1500)
                                shot(page, f"est_items_599_05_combo_{sufijo}")
                                textos = dlg.evaluate(
                                    """() => [...document.querySelectorAll('[id*="_DDD"] td, [id*="_DDD"] li')]
                                      .filter(e => e.offsetWidth && e.children.length == 0)
                                      .map(e => e.innerText.trim()).filter(Boolean)"""
                                )
                                print(sufijo, len(textos), textos[:300])
                                if sufijo == "RubroProduccion":
                                    dlg.get_by_text("SERVICIOS PROPIOS Y TARIFARIO", exact=True).last.click()
                                    esperar_postback(page)
                                    page.wait_for_timeout(1500)
                                else:
                                    page.keyboard.press("Escape")
                                    page.wait_for_timeout(500)
        finally:
            browser.close()


if __name__ == "__main__":
    main()
