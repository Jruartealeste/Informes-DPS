"""
ESCRIBE EN ADVERTYS REAL. Completa un Recibo Cliente (Administracion >
Tesoreria > Recibo Cliente) a partir de un JSON de especificacion y, solo si
los totales de la cabecera cuadran con lo esperado Y se paso --guardar,
hace "Guardar y cerrar". Si algo no cuadra NO guarda (el recibo queda como
Borrador en Advertys, sin cargar el resto).

Pasos (receta de Javier, 2026-11-18):
  Fecha > Cliente > Referencias canceladas ("Cancelar Referencias Deudoras",
  tildar facturas) > RetencionesSufridas (Nuevo: año / nro / tipo / fecha /
  base / importe) > Otros Valores (Nuevo: cuenta Galicia / tipo referencia
  Transferencia Bancaria / referencia / Debe = neto) > Guardar y cerrar.

Spec JSON:
{
  "recibo": "463",                   # borrador existente a completar; si falta, crea uno nuevo
  "fecha": "16/11/2026",
  "cliente": "ALUAR",
  "facturas": ["00005A00001513", ...],  # numero tal como figura en el PDF
  "retenciones": [{"tipo": "112310-RET.IMP.GCIAS.DE CLIENTES", "anio": "2026",
                   "numero": "0000283617", "fecha": "16/11/2026",
                   "base": "1465815,68", "importe": "29316,31"}, ...],
  "otros_valores": {"cuenta": "Galicia", "tipo_referencia": "Transferencia",
                    "ref1": "0", "ref2": "2000014747", "debe": "1481939,66"},
  "totales": {"referencias": "1773636,97", "retenciones": "291697,31",
              "otros": "1481939,66"}
}

Uso (parado en informes/):
    python -m modules.recibos.crear_recibo spec.json            # carga, NO guarda
    python -m modules.recibos.crear_recibo spec.json --guardar  # carga y guarda si cuadra

Workflow: workflows/registrar_cobranza.md (skill registrar-cobranzas).
"""
import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from modules.recibos.explore_nuevo_recibo import (
    LIST_URL_SUFFIX, SCREENSHOT_DIR, cerrar_popup, click_visible, click_visible_debajo,
)
from tools.advertys_session import AdvertysLoginError, base_url, esperar_postback, login


class CrearReciboError(RuntimeError):
    pass


def shot(page, nombre):
    page.screenshot(path=str(SCREENSHOT_DIR / f"crear_recibo_{nombre}.png"), full_page=True)


def num(texto: str) -> float:
    """'1.481.939,66' o '1481939,66' -> 1481939.66"""
    limpio = texto.replace("$", "").replace(" ", "").replace(".", "").replace(",", ".")
    return round(float(limpio), 2)


def dialog_frames(page):
    return [f for f in page.frames if "Dialog=true" in f.url]


def set_texto(ctx, sufijo: str, valor: str):
    campo = ctx.locator(f"input[id$='{sufijo}']").first
    if campo.count() == 0:
        raise CrearReciboError(f"No se encontro el campo ...{sufijo}")
    campo.click()
    campo.press("Control+A")
    campo.fill(valor)
    campo.press("Tab")


def leer(page, sufijo: str) -> str:
    return page.locator(f"input[id$='{sufijo}']").first.input_value().strip()


def elegir_en_lookup(page, ctx, campo_dvi: str, busqueda: str, texto_fila: str | None = None):
    """Abre el buscador de un lookup (dviCliente, dviCuenta, dviTipoReferencia),
    busca y elige la fila que contenga `texto_fila` (o la unica)."""
    antes = len(dialog_frames(page))
    ctx.locator(f"td[id$='_xaf_{campo_dvi}_Edit_find_Edit_B0']").first.click(timeout=5000)
    page.wait_for_timeout(1200)
    frames = dialog_frames(page)
    if len(frames) <= antes - 0 and not frames:
        raise CrearReciboError(f"No se abrio el buscador de {campo_dvi}")
    sub = frames[-1]
    buscador = sub.locator("input[id$='_Ed_I']").first
    buscador.click()
    buscador.fill(busqueda)
    buscador.press("Enter")
    page.wait_for_timeout(1200)
    filas = sub.locator("tr[id*='DXDataRow']")
    if texto_fila:
        filas = filas.filter(has_text=texto_fila)
    n = filas.count()
    if n != 1:
        raise CrearReciboError(f"{campo_dvi}: '{busqueda}' dio {n} filas (se esperaba 1).")
    filas.first.click(timeout=5000)
    page.wait_for_timeout(400)
    try:
        click_visible(sub, "Aceptar", timeout=2000)
    except Exception:
        pass
    esperar_postback(page)
    page.wait_for_timeout(800)


def abrir_recibo(page, numero: str | None):
    page.goto(f"{base_url()}{LIST_URL_SUFFIX}", wait_until="networkidle", timeout=30000)
    esperar_postback(page)
    page.wait_for_timeout(800)
    if numero:
        fila = page.locator("tr[id*='DXDataRow']", has_text=numero).first
        if fila.count() == 0:
            raise CrearReciboError(f"No se encontro el recibo {numero} en el listado (filtro Mes Actual).")
        estado = fila.inner_text()
        if "Borrador" not in estado:
            raise CrearReciboError(f"El recibo {numero} no esta en Borrador; no se toca.")
        fila.locator("img, a").nth(0).click(timeout=5000)
    else:
        page.locator('a[title="Nuevo"]').first.click()
    esperar_postback(page)
    page.wait_for_timeout(1500)


def cargar_referencias(page, facturas: list[str]):
    if not click_visible(page, "Cancelar Referencias Deudoras"):
        raise CrearReciboError("No se encontro el boton 'Cancelar Referencias Deudoras'.")
    esperar_postback(page)
    page.wait_for_timeout(2000)
    frames = dialog_frames(page)
    if not frames:
        raise CrearReciboError("No se abrio el dialogo de referencias deudoras.")
    fr = frames[-1]
    for f in facturas:
        # PDF: 00005A00001513 (pto vta 5 dig + letra + nro 8 dig) -> Advertys: 000500001513
        m = re.fullmatch(r"(\d+)[A-Za-z](\d+)", f.strip())
        clave = (m.group(1).zfill(4)[-4:] + m.group(2).zfill(8)) if m else f.strip()
        filas = fr.locator("tr[id*='DXDataRow']").filter(has_text=clave)
        if filas.count() != 1:
            raise CrearReciboError(f"Factura {f}: {filas.count()} filas en deudoras (se esperaba 1).")
        filas.first.locator("td").first.click(timeout=3000)  # checkbox de seleccion
        page.wait_for_timeout(500)
    if not click_visible(fr, "Aceptar", timeout=5000):
        raise CrearReciboError("No se encontro 'Aceptar' en el dialogo de referencias.")
    esperar_postback(page)
    page.wait_for_timeout(1500)


def cargar_retencion(page, r: dict):
    click_visible(page, "RetencionesSufridas")
    esperar_postback(page)
    page.wait_for_timeout(800)
    if not click_visible_debajo(page, "Nuevo", min_y=560):
        raise CrearReciboError("No se encontro el 'Nuevo' de Retenciones sufridas.")
    esperar_postback(page)
    page.wait_for_timeout(1500)
    fr = dialog_frames(page)[-1]
    set_texto(fr, "dviRefe1_Edit_I", r["anio"])
    set_texto(fr, "dviRefe2_Edit_I", r["numero"][-7:])
    fr.locator("td[id$='dviTipoRetencionSufrida_Edit_dropdown_DD_B-1']").first.click(timeout=3000)
    page.wait_for_timeout(600)
    item = fr.get_by_text(r["tipo"], exact=True)
    if item.count() == 0:
        raise CrearReciboError(f"Tipo de retencion '{r['tipo']}' no esta en el desplegable.")
    item.last.click(timeout=3000)
    page.wait_for_timeout(400)
    set_texto(fr, "dviFecha_Edit_I", r["fecha"])
    set_texto(fr, "dviBaseImponible_Edit_I", r["base"])
    set_texto(fr, "dviImporte_Edit_I", r["importe"])
    if not click_visible(fr, "Aceptar", timeout=5000):
        raise CrearReciboError("No se encontro 'Aceptar' en el dialogo de retencion.")
    esperar_postback(page)
    page.wait_for_timeout(1200)


def cargar_otros_valores(page, ov: dict):
    click_visible(page, "Otros Valores")
    esperar_postback(page)
    page.wait_for_timeout(800)
    if not click_visible_debajo(page, "Nuevo", min_y=560):
        raise CrearReciboError("No se encontro el 'Nuevo' de Otros Valores.")
    esperar_postback(page)
    page.wait_for_timeout(1500)
    fr = dialog_frames(page)[-1]
    elegir_en_lookup(page, fr, "dviCuenta", ov["cuenta"], texto_fila="BANCO GALICIA")
    fr = dialog_frames(page)[-1]
    elegir_en_lookup(page, fr, "dviTipoReferencia", ov["tipo_referencia"], texto_fila="Transferencia Bancaria")
    fr = dialog_frames(page)[-1]
    set_texto(fr, "dviRefe1_Edit_I", ov.get("ref1", "0"))
    set_texto(fr, "dviRefe2_Edit_I", ov["ref2"])
    set_texto(fr, "dviDebe_Edit_I", ov["debe"])
    if not click_visible(fr, "Aceptar", timeout=5000):
        raise CrearReciboError("No se encontro 'Aceptar' en el dialogo de Otros Valores.")
    esperar_postback(page)
    page.wait_for_timeout(1200)


def totales_cabecera(page) -> dict:
    return {
        "referencias": num(leer(page, "dviTotalReferenciasCanceladas_Edit_I")),
        "retenciones": num(leer(page, "dviTotalRetenciones_Edit_I")),
        "otros": num(leer(page, "dviVarios_Edit_I")),
        "saldo": num(leer(page, "dviSaldo_Edit_I").replace("$", "").strip()),
    }


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    guardar = "--guardar" in sys.argv
    if not args:
        print(__doc__)
        sys.exit(1)
    spec = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    esperado = {k: num(v) for k, v in spec["totales"].items()}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 1500})
        try:
            try:
                login(page)
            except AdvertysLoginError as e:
                print(f"ERROR: {e}")
                sys.exit(1)

            abrir_recibo(page, spec.get("recibo"))
            set_texto(page, "_xaf_dviFecha_Edit_I", spec["fecha"])
            page.wait_for_timeout(800)
            if leer(page, "dviCliente_Edit_find_Edit_I") in ("", "N / D"):
                elegir_en_lookup(page, page, "dviCliente", spec["cliente"])
            print("Cliente:", leer(page, "dviCliente_Edit_find_Edit_I"), "| Fecha:", leer(page, "_xaf_dviFecha_Edit_I"))

            # Idempotente: el borrador conserva lo ya cargado entre corridas, asi
            # que cada bloque se saltea si el total de cabecera ya coincide.
            def ya(clave):
                return abs(totales_cabecera(page)[clave] - esperado[clave]) < 0.01 and esperado[clave] != 0

            if ya("referencias"):
                print("Referencias ya cargadas, se saltean.")
            else:
                cargar_referencias(page, spec["facturas"])
            print("Referencias canceladas ->", totales_cabecera(page)["referencias"])
            if ya("retenciones"):
                print("Retenciones ya cargadas, se saltean.")
            else:
                for r in spec["retenciones"]:
                    cargar_retencion(page, r)
            print("Retenciones ->", totales_cabecera(page)["retenciones"])
            if ya("otros"):
                print("Otros Valores ya cargado, se saltea.")
            else:
                cargar_otros_valores(page, spec["otros_valores"])

            click_visible(page, "Referencias Canceladas")
            page.wait_for_timeout(500)
            tot = totales_cabecera(page)
            shot(page, "listo_para_guardar")
            print("Totales cabecera:", tot)
            print("Esperado:        ", esperado)

            ok = (
                abs(tot["referencias"] - esperado["referencias"]) < 0.01
                and abs(tot["retenciones"] - esperado["retenciones"]) < 0.01
                and abs(tot["otros"] - esperado["otros"]) < 0.01
                and abs(tot["saldo"]) < 0.01
            )
            if not ok:
                print("NO CUADRA: no se guarda. El recibo queda en Borrador / sin guardar.")
                sys.exit(2)
            if not guardar:
                print("Cuadra. Sin --guardar: no se guarda.")
                return
            print("Cuadra: Guardar y cerrar...")
            if not click_visible(page, "Guardar y cerrar"):
                raise CrearReciboError("No se encontro 'Guardar y cerrar'.")
            esperar_postback(page)
            page.wait_for_timeout(2000)
            shot(page, "guardado")
            print("OK: recibo guardado. Verificar en el listado.")
        except CrearReciboError as e:
            shot(page, "error")
            print(f"ERROR: {e}  (no se guardo nada mas; ver screenshot crear_recibo_error.png)")
            sys.exit(1)
        finally:
            browser.close()


if __name__ == "__main__":
    main()
