"""
Script de RECONOCIMIENTO (no productivo, NO guarda nada en Advertys):
abre la vista de Facturas de Produccion (DPS_Factura) > Nuevo, fotografia el
formulario, elige un cliente (ALUAR) y abre el sub-formulario "Nuevo" de cada
pestana de items para relevar campos. Vuelca todo a
exploracion/factura_nueva_*.json + capturas.

Jamas clickea Guardar / Aceptar / Guardar y cerrar: al final navega fuera
del formulario. Si Advertys persiste un Borrador al abrir (como pasa con el
Recibo Cliente), ese borrador vacio se elimina a mano desde el listado.
Aprobado por Javier el 2026-11-25 solo para este relevamiento (ver
salvaguarda en informes/CLAUDE.md). No se corre desde ningun flujo automatico.

Uso (parado en informes/):
    python -m modules.facturas.explore_nueva_factura
"""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

from modules.recibos.explore_nuevo_recibo import (
    JS_CAMPOS,
    cerrar_popup,
    click_visible,
    click_visible_debajo,
    seleccionar_cliente,
)
from tools.advertys_session import AdvertysLoginError, base_url, esperar_postback, login

OUT_DIR = Path("exploracion")
OUT_DIR.mkdir(exist_ok=True)
SCREENSHOT_DIR = OUT_DIR / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)

# Administracion > Facturacion > Produccion > Factura Manual (el listado de
# Consultas > Facturacion > Facturas, DPS_Factura, es solo consulta: no tiene "Nuevo").
LIST_URL_SUFFIX = "Default.aspx#ViewID=FacturaProduccionManual_ListView&ObjectClassName=DPS_SAS_SR.Module.FacturaProduccionManual"

JS_PESTANAS = """() => [...document.querySelectorAll('[id*="_T"][class*="dxtc-tab"], li.dxtc-tab, td.dxtc-tab')]
    .map(e => (e.textContent || '').trim()).filter(t => t && t.length < 50)"""


def shot(page, nombre):
    destino = SCREENSHOT_DIR / f"factura_nueva_{nombre}.png"
    page.screenshot(path=str(destino), full_page=True)
    print(f"  -> {destino}")


def volcar(page, nombre):
    resultado = {"pagina": page.evaluate(JS_CAMPOS), "frames": []}
    for fr in page.frames:
        if fr == page.main_frame:
            continue
        try:
            resultado["frames"].append({"url": fr.url, **fr.evaluate(JS_CAMPOS)})
        except Exception:
            continue
    destino = OUT_DIR / f"factura_nueva_{nombre}.json"
    destino.write_text(json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  campos -> {destino}")
    return resultado


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
            shot(page, "00_listado")
            volcar(page, "00_listado")

            print("Click en 'Nuevo' (solo abrir el formulario, NO se guarda)...")
            nuevo = page.locator('a[title="Nuevo"], a[title="New"]').first
            if nuevo.count() > 0:
                nuevo.click()
            elif not (click_visible(page, "Nuevo") or click_visible(page, "New")):
                print("ERROR: no se encontro el boton 'Nuevo' en el listado.")
                (OUT_DIR / "factura_nueva_listado.html").write_text(page.content(), encoding="utf-8")
                raise SystemExit(1)
            esperar_postback(page)
            page.wait_for_timeout(1500)
            shot(page, "01_formulario")
            (OUT_DIR / "factura_nueva_formulario.html").write_text(page.content(), encoding="utf-8")
            volcar(page, "01_formulario")

            try:
                print("Eligiendo cliente ALUAR (sin guardar)...")
                print("  cliente cargado:", seleccionar_cliente(page, "ALUAR"))
                shot(page, "02_cliente_elegido")
                volcar(page, "02_cliente_elegido")
            except Exception as e:
                print(f"  (no se pudo elegir cliente: {e})")

            # Grilla "Items de la factura" (debajo del formulario, y ~ 616 a 1600px)
            print("Abriendo 'Nuevo' de Items de la factura (sin aceptar)...")
            if click_visible_debajo(page, "Nuevo", min_y=590) or click_visible_debajo(page, "New", min_y=590):
                esperar_postback(page)
                page.wait_for_timeout(2000)
                shot(page, "02b_item_nuevo")
                volcar(page, "02b_item_nuevo")
                for fr in page.frames:
                    if "Dialog=true" in fr.url:
                        (OUT_DIR / "factura_nueva_item_popup.html").write_text(fr.content(), encoding="utf-8")
                cerrar_popup(page)  # SIN aceptar
                esperar_postback(page)
                shot(page, "02c_item_cerrado")

            pestanas = page.evaluate(JS_PESTANAS)
            print("Pestanas detectadas:", pestanas)
            for i, pestana in enumerate(pestanas, start=3):
                slug = pestana.lower().replace(" ", "_").replace(".", "")
                if not click_visible(page, pestana):
                    continue
                esperar_postback(page)
                page.wait_for_timeout(1000)
                shot(page, f"{i:02d}_{slug}")
                volcar(page, f"{i:02d}_{slug}_tab")
                if "item" not in pestana.lower():
                    continue
                print(f"  abriendo sub-formulario 'Nuevo' de '{pestana}' (sin aceptar)...")
                if click_visible_debajo(page, "Nuevo", min_y=450) or click_visible_debajo(page, "New", min_y=450):
                    esperar_postback(page)
                    page.wait_for_timeout(1500)
                    shot(page, f"{i:02d}_{slug}_nuevo")
                    volcar(page, f"{i:02d}_{slug}_nuevo")
                    cerrar_popup(page)  # SIN aceptar

            print("Saliendo SIN guardar (navegando al listado)...")
            page.once("dialog", lambda d: d.accept())  # "salir sin guardar?" del navegador
            page.goto("about:blank")
            page.goto(f"{base_url()}{LIST_URL_SUFFIX}", wait_until="networkidle", timeout=30000)
            esperar_postback(page)
            page.wait_for_timeout(800)
            shot(page, "99_cerrado_sin_guardar")
        finally:
            browser.close()


if __name__ == "__main__":
    main()
