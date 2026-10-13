"""Tests de la logica pura de tools/crawl_comun.py (sin Advertys ni Playwright).
Correr: python -m tests.test_crawl_comun  (o pytest)"""
import os
import tempfile
from datetime import date

import db
from tools import crawl_comun as cc

HOY = date(2026, 10, 13)


def test_mes_cerrado():
    # septiembre cierra el 20/10: el 13/10 todavia esta abierto
    assert not cc.mes_cerrado("2026-09-15", HOY)
    assert cc.mes_cerrado("2026-09-15", date(2026, 10, 21))
    assert not cc.mes_cerrado("2026-09-15", date(2026, 10, 20))  # el 20 aun abierto
    assert cc.mes_cerrado("2026-08-31", HOY)                    # agosto ya cerro
    assert not cc.mes_cerrado("2026-10-01", HOY)
    assert cc.mes_cerrado("2025-12-31", date(2026, 1, 21))      # cruce de anio
    assert not cc.mes_cerrado("2025-12-31", date(2026, 1, 20))
    assert not cc.mes_cerrado(None, HOY) and not cc.mes_cerrado("", HOY)


def test_firma():
    assert cc.firma("a", 1.0, None) == cc.firma("a", 1.0, "")
    assert cc.firma(10.001) == cc.firma(10.0)
    assert cc.firma("a", "b") != cc.firma("ab", "")


def _e(firma="f", n_filas=1, n_ok=1):
    return cc.EntradaCache(firma, None, None, n_filas, n_ok)


def test_decidir():
    pol = cc.Politica(congelar_mes_cerrado=True, dias_recientes=7, reintentar_sin_ok=True)
    c = lambda fecha, f="f": cc.Candidato("k", f, fecha)
    assert cc.decidir(c("2026-10-01"), None, pol, HOY) == (True, "nuevo")
    assert cc.decidir(c("2026-10-01"), _e(), pol, HOY, completo=True) == (True, "completo")
    # mes cerrado y cacheado: congelado aunque la firma cambie
    assert cc.decidir(c("2026-08-10", "otra"), _e(), pol, HOY) == (False, "mes cerrado")
    # mes cerrado pero NO cacheado: se crawlea
    assert cc.decidir(c("2026-08-10"), None, pol, HOY)[0]
    # reciente
    assert cc.decidir(c("2026-10-10"), _e(), pol, HOY) == (True, "reciente")
    # abierto, no reciente (septiembre), firma igual -> vigente; distinta -> recrawl
    assert cc.decidir(c("2026-09-02"), _e(), pol, HOY) == (False, "vigente")
    assert cc.decidir(c("2026-09-02", "otra"), _e(), pol, HOY) == (True, "firma cambio")
    # sin resultado util
    assert cc.decidir(c("2026-09-02"), _e(n_ok=0), pol, HOY) == (True, "sin resultado util")
    # ordenes: no congelan por fecha
    pol_oc = cc.Politica(congelar_mes_cerrado=False, reintentar_sin_ok=True)
    assert cc.decidir(c("2026-03-01"), _e(), pol_oc, HOY) == (False, "vigente")
    assert cc.decidir(c("2026-03-01", "otra"), _e(), pol_oc, HOY) == (True, "firma cambio")


def test_cache_y_reemplazo():
    d = tempfile.mkdtemp()
    old = db.DB_PATH
    db.DB_PATH = os.path.join(d, "t.db")
    try:
        with db.get_connection() as conn:
            conn.execute("CREATE TABLE res (k TEXT, v INTEGER)")
            conn.executemany("INSERT INTO res VALUES (?, ?)", [("a", 1), ("b", 2), ("viejo", 9)])
            conn.commit()
        cache = cc.CrawlCache("t")
        cache.guardar("a", "f1", "2026-08-01", 1, 1)
        cache.guardar("viejo", "f", "2026-01-01", 1, 1)
        cache.guardar("cero", "f", "2026-09-05", 0, 0)
        pol = cc.Politica(dias_recientes=7)
        cands = [cc.Candidato("a", "f1", "2026-08-01"), cc.Candidato("cero", "f", "2026-09-05"),
                 cc.Candidato("nueva", "f", "2026-10-12")]
        visitar, saltados, motivos = cc.seleccionar(cands, cache, pol, HOY)
        assert [c.clave for c in visitar] == ["nueva"] and len(saltados) == 2, motivos
        # upsert por clave: recrawlea 'b' y limpia 'viejo' (fuera de ventana)
        total = cc.reemplazar_por_clave("res", "k", ["k", "v"], [{"k": "b", "v": 20}], ["b"], ["a", "b"])
        with db.get_connection() as conn:
            assert sorted(tuple(r) for r in conn.execute("SELECT k, v FROM res")) == [("a", 1), ("b", 20)]
        assert total == 2
        assert cache.olvidar_fuera_de(["a", "cero"]) == 1  # 'viejo'
    finally:
        db.DB_PATH = old


if __name__ == "__main__":
    for nombre, fn in list(globals().items()):
        if nombre.startswith("test_"):
            fn()
            print("OK", nombre)
