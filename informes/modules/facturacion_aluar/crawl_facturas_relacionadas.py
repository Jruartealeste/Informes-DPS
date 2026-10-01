"""
Crawl de SOLO LECTURA (nunca clickea 'Editar'/'Guardar'/'Nuevo', ver
salvaguarda en CLAUDE.md): para cada documento de cancelacion (TR='CA')
que aparece en Imputaciones dentro de las cuentas de ingreso de ALUAR, abre
esa factura en Advertys y lee el campo "Factura Relacionada" -- el N° de
Referencia de la factura ORIGINAL que esa cancelacion revierte.

Por que hace falta esto (ver docstring largo de config.py): sumar
Imputaciones con signo ya neta la mayoria de los pares
factura-cancelacion automaticamente, pero cuando Advertys cancela una
factura y la reemplaza por otra en un MES DISTINTO, hay que excluir tanto
la cancelacion como la factura original para no duplicar el monto (una
vez en el mes viejo, otra en el nuevo con el reemplazo). El unico lugar
donde vive esa relacion factura-cancelacion es el campo "Factura
Relacionada" del detalle de cada factura -- no sale de ningun export bulk
(confirmado en vivo 2026-09-28, ver modules/facturacion_aluar/explore.py).

Acotado: solo se crawlean documentos TR='CA' de ALUAR (15 en toda la
historia relevada 2026-09-28), no las 1000+ facturas del sistema -- tarda
menos de un minuto por factura, un puñado de facturas en total.

Igual que los demas crawls de este proyecto (crawl_oc_por_factura.py,
crawl_referencias_canceladas.py), la tabla resultante se REEMPLAZA entera
en cada corrida: es un snapshot de la relacion actual, no un historico.

Requiere `facturas` al dia y un export crudo reciente de Imputaciones
(`python -m modules.iibb.export`) -- ver modules/facturacion_aluar/imputaciones.py.

Uso:
    python -m modules.facturacion_aluar.crawl_facturas_relacionadas
"""
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

import db
from tools.advertys_session import AdvertysLoginError, base_url, esperar_postback, login
from . import config
from .imputaciones import documentos_cancelacion_aluar

SCREENSHOT_DIR = Path("exploracion") / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS {config.DB_TABLE_RELACIONADAS} (
    clave TEXT,
    tipo_asiento TEXT,
    numero_referencia TEXT,
    factura_relacionada TEXT,
    fecha_crawl TEXT
);
"""

COLUMNAS = ["clave", "tipo_asiento", "numero_referencia", "factura_relacionada", "fecha_crawl"]

_RE_FACTURA_RELACIONADA = re.compile(r"Factura [Rr]elacionada:\s*\n?\s*([^\n]+)")


def init_db():
    with db.get_connection() as conn:
        conn.execute(SCHEMA)
        conn.commit()


def reemplazar_todo(records: list[dict]) -> int:
    with db.get_connection() as conn:
        conn.execute(f"DELETE FROM {config.DB_TABLE_RELACIONADAS}")
        if records:
            placeholders = ", ".join("?" for _ in COLUMNAS)
            sql = f"INSERT INTO {config.DB_TABLE_RELACIONADAS} ({', '.join(COLUMNAS)}) VALUES ({placeholders})"
            conn.executemany(sql, [tuple(r.get(c) for c in COLUMNAS) for r in records])
        conn.commit()
    return len(records)


def ir_a_factura(page, numero_referencia: str) -> bool:
    """Busca por N° Referencia en la vista unica "Facturas" (Consultas >
    Facturacion), que trae Produccion (FP/DPS_Factura) y Medios
    (FM/FacturasMedios) mezcladas en la misma grilla -- alcanza con esta
    URL para ambos tipos, solo el detalle que abre despues difiere de
    layout (ver config.py)."""
    direct_url = f"{base_url()}Default.aspx#ViewID=DPS_Factura_ListView&ObjectClassName=DPS_SAS_SR.Module.DPS_Factura"
    page.goto(direct_url, wait_until="networkidle", timeout=30000)
    esperar_postback(page)
    page.wait_for_timeout(800)

    inputs = page.locator("input[id$='_Cb_I']")
    for i in range(inputs.count()):
        inp = inputs.nth(i)
        try:
            valor = inp.input_value(timeout=500)
        except Exception:
            continue
        if valor.strip() == "Mes Actual":
            btn_id = inp.get_attribute("id").replace("_Cb_I", "_Cb_B-1")
            page.locator(f"#{btn_id}").click(timeout=3000)
            page.wait_for_timeout(500)
            item = page.get_by_text("Todos", exact=True)
            if item.count() > 0:
                item.first.click(timeout=3000)
                esperar_postback(page)
            break

    search_inputs = page.locator("input[id$='_Ed_I']")
    encontrado = False
    for i in range(search_inputs.count()):
        inp = search_inputs.nth(i)
        try:
            valor = inp.input_value(timeout=500)
        except Exception:
            continue
        if valor.strip() == "Texto a buscar...":
            inp.click()
            inp.fill(str(numero_referencia))
            inp.press("Enter")
            encontrado = True
            break
    if not encontrado:
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


def leer_factura_relacionada(page) -> str | None:
    """Vive en la pestaña "Datos Generales", que es la que abre por
    default -- no hace falta clickear nada mas. Devuelve None si el campo
    dice "N / D" (factura original, sin relacion) o no se encontro."""
    texto = page.inner_text("body")
    m = _RE_FACTURA_RELACIONADA.search(texto)
    if not m:
        return None
    valor = m.group(1).strip()
    if valor.upper().replace(" ", "") in ("N/D", ""):
        return None
    return valor


def main():
    init_db()
    documentos = documentos_cancelacion_aluar()
    if not documentos:
        print("No hay documentos de cancelacion (TR='CA') para ALUAR. Nada para crawlear.")
        print(f"OK: 0 relaciones guardadas en {config.DB_TABLE_RELACIONADAS}.")
        reemplazar_todo([])
        return

    print(f"Se van a revisar {len(documentos)} documento(s) de cancelacion de ALUAR...")

    resultados = []
    sin_resolver = []
    ahora = datetime.now(timezone.utc).isoformat()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(accept_downloads=True)
        try:
            login(page)
        except AdvertysLoginError as e:
            print(f"ERROR: {e}")
            sys.exit(1)

        for i, (clave, tipo_asiento, numero_referencia) in enumerate(documentos, 1):
            print(f"  [{i}/{len(documentos)}] {clave}...")
            try:
                if not ir_a_factura(page, numero_referencia):
                    print("    AVISO: no se encontro la factura en la grilla")
                    sin_resolver.append(clave)
                    continue
                relacionada = leer_factura_relacionada(page)
                if relacionada is None:
                    print("    AVISO: no se pudo leer 'Factura Relacionada' (o vino 'N/D')")
                    sin_resolver.append(clave)
                    continue
                print(f"    -> Factura Relacionada: {relacionada}")
                resultados.append({
                    "clave": clave,
                    "tipo_asiento": tipo_asiento,
                    "numero_referencia": numero_referencia,
                    "factura_relacionada": relacionada,
                    "fecha_crawl": ahora,
                })
            except Exception as e:
                print(f"    ERROR: {e}")
                sin_resolver.append(clave)

        browser.close()

    cantidad = reemplazar_todo(resultados)
    print(f"OK: {cantidad} relacion(es) guardadas en {config.DB_TABLE_RELACIONADAS}.")
    if sin_resolver:
        print(
            f"AVISO: {len(sin_resolver)} documento(s) de cancelacion quedaron sin resolver "
            f"({', '.join(sin_resolver)}) -- ingest.py va a excluir solo la cancelacion en "
            "esos casos (sin poder excluir tambien la factura original), lo que puede dejar "
            "un pequeño remanente si esa factura se reemitio en otro mes."
        )


if __name__ == "__main__":
    main()
