"""
Script de RECONOCIMIENTO (no productivo, NO guarda nada en Advertys):
abre Administracion > Tesoreria > Recibo Cliente > Nuevo, fotografia el
formulario y, dentro de ese recibo sin guardar, abre los sub-formularios
"Nuevo" de las pestanas "Retenciones sufridas" y "Otros Valores" para
relevar sus campos y desplegables (tipo de retencion, cuenta, tipo de
referencia). Vuelca todo a exploracion/recibo_nuevo_*.json + capturas.

Jamas clickea Guardar / Aceptar / Guardar y cerrar: al final navega fuera
del formulario y Advertys descarta el recibo sin persistirlo. Aprobado por
Javier el 2026-11-18 solo para este relevamiento (ver salvaguarda en
informes/CLAUDE.md). No se corre desde ningun flujo automatico.

Uso (parado en informes/):
    python -m modules.recibos.explore_nuevo_recibo
"""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

from tools.advertys_session import AdvertysLoginError, base_url, esperar_postback, login

OUT_DIR = Path("exploracion")
OUT_DIR.mkdir(exist_ok=True)
SCREENSHOT_DIR = OUT_DIR / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)

LIST_URL_SUFFIX = "Default.aspx#ViewID=IC_ReciboCliente_ListView&ObjectClassName=DPS_SAS_SR.Module.IC_ReciboCliente"

JS_CAMPOS = """() => {
    const campos = [];
    for (const el of document.querySelectorAll('input, textarea, select')) {
        if (el.type === 'hidden') continue;
        const r = el.getBoundingClientRect();
        if (r.width === 0 && r.height === 0) continue;
        let label = null;
        const lab = el.id ? document.querySelector(`label[for="${el.id}"]`) : null;
        if (lab) label = lab.textContent.trim();
        else {
            const row = el.closest('td, tr, div');
            if (row && row.previousElementSibling)
                label = row.previousElementSibling.textContent.trim().slice(0, 80);
        }
        campos.push({id: el.id || '', tag: el.tagName.toLowerCase(), type: el.type || null,
                     label, value: el.value || null, disabled: !!el.disabled, readonly: !!el.readOnly});
    }
    // botones / pestanas visibles (texto corto) para ubicar Aceptar/Cancelar/pestanas
    const acciones = [];
    for (const el of document.querySelectorAll('a, span.dx-vam, li, td')) {
        const t = (el.textContent || '').trim();
        const r = el.getBoundingClientRect();
        if (t && t.length < 40 && r.width > 0 && r.height > 0 && el.children.length === 0)
            acciones.push(t);
    }
    return {campos, acciones: [...new Set(acciones)]};
}"""


def shot(page, nombre):
    destino = SCREENSHOT_DIR / f"recibo_nuevo_{nombre}.png"
    page.screenshot(path=str(destino), full_page=True)
    print(f"  -> {destino}")


def click_visible(page, texto, timeout=5000):
    cands = page.get_by_text(texto, exact=True)
    for i in range(cands.count()):
        c = cands.nth(i)
        try:
            if c.is_visible():
                c.click(timeout=timeout)
                return True
        except Exception:
            continue
    return False


def click_visible_debajo(page, texto, min_y, timeout=5000):
    """Como click_visible pero solo elementos con y > min_y (el 'Nuevo' de la
    grilla de una pestana, no el de la barra superior ni el del combo Moneda)."""
    cands = page.get_by_text(texto, exact=True)
    for i in range(cands.count()):
        c = cands.nth(i)
        try:
            box = c.bounding_box()
            if c.is_visible() and box and box["y"] > min_y:
                c.click(timeout=timeout)
                return True
        except Exception:
            continue
    return False


def seleccionar_cliente(page, busqueda: str) -> str:
    """Mismo patron que crear_ot.seleccionar_anunciante (popup de busqueda
    del lookup dviCliente). Solo elige el cliente en el formulario."""
    boton = page.locator("td[id$='_xaf_dviCliente_Edit_find_Edit_B0']")
    if boton.count() == 0:
        raise RuntimeError("No se encontro el boton de busqueda de Cliente.")
    boton.first.click(timeout=5000)
    page.wait_for_timeout(1000)
    frame = next((f for f in page.frames if "Dialog=true" in f.url), None)
    if frame is None:
        raise RuntimeError("No se abrio el popup de busqueda de Cliente.")
    campo = frame.locator("input[id$='_Ed_I']").first
    campo.click()
    campo.fill(busqueda)
    campo.press("Enter")
    page.wait_for_timeout(1200)
    filas = frame.locator("tr[id*='DXDataRow']")
    n = filas.count()
    print(f"  clientes que matchean '{busqueda}': {n}")
    for i in range(n):
        print("   -", filas.nth(i).inner_text().strip().replace("\n", " | "))
    if n == 0:
        raise RuntimeError(f"Ningun cliente para '{busqueda}'.")
    filas.first.click(timeout=5000)
    page.wait_for_timeout(400)
    try:
        click_visible(frame, "Aceptar", timeout=2000)
    except Exception:
        pass
    esperar_postback(page)
    page.wait_for_timeout(800)
    valor = page.locator("input[id$='_xaf_dviCliente_Edit_find_Edit_I']").first.input_value()
    if valor.strip() in ("", "N / D"):
        raise RuntimeError("El Cliente no quedo seleccionado.")
    return valor.strip()


def cerrar_popup(page):
    """Cierra el dialogo abierto con Cancelar, sin aceptar nada."""
    for f in page.frames:
        if "Dialog=true" in f.url:
            try:
                if click_visible(f, "Cancelar", timeout=2000):
                    esperar_postback(page)
                    page.wait_for_timeout(500)
                    return True
            except Exception:
                pass
    page.keyboard.press("Escape")
    page.wait_for_timeout(500)
    return False


def volcar(page, nombre):
    """Vuelca campos de la pagina y de todos sus iframes."""
    resultado = {"pagina": page.evaluate(JS_CAMPOS), "frames": []}
    for fr in page.frames:
        if fr == page.main_frame:
            continue
        try:
            resultado["frames"].append({"url": fr.url, **fr.evaluate(JS_CAMPOS)})
        except Exception:
            continue
    destino = OUT_DIR / f"recibo_nuevo_{nombre}.json"
    destino.write_text(json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  campos -> {destino}")
    return resultado


def main():
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
            shot(page, "00_listado")

            print("Click en 'Nuevo' (solo abrir el formulario, NO se guarda)...")
            nuevo = page.locator('a[title="Nuevo"]').first
            if nuevo.count() > 0:
                nuevo.click()
            elif not click_visible(page, "Nuevo"):
                print("ERROR: no se encontro el boton 'Nuevo'.")
                (OUT_DIR / "recibo_nuevo_listado.html").write_text(page.content(), encoding="utf-8")
                raise SystemExit(1)
            esperar_postback(page)
            page.wait_for_timeout(1500)
            shot(page, "01_formulario")
            (OUT_DIR / "recibo_nuevo_formulario.html").write_text(page.content(), encoding="utf-8")
            volcar(page, "01_formulario")

            print("Eligiendo cliente ALUAR (aprobado por Javier 2026-11-18, sin guardar)...")
            print("  cliente cargado:", seleccionar_cliente(page, "ALUAR"))
            shot(page, "01b_cliente_elegido")

            for i, pestana in enumerate(["Referencias Canceladas", "RetencionesSufridas", "Otros Valores"], start=2):
                print(f"Pestana '{pestana}'...")
                if not click_visible(page, pestana):
                    print(f"  (no se encontro la pestana '{pestana}')")
                    continue
                esperar_postback(page)
                page.wait_for_timeout(1000)
                shot(page, f"{i:02d}_{pestana.lower().replace(' ', '_')}")
                volcar(page, f"{i:02d}_{pestana.lower().replace(' ', '_')}_tab")

                if pestana == "Referencias Canceladas":
                    continue
                print("  abriendo sub-formulario 'Nuevo' (sin aceptar)...")
                # el 'Nuevo' de la grilla esta debajo de la tira de pestanas (y ~ 579)
                abierto = click_visible_debajo(page, "Nuevo", min_y=560)
                if abierto:
                    esperar_postback(page)
                    page.wait_for_timeout(1500)
                    nombre = f"{i:02d}_{pestana.lower().replace(' ', '_')}_nuevo"
                    shot(page, nombre)
                    volcar(page, nombre)
                    cerrar_popup(page)  # SIN aceptar

            print("Saliendo SIN guardar (navegando al listado)...")
            page.goto(f"{base_url()}{LIST_URL_SUFFIX}", wait_until="networkidle", timeout=30000)
            esperar_postback(page)
            shot(page, "99_cerrado_sin_guardar")
        finally:
            browser.close()


if __name__ == "__main__":
    main()
