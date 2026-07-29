"""
Crawl de SOLO LECTURA (nunca clickea 'Editar'/'Guardar'/'Nuevo', ver
salvaguarda en CLAUDE.md): para cada factura de venta de los ultimos 6
meses que tiene monto OC/OP deducible (segun modules/iibb, cruzando
facturas + imputaciones_iibb), abre la factura individual en Advertys y lee
su pestana "Items Facturas" para traer el N° de Orden de Compra/Publicidad
EXACTO por item.

Por que hace falta esto (no alcanza con el export bulk de Imputaciones):
la vista Imputaciones (modules/iibb) no trae el numero de OC/OP -- solo el
monto y una Leyenda de texto libre. El numero real solo esta en la grilla
de items de cada factura individual (confirmado por Javier con una
captura real, 2026-07-23), sin export masivo posible. Por eso este script
navega factura por factura con Playwright (mas lento que un ingest de
Excel -- pensar unos minutos para correrlo -- pero acotado: solo las
facturas CON deducible de la ventana de 6 meses, no las 1000+ facturas
historicas).

Ojo (relevado 2026-07-23): las facturas TA='FP' (Produccion) y TA='FM'
(Medios) son objetos DISTINTOS en Advertys -- DPS_Factura vs
FacturasMedios, layouts de detalle completamente diferentes. La pestana
con los items no se llama igual en las dos: "Items Facturas" en
Produccion, "Items Facturas Medios" en Medios (ver PESTANAS_ITEMS mas
abajo). Ambas tienen una columna "Orden Compra" con el mismo formato de
texto ("<numero> - <proveedor> -$<monto> - <estado>"), asi que se parsea
igual una vez identificada la pestana correcta. Medios ademas tiene una
columna "Pauta" (la Orden de Publicidad propiamente dicha) que este script
no releva todavia -- si en el futuro hace falta ese numero aparte del de
"Orden Compra", hay que sumarlo a leer_items_factura().

Tambien sirve de control de calidad: generate_html_report.py compara la
suma de "Neto Sin Iva" de los items con OC/OP cargada (este crawl) contra
el monto_deducible que sale de Imputaciones, y avisa si no coinciden --
ver _reportar_discrepancias().

Igual que modules/ordenes_trabajo/crawl_items_pendientes.py, la tabla
resultante (items_factura_oc) se REEMPLAZA entera en cada corrida: es un
snapshot de la ventana de 6 meses actual, no un historico acumulado.

Uso:
    python -m modules.iibb.crawl_oc_por_factura
"""
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

import db
from common import normalizar_numero
from . import config

load_dotenv()

URL = os.environ.get("ADVERTYS_URL")
USER = os.environ.get("ADVERTYS_USER")
PASSWORD = os.environ.get("ADVERTYS_PASSWORD")

SCREENSHOT_DIR = Path("exploracion") / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

SCHEMA = """
CREATE TABLE IF NOT EXISTS items_factura_oc (
    numero_referencia TEXT,
    detalle TEXT,
    neto_sin_iva REAL,
    orden_trabajo_raw TEXT,
    estimado_costos_raw TEXT,
    orden_compra_raw TEXT,
    numero_oc TEXT,
    fecha_crawl TEXT
);
"""

COLUMNAS_TABLA = [
    "numero_referencia", "detalle", "neto_sin_iva", "orden_trabajo_raw",
    "estimado_costos_raw", "orden_compra_raw", "numero_oc", "fecha_crawl",
]


def init_db():
    with db.get_connection() as conn:
        conn.execute(SCHEMA)
        conn.commit()


def reemplazar_todo(records: list[dict]) -> int:
    with db.get_connection() as conn:
        conn.execute("DELETE FROM items_factura_oc")
        if records:
            placeholders = ", ".join("?" for _ in COLUMNAS_TABLA)
            sql = f"INSERT INTO items_factura_oc ({', '.join(COLUMNAS_TABLA)}) VALUES ({placeholders})"
            conn.executemany(sql, [tuple(r.get(c) for c in COLUMNAS_TABLA) for r in records])
        conn.commit()
    return len(records)


def facturas_a_revisar() -> list[str]:
    """Facturas de los ultimos 6 meses con monto OC/OP deducible > 0 (mismo
    recorte que modules/iibb/generate_html_report.py) -- no tiene sentido
    crawlear facturas sin ninguna linea deducible."""
    sql = f"""
        SELECT f.numero_referencia
        FROM facturas f
        JOIN {config.DB_TABLE} i
          ON f.tipo_asiento = i.tipo_asiento AND f.numero_asiento = i.numero_asiento
         AND f.tipo_referencia = i.tipo_referencia AND f.numero_referencia = i.numero_referencia
        WHERE f.fecha >= date('now', '-6 months')
        GROUP BY f.clave_factura
        ORDER BY f.fecha DESC
    """
    with db.get_connection() as conn:
        return [r[0] for r in conn.execute(sql)]


def esperar_postback(page, timeout=25000):
    try:
        page.wait_for_selector(".dxlpLoadingDiv", state="visible", timeout=3000)
    except Exception:
        pass
    try:
        page.wait_for_selector(".dxlpLoadingDiv", state="hidden", timeout=timeout)
    except Exception:
        pass
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass


def login(page):
    print(f"Abriendo {URL}")
    page.goto(URL, wait_until="networkidle", timeout=30000)
    user_input = page.locator('input[id$="xaf_dviUserName_Edit_I"]')
    pass_input = page.locator('input[id$="xaf_dviPassword_Edit_I"]')
    user_input.wait_for(state="visible", timeout=15000)
    user_input.click()
    user_input.fill(USER)
    pass_input.click()
    pass_input.fill(PASSWORD)
    pass_input.press("Enter")
    esperar_postback(page)
    if "Login.aspx" in page.url:
        login_link = page.locator('a[title="Iniciar sesión"], a[title="Iniciar sesion"]')
        if login_link.count() > 0:
            login_link.first.click(force=True, timeout=10000)
            esperar_postback(page)
    if "Login.aspx" in page.url:
        print("ERROR: no se pudo hacer login. Revisa usuario/contraseña en .env")
        page.screenshot(path=str(SCREENSHOT_DIR / "iibb_crawl_error_login.png"))
        sys.exit(1)
    print("Login OK.")


def abrir_combo_filtro(page):
    """Mismo patron que modules/ordenes_trabajo/cerrar_ot.abrir_combo_filtro:
    busca el combo de Filtro por el VALOR actual (no por ID fijo, que puede
    variar segun como se llego a la vista) y lo abre."""
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


def click_boton_visible(page, texto, timeout=5000):
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


def leer_grid_visible(page):
    """Lee la grilla ASPxGridView actualmente visible -- ver docstring
    identico en modules/ordenes_trabajo/cerrar_ot.leer_grid_visible."""
    tablas = page.locator("table[id*='DXMainTable']")
    tabla = None
    for i in range(tablas.count()):
        candidata = tablas.nth(i)
        try:
            if candidata.is_visible():
                tabla = candidata
                break
        except Exception:
            continue
    if tabla is None:
        return []

    headers_loc = tabla.locator("td[class*='dxgvHeader']")
    headers = [headers_loc.nth(i).inner_text().strip() for i in range(headers_loc.count())]
    if not headers:
        return []

    filas_loc = tabla.locator("tr[id*='DXDataRow']")
    filas = []
    for i in range(filas_loc.count()):
        celdas = filas_loc.nth(i).locator("td")
        n = celdas.count()
        fila = {nombre: (celdas.nth(j).inner_text().strip() if j < n else "") for j, nombre in enumerate(headers)}
        filas.append(fila)
    return filas


def _col(fila, *nombres_posibles):
    for clave, valor in fila.items():
        for nombre in nombres_posibles:
            if nombre in clave:
                return valor
    return ""


def _boton_pagina_siguiente(page):
    """Boton 'Siguiente' del pager DevExpress (id termina en '_PBN'), o None
    si no hay mas paginas (boton con clase 'dxp-disabledButton') o no existe
    ningun pager visible. Confirmado en vivo 2026-07-23 (factura 000500000509,
    "Pagina 1 de 2, 21 elementos") -- leer_grid_visible por si sola solo trae
    la pagina actual, y el default de la grilla es 20 filas: cualquier
    factura con mas de 20 items quedaba truncada sin este paginado."""
    botones = page.locator('a[id$="_PBN"]')
    for i in range(botones.count()):
        boton = botones.nth(i)
        try:
            if not boton.is_visible():
                continue
            clase = boton.get_attribute("class") or ""
            if "disabledButton" in clase:
                return None
            return boton
        except Exception:
            continue
    return None


def leer_grid_completo(page, max_paginas=25):
    """Igual que leer_grid_visible, pero recorre TODAS las paginas del
    pager (ver _boton_pagina_siguiente) y concatena las filas."""
    filas = list(leer_grid_visible(page))
    paginas = 1
    while paginas < max_paginas:
        boton = _boton_pagina_siguiente(page)
        if boton is None:
            break
        boton.click(timeout=5000)
        esperar_postback(page)
        page.wait_for_timeout(500)
        filas.extend(leer_grid_visible(page))
        paginas += 1
    return filas


# "198 - SADAIC -$677000,00 - Autorizada" -> numero de OC = "198"
_RE_NUMERO_OC = re.compile(r"^\s*(\d+)\s*-")


def parsear_numero_oc(texto: str) -> str | None:
    m = _RE_NUMERO_OC.match(texto or "")
    return m.group(1) if m else None


def ir_a_factura(page, numero_referencia: str) -> bool:
    base_url = URL.split("Login.aspx")[0]
    direct_url = f"{base_url}Default.aspx#ViewID=DPS_Factura_ListView&ObjectClassName=DPS_SAS_SR.Module.DPS_Factura"
    page.goto(direct_url, wait_until="networkidle", timeout=30000)
    esperar_postback(page)
    page.wait_for_timeout(800)

    if abrir_combo_filtro(page):
        page.wait_for_timeout(500)
        item = page.get_by_text("Todos", exact=True)
        if item.count() > 0:
            item.first.click(timeout=3000)
            esperar_postback(page)
        else:
            page.keyboard.press("Escape")
        page.wait_for_timeout(500)

    if not buscar_texto(page, numero_referencia):
        raise RuntimeError("No se encontro el buscador 'Texto a buscar...'")
    esperar_postback(page)
    page.wait_for_timeout(800)

    fila = page.get_by_text(str(numero_referencia), exact=True)
    if fila.count() == 0:
        return False
    fila.first.click(timeout=5000)
    esperar_postback(page)
    page.wait_for_timeout(800)
    return True


# Facturas "Producción" (TA=FP) y "Medios" (TA=FM) son objetos DISTINTOS en
# Advertys (DPS_Factura vs FacturasMedios -- confirmado en vivo 2026-07-23,
# ver docstring del modulo): cada uno tiene su propia pestana de items con
# nombre distinto, aunque ambas tengan una columna "Orden Compra" con el
# mismo formato de texto.
PESTANAS_ITEMS = ("Items Facturas Medios", "Items Facturas")


def leer_items_factura(page, numero_referencia: str) -> list[dict]:
    if not any(click_boton_visible(page, pestana) for pestana in PESTANAS_ITEMS):
        print(f"    AVISO: no se encontro ninguna pestana de items ({PESTANAS_ITEMS}) para {numero_referencia}")
        return []
    esperar_postback(page)
    page.wait_for_timeout(600)

    filas = leer_grid_completo(page)
    items = []
    for fila in filas:
        detalle = _col(fila, "Detalle").strip()
        neto_sin_iva_txt = _col(fila, "Neto Sin Iva")
        orden_trabajo = _col(fila, "Orden Trabajo").strip()
        estimado_costos = _col(fila, "Estimado Costos").strip()
        orden_compra_raw = _col(fila, "Orden Compra").strip()
        items.append({
            "numero_referencia": numero_referencia,
            "detalle": detalle,
            "neto_sin_iva": normalizar_numero(neto_sin_iva_txt) or 0.0,
            "orden_trabajo_raw": orden_trabajo,
            "estimado_costos_raw": estimado_costos,
            "orden_compra_raw": orden_compra_raw,
            "numero_oc": parsear_numero_oc(orden_compra_raw),
        })
    return items


def main():
    if not URL or not USER or not PASSWORD:
        print("ERROR: completa ADVERTYS_URL, ADVERTYS_USER y ADVERTYS_PASSWORD en .env")
        sys.exit(1)

    init_db()
    facturas = facturas_a_revisar()
    if not facturas:
        print("No hay facturas con OC/OP deducible en la ventana de 6 meses (o falta correr los ingest de facturas/iibb).")
        return

    print(f"Se van a revisar {len(facturas)} facturas (esto tarda varios minutos, una factura a la vez)...")

    resultados = []
    ahora = datetime.now(timezone.utc).isoformat()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(accept_downloads=True)
        login(page)

        for i, numero_referencia in enumerate(facturas, 1):
            print(f"  [{i}/{len(facturas)}] Factura {numero_referencia}...")
            try:
                if not ir_a_factura(page, numero_referencia):
                    print(f"    AVISO: no se encontro la factura {numero_referencia} en la grilla, salteo")
                    continue
                items = leer_items_factura(page, numero_referencia)
                for it in items:
                    it["fecha_crawl"] = ahora
                resultados.extend(items)
                con_oc = sum(1 for it in items if it["numero_oc"])
                print(f"    -> {len(items)} item(s), {con_oc} con N° de OC/OP")
            except Exception as e:
                print(f"    ERROR revisando factura {numero_referencia}: {e}")
                continue

        browser.close()

    cantidad = reemplazar_todo(resultados)
    print(f"OK: {cantidad} items de factura guardados en items_factura_oc ({len(facturas)} facturas revisadas).")


if __name__ == "__main__":
    main()
