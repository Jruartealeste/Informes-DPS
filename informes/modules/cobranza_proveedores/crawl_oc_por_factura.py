"""
Crawl de SOLO LECTURA (nunca clickea 'Editar'/'Guardar'/'Nuevo', ver
salvaguarda en CLAUDE.md): para cada factura de venta referenciada por un
Recibo Cliente cobrado en los ultimos 2 meses (ver
modules/recibos/crawl_referencias_canceladas.py), abre la factura
individual en Advertys y lee su pestana "Items Facturas"/"Items Facturas
Medios" para traer el N° de Orden de Compra/Publicidad EXACTO por item.

Mismo patron y mismo motivo que modules/iibb/crawl_oc_por_factura.py (no se
toca ese script: tiene su propio alcance -- facturas con deducible IIBB en
la ventana de 6 meses -- distinto al de este modulo -- facturas cobradas en
la ventana de 2 meses (ver modules/cobranza_proveedores/config.py: bajada
de 6 a 2 meses el 2026-08-04 por costo del crawl de recibos). El proyecto
ya decidio duplicar el patron simple en vez de compartir un framework
generico, ver README).

Diferencia clave con el crawl de IIBB: la sub-grilla "Referencias
Canceladas" de un recibo (fuente de las facturas a revisar aca) NO trae el
"TA" (tipo de asiento) de la factura -- por eso una misma N° Referencia
puede, en el caso raro de que exista tanto como factura Produccion (TA=FP)
como Medios (TA=FM), traer AMBAS filas al buscarla en el listado de
Facturas. Este crawl no asume "la primera fila": abre TODAS las filas que
matchean el texto buscado y guarda el tipo de factura inferido segun cual
pestana de items encontro ("Items Facturas Medios" -> FM, "Items Facturas"
-> FP) -- asi generate_html_report.py puede desambiguar con la clave
completa en vez de a ciegas.

Igual que modules/iibb/crawl_oc_por_factura.py, la tabla resultante
(items_factura_oc_cobranza) se REEMPLAZA entera en cada corrida.

Uso:
    python -m modules.cobranza_proveedores.crawl_oc_por_factura
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

load_dotenv()

URL = os.environ.get("ADVERTYS_URL")
USER = os.environ.get("ADVERTYS_USER")
PASSWORD = os.environ.get("ADVERTYS_PASSWORD")

SCREENSHOT_DIR = Path("exploracion") / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

SCHEMA = """
CREATE TABLE IF NOT EXISTS items_factura_oc_cobranza (
    numero_referencia TEXT,
    tipo_asiento_inferido TEXT,
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
    "numero_referencia", "tipo_asiento_inferido", "detalle", "neto_sin_iva",
    "orden_trabajo_raw", "estimado_costos_raw", "orden_compra_raw",
    "numero_oc", "fecha_crawl",
]


def init_db():
    with db.get_connection() as conn:
        conn.execute(SCHEMA)
        conn.commit()


def reemplazar_todo(records: list[dict]) -> int:
    with db.get_connection() as conn:
        conn.execute("DELETE FROM items_factura_oc_cobranza")
        if records:
            placeholders = ", ".join("?" for _ in COLUMNAS_TABLA)
            sql = f"INSERT INTO items_factura_oc_cobranza ({', '.join(COLUMNAS_TABLA)}) VALUES ({placeholders})"
            conn.executemany(sql, [tuple(r.get(c) for c in COLUMNAS_TABLA) for r in records])
        conn.commit()
    return len(records)


def facturas_a_revisar() -> list[str]:
    """N Referencia distintos que aparecen en Referencias Canceladas de
    recibos de los ultimos 2 meses (la tabla ya viene acotada a esa ventana,
    ver modules/recibos/crawl_referencias_canceladas.py)."""
    sql = """
        SELECT DISTINCT numero_referencia
        FROM referencias_canceladas
        WHERE numero_referencia IS NOT NULL AND numero_referencia != ''
        ORDER BY numero_referencia
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
        page.screenshot(path=str(SCREENSHOT_DIR / "cobranza_crawl_error_login.png"))
        sys.exit(1)
    print("Login OK.")


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


def tabla_visible(page):
    """Locator de la tabla ASPxGridView actualmente visible, o None. Se usa
    tanto para leer datos (leer_grid_visible) como para clickear una fila
    puntual por indice (ver filas_candidatas/main): clickear DENTRO de esta
    tabla evita el bug real detectado 2026-08-04 -- buscar por texto en TODA
    la pagina (page.get_by_text) y clickear .nth(idx) podia, en el caso raro
    de N Referencia duplicado entre TA distintos, hacer que dos indices
    distintos terminaran clickeando la MISMA fila (confirmado comparando
    contra facturas.tipo_asiento local: dos facturas realmente distintas
    -000500000015 ALUAR/FM e INCAA/FP- pero el crawl trajo la de ALUAR dos
    veces). Acotar el click a la fila real de la grilla lo evita."""
    tablas = page.locator("table[id*='DXMainTable']")
    for i in range(tablas.count()):
        candidata = tablas.nth(i)
        try:
            if candidata.is_visible():
                return candidata
        except Exception:
            continue
    return None


def leer_grid_visible(page):
    tabla = tabla_visible(page)
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


def ir_al_listado_facturas(page):
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


def filas_candidatas(page, numero_referencia: str) -> int:
    """Busca la factura por N Referencia y devuelve cuantas filas matchean
    en la GRILLA (no en toda la pagina, ver tabla_visible) -- normalmente 1;
    en el caso raro de N Referencia repetido entre TA distintos, puede haber
    mas de 1 (ver docstring del modulo)."""
    if not buscar_texto(page, numero_referencia):
        raise RuntimeError("No se encontro el buscador 'Texto a buscar...'")
    esperar_postback(page)
    page.wait_for_timeout(800)
    tabla = tabla_visible(page)
    if tabla is None:
        return 0
    return tabla.locator("tr[id*='DXDataRow']").count()


# Facturas "Produccion" (TA=FP) y "Medios" (TA=FM) son objetos DISTINTOS en
# Advertys, cada uno con su propia pestana de items -- ver docstring.
PESTANAS_ITEMS = (("Items Facturas Medios", "FM"), ("Items Facturas", "FP"))


def leer_items_factura(page, numero_referencia: str) -> tuple[list[dict], str | None]:
    tipo_inferido = None
    for pestana, ta in PESTANAS_ITEMS:
        if click_boton_visible(page, pestana):
            tipo_inferido = ta
            break
    if tipo_inferido is None:
        print(f"    AVISO: no se encontro ninguna pestana de items ({[p for p, _ in PESTANAS_ITEMS]}) para {numero_referencia}")
        return [], None
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
            "tipo_asiento_inferido": tipo_inferido,
            "detalle": detalle,
            "neto_sin_iva": normalizar_numero(neto_sin_iva_txt) or 0.0,
            "orden_trabajo_raw": orden_trabajo,
            "estimado_costos_raw": estimado_costos,
            "orden_compra_raw": orden_compra_raw,
            "numero_oc": parsear_numero_oc(orden_compra_raw),
        })
    return items, tipo_inferido


def main():
    if not URL or not USER or not PASSWORD:
        print("ERROR: completa ADVERTYS_URL, ADVERTYS_USER y ADVERTYS_PASSWORD en .env")
        sys.exit(1)

    init_db()
    facturas = facturas_a_revisar()
    if not facturas:
        print("No hay facturas referenciadas por recibos en la ventana de 2 meses (o falta correr")
        print("modules/recibos/ingest.py + modules/recibos/crawl_referencias_canceladas.py primero).")
        return

    print(f"Se van a revisar {len(facturas)} facturas (esto tarda varios minutos, una a la vez)...")

    resultados = []
    ahora = datetime.now(timezone.utc).isoformat()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(accept_downloads=True)
        login(page)

        for i, numero_referencia in enumerate(facturas, 1):
            print(f"  [{i}/{len(facturas)}] Factura {numero_referencia}...")
            try:
                ir_al_listado_facturas(page)
                n_filas = filas_candidatas(page, numero_referencia)
                if n_filas == 0:
                    print(f"    AVISO: no se encontro la factura {numero_referencia} en la grilla, salteo")
                    continue
                if n_filas > 1:
                    print(f"    AVISO: {n_filas} facturas distintas comparten N Referencia {numero_referencia} (caso raro FP/FM) -- se revisan todas")

                for idx in range(n_filas):
                    if idx > 0:
                        # Volver al listado y re-buscar: el orden de las filas
                        # filtradas es estable entre corridas de la misma
                        # busqueda, asi que nth(idx) apunta siempre a la misma
                        # fila candidata (no se "consumen" filas al abrirlas,
                        # es solo lectura).
                        ir_al_listado_facturas(page)
                        filas_candidatas(page, numero_referencia)
                    tabla = tabla_visible(page)
                    if tabla is None:
                        break
                    filas_tr = tabla.locator("tr[id*='DXDataRow']")
                    if filas_tr.count() <= idx:
                        break
                    # Click en la celda que tiene el N Referencia buscado,
                    # pero ACOTADO a esta fila puntual (get_by_text scoped al
                    # locator de la fila, no a toda la pagina) -- clickear la
                    # primera celda "a ciegas" (columna 0) no dispara el
                    # handler de apertura (confirmado en vivo: 0 items,
                    # ninguna pestana encontrada, la fila nunca se abrio).
                    fila_actual = filas_tr.nth(idx)
                    celda_texto = fila_actual.get_by_text(str(numero_referencia), exact=True).first
                    if celda_texto.count() > 0:
                        celda_texto.click(timeout=5000)
                    else:
                        fila_actual.locator("td").nth(1).click(timeout=5000)
                    esperar_postback(page)
                    page.wait_for_timeout(800)

                    items, tipo_inferido = leer_items_factura(page, numero_referencia)
                    for it in items:
                        it["fecha_crawl"] = ahora
                    resultados.extend(items)
                    con_oc = sum(1 for it in items if it["numero_oc"])
                    print(f"    -> [{tipo_inferido}] {len(items)} item(s), {con_oc} con N° de OC/OP")
            except Exception as e:
                print(f"    ERROR revisando factura {numero_referencia}: {e}")
                continue

        browser.close()

    cantidad = reemplazar_todo(resultados)
    print(f"OK: {cantidad} items de factura guardados en items_factura_oc_cobranza ({len(facturas)} facturas revisadas).")


if __name__ == "__main__":
    main()
