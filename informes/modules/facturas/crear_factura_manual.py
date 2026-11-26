"""
Crea una Factura Produccion Manual en Advertys (Administracion > Facturacion >
Produccion > Factura Manual) y la deja en BORRADOR.

ESCRIBE en Advertys real solo con --guardar (skill
`crear-factura-manual-produccion`, workflow workflows/crear_factura_manual.md).
Sin --guardar: valida el spec, abre el formulario, completa la cabecera y
verifica cliente/producto/cuentas/IVA contra las opciones reales, sin guardar.

NUNCA clickea Autorizar, Facturar, Solicitar CAE ni Clona Comprobante: la
factura queda en Borrador (sin numero ni CAE) y Javier la autoriza a mano.

Relevado 2026-11-25 (explore_nueva_factura.py / explore_item_factura.py):
- La cabecera debe estar GUARDADA antes de poder abrir el "Nuevo" de items;
  Producto es obligatorio para guardar.
- Popup de item (iframe Dialog=true): Cuenta (combo, ej. 411010-FEE), Sub
  Cuenta (deshabilitada, la pone Advertys), % IVA (combo, default 21,00),
  Cantidad, Precio Unitario (sin IVA), Detalle (memo), Tipo Facturacion y
  Rubro Produccion (opcionales).

Spec JSON:
{
  "cliente": "ALUAR",                      # texto de busqueda del lookup
  "anunciante": "...",                     # opcional; default = nombre del cliente
  "producto": "Mantenimiento RR.SS. - Aluar",
  "titulo": "Fee diciembre 2026",          # opcional
  "condicion_pago": "15 DIAS FECHA FACTURA",  # opcional (default del cliente)
  "items": [
    {"cuenta": "411010-FEE", "detalle": "Fee mensual diciembre 2026",
     "cantidad": 1, "precio_unitario": 4025390.00, "iva": "21,00",
     "tipo_facturacion": "DIGITAL", "rubro": "..."}  # ambos OBLIGATORIOS (Advertys:
                                          # "Falta tipo/Rubro de facturacion")
  ],
  "neto_esperado": 4025390.00
}

Uso (parado en informes/):
    python -m modules.facturas.crear_factura_manual <spec>.json            # prueba
    python -m modules.facturas.crear_factura_manual <spec>.json --guardar  # escribe
"""
import argparse
import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from modules.recibos.explore_nuevo_recibo import cerrar_popup, click_visible, click_visible_debajo, seleccionar_cliente
from tools.advertys_session import AdvertysLoginError, base_url, esperar_postback, login

OUT_DIR = Path("exploracion")
SCREENSHOT_DIR = OUT_DIR / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

LIST_URL_SUFFIX = "Default.aspx#ViewID=FacturaProduccionManual_ListView&ObjectClassName=DPS_SAS_SR.Module.FacturaProduccionManual"

# Piso para descartar comprobantes nominales (ej. facturas de $1): la skill es
# para facturar servicios reales. No tiene override por linea de comandos.
NETO_MINIMO = 10_000.00

ALICUOTAS = {"21,00", "10,50", "27,00", "5,00", "2,50"}


class CrearFacturaError(Exception):
    pass


def shot(page, nombre):
    destino = SCREENSHOT_DIR / f"factura_manual_{nombre}.png"
    page.screenshot(path=str(destino), full_page=True)
    print(f"  -> {destino}")


def fmt(n: float) -> str:
    """12345.6 -> '12345,60' (formato de tipeo de Advertys)."""
    return f"{n:.2f}".replace(".", ",")


def parse_monto(s: str) -> float:
    s = re.sub(r"[^\d,.-]", "", s or "")
    return float(s.replace(".", "").replace(",", ".")) if s else 0.0


def validar_spec(spec: dict) -> float:
    for k in ("cliente", "producto", "items"):
        if not spec.get(k):
            raise CrearFacturaError(f"Falta '{k}' en el spec.")
    neto = 0.0
    for i, it in enumerate(spec["items"], 1):
        for k in ("cuenta", "detalle", "cantidad", "precio_unitario", "tipo_facturacion", "rubro"):
            if it.get(k) in (None, ""):
                raise CrearFacturaError(f"Item {i}: falta '{k}'.")
        iva = it.setdefault("iva", "21,00")
        if iva not in ALICUOTAS:
            raise CrearFacturaError(f"Item {i}: alicuota de IVA '{iva}' invalida ({sorted(ALICUOTAS)}).")
        if float(it["cantidad"]) <= 0 or float(it["precio_unitario"]) <= 0:
            raise CrearFacturaError(f"Item {i}: cantidad y precio deben ser positivos.")
        neto += round(float(it["cantidad"]) * float(it["precio_unitario"]), 2)
    neto = round(neto, 2)
    if neto < NETO_MINIMO:
        raise CrearFacturaError(
            f"Neto total ${neto:,.2f} por debajo del minimo ${NETO_MINIMO:,.2f}: "
            "esta skill no emite comprobantes nominales.")
    esperado = spec.get("neto_esperado")
    if esperado is not None and abs(float(esperado) - neto) > 0.01:
        raise CrearFacturaError(f"Neto de items ${neto:,.2f} != neto_esperado ${float(esperado):,.2f}.")
    return neto


def seleccionar_combo(ctx, campo: str, opcion: str, scope_page=None):
    """ASPxComboBox en `ctx` (page o frame). Si la opcion no esta en la lista
    visible (virtual scroll), tipea el texto para filtrar."""
    inp = ctx.locator(f"input[id$='_xaf_{campo}_Edit_dropdown_DD_I']")
    if inp.count() == 0:
        raise CrearFacturaError(f"No se encontro el combo {campo}.")
    iid = inp.first.get_attribute("id")
    lista = ctx.locator(f"#{iid.replace('_DD_I', '_DD_DDD_L')} td")

    def buscar():
        for i in range(lista.count()):
            if lista.nth(i).inner_text().strip() == opcion:
                lista.nth(i).click()
                ctx.wait_for_timeout(500)
                return True
        return False

    ctx.locator(f"#{iid.replace('_DD_I', '_DD_B-1')}").click(timeout=5000)
    ctx.wait_for_timeout(800)
    if buscar():
        return
    inp.first.click()
    inp.first.press("Control+a")
    inp.first.type(opcion[:20], delay=40)
    ctx.wait_for_timeout(1500)
    if buscar():
        return
    vistas = [t.strip() for t in lista.all_inner_texts() if t.strip() and "
" not in t]
    (scope_page or ctx).keyboard.press("Escape")
    raise CrearFacturaError(f"'{opcion}' no esta entre las opciones de {campo}. Visibles: {vistas[:40]}")


def tipear(ctx, campo: str, valor: str, numerico: bool = False):
    """Completa un input y verifica que el valor quedo. type() caracter por
    caracter se corta con el postback del primer caracter (Titulo quedaba
    'P', visto 2026-11-25): por eso fill() + Tab + releer."""
    loc = ctx.locator(f"[id$='_xaf_{campo}_Edit_I']").first
    for _ in range(3):
        loc.click()
        loc.fill(valor)
        loc.press("Tab")
        ctx.wait_for_timeout(1200)
        leido = loc.input_value()
        ok = (abs(parse_monto(leido) - parse_monto(valor)) < 0.005) if numerico else leido.strip() == valor.strip()
        if ok:
            return
    raise CrearFacturaError(f"{campo}: quedo {leido!r} en vez de {valor!r}.")


def frame_dialogo(page):
    for _ in range(20):
        fr = next((f for f in page.frames if "Dialog=true" in f.url), None)
        if fr is not None:
            try:
                fr.wait_for_selector("input[id$='_xaf_dviCuenta_Edit_dropdown_DD_I']", timeout=1000)
                return fr
            except Exception:
                pass
        page.wait_for_timeout(500)
    raise CrearFacturaError("No se abrio el popup de item.")


def leer_items(page):
    filas = page.locator("tr[id*='DXDataRow']")
    out = []
    for i in range(filas.count()):
        celdas = [c.strip() for c in filas.nth(i).locator("td").all_inner_texts()]
        out.append(celdas)
    return out


def leer_estado(page) -> str:
    """Estado de la factura, en modo edicion (input) o vista (texto plano)."""
    inp = page.locator("[id$='_xaf_dviEstado_Edit_I']")
    if inp.count():
        return inp.first.input_value().strip()
    return page.evaluate("""() => {
        const lab = [...document.querySelectorAll('td, span, label')]
            .find(e => e.children.length === 0 && e.textContent.trim() === 'Estado:');
        if (!lab) return '';
        const cel = lab.closest('td');
        let sig = cel ? cel.nextElementSibling : null;
        while (sig && !sig.innerText.trim()) sig = sig.nextElementSibling;
        return sig ? sig.innerText.trim().split('\\n')[0].trim() : '';
    }""")


def eliminar_borrador(page, key: str):
    """Solo para corridas de prueba (--eliminar-al-final): borra el Borrador
    recien creado con el 'Eliminar' de la barra superior y confirma."""
    estado = leer_estado(page)
    if estado != "Borrador":
        raise CrearFacturaError(f"No se elimina: el estado es {estado!r}, no Borrador (ObjectKey {key}).")
    page.once("dialog", lambda d: d.accept())
    btn = page.locator("#Vertical_TB_Menu a, #Vertical_TB_Menu span").filter(has_text="Eliminar")
    if btn.count() == 0 or not (btn.first.click() or True):
        raise CrearFacturaError(f"No se encontro 'Eliminar' (Borrador {key} queda).")
    esperar_postback(page)
    page.wait_for_timeout(2000)
    shot(page, "04_eliminado")
    if "DetailView" in page.url and f"ObjectKey={key}" in page.url:
        raise CrearFacturaError(f"Tras Eliminar sigue abierto el Borrador {key}: revisar a mano.")
    print(f"Borrador {key} eliminado (prueba).")


def crear_factura(spec: dict, guardar: bool, eliminar_al_final: bool = False) -> str | None:
    neto = validar_spec(spec)
    print(f"Spec OK: {len(spec['items'])} item(s), neto ${neto:,.2f}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        try:
            try:
                login(page)
            except AdvertysLoginError as e:
                raise CrearFacturaError(str(e))
            page.goto(f"{base_url()}{LIST_URL_SUFFIX}", wait_until="networkidle", timeout=30000)
            esperar_postback(page)
            page.wait_for_timeout(800)
            if not (click_visible(page, "Nuevo") or click_visible(page, "New")):
                raise CrearFacturaError("No se encontro 'Nuevo' en el listado.")
            esperar_postback(page)
            page.wait_for_timeout(1500)

            for intento in range(2):  # el popup de busqueda a veces no abre a la primera
                try:
                    cliente = seleccionar_cliente(page, spec["cliente"])
                    break
                except RuntimeError:
                    if intento:
                        raise
                    page.wait_for_timeout(2000)
            print("Cliente:", cliente)
            esperar_postback(page)
            page.wait_for_timeout(1000)
            # Advertys autocompleta Anunciante con el PRIMERO asociado al cliente
            # (HORA DATA -> TWDC, visto 2026-11-25), y los Productos dependen del
            # anunciante. Se fija explicito: por defecto, mismo nombre que el cliente.
            anunciante = spec.get("anunciante") or cliente
            seleccionar_combo(page, "dviAnunciante", anunciante)
            esperar_postback(page)
            page.wait_for_timeout(1000)
            leido = page.locator("input[id$='_xaf_dviAnunciante_Edit_dropdown_DD_I']").first.input_value().strip()
            if leido != anunciante.strip():
                raise CrearFacturaError(f"Anunciante quedo {leido!r} en vez de {anunciante!r}.")
            print("Anunciante:", leido)
            seleccionar_combo(page, "dviProductoDefault", spec["producto"])
            if spec.get("condicion_pago"):
                seleccionar_combo(page, "dviCondicionPago", spec["condicion_pago"])
            if spec.get("titulo"):
                tipear(page, "dviTitulo", spec["titulo"])
            esperar_postback(page)
            shot(page, "01_cabecera")

            if not guardar:
                print("MODO PRUEBA: cabecera completada y validada; no se guarda nada.")
                print("  (los items se validan por spec; sus combos se verifican al guardar)")
                return None

            print("Guardando cabecera (Borrador)...")
            if not click_visible(page, "Guardar"):
                raise CrearFacturaError("No se encontro 'Guardar'.")
            esperar_postback(page)
            page.wait_for_timeout(1500)
            m = re.search(r"ObjectKey=(\d+)", page.url)
            key = m.group(1) if m else "?"
            print(f"  Borrador guardado, ObjectKey={key}")

            try:
                for i, it in enumerate(spec["items"], 1):
                    print(f"Item {i}: {it['cuenta']} | {it['detalle'][:40]} | {it['cantidad']} x {fmt(float(it['precio_unitario']))}")
                    if not click_visible_debajo(page, "Nuevo", min_y=450):
                        raise CrearFacturaError(f"Item {i}: no se encontro el 'Nuevo' de items (Borrador {key}).")
                    esperar_postback(page)
                    fr = frame_dialogo(page)
                    seleccionar_combo(fr, "dviCuenta", it["cuenta"], scope_page=page)
                    esperar_postback(page)
                    seleccionar_combo(fr, "dviAlicuotaIva", it["iva"], scope_page=page)
                    # Tipo y Rubro son obligatorios; el Rubro depende del Tipo elegido
                    seleccionar_combo(fr, "dviTipoFacturacion", it["tipo_facturacion"], scope_page=page)
                    esperar_postback(page)
                    fr.wait_for_timeout(1200)
                    seleccionar_combo(fr, "dviRubroProduccion", it["rubro"], scope_page=page)
                    tipear(fr, "dviCantidad", fmt(float(it["cantidad"])), numerico=True)
                    tipear(fr, "dviPrecioUnitario", fmt(float(it["precio_unitario"])), numerico=True)
                    det = fr.locator("[id$='_xaf_dviDetalle_Edit_I']").first
                    det.click()
                    det.fill(it["detalle"])
                    det.press("Tab")
                    esperado = round(float(it["cantidad"]) * float(it["precio_unitario"]), 2)
                    neto_loc = fr.locator("[id$='_xaf_dviNeto_Edit_I']").first
                    neto_item = 0.0
                    for _ in range(12):  # Advertys recalcula Neto con un callback, a veces tarda
                        neto_item = parse_monto(neto_loc.input_value())
                        if neto_item:
                            break
                        fr.wait_for_timeout(500)
                    if not neto_item:
                        # 2026-11-25: Neto quedo en $0 tras cargar cantidad y precio. El campo es
                        # editable en el popup: se completa y se verifica igual.
                        print("  Neto no se recalculo solo; se completa a mano.")
                        tipear(fr, "dviNeto", fmt(esperado), numerico=True)
                        neto_item = parse_monto(neto_loc.input_value())
                    shot(page, f"02_item_{i}_cargado")
                    if abs(neto_item - esperado) > 0.01:
                        cerrar_popup(page)
                        raise CrearFacturaError(
                            f"Item {i}: Advertys calcula neto ${neto_item:,.2f} y se esperaba ${esperado:,.2f} "
                            f"(Borrador {key}, item no aceptado).")
                    shot(page, f"02_item_{i}")
                    if not click_visible(fr, "Aceptar"):
                        raise CrearFacturaError(f"Item {i}: no se encontro 'Aceptar' (Borrador {key}).")
                    esperar_postback(page)
                    page.wait_for_timeout(2500)
                    shot(page, f"02_item_{i}_aceptado")
                    abierto = next((f for f in page.frames if "Dialog=true" in f.url), None)
                    if abierto is not None:
                        try:
                            msg = abierto.evaluate("() => document.body.innerText").strip()
                        except Exception:
                            msg = "?"
                        raise CrearFacturaError(
                            f"Item {i}: el popup sigue abierto tras Aceptar (Borrador {key}). Texto: {msg[:400]!r}")

                print("Guardando factura...")
                if not click_visible(page, "Guardar"):
                    raise CrearFacturaError(f"No se encontro 'Guardar' final (Borrador {key}).")
                esperar_postback(page)
                page.wait_for_timeout(1500)
                shot(page, "03_guardada")

                filas = leer_items(page)
                # columnas: [chk, cuenta, subcuenta, detalle, cantidad, %iva, p.unit, neto, ...]
                total = round(sum(parse_monto(f[7]) for f in filas if len(f) > 7), 2)
                print(f"Items en grilla: {len(filas)} | neto ${total:,.2f}")
                if len(filas) != len(spec["items"]) or abs(total - neto) > 0.01:
                    raise CrearFacturaError(
                        f"Verificacion fallida: grilla {len(filas)} items / ${total:,.2f}, "
                        f"esperado {len(spec['items'])} / ${neto:,.2f}. Revisar Borrador {key} a mano.")
                estado = page.locator("[id$='_xaf_dviEstado_Edit_I']").first.input_value() \
                    if page.locator("[id$='_xaf_dviEstado_Edit_I']").count() else "?"
                print(f"OK: Factura Produccion Manual en Borrador, ObjectKey={key}, estado={estado!r}, neto ${neto:,.2f}.")
                print(f"    {base_url()}Default.aspx#ViewID=FacturaProduccionManual_DetailView&ObjectKey={key}"
                      "&ObjectClassName=DPS_SAS_SR.Module.FacturaProduccionManual")
                if eliminar_al_final:
                    eliminar_borrador(page, key)
            except Exception:
                if eliminar_al_final:
                    print("Fallo la prueba: se elimina el Borrador creado...")
                    try:
                        cerrar_popup(page)
                        page.goto(f"{base_url()}Default.aspx#ViewID=FacturaProduccionManual_DetailView&ObjectKey={key}"
                                  "&ObjectClassName=DPS_SAS_SR.Module.FacturaProduccionManual", wait_until="networkidle")
                        esperar_postback(page)
                        page.wait_for_timeout(1500)
                        eliminar_borrador(page, key)
                    except Exception as e2:
                        print(f"  No se pudo eliminar el Borrador {key}: {e2}")
                raise
            return key
        finally:
            browser.close()


def main():
    ap = argparse.ArgumentParser(description="Crea una Factura Produccion Manual en Borrador en Advertys")
    ap.add_argument("spec", help="ruta al spec JSON")
    ap.add_argument("--guardar", action="store_true", help="escribe en Advertys (sin esto: modo prueba)")
    ap.add_argument("--eliminar-al-final", action="store_true",
                    help="solo pruebas: tras verificar, elimina el Borrador creado (requiere --guardar)")
    args = ap.parse_args()
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    try:
        crear_factura(spec, args.guardar, args.eliminar_al_final)
    except CrearFacturaError as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
