"""
Script de RECONOCIMIENTO (no productivo, no escribe nada en Advertys):
abre el listado Entidades > Generales > Proveedores > Proveedor, hace click
en "Nuevo", fotografia el formulario, vuelca sus inputs a JSON y cierra SIN
guardar. Es el insumo para escribir despues `crear_proveedor.py`.

Jamas clickea "Guardar". El click en "Nuevo" es exactamente la accion que la
salvaguarda "Advertys es de solo lectura" (informes/CLAUDE.md) pide
confirmar con Javier: aprobado explicitamente el 2026-11-19 solo para este
relevamiento. No se corre como parte de ningun flujo automatico.

El ViewID del listado es una suposicion por analogia con Cliente_ListView /
OrdenTrabajo_ListView -- si no abre, el script lo avisa y deja una captura
para ajustarlo.

Uso (parado en informes/):
    python -m modules.proveedores.explore_nuevo_proveedor
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from tools.advertys_session import AdvertysLoginError, base_url, esperar_postback, login

OUT_DIR = Path("exploracion")
SCREENSHOT_DIR = OUT_DIR / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

DIRECT_URL_SUFFIX = "Default.aspx#ViewID=Proveedor_ListView&ObjectClassName=DPS_SAS_SR.Module.Proveedor"


def shot(page, nombre):
    destino = SCREENSHOT_DIR / f"{nombre}.png"
    page.screenshot(path=str(destino), full_page=True)
    print(f"  -> {destino}")


def relevar_campos(page) -> list[dict]:
    return page.evaluate(
        """() => {
            const campos = [];
            for (const el of document.querySelectorAll('input, textarea, select')) {
                if (el.type === 'hidden') continue;
                const rect = el.getBoundingClientRect();
                if (rect.width === 0 && rect.height === 0) continue;
                let label = null;
                const id = el.id || '';
                const labelEl = id ? document.querySelector(`label[for="${id}"]`) : null;
                if (labelEl) label = labelEl.textContent.trim();
                else {
                    const row = el.closest('td, tr, div');
                    if (row && row.previousElementSibling)
                        label = row.previousElementSibling.textContent.trim().slice(0, 80);
                }
                campos.push({id, name: el.name || null, tag: el.tagName.toLowerCase(),
                    type: el.type || null, label, value: el.value || null,
                    disabled: !!el.disabled, readonly: !!el.readOnly});
            }
            return campos;
        }"""
    )


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 1000})
        try:
            try:
                login(page)
            except AdvertysLoginError as e:
                print(f"ERROR: {e}")
                sys.exit(1)

            url = base_url() + DIRECT_URL_SUFFIX
            print(f"Abriendo listado Proveedores: {url}")
            page.goto(url, wait_until="networkidle", timeout=30000)
            esperar_postback(page)
            shot(page, "prov_nuevo_00_listado")

            nuevo = page.locator('a[title="Nuevo"], span:has-text("Nuevo")')
            if nuevo.count() == 0:
                print("ERROR: no hay boton 'Nuevo'; revisar el ViewID en la captura 00.")
                (OUT_DIR / "prov_nuevo_listado.html").write_text(page.content(), encoding="utf-8")
                sys.exit(1)

            print("Click en 'Nuevo' (SOLO ABRIR el formulario, no se guarda nada)...")
            nuevo.first.click()
            esperar_postback(page)
            page.wait_for_timeout(1500)
            shot(page, "prov_nuevo_01_formulario")
            (OUT_DIR / "prov_nuevo_formulario.html").write_text(page.content(), encoding="utf-8")

            por_pestana = {"Proveedor": relevar_campos(page)}
            # Solo se cambia de pestana (lectura); no se toca ningun campo.
            for i, pestana in enumerate(["Datos Impositivos", "Ganancias e Iva", "IIBB", "Parámetros", "CBU"], 2):
                tab = page.get_by_text(pestana, exact=True).locator("visible=true")
                if tab.count() == 0:
                    print(f"  (sin pestana {pestana})")
                    continue
                # .last: "Parámetros" también es un nodo del menú lateral (viene antes en el DOM)
                tab.last.click(timeout=8000)
                esperar_postback(page)
                page.wait_for_timeout(800)
                shot(page, f"prov_nuevo_{i:02d}_{pestana.split()[0].lower()}")
                por_pestana[pestana] = relevar_campos(page)
            # Opciones de los combos: abrir y leer la lista, sin seleccionar nada.
            combos = {}
            for pestana in ["Datos Impositivos", "Ganancias e Iva", "Parámetros"]:
                page.get_by_text(pestana, exact=True).locator("visible=true").last.click(timeout=8000)
                esperar_postback(page)
                page.wait_for_timeout(800)
                for inp in page.locator("input[id$='_dropdown_DD_I']").all():
                    if not inp.is_visible():
                        continue
                    input_id = inp.get_attribute("id")
                    nombre = input_id.split("_xaf_dvi")[-1].split("_Edit")[0]
                    try:
                        page.locator("#" + input_id.replace("_DD_I", "_DD_B-1")).click(timeout=5000)
                    except Exception:
                        continue
                    page.wait_for_timeout(900)
                    filas = page.locator("#" + input_id.replace("_DD_I", "_DD_DDD_L") + " td")
                    ops = []
                    for j in range(filas.count()):
                        t = filas.nth(j).inner_text().strip()
                        if t and t not in ops:
                            ops.append(t)
                    combos[nombre] = ops
                    print(f"  {nombre}: {len(ops)} opciones")
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(300)
            (OUT_DIR / "prov_nuevo_opciones_combos.json").write_text(
                json.dumps(combos, indent=2, ensure_ascii=False), encoding="utf-8")
            destino = OUT_DIR / "prov_nuevo_campos.json"
            destino.write_text(json.dumps(por_pestana, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"OK: campos por pestana -> {destino}")

            print("Cerrando SIN guardar (navegando fuera del formulario)...")
            page.goto(url, wait_until="networkidle", timeout=30000)
            esperar_postback(page)
            shot(page, "prov_nuevo_02_cerrado_sin_guardar")
        finally:
            browser.close()


if __name__ == "__main__":
    main()
