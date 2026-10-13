"""
Crawl de SOLO LECTURA (nunca clickea 'Editar'/'Guardar'/'Nuevo', ver
salvaguarda en CLAUDE.md): para cada Orden de Compra (Produccion) u Orden
de Publicidad que aparece en el informe de Cobranza x Proveedores, abre su
ficha en Advertys y lee la sub-grilla contable donde figuran las FACTURAS
DE COMPRA imputadas a esa orden (pedido de Javier, 2026-09-30: "agregarle
la factura de compra relacionada a esa OC y la leyenda de la factura de
compra").

Por que crawl y no cruce local: el export de Compras trae la columna
"Orden Compra Generica" VACIA en todas las filas (verificado 2026-09-30,
0 de 3.398), y su "Leyenda" es texto libre sin numero de OC. El unico lugar
donde Advertys guarda el vinculo OC <-> factura de compra es la ficha de la
orden:

    OC Produccion (OrdenCompraProduccion_DetailView) -> pestana
        "Detalles contables de esta OC"
    OP Publicidad (OrdenPublicidad_DetailView)       -> pestana
        "Ordenes Compras Aplicadas" (la pestana "Facturas" viene vacia)

Ambas sub-grillas traen el mismo formato (TA, N Asiento, TR, N Referencia,
Fecha, Importe, Leyenda, Ver Referencia Compra, Importe Compra, Saldo
Compra, ...). Mezclan asientos de compra y de venta: una fila es factura de
compra cuando "Ver Referencia Compra" no esta vacio (TR = FC en Produccion;
FA/CA -- factura/nota de credito de proveedor -- en Publicidad). Se guardan
solo esas. "Importe" es la porcion imputada a ESTA orden; "Importe Compra"
es el total de la factura (una factura de Medios suele cubrir varias OP).

Numero de OP repetido entre años: el buscador del listado solo filtra por
texto, asi que si mas de una fila matchea se elige por Proveedor (mismo
criterio que oc_resolver._resolver_op) y, si sigue empatado, la de año mas
reciente.

Igual que los demas crawls (crawl_oc_por_factura.py), la tabla resultante
(facturas_compra_oc_cobranza) se REEMPLAZA entera en cada corrida.

Requiere el resto de las tablas del modulo al dia (ver docstring de
generate_html_report.py): de ahi sale la lista de OC/OP a revisar.

Uso:
    python -m modules.cobranza_proveedores.crawl_facturas_compra_por_oc
"""
import sys
import time
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright

import db
from common import normalizar_numero
from tools import crawl_comun as cc
from tools.advertys_session import AdvertysLoginError, base_url, esperar_postback, login
from . import generate_html_report as informe
from .crawl_oc_por_factura import (
    abrir_combo_filtro, buscar_texto, click_boton_visible, leer_grid_visible, tabla_visible,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SCHEMA = """
CREATE TABLE IF NOT EXISTS facturas_compra_oc_cobranza (
    numero_oc TEXT,
    oc_origen TEXT,
    proveedor_oc TEXT,
    ta TEXT,
    numero_asiento TEXT,
    tr TEXT,
    numero_referencia_compra TEXT,
    fecha TEXT,
    importe REAL,
    leyenda TEXT,
    importe_compra REAL,
    saldo_compra REAL,
    fecha_crawl TEXT
);
"""

COLUMNAS_TABLA = [
    "numero_oc", "oc_origen", "proveedor_oc", "ta", "numero_asiento", "tr",
    "numero_referencia_compra", "fecha", "importe", "leyenda", "importe_compra",
    "saldo_compra", "fecha_crawl",
]

LISTADO_PRODUCCION = "Default.aspx#ViewID=OrdenCompraProduccion_ListView&ObjectClassName=DPS_SAS_SR.Module.OrdenCompraProduccion"
LISTADO_PUBLICIDAD = "Default.aspx#ViewID=OrdenPublicidad_ListView&ObjectClassName=DPS_SAS_SR.Module.OrdenPublicidad"
PESTANA_PRODUCCION = "Detalles contables de esta OC"
PESTANA_PUBLICIDAD = "Ordenes Compras Aplicadas"


def init_db():
    with db.get_connection() as conn:
        conn.execute(SCHEMA)
        conn.commit()


def reemplazar_todo(records: list[dict]) -> int:
    with db.get_connection() as conn:
        conn.execute("DELETE FROM facturas_compra_oc_cobranza")
        if records:
            placeholders = ", ".join("?" for _ in COLUMNAS_TABLA)
            sql = f"INSERT INTO facturas_compra_oc_cobranza ({', '.join(COLUMNAS_TABLA)}) VALUES ({placeholders})"
            conn.executemany(sql, [tuple(r.get(c) for c in COLUMNAS_TABLA) for r in records])
        conn.commit()
    return len(records)


def ordenes_a_revisar():
    """(numero_oc, oc_origen, proveedor) distintos del informe de cobranza,
    en la misma ventana que usa generate_html_report."""
    recibos, referencias, facturas, items_oc, oc, op, _ = informe.cargar_datos()
    recibos_ventana, _, _ = informe._recortar_ultimos_n_meses(recibos, informe.config.VENTANA_MESES)
    tabla = informe.armar_tabla(recibos_ventana, referencias, facturas, items_oc, oc, op)
    con_oc = tabla[tabla["numero_oc"].notna()].drop_duplicates(subset=["numero_oc", "proveedor"])
    return [(str(r.numero_oc), r.oc_origen or "", r.proveedor) for r in con_oc.itertuples()]


def ir_al_listado(page, sufijo: str):
    page.goto(base_url() + sufijo, wait_until="networkidle", timeout=30000)
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


def _norm(s) -> str:
    return (s or "").strip().upper()


def _elegir_fila(filas: list[dict], proveedor: str, es_op: bool) -> int | None:
    """Indice de la fila del listado que corresponde a la orden buscada."""
    if not filas:
        return None
    if len(filas) == 1:
        return 0
    por_prov = [i for i, f in enumerate(filas) if _norm(f.get("Proveedor")) == _norm(proveedor)]
    candidatas = por_prov or list(range(len(filas)))
    if es_op:
        candidatas.sort(key=lambda i: normalizar_numero(filas[i].get("Año OP")) or 0, reverse=True)
    return candidatas[0]


def leer_facturas_compra(page, numero_oc: str, origen: str, proveedor: str, ahora: str) -> list[dict]:
    es_op = origen.startswith("Publicidad")
    ir_al_listado(page, LISTADO_PUBLICIDAD if es_op else LISTADO_PRODUCCION)
    if not buscar_texto(page, numero_oc):
        raise RuntimeError("No se encontro el buscador 'Texto a buscar...'")
    esperar_postback(page)
    page.wait_for_timeout(800)

    # El buscador matchea texto en cualquier columna: quedarse con las filas
    # cuyo numero de orden es exactamente el buscado.
    col_orden = "Orden" if es_op else "Nº O.C."
    buscado = str(normalizar_numero(numero_oc) or "")
    filas = [f for f in leer_grid_visible(page) if str(normalizar_numero(f.get(col_orden)) or "") == buscado]
    idx = _elegir_fila(filas, proveedor, es_op)
    if idx is None:
        print(f"    AVISO: no se encontro la orden {numero_oc} ({origen}), salteo")
        return []

    tabla = tabla_visible(page)
    # Si se filtro por N Orden hay que recordar la posicion real en la grilla
    todas = leer_grid_visible(page)
    pos = todas.index(filas[idx])
    tabla.locator("tr[id*='DXDataRow']").nth(pos).locator("td").nth(3).click(timeout=5000)
    esperar_postback(page)
    page.wait_for_timeout(1500)

    if not click_boton_visible(page, PESTANA_PUBLICIDAD if es_op else PESTANA_PRODUCCION):
        print(f"    AVISO: no se encontro la pestana contable de la orden {numero_oc}")
        return []
    esperar_postback(page)
    page.wait_for_timeout(1500)

    resultado = []
    for fila in leer_grid_visible(page):
        ref_compra = (fila.get("Ver Referencia Compra") or "").strip()
        if not ref_compra:
            continue  # asiento de venta u otro, no es factura de compra
        resultado.append({
            "numero_oc": numero_oc,
            "oc_origen": origen,
            "proveedor_oc": proveedor,
            "ta": fila.get("TA", "").strip(),
            "numero_asiento": fila.get("N° Asiento", "").strip(),
            "tr": fila.get("TR", "").strip(),
            "numero_referencia_compra": ref_compra,
            "fecha": fila.get("Fecha", "").strip(),
            "importe": normalizar_numero(fila.get("Importe")) or 0.0,
            "leyenda": fila.get("Leyenda", "").strip(),
            "importe_compra": normalizar_numero(fila.get("Importe Compra")) or 0.0,
            "saldo_compra": normalizar_numero(fila.get("Saldo Compra")) or 0.0,
            "fecha_crawl": ahora,
        })
    return resultado


def main_legacy():
    """Corrida vieja (--legacy): borra la tabla y recrawlea todo, de a uno.
    Se conserva tal cual por pedido de Javier (2026-10-13)."""
    init_db()
    ordenes = ordenes_a_revisar()
    if not ordenes:
        print("No hay OC/OP en el informe de cobranza (correr antes los ingest/crawls, ver docstring).")
        return
    print(f"Se van a revisar {len(ordenes)} ordenes (una a la vez)...")

    ahora = datetime.now(timezone.utc).isoformat()
    resultados: list[dict] = []
    errores = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 1000})
        try:
            login(page)
        except AdvertysLoginError as e:
            print(f"ERROR: {e}")
            sys.exit(1)

        for i, (numero_oc, origen, proveedor) in enumerate(ordenes, 1):
            print(f"  [{i}/{len(ordenes)}] {origen or 'OC'} {numero_oc} ({proveedor})...")
            # El buscador del listado a veces no aparece a tiempo (carga
            # lenta de Advertys): un reintento alcanza (verificado 2026-09-30,
            # 5 de 28 fallaban a la primera).
            for intento in (1, 2):
                try:
                    resultados.extend(leer_facturas_compra(page, numero_oc, origen, proveedor, ahora))
                    break
                except Exception as e:
                    if intento == 2:
                        errores += 1
                        print(f"    ERROR en {numero_oc}: {e}")
        browser.close()

    if errores == len(ordenes):
        print("Todas las ordenes fallaron: no se pisa la tabla existente.")
        sys.exit(1)
    n = reemplazar_todo(resultados)
    print(f"OK: {n} facturas de compra guardadas para {len({r['numero_oc'] for r in resultados})} ordenes ({errores} con error).")


# ---------------------------------------------------------------------------
# Modo incremental (default desde 2026-10-13) -- ver tools/crawl_comun.py
#
# Para OC/OP la fecha de la orden NO congela (una orden vieja puede recibir una
# factura de compra nueva): manda la firma de cabecera -- estado, saldo,
# facturado/comprado/cobrado/pagado, que ya trae el export de cada tabla y se
# actualiza antes de esta cadena. Si Advertys no reflejara una factura de
# compra nueva en esas columnas, `--completo` es la red de seguridad.
# ---------------------------------------------------------------------------
MODULO_CACHE = "facturas_compra_oc_cobranza"
# Clave compuesta de la tabla de resultados (misma que arma `clave_orden`).
EXPR_CLAVE = "numero_oc || '|' || COALESCE(oc_origen, '') || '|' || COALESCE(proveedor_oc, '')"


def clave_orden(numero_oc, origen, proveedor) -> str:
    return f"{numero_oc}|{origen or ''}|{proveedor or ''}"


def _firmas_cabecera() -> tuple[dict, dict]:
    """(por_numero_oc_produccion, por_numero_oc_publicidad -> lista de
    (proveedor, tupla de campos)) desde las tablas ya ingeridas."""
    prod, pub = {}, {}
    with db.get_connection() as conn:
        for r in conn.execute("SELECT numero_oc, estado, saldo, importe_sin_iva, facturado, comprado, cobrado, pagado, ajustado FROM ordenes_compra_produccion"):
            prod[str(r["numero_oc"])] = tuple(r)[1:]
        for r in conn.execute("SELECT numero_oc, proveedor, ano_op, estado, saldo, importe_sin_iva, facturado, comprado, cobrado, pagado, ajustado FROM ordenes_publicidad"):
            pub.setdefault(str(r["numero_oc"]), []).append((r["proveedor"], tuple(r)[2:]))
    return prod, pub


def candidatos_ordenes() -> list[cc.Candidato]:
    prod, pub = _firmas_cabecera()
    out = []
    for numero_oc, origen, proveedor in ordenes_a_revisar():
        if origen.startswith("Publicidad"):
            filas = pub.get(str(numero_oc), [])
            propias = [f for p, f in filas if _norm(p) == _norm(proveedor)] or [f for _, f in filas]
            f_ = cc.firma(*sorted(str(x) for x in propias)) if propias else ""
        else:
            f_ = cc.firma(*prod[str(numero_oc)]) if str(numero_oc) in prod else ""
        out.append(cc.Candidato(clave_orden(numero_oc, origen, proveedor), f_, None))
    return out


def procesar_orden(page, cand: cc.Candidato) -> list[dict]:
    numero_oc, origen, proveedor = cand.clave.split("|", 2)
    es_op = origen.startswith("Publicidad")
    lst = cc.listado_de(page, LISTADO_PUBLICIDAD if es_op else LISTADO_PRODUCCION)
    lst.asegurar()
    lst.buscar(numero_oc)

    # El buscador matchea texto en cualquier columna: quedarse con las filas
    # cuyo numero de orden es exactamente el buscado (igual que el modo legacy).
    col_orden = "Orden" if es_op else "Nº O.C."
    todas = leer_grid_visible(page)
    buscado = str(normalizar_numero(numero_oc) or "")
    filas = [f for f in todas if str(normalizar_numero(f.get(col_orden)) or "") == buscado]
    idx = _elegir_fila(filas, proveedor, es_op)
    if idx is None:
        # None = "no se pudo ver la orden": NO se cachea ni pisa lo guardado
        # (con 3 workers 34 ordenes dieron este falso negativo y quedaron
        # cacheadas como vacias, 2026-10-13).
        print(f"    AVISO: no se encontro la orden {numero_oc} ({origen}), salteo")
        return None
    pos = todas.index(filas[idx])
    tabla = cc.tabla_visible(page)
    tabla.locator("tr[id*='DXDataRow']").nth(pos).locator("td").nth(3).click(timeout=5000)
    lst.en_registro = True

    pestana = PESTANA_PUBLICIDAD if es_op else PESTANA_PRODUCCION
    if not cc.esperar_texto(page, pestana, timeout=15000):
        raise RuntimeError(f"orden {numero_oc}: no aparecio la pestana '{pestana}'")
    cc.click_texto(page, pestana)
    cc.esperar_postback_rapido(page)
    cc.esperar_filas(page, timeout=4000)

    ahora = datetime.now(timezone.utc).isoformat()
    resultado = []
    for fila in leer_grid_visible(page):
        ref_compra = (fila.get("Ver Referencia Compra") or "").strip()
        if not ref_compra:
            continue  # asiento de venta u otro, no es factura de compra
        resultado.append({
            "numero_oc": numero_oc,
            "oc_origen": origen,
            "proveedor_oc": proveedor,
            "ta": fila.get("TA", "").strip(),
            "numero_asiento": fila.get("N° Asiento", "").strip(),
            "tr": fila.get("TR", "").strip(),
            "numero_referencia_compra": ref_compra,
            "fecha": fila.get("Fecha", "").strip(),
            "importe": normalizar_numero(fila.get("Importe")) or 0.0,
            "leyenda": fila.get("Leyenda", "").strip(),
            "importe_compra": normalizar_numero(fila.get("Importe Compra")) or 0.0,
            "saldo_compra": normalizar_numero(fila.get("Saldo Compra")) or 0.0,
            "fecha_crawl": ahora,
        })
    return resultado


def main(argv=None):
    args = cc.parsear_args("Facturas de compra de cada OC/OP (solo lectura).", argv)
    if args.legacy:
        return main_legacy()

    t0 = time.time()
    init_db()
    candidatos = candidatos_ordenes()
    if not candidatos:
        print("No hay OC/OP en el informe de cobranza (correr antes los ingest/crawls, ver docstring).")
        return

    cache = cc.CrawlCache(MODULO_CACHE)
    sembrados = cc.sembrar_si_vacia(
        cache, "facturas_compra_oc_cobranza", EXPR_CLAVE,
        {c.clave: c.firma for c in candidatos}, {})
    if sembrados:
        print(f"Cache vacia: sembrada con {sembrados} ordenes de la corrida anterior.")

    pol = cc.Politica(congelar_mes_cerrado=False)
    a_visitar, saltados, motivos = cc.seleccionar(candidatos, cache, pol, completo=args.completo)
    print(f"{len(candidatos)} ordenes: {len(a_visitar)} a revisar, {len(saltados)} salteadas por cache. Motivos: {motivos}")

    registros, ok_claves, errores, no_encontradas = [], [], 0, 0
    ahora = datetime.now(timezone.utc).isoformat()
    if a_visitar:
        resultados = cc.correr_en_paralelo(a_visitar, procesar_orden, args.workers, etiqueta=lambda c: f"Orden {c.clave}")
        for r in resultados:
            if r.error:
                errores += 1
                continue
            if r.valor is None:  # orden no encontrada en el listado: no se cachea
                no_encontradas += 1
                continue
            registros.extend(r.valor)
            ok_claves.append(r.item.clave)
            cache.guardar(r.item.clave, r.item.firma, None, len(r.valor), len(r.valor), fecha_crawl=ahora)
        if errores == len(a_visitar):
            print("Todas las ordenes fallaron: no se pisa la tabla existente.")
            sys.exit(1)

    vigentes = [c.clave for c in candidatos]
    total = cc.reemplazar_por_clave("facturas_compra_oc_cobranza", EXPR_CLAVE, COLUMNAS_TABLA, registros, ok_claves, vigentes)
    cache.olvidar_fuera_de(vigentes)
    print(f"OK: {total} facturas de compra en la tabla ({len(ok_claves)} ordenes revisadas, "
          f"{len(saltados)} desde cache, {errores} con error, {no_encontradas} no encontradas) en {time.time() - t0:.0f}s.")


if __name__ == "__main__":
    main()
