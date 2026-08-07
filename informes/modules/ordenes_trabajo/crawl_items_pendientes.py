"""
Crawl de SOLO LECTURA (nunca clickea 'Editar'/'Guardar', ver salvaguarda en
CLAUDE.md): recorre, para cada OT **abierta**, los Estimados de Costo que
todavia estan en un estado NO terminal (Provisorio, Definitivo, Autorizado
AFacturar -- ver ESTIMADO_ESTADOS_TERMINALES en
modules/pendientes/generate_html_report.py) y lee su pestana "Items del
Estimado" item por item.

Por que existe este script (no alcanza con modules/oc_pendientes_generar):
la vista propia de Advertys "OCs Pendientes de Generar" solo muestra casos
en un estado YA avanzado -- confirmado con Javier (2026-07-21) e
inspeccionando en vivo el Estimado 472 / OT 272 (estado "Provisorio"): un
item de rubro "SERVICIOS/PRODUCTOS DE TERCEROS" con Costo real de
$2.400.000, sin Proveedor ni O.C. cargados, que NO aparece en esa vista
del sistema (que ese dia tenia solo 4 filas en total). Javier pidio
detectarlo bien mas temprano: desde el momento en que a un item se le
asigna un Proveedor (o incluso antes, si ya es un item tercerizado con
costo real).

Este script marca dos señales por item:
  - "sin_oc": tiene Proveedor cargado pero el campo N° O.C. esta vacio --
    la señal que Javier pidio explicitamente.
  - "sin_proveedor": es de rubro tercerizado (Rubro Produccion contiene
    "TERCEROS") con Costo > 0 pero el Proveedor todavia esta vacio -- una
    señal mas temprana encontrada durante el relevamiento (ver Estimado
    472 arriba), tambien indica que mas adelante va a hacer falta una O.C.

A diferencia de los ingest.py de este proyecto (que parsean un Excel
exportado), aca no hay bulk export posible: Advertys no tiene una vista de
lista para "Items del Estimado" de TODOS los estimados a la vez, solo se
ve abriendo cada estimado. Por eso este script navega estimado por
estimado con Playwright reusando una sola sesion de login (mas lento que
un ingest de Excel -- pensar unos minutos para correrlo, no segundos --
pero acotado: solo recorre estimados NO terminales de OT abiertas, no los
506 estimados del sistema).

Igual que modules/oc_pendientes_generar, la tabla resultante
(items_pendientes_oc) se REEMPLAZA entera en cada corrida: es un snapshot
de "que esta pendiente ahora mismo".

Uso:
    python -m modules.ordenes_trabajo.crawl_items_pendientes
"""
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

import db
from common import normalizar_numero
from modules.pendientes.generate_html_report import ESTIMADO_ESTADOS_TERMINALES
from .cerrar_ot import (
    URL, USER, PASSWORD,
    login, ir_a_ot, click_boton_visible, esperar_postback, leer_grid_visible, _col,
)

load_dotenv()

SCHEMA = """
CREATE TABLE IF NOT EXISTS items_pendientes_oc (
    numero_ot TEXT,
    numero_estimado TEXT,
    estado_estimado TEXT,
    item_nro TEXT,
    titulo TEXT,
    detalle TEXT,
    rubro_produccion TEXT,
    costo REAL,
    proveedor TEXT,
    numero_oc TEXT,
    motivo TEXT,
    fecha_crawl TEXT
);
"""

COLUMNAS_TABLA = [
    "numero_ot", "numero_estimado", "estado_estimado", "item_nro", "titulo",
    "detalle", "rubro_produccion", "costo", "proveedor", "numero_oc",
    "motivo", "fecha_crawl",
]


def init_db():
    with db.get_connection() as conn:
        conn.execute(SCHEMA)
        conn.commit()


def reemplazar_todo(records: list[dict]) -> int:
    """Vacia la tabla y carga los registros del crawl actual (mismo motivo
    que modules/oc_pendientes_generar: es un snapshot, no un historico)."""
    with db.get_connection() as conn:
        conn.execute("DELETE FROM items_pendientes_oc")
        if records:
            placeholders = ", ".join("?" for _ in COLUMNAS_TABLA)
            sql = f"INSERT INTO items_pendientes_oc ({', '.join(COLUMNAS_TABLA)}) VALUES ({placeholders})"
            conn.executemany(sql, [tuple(r.get(c) for c in COLUMNAS_TABLA) for r in records])
        conn.commit()
    return len(records)


def estimados_a_revisar() -> list[dict]:
    """OT abiertas + sus estimados que todavia NO estan en un estado
    terminal -- son los unicos candidatos a tener un item pendiente (un
    estimado terminal ya paso el chequeo de Advertys para llegar ahi)."""
    placeholders = ", ".join("?" for _ in ESTIMADO_ESTADOS_TERMINALES)
    sql = f"""
        SELECT e.numero_ot, e.numero_estimado, e.estado
        FROM estimados_costos e
        JOIN ordenes_trabajo o ON o.numero_ot = e.numero_ot
        WHERE o.estado = 'Abierta' AND e.estado NOT IN ({placeholders})
        ORDER BY e.numero_ot, e.numero_estimado
    """
    with db.get_connection() as conn:
        cur = conn.execute(sql, list(ESTIMADO_ESTADOS_TERMINALES))
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def revisar_items_estimado(page, fila_items: list[dict], numero_ot: str, numero_estimado: str, estado_estimado: str) -> list[dict]:
    encontrados = []
    for item in fila_items:
        proveedor = _col(item, "Proveedor").strip()
        numero_oc = _col(item, "O.C.").strip()
        rubro = _col(item, "Rubro Produccion").strip()
        costo_txt = _col(item, "Costo U.")
        costo = normalizar_numero(costo_txt) or 0.0
        item_nro = _col(item, "Nro").strip()
        titulo = _col(item, "Titulo").strip()
        detalle = _col(item, "Detalle").strip()

        motivo = None
        if proveedor and not numero_oc:
            motivo = "sin_oc"
        elif not proveedor and "TERCEROS" in rubro.upper() and costo > 0:
            motivo = "sin_proveedor"

        if motivo:
            encontrados.append({
                "numero_ot": numero_ot,
                "numero_estimado": numero_estimado,
                "estado_estimado": estado_estimado,
                "item_nro": item_nro,
                "titulo": titulo,
                "detalle": detalle,
                "rubro_produccion": rubro,
                "costo": costo,
                "proveedor": proveedor,
                "numero_oc": numero_oc,
                "motivo": motivo,
            })
    return encontrados


def main():
    if not URL or not USER or not PASSWORD:
        print("ERROR: completa ADVERTYS_URL, ADVERTYS_USER y ADVERTYS_PASSWORD en .env")
        sys.exit(1)

    init_db()
    candidatos = estimados_a_revisar()
    if not candidatos:
        print("No hay estimados no-terminales en OT abiertas para revisar (o no corriste los ingest de ordenes_trabajo/estimados_costos todavia).")
        return

    print(f"Se van a revisar {len(candidatos)} estimados no-terminales (esto tarda unos minutos, un estimado a la vez)...")

    resultados = []
    ahora = datetime.now(timezone.utc).isoformat()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(accept_downloads=True)
        login(page)

        ot_actual = None
        for i, c in enumerate(candidatos, 1):
            numero_ot, numero_estimado, estado_estimado = c["numero_ot"], c["numero_estimado"], c["estado"]
            print(f"  [{i}/{len(candidatos)}] OT {numero_ot} / Estimado {numero_estimado} ({estado_estimado})...")
            try:
                if numero_ot != ot_actual:
                    ir_a_ot(page, numero_ot)
                    if not click_boton_visible(page, "Estimados Costo"):
                        print(f"    AVISO: no se encontro la pestana 'Estimados Costo' en OT {numero_ot}, salteo sus estimados")
                        ot_actual = numero_ot
                        continue
                    esperar_postback(page)
                    page.wait_for_timeout(600)
                    ot_actual = numero_ot

                fila_est = page.get_by_text(str(numero_estimado), exact=True)
                if fila_est.count() == 0:
                    print(f"    AVISO: no se encontro el estimado {numero_estimado} en la grilla, salteo")
                    continue
                fila_est.first.click(timeout=5000)
                esperar_postback(page)
                page.wait_for_timeout(600)

                if not click_boton_visible(page, "Items del Estimado"):
                    print(f"    AVISO: no se encontro la pestana 'Items del Estimado', salteo")
                    continue
                esperar_postback(page)
                page.wait_for_timeout(500)

                items = leer_grid_visible(page)
                encontrados = revisar_items_estimado(page, items, numero_ot, numero_estimado, estado_estimado)
                for e in encontrados:
                    e["fecha_crawl"] = ahora
                resultados.extend(encontrados)
                if encontrados:
                    print(f"    -> {len(encontrados)} item(s) pendiente(s)")

                # Volver a la grilla de Estimados Costo antes del siguiente,
                # sin volver a navegar por la OT si es la misma.
                if not click_boton_visible(page, "Estimados Costo"):
                    ot_actual = None
                else:
                    esperar_postback(page)
                    page.wait_for_timeout(400)
            except Exception as e:
                print(f"    ERROR revisando OT {numero_ot} / Estimado {numero_estimado}: {e}")
                ot_actual = None
                continue

        browser.close()

    cantidad = reemplazar_todo(resultados)
    print(f"OK: {cantidad} items pendientes detectados y guardados en items_pendientes_oc.")


if __name__ == "__main__":
    main()
