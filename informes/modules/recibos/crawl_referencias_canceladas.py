"""
Crawl de SOLO LECTURA (nunca clickea 'Editar'/'Guardar'/'Nuevo', ver
salvaguarda en CLAUDE.md): para cada Recibo Cliente de los ultimos 2 meses
(cargados por modules/recibos/ingest.py), abre el recibo individual en
Advertys y lee su pestana "Referencias Canceladas" -- el detalle de que
factura(s) de venta cancela ese recibo.

Por que hace falta esto (no alcanza con el export bulk del listado): el
export de la grilla de Recibo Cliente solo trae la cabecera (Nº Recibo,
Cliente, Cancelaciones, Estado...) -- la referencia a la(s) factura(s)
canceladas solo esta en la sub-grilla "Referencias Canceladas" de cada
recibo individual, sin export masivo posible (confirmado en vivo,
2026-08-04, igual situacion que "Items Facturas" en modules/iibb). Por eso
este script navega recibo por recibo con Playwright.

Ojo (relevado 2026-08-04): esta sub-grilla trae "TR" + "N° Referencia" pero
NO trae "TA" ni "N° Asiento" de la factura -- no alcanza para reconstruir
sola la clave compuesta completa que usa facturas.clave_factura (TA +
N° Asiento + TR + N° Referencia). Existe un caso real documentado en
modules/iibb (mismo N° Referencia usado por una factura Produccion TA=FP y
una factura Medios TA=FM a la vez) -- por eso este modulo NO arma el cruce
ac referencias_canceladas -> facturas aca mismo: lo hace
generate_html_report.py desambiguando por monto cuando hay mas de una
factura candidata (decision confirmada con Javier, 2026-08-04).

Igual que modules/iibb/crawl_oc_por_factura.py, la tabla resultante
(referencias_canceladas) se REEMPLAZA entera en cada corrida: es un
snapshot de la ventana actual, no un historico acumulado.

Ventana acortada a 2 meses (decision de Javier, 2026-08-04, bajada de los 6
meses originales): en la corrida real con 71 recibos (ventana de 6 meses)
el crawl no habia terminado despues de varios minutos -- a diferencia del
crawl de Facturas de IIBB (una sola pagina por factura), aca cada recibo
implica volver al listado, reabrir el filtro y buscar de nuevo, asi que el
costo por recibo es mas alto. Con el volumen real de recibos/mes (ver
modules/recibos/config.py, ~10-15/mes), 2 meses alcanza para el uso
operativo real ("que pago ahora") sin que el crawl se vuelva impracticable.
Si en el futuro hace falta mas historico, correrlo por tandas en vez de
agrandar la ventana de una sola corrida.

Uso:
    python -m modules.recibos.crawl_referencias_canceladas
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
CREATE TABLE IF NOT EXISTS referencias_canceladas (
    numero_recibo TEXT,
    cuenta TEXT,
    tipo_referencia TEXT,
    numero_referencia TEXT,
    fecha TEXT,
    saldo REAL,
    aplicar REAL,
    dif_cambio REAL,
    saldo_me REAL,
    cotizacion REAL,
    aplicado_me REAL,
    fecha_crawl TEXT
);
"""

COLUMNAS_TABLA = [
    "numero_recibo", "cuenta", "tipo_referencia", "numero_referencia",
    "fecha", "saldo", "aplicar", "dif_cambio", "saldo_me", "cotizacion",
    "aplicado_me", "fecha_crawl",
]


def init_db():
    with db.get_connection() as conn:
        conn.execute(SCHEMA)
        conn.commit()


def reemplazar_todo(records: list[dict]) -> int:
    with db.get_connection() as conn:
        conn.execute("DELETE FROM referencias_canceladas")
        if records:
            placeholders = ", ".join("?" for _ in COLUMNAS_TABLA)
            sql = f"INSERT INTO referencias_canceladas ({', '.join(COLUMNAS_TABLA)}) VALUES ({placeholders})"
            conn.executemany(sql, [tuple(r.get(c) for c in COLUMNAS_TABLA) for r in records])
        conn.commit()
    return len(records)


def recibos_a_revisar() -> list[str]:
    """Recibos de los ultimos 2 meses ya cargados via modules/recibos/ingest.py
    (ver docstring del modulo: ventana acortada de 6 a 2 meses por costo del
    crawl, decision de Javier 2026-08-04)."""
    sql = f"""
        SELECT numero_recibo
        FROM {config.DB_TABLE}
        WHERE fecha >= date('now', '-2 months')
        ORDER BY fecha DESC
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
        page.screenshot(path=str(SCREENSHOT_DIR / "recibos_crawl_error_login.png"))
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
        if valor.strip() in ("Mes Actual", "Abiertas", "Año Actual", "Ano Actual"):
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


def ir_a_recibo(page, numero_recibo: str) -> bool:
    base_url = URL.split("Login.aspx")[0]
    direct_url = f"{base_url}Default.aspx#ViewID=IC_ReciboCliente_ListView&ObjectClassName=DPS_SAS_SR.Module.IC_ReciboCliente"
    page.goto(direct_url, wait_until="networkidle", timeout=30000)
    esperar_postback(page)
    page.wait_for_timeout(800)

    if abrir_combo_filtro(page):
        page.wait_for_timeout(500)
        item = page.get_by_text("Todas", exact=True)
        if item.count() == 0:
            item = page.get_by_text("Todos", exact=True)
        if item.count() > 0:
            item.first.click(timeout=3000)
            esperar_postback(page)
        else:
            page.keyboard.press("Escape")
        page.wait_for_timeout(500)

    if not buscar_texto(page, numero_recibo):
        raise RuntimeError("No se encontro el buscador 'Texto a buscar...'")
    esperar_postback(page)
    page.wait_for_timeout(800)

    fila = page.get_by_text(str(numero_recibo), exact=True)
    if fila.count() == 0:
        return False
    fila.first.click(timeout=5000)
    esperar_postback(page)
    page.wait_for_timeout(800)
    return True


def leer_referencias_canceladas(page, numero_recibo: str) -> list[dict]:
    if not click_boton_visible(page, "Referencias Canceladas"):
        print(f"    AVISO: no se encontro la pestana 'Referencias Canceladas' para el recibo {numero_recibo}")
        return []
    esperar_postback(page)
    page.wait_for_timeout(600)

    filas = leer_grid_completo(page)
    items = []
    for fila in filas:
        items.append({
            "numero_recibo": numero_recibo,
            "cuenta": _col(fila, "Cuenta").strip(),
            "tipo_referencia": _col(fila, "TR").strip(),
            "numero_referencia": _col(fila, "Referencia").strip(),
            "fecha": _col(fila, "Fecha").strip(),
            "saldo": normalizar_numero(_col(fila, "Saldo")),
            "aplicar": normalizar_numero(_col(fila, "Aplicar")),
            "dif_cambio": normalizar_numero(_col(fila, "Dif.Cambio")),
            "saldo_me": normalizar_numero(_col(fila, "Saldo ME")),
            "cotizacion": normalizar_numero(_col(fila, "Cotizacion")),
            "aplicado_me": normalizar_numero(_col(fila, "Aplicado ME")),
        })
    return items


def main():
    if not URL or not USER or not PASSWORD:
        print("ERROR: completa ADVERTYS_URL, ADVERTYS_USER y ADVERTYS_PASSWORD en .env")
        sys.exit(1)

    init_db()
    recibos = recibos_a_revisar()
    if not recibos:
        print("No hay recibos en la ventana de 6 meses (o falta correr modules/recibos/ingest.py).")
        return

    print(f"Se van a revisar {len(recibos)} recibos (esto tarda varios minutos, uno a la vez)...")

    resultados = []
    ahora = datetime.now(timezone.utc).isoformat()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(accept_downloads=True)
        login(page)

        for i, numero_recibo in enumerate(recibos, 1):
            print(f"  [{i}/{len(recibos)}] Recibo {numero_recibo}...")
            try:
                if not ir_a_recibo(page, numero_recibo):
                    print(f"    AVISO: no se encontro el recibo {numero_recibo} en la grilla, salteo")
                    continue
                items = leer_referencias_canceladas(page, numero_recibo)
                for it in items:
                    it["fecha_crawl"] = ahora
                resultados.extend(items)
                print(f"    -> {len(items)} referencia(s) cancelada(s)")
            except Exception as e:
                print(f"    ERROR revisando recibo {numero_recibo}: {e}")
                continue

        browser.close()

    cantidad = reemplazar_todo(resultados)
    print(f"OK: {cantidad} referencias canceladas guardadas ({len(recibos)} recibos revisados).")


if __name__ == "__main__":
    main()
