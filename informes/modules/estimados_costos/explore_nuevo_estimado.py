"""
Script de RECONOCIMIENTO (no productivo, no escribe nada en Advertys):
entra a una Orden de Trabajo real, abre su pestana "Estimados Costo" y
releva en modo lectura el formulario de alta ("Nuevo Estimado") -- que
campos pide, cuales vienen pre-completados o autogenerados (ej. el numero
de estimado, o si arrastra datos de la OT) y cuales son obligatorios.

Confirmado por Javier (2026-09-18): el alta de un Estimado es CONTEXTUAL,
no suelta -- se crea desde adentro de una OT (existente o recien creada),
pestana "Estimados Costo", boton "Nuevo Estimado". Por eso este script NO
navega al listado global de Estimado Costos (ver explore.py / export.py,
que sí viven ahi para leer/exportar el listado ya existente) sino que
entra a una OT puntual, igual que hace `ir_a_ot()` en cerrar_ot.py (unico
otro lugar del proyecto que ya navega hasta adentro de una OT).

Este script jamas clickea "Guardar": abre el formulario, lo fotografia,
vuelca la estructura de sus inputs a un JSON y cierra sin persistir nada.
Ver salvaguarda "Advertys es de solo lectura" en CLAUDE.md -- el click en
"Nuevo Estimado" que este script hace es exactamente el tipo de accion que
esa salvaguarda pide frenar y confirmar con Javier antes de ejecutar (ya
confirmado 2026-09-18 para este relevamiento puntual); no se corre como
parte de ningun flujo automatico (ni `actualizar_todo`, ni un cron).

Uso:
    python -m modules.estimados_costos.explore_nuevo_estimado <numero_ot>
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from tools.advertys_session import AdvertysLoginError, base_url, esperar_postback, login

OUT_DIR = Path("exploracion")
OUT_DIR.mkdir(exist_ok=True)
SCREENSHOT_DIR = OUT_DIR / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)

OT_LIST_URL_SUFFIX = "Default.aspx#ViewID=OrdenTrabajo_ListView&ObjectClassName=DPS_SAS_SR.Module.OrdenTrabajo"


def shot(page, nombre):
    destino = SCREENSHOT_DIR / f"{nombre}.png"
    page.screenshot(path=str(destino), full_page=True)
    print(f"  -> {destino}")


def click_boton_visible(page, texto, timeout=5000):
    """Clickea el primer elemento VISIBLE con este texto exacto (evita
    matchear items de menu lateral / opciones ocultas con el mismo texto).
    Mismo helper que cerrar_ot.py -- ver ahi el motivo (varios elementos
    ocultos pueden compartir texto en este layout de Advertys)."""
    candidatos = page.get_by_text(texto, exact=True)
    for i in range(candidatos.count()):
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


def ir_a_ot(page, numero_ot):
    """Mismo flujo que cerrar_ot.py::ir_a_ot -- listado de OT, filtro
    'Todas', buscar por numero exacto, click en la fila para abrir el
    detalle (modo vista, no 'Editar')."""
    direct_url = f"{base_url()}{OT_LIST_URL_SUFFIX}"
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


def frame_del_popup(page):
    """El dialogo 'Agregar Estimado' se renderiza dentro de un iframe propio
    (confirmado en vivo: relevar_campos() contra `page` directamente solo
    encontraba los combos del fondo, ninguno de los 3 campos visibles en la
    captura del popup) -- busca el frame que contiene 'Fecha Solicitada' y
    devuelve ese, o `page` como fallback si no se encuentra ninguno."""
    for frame in page.frames:
        try:
            if frame.get_by_text("Fecha Solicitada", exact=False).count() > 0:
                return frame
        except Exception:
            continue
    return page


def relevar_campos(page) -> list[dict]:
    """Vuelca cada input/combo visible del formulario: label asociado (si
    se encuentra), id, tipo, valor actual y si esta deshabilitado (senal de
    que Advertys lo autogenera o lo arrastra de la OT)."""
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


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    numero_ot = sys.argv[1]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            try:
                login(page)
            except AdvertysLoginError as e:
                print(f"ERROR: {e}")
                sys.exit(1)

            print(f"Navegando a OT {numero_ot}...")
            ir_a_ot(page, numero_ot)
            shot(page, f"estimado_nuevo_00_ot_{numero_ot}")

            print("Abriendo pestana 'Estimados Costo'...")
            if not click_boton_visible(page, "Estimados Costo"):
                print("ERROR: no se encontro la pestana 'Estimados Costo' en esta OT.")
                (OUT_DIR / f"estimado_nuevo_ot_{numero_ot}.html").write_text(page.content(), encoding="utf-8")
                sys.exit(1)
            esperar_postback(page)
            page.wait_for_timeout(800)
            shot(page, f"estimado_nuevo_01_ot_{numero_ot}_tab_estimados")

            print("Buscando boton 'Nuevo Estimado'...")
            nuevo_btn = page.locator('a[title="Nuevo Estimado"], a[title="Nuevo"]').first
            encontrado_por_selector = nuevo_btn.count() > 0
            if not encontrado_por_selector:
                (OUT_DIR / f"estimado_nuevo_ot_{numero_ot}_tab.html").write_text(page.content(), encoding="utf-8")

            print("Click en 'Nuevo Estimado' (SOLO ABRIR el formulario, no se guarda nada)...")
            if encontrado_por_selector:
                nuevo_btn.click()
            elif not click_boton_visible(page, "Nuevo Estimado"):
                print("ERROR: no se encontro un boton 'Nuevo Estimado' visible en esta pestana.")
                print("Revisa la captura/HTML volcados para ver que opciones hay realmente.")
                sys.exit(1)
            esperar_postback(page)
            page.wait_for_timeout(800)
            shot(page, f"estimado_nuevo_02_ot_{numero_ot}_formulario")
            (OUT_DIR / f"estimado_nuevo_ot_{numero_ot}_formulario.html").write_text(page.content(), encoding="utf-8")

            print("Relevando campos del formulario...")
            frame = frame_del_popup(page)
            print(f"  (leyendo campos desde {'un iframe del popup' if frame is not page else 'la pagina principal'})")
            campos = relevar_campos(frame)
            destino_json = OUT_DIR / f"estimado_nuevo_ot_{numero_ot}_campos.json"
            destino_json.write_text(json.dumps(campos, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"OK: {len(campos)} campos relevados -> {destino_json}")

            print("Cerrando SIN guardar (navegando fuera del formulario)...")
            ir_a_ot(page, numero_ot)
            shot(page, f"estimado_nuevo_03_ot_{numero_ot}_cerrado_sin_guardar")

        finally:
            browser.close()


if __name__ == "__main__":
    main()
