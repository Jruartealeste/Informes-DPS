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

Ademas (desde 2026-09-28), en la MISMA visita a cada factura se lee la
pestana "Importes" (seccion "Detalle impositivo": No Gravado/Gravado
1/Gravado 2/Gravado 3 (o "Gravado Otros") + sus Iva) y se guarda en
`detalle_impositivo_factura`. Motivo (caso real, factura 000500000567,
ALUAR, 2026-09-07, confirmado con Javier): el export masivo de Facturas
vuelca en "Subtotal ML"/"Impuestos ML" SOLO el concepto "Gravado 2" (la
alicuota 21%) -- si una factura mezcla alicuotas (ahi: Servicio de Agencia
$874.950 al 21% + recupero de terceros $9.210.000 gravado al 5%, en el
campo que Produccion llama "Gravado 3" y Medios llama "Gravado Otros"),
"Subtotal ML" queda ~10x mas chico que el verdadero subtotal de la
factura, y la Base Imponible IIBB del informe (subtotal - deducible -
servicio agencia) da negativa en vez de la base real. El "Subtotal ML"
del export SI alcanza cuando la factura factura todo a una sola alicuota
(caso normal, verificado contra facturas 000500000568 y 000500000569) --
por eso generate_html_report.py solo pisa subtotal_ml con la suma de
Gravados de esta tabla cuando existe esa fila (facturas sin deducible no
se crawlean, siguen usando el Subtotal ML del export tal cual).

Igual que modules/ordenes_trabajo/crawl_items_pendientes.py, la tabla
resultante (items_factura_oc) se REEMPLAZA entera en cada corrida: es un
snapshot de la ventana de 6 meses actual, no un historico acumulado.

Reintento automatico (desde 2026-08-18): una factura que falla en la
primera pasada (postback lento, grilla que todavia no refresco) se
reintenta una vez al final, misma sesion de browser -- antes quedaba
"pendiente" en silencio (con deducible pero sin detalle de OC/OP en el
informe) y habia que reintentarla a mano. Si sigue fallando tras el
reintento, se avisa por nombre al final del output (ver `siguen_fallando`
en main()).

Para un refresh de IIBB que garantice que no quede nada pendiente (este
crawl necesita facturas/imputaciones_iibb al dia, y el informe ademas
necesita ordenes_compra/ordenes_publicidad frescas para resolver
Proveedor/Monto -- ver oc_resolver.py), usar
`python -m tools.actualizar_iibb` en vez de correr este script suelto.

Uso (suelto, si ya tenes todo lo demas al dia):
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

# Detalle impositivo (pestana "Importes" de cada factura) -- ver docstring
# del modulo para el porque. "gravado_3" cubre tanto "Gravado 3" (label en
# facturas de Produccion) como "Gravado Otros" (label en Medios) -- mismo
# concepto, tercera alicuota, nombre distinto segun el tipo de factura.
SCHEMA_IMPOSITIVO = """
CREATE TABLE IF NOT EXISTS detalle_impositivo_factura (
    numero_referencia TEXT,
    no_gravado REAL,
    gravado_1 REAL,
    gravado_2 REAL,
    gravado_3 REAL,
    iva_1 REAL,
    iva_2 REAL,
    iva_3 REAL,
    percepcion_iva REAL,
    percepcion_iibb1 REAL,
    percepcion_iibb2 REAL,
    total REAL,
    fecha_crawl TEXT
);
"""

COLUMNAS_IMPOSITIVO = [
    "numero_referencia", "no_gravado", "gravado_1", "gravado_2", "gravado_3",
    "iva_1", "iva_2", "iva_3", "percepcion_iva", "percepcion_iibb1",
    "percepcion_iibb2", "total", "fecha_crawl",
]


def init_db():
    with db.get_connection() as conn:
        conn.execute(SCHEMA)
        conn.execute(SCHEMA_IMPOSITIVO)
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


def reemplazar_todo_impositivo(records: list[dict]) -> int:
    with db.get_connection() as conn:
        conn.execute("DELETE FROM detalle_impositivo_factura")
        if records:
            placeholders = ", ".join("?" for _ in COLUMNAS_IMPOSITIVO)
            sql = f"INSERT INTO detalle_impositivo_factura ({', '.join(COLUMNAS_IMPOSITIVO)}) VALUES ({placeholders})"
            conn.executemany(sql, [tuple(r.get(c) for c in COLUMNAS_IMPOSITIVO) for r in records])
        conn.commit()
    return len(records)


def facturas_a_revisar() -> list[str]:
    """Facturas de los ultimos 6 meses con monto OC/OP deducible > 0 (mismo
    recorte que modules/iibb/generate_html_report.py) -- no tiene sentido
    crawlear facturas sin ninguna linea deducible.

    Filtra explicitamente por cuenta (config.CUENTAS_DEDUCIBLES): desde que
    imputaciones_iibb tambien carga Servicio de Agencia/FEE (ver
    config.CUENTAS_A_CARGAR), un JOIN sin filtro de cuenta traeria casi
    cualquier factura con FEE, no solo las que tienen OC/OP deducible --
    esto reventaria el alcance acotado que describe el docstring del
    modulo (crawl factura por factura, pensado para un subconjunto chico)."""
    placeholders = ", ".join("?" for _ in config.CUENTAS_DEDUCIBLES)
    sql = f"""
        SELECT f.numero_referencia
        FROM facturas f
        JOIN {config.DB_TABLE} i
          ON f.tipo_asiento = i.tipo_asiento AND f.numero_asiento = i.numero_asiento
         AND f.tipo_referencia = i.tipo_referencia AND f.numero_referencia = i.numero_referencia
        WHERE f.fecha >= date('now', '-6 months')
          AND i.cuenta IN ({placeholders})
        GROUP BY f.clave_factura
        ORDER BY f.fecha DESC
    """
    with db.get_connection() as conn:
        return [r[0] for r in conn.execute(sql, config.CUENTAS_DEDUCIBLES)]


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


# Etiqueta(s) de la 2da columna de "Detalle impositivo" -> nombre interno.
# "gravado_3"/"iva_3" aceptan las dos variantes de label segun el tipo de
# factura (ver docstring del modulo): Produccion dice "Gravado 3"/"Iva 3",
# Medios dice "Gravado Otros"/"Iva Otros" -- mismo concepto.
_CAMPOS_IMPOSITIVOS = [
    ("no_gravado", ("No Gravado",)),
    ("gravado_1", ("Gravado 1",)),
    ("gravado_2", ("Gravado 2",)),
    ("gravado_3", ("Gravado 3", "Gravado Otros")),
    ("iva_1", ("Iva 1",)),
    ("iva_2", ("Iva 2",)),
    ("iva_3", ("Iva 3", "Iva Otros")),
    ("percepcion_iva", ("Percepcion Iva",)),
    ("percepcion_iibb1", ("Percepcion IIBB1",)),
    ("percepcion_iibb2", ("Percepcion IIBB2",)),
    ("total", ("Total",)),
]


def leer_detalle_impositivo(page, numero_referencia: str) -> dict | None:
    """Lee la seccion "Detalle impositivo" de la pestana "Importes" -- ver
    docstring del modulo. Devuelve None si no se encontro la pestana (en
    vez de levantar, para no tirar abajo el crawl de items por esto)."""
    if not click_boton_visible(page, "Importes"):
        return None
    esperar_postback(page)
    page.wait_for_timeout(500)

    texto = page.inner_text("body")
    inicio = texto.find("Detalle impositivo")
    if inicio == -1:
        return None
    # Cortar antes de la proxima seccion/grilla para no levantar un "Total"
    # de otra parte de la pagina por error.
    fin_candidatos = [texto.find(m, inicio) for m in ("Items Facturas", "Pautas", "Ordenes")]
    fin_candidatos = [f for f in fin_candidatos if f != -1]
    fin = min(fin_candidatos) if fin_candidatos else len(texto)
    bloque = texto[inicio:fin]

    def _buscar(etiquetas):
        for etiqueta in etiquetas:
            m = re.search(re.escape(etiqueta) + r":\s*\$?\s*([\-\d\.,]+)", bloque)
            if m:
                return normalizar_numero(m.group(1)) or 0.0
        return 0.0

    resultado = {nombre: _buscar(etiquetas) for nombre, etiquetas in _CAMPOS_IMPOSITIVOS}
    resultado["numero_referencia"] = numero_referencia
    return resultado


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


def _revisar_una(page, numero_referencia: str, ahora: str) -> tuple[list[dict] | None, dict | None, str | None]:
    """Devuelve (items, detalle_impositivo, None) si pudo leer la factura
    (aunque sea 0 items validos, o detalle_impositivo=None si no se
    encontro la pestana "Importes"), o (None, None, motivo) si fallo --
    separado de main() para poder reintentar con la misma firma en la
    segunda pasada."""
    try:
        if not ir_a_factura(page, numero_referencia):
            return None, None, "no se encontro la factura en la grilla"
        detalle_impositivo = leer_detalle_impositivo(page, numero_referencia)
        items = leer_items_factura(page, numero_referencia)
        for it in items:
            it["fecha_crawl"] = ahora
        if detalle_impositivo is not None:
            detalle_impositivo["fecha_crawl"] = ahora
        return items, detalle_impositivo, None
    except Exception as e:
        return None, None, str(e)


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
    resultados_impositivo = []
    pendientes = []
    ahora = datetime.now(timezone.utc).isoformat()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(accept_downloads=True)
        login(page)

        for i, numero_referencia in enumerate(facturas, 1):
            print(f"  [{i}/{len(facturas)}] Factura {numero_referencia}...")
            items, detalle_impositivo, motivo = _revisar_una(page, numero_referencia, ahora)
            if motivo is not None:
                print(f"    AVISO: {motivo} -- se reintenta al final")
                pendientes.append(numero_referencia)
                continue
            resultados.extend(items)
            if detalle_impositivo is not None:
                resultados_impositivo.append(detalle_impositivo)
            con_oc = sum(1 for it in items if it["numero_oc"])
            print(f"    -> {len(items)} item(s), {con_oc} con N° de OC/OP")

        # Los fallos de la primera pasada son casi siempre transitorios
        # (postback lento, grilla que todavia no termino de refrescar) --
        # confirmado en vivo 2026-08-18: 3 facturas fallaron asi en una
        # corrida y las 3 anduvieron bien al reintentarlas en la misma
        # sesion de browser. Sin este reintento quedaban "pendientes" en
        # silencio (con deducible pero sin detalle de OC/OP en el informe).
        siguen_fallando = []
        if pendientes:
            print(f"Reintentando {len(pendientes)} factura(s) que fallaron en la primera pasada...")
            for numero_referencia in pendientes:
                print(f"  [reintento] Factura {numero_referencia}...")
                items, detalle_impositivo, motivo = _revisar_una(page, numero_referencia, ahora)
                if motivo is not None:
                    print(f"    ERROR definitivo: {motivo}")
                    siguen_fallando.append(numero_referencia)
                    continue
                resultados.extend(items)
                if detalle_impositivo is not None:
                    resultados_impositivo.append(detalle_impositivo)
                con_oc = sum(1 for it in items if it["numero_oc"])
                print(f"    -> {len(items)} item(s), {con_oc} con N° de OC/OP")

        browser.close()

    cantidad = reemplazar_todo(resultados)
    cantidad_impositivo = reemplazar_todo_impositivo(resultados_impositivo)
    print(f"OK: {cantidad} items de factura guardados en items_factura_oc ({len(facturas)} facturas revisadas).")
    print(f"OK: {cantidad_impositivo} detalle(s) impositivo guardados en detalle_impositivo_factura.")
    if pendientes:
        print(f"  Reintento: {len(pendientes) - len(siguen_fallando)}/{len(pendientes)} recuperadas.")
    if siguen_fallando:
        print(f"AVISO: {len(siguen_fallando)} factura(s) siguen sin poder revisarse tras el reintento, van a quedar sin detalle de OC/OP: {', '.join(siguen_fallando)}")


if __name__ == "__main__":
    main()
