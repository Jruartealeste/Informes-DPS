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

from playwright.sync_api import sync_playwright

from tools.advertys_session import AdvertysLoginError, base_url, esperar_postback, login

OUT_DIR = Path("exploracion")
OUT_DIR.mkdir(exist_ok=True)
SCREENSHOT_DIR = OUT_DIR / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)

DIRECT_URL_SUFFIX = "Default.aspx#ViewID=OrdenTrabajo_ListView&ObjectClassName=DPS_SAS_SR.Module.OrdenTrabajo"


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

            print("Cerrando SIN guardar (navegando fuera del formulario)...")
            page.goto(direct_url, wait_until="networkidle", timeout=30000)
            esperar_postback(page)
            shot(page, "ot_nuevo_02_cerrado_sin_guardar")

        finally:
            browser.close()


if __name__ == "__main__":
    main()
