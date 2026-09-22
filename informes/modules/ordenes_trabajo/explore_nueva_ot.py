"""
Script de RECONOCIMIENTO (no productivo, no escribe nada en Advertys):
navega hasta "Orden Trabajo", abre el formulario de alta ("Nuevo") y
releva en modo lectura que campos pide, cuales vienen pre-completados o
autogenerados (ej. el numero de OT) y cuales son obligatorios -- para
poder escribir despues `crear_ot.py` (unico consumidor productivo de este
relevamiento) sin tener que explorar a ciegas contra Advertys real.

Este script jamas clickea "Guardar": abre el formulario, lo fotografia,
vuelca la estructura de sus inputs a un JSON y cierra sin persistir nada.
Ver salvaguarda "Advertys es de solo lectura" en CLAUDE.md -- el click en
"Nuevo" que este script hace es exactamente el tipo de accion que esa
salvaguarda pide frenar y confirmar con Javier antes de ejecutar, por eso
no se corre como parte de ningun flujo automatico (ni `actualizar_todo`,
ni un cron): se ejecuta una sola vez, a mano, con aprobacion explicita.

Uso:
    python -m modules.ordenes_trabajo.explore_nueva_ot
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import TimeoutError as PWTimeoutError
from playwright.sync_api import sync_playwright

from tools.advertys_session import AdvertysLoginError, base_url, esperar_postback, login

OUT_DIR = Path("exploracion")
OUT_DIR.mkdir(exist_ok=True)
SCREENSHOT_DIR = OUT_DIR / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)

DIRECT_URL_SUFFIX = "Default.aspx#ViewID=OrdenTrabajo_ListView&ObjectClassName=DPS_SAS_SR.Module.OrdenTrabajo"

# Combos simples (ASPxComboBox) del formulario "Nuevo" -- se relevan sus
# opciones cargadas via callback (no vienen en el HTML inicial) abriendo
# cada uno y leyendo la lista, sin seleccionar nada.
COMBOS_SIMPLES = [
    "dviNegocioPoduccion",
    "dviProducto",
    "dviCentroCosto",
    "dviTag",
    "dviEquipo",
    "dviContactoAnunciante",
]


def shot(page, nombre):
    destino = SCREENSHOT_DIR / f"{nombre}.png"
    page.screenshot(path=str(destino), full_page=True)
    print(f"  -> {destino}")


def relevar_campos(page) -> list[dict]:
    """Vuelca cada input/combo visible del formulario: label asociado (si
    se encuentra), id, tipo, valor actual y si esta deshabilitado (senal de
    que Advertys lo autogenera, como el numero de OT)."""
    return page.evaluate(
        """() => {
            const campos = [];
            const inputs = document.querySelectorAll('input, textarea, select');
            for (const el of inputs) {
                if (el.type === 'hidden') continue;
                const rect = el.getBoundingClientRect();
                if (rect.width === 0 && rect.height === 0) continue;
                let label = null;
                const id = el.id || '';
                const labelEl = id ? document.querySelector(`label[for="${id}"]`) : null;
                if (labelEl) {
                    label = labelEl.textContent.trim();
                } else {
                    const row = el.closest('td, tr, div');
                    if (row) {
                        const prevCell = row.previousElementSibling;
                        if (prevCell) label = prevCell.textContent.trim().slice(0, 80);
                    }
                }
                campos.push({
                    id,
                    name: el.name || null,
                    tag: el.tagName.toLowerCase(),
                    type: el.type || null,
                    label,
                    value: el.value || null,
                    disabled: !!el.disabled,
                    readonly: !!el.readOnly,
                });
            }
            return campos;
        }"""
    )


def relevar_opciones_combo(page, campo: str) -> list[str]:
    """Abre el combo (click en el boton flecha, SOLO ver la lista, nunca
    seleccionar nada) y devuelve los textos visibles. Las opciones de estos
    ASPxComboBox se cargan por callback al abrirlos -- no estan en el HTML
    inicial del formulario, por eso no alcanzaba con `relevar_campos`."""
    input_loc = page.locator(f"input[id$='_xaf_{campo}_Edit_dropdown_DD_I']")
    if input_loc.count() == 0:
        return []
    input_id = input_loc.first.get_attribute("id")
    boton_id = input_id.replace("_DD_I", "_DD_B-1")
    try:
        page.locator(f"#{boton_id}").click(timeout=5000)
    except PWTimeoutError:
        return []
    page.wait_for_timeout(700)

    lista_id = input_id.replace("_DD_I", "_DD_DDD_L")
    filas = page.locator(f"#{lista_id} td")
    opciones = []
    for i in range(filas.count()):
        texto = filas.nth(i).inner_text().strip()
        if texto and texto not in opciones:
            opciones.append(texto)

    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    return opciones


def relevar_anunciante(page):
    """El campo Anunciante no es un combo simple sino un lookup con boton de
    busqueda (icono lupa) -- abre un popup/ventana propia con una grilla para
    elegir. Solo se abre para fotografiarlo (relevamiento visual), nunca se
    selecciona ni confirma nada."""
    boton = page.locator("td[id$='_xaf_dviAnunciante_Edit_find_Edit_B0']")
    if boton.count() == 0:
        print("  (no se encontro el boton de busqueda de Anunciante)")
        return
    try:
        with page.context.expect_page(timeout=3000) as popup_info:
            boton.first.click(timeout=5000)
        popup = popup_info.value
        popup.wait_for_load_state("networkidle", timeout=15000)
        shot(popup, "ot_nuevo_03_anunciante_popup")
        popup.close()
    except PWTimeoutError:
        page.wait_for_timeout(1000)
        shot(page, "ot_nuevo_03_anunciante_popup")
        (OUT_DIR / "ot_nuevo_anunciante_popup.html").write_text(page.content(), encoding="utf-8")

        frame = None
        for f in page.frames:
            if "Dialog=true" in f.url:
                frame = f
                break
        if frame is None:
            print("  (no se encontro el iframe del popup de Anunciante)")
        else:
            (OUT_DIR / "ot_nuevo_anunciante_popup_frame.html").write_text(
                frame.content(), encoding="utf-8"
            )
            # El buscador del popup es el mismo widget generico de Advertys
            # que buscar_texto() en crear_estimado.py/cerrar_ot.py, pero acá
            # adentro del iframe del popup solo hay una instancia -- "Texto a
            # buscar..." es un NullText visual (watermark), no el .value real
            # del input, por eso no sirve filtrar por valor como en buscar_texto.
            candidatos = frame.locator("input[id$='_Ed_I']")
            encontrado = candidatos.count() > 0
            if encontrado:
                cand = candidatos.first
                cand.click()
                cand.fill("ALUAR")
                cand.press("Enter")
                page.wait_for_timeout(1200)
                shot(page, "ot_nuevo_04_anunciante_busqueda_aluar")
                (OUT_DIR / "ot_nuevo_anunciante_resultados.html").write_text(
                    frame.content(), encoding="utf-8"
                )
            else:
                print("  (no se encontro el buscador 'Texto a buscar...' en el popup)")

        page.keyboard.press("Escape")
        page.wait_for_timeout(300)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            try:
                login(page)
            except AdvertysLoginError as e:
                print(f"ERROR: {e}")
                sys.exit(1)

            direct_url = f"{base_url()}{DIRECT_URL_SUFFIX}"
            print(f"Abriendo listado Orden Trabajo: {direct_url}")
            page.goto(direct_url, wait_until="networkidle", timeout=30000)
            esperar_postback(page)
            shot(page, "ot_nuevo_00_listado")

            print("Buscando boton 'Nuevo'...")
            nuevo_btn = page.locator('a[title="Nuevo"], span:has-text("Nuevo")').first
            if nuevo_btn.count() == 0:
                print("ERROR: no se encontro un boton 'Nuevo' visible en el listado.")
                (OUT_DIR / "ot_nuevo_listado.html").write_text(page.content(), encoding="utf-8")
                sys.exit(1)

            print("Click en 'Nuevo' (SOLO ABRIR el formulario, no se guarda nada)...")
            nuevo_btn.click()
            esperar_postback(page)
            shot(page, "ot_nuevo_01_formulario")
            (OUT_DIR / "ot_nuevo_formulario.html").write_text(page.content(), encoding="utf-8")

            print("Relevando campos del formulario...")
            campos = relevar_campos(page)
            destino_json = OUT_DIR / "ot_nuevo_campos.json"
            destino_json.write_text(json.dumps(campos, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"OK: {len(campos)} campos relevados -> {destino_json}")

            print("Relevando opciones de los combos (abrir y leer, sin seleccionar)...")
            opciones_combos = {}
            for campo in COMBOS_SIMPLES:
                opciones_combos[campo] = relevar_opciones_combo(page, campo)
                print(f"  {campo}: {len(opciones_combos[campo])} opciones")
            destino_combos = OUT_DIR / "ot_nuevo_opciones_combos.json"
            destino_combos.write_text(
                json.dumps(opciones_combos, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            print(f"OK: opciones de combos -> {destino_combos}")

            print("Abriendo popup de busqueda de Anunciante (solo para fotografiar)...")
            relevar_anunciante(page)

            print("Cerrando SIN guardar (navegando fuera del formulario)...")
            page.goto(direct_url, wait_until="networkidle", timeout=30000)
            esperar_postback(page)
            shot(page, "ot_nuevo_02_cerrado_sin_guardar")

        finally:
            browser.close()


if __name__ == "__main__":
    main()
