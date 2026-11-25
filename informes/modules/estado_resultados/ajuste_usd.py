"""
Ajuste de cotizacion de las compras en dolares (USD).

Contexto (Javier, 2026-11-25): las compras con moneda USD se cargan en
Advertys con una cotizacion que el pone a mano, y esa cotizacion NO es la
del dia de la factura. El libro queda entonces con pesos = USD x cotizacion
cargada. Este modulo recalcula esas compras con el dolar BNA oficial
COMPRADOR de la fecha de la factura y devuelve la diferencia, para
mostrarla como una linea aparte en el EERR (no se pisa el libro).

Fuentes:
- compras (advertys.db, modules/compras): las filas con moneda 'Dolar EEUU'
  (importe_sin_iva en USD, fecha_factura, proveedor). Solo estados que
  llegan al libro: Contabilizado / Reactivado.
- Imputaciones (exploracion/iibb_export.xlsx, modules/iibb/export.py): trae
  la 'Cotizacion' que se cargo en el asiento. Es la unica fuente de ese
  dato (el export de Compras no lo trae). Cruce por (TA, Asiento, N°
  Referencia), normalizados a entero porque Compras los guarda como texto
  con ceros a la izquierda ('030006') e Imputaciones como numero.
- Dolar BNA oficial comprador historico: api.argentinadatos.com
  (el mismo proyecto que dolarapi.com, que solo expone el valor del dia).
  Se cachea en exploracion/bna_oficial_comprador.json para trabajar sin
  conexion. Fines de semana/feriados usan el ultimo dia habil anterior.

Signo: ajuste = USD x (cotizacion cargada - BNA comprador). Positivo = el
costo real es menor que el cargado (mejora el resultado); negativo = el
costo real es mayor.
"""
import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd

import db

API_HISTORICO = "https://api.argentinadatos.com/v1/cotizaciones/dolares/oficial"
CACHE = Path("exploracion/bna_oficial_comprador.json")
IMPUTACIONES_XLSX = Path("exploracion/iibb_export.xlsx")
ESTADOS_EN_LIBRO = ("Contabilizado", "Reactivado")


def ajuste(usd: float, tc_cargado: float, tc_bna: float) -> float:
    """Diferencia en pesos entre lo cargado y lo que correspondia (ver docstring)."""
    return usd * (tc_cargado - tc_bna)


def cargar_cotizaciones(refrescar: bool = True) -> dict:
    """{'YYYY-MM-DD': compra} del dolar oficial BNA. Si la API falla usa el cache."""
    if refrescar:
        try:
            # La API rechaza (403) el User-Agent por defecto de urllib.
            req = Request(API_HISTORICO, headers={"User-Agent": "estado-resultados-informes/1.0"})
            with urlopen(req, timeout=20) as r:
                datos = json.loads(r.read().decode("utf-8"))
            cot = {d["fecha"]: float(d["compra"]) for d in datos if d.get("compra") is not None}
            CACHE.parent.mkdir(exist_ok=True)
            CACHE.write_text(json.dumps(cot), encoding="utf-8")
            return cot
        except Exception as e:  # sin red / API caida
            print(f"AVISO: no se pudo consultar la API del dolar ({e}); se usa el cache local.")
    if not CACHE.exists():
        raise RuntimeError("Sin API del dolar y sin cache local: no se puede calcular el ajuste USD.")
    return json.loads(CACHE.read_text(encoding="utf-8"))


def tc_comprador(fecha: str, cot: dict, max_dias_atras: int = 7):
    """(cotizacion, fecha_usada): el valor del dia o el del ultimo dia habil anterior."""
    d = date.fromisoformat(fecha)
    for i in range(max_dias_atras + 1):
        k = (d - timedelta(days=i)).isoformat()
        if k in cot:
            return cot[k], k
    raise KeyError(f"Sin cotizacion BNA para {fecha} (ni en los {max_dias_atras} dias anteriores)")


def _clave(ta, asiento, ref):
    try:
        return (str(ta).strip(), int(float(asiento)), int(float(ref)))
    except (TypeError, ValueError):
        return None


def compras_usd(anio: int) -> pd.DataFrame:
    with db.get_connection() as conn:
        df = pd.read_sql_query(
            "SELECT proveedor, tipo_asiento, numero_asiento, numero_referencia, fecha_factura, "
            "importe_sin_iva_signado AS usd, estado, leyenda FROM compras "
            "WHERE moneda LIKE 'Dolar%' AND fecha_factura >= ? AND fecha_factura <= ?",
            conn, params=(f"{anio}-01-01", f"{anio}-12-31"),
        )
    return df[df["estado"].isin(ESTADOS_EN_LIBRO)].reset_index(drop=True)


def cotizaciones_cargadas(path: Path = IMPUTACIONES_XLSX) -> dict:
    """{(TA, asiento, ref): cotizacion} de las lineas de Imputaciones en dolares."""
    imp = pd.read_excel(path)
    ref_col = next(c for c in imp.columns if "Referencia" in c)
    imp = imp[imp["Moneda"].astype(str).str.startswith("Dolar")]
    out = {}
    for r in imp.itertuples(index=False):
        k = _clave(getattr(r, "TA"), getattr(r, "Asiento"), r[list(imp.columns).index(ref_col)])
        if k and k not in out:
            out[k] = float(getattr(r, "Cotizacion"))
    return out


def calcular_ajustes(anio: int, cot_bna: dict | None = None, imputaciones_path: Path = IMPUTACIONES_XLSX) -> dict:
    """Devuelve {'items': [...], 'sin_cotizacion': [...]}: un item por compra USD con
    mes, proveedor, referencia, usd, tc_cargado, tc_bna, fecha_bna y ajuste (pesos)."""
    compras = compras_usd(anio)
    if compras.empty:
        return {"items": [], "sin_cotizacion": []}
    cot_bna = cot_bna if cot_bna is not None else cargar_cotizaciones()
    cargadas = cotizaciones_cargadas(imputaciones_path)
    items, sin_cot = [], []
    for r in compras.itertuples(index=False):
        k = _clave(r.tipo_asiento, r.numero_asiento, r.numero_referencia)
        tc_cargado = cargadas.get(k)
        if tc_cargado is None:
            sin_cot.append(f"{r.proveedor} {r.numero_referencia}: no se encontro la cotizacion cargada en Imputaciones")
            continue
        tc_bna, fecha_bna = tc_comprador(r.fecha_factura, cot_bna)
        items.append({
            "mes": int(r.fecha_factura[5:7]), "fecha": r.fecha_factura, "proveedor": r.proveedor,
            "referencia": str(r.numero_referencia), "usd": float(r.usd),
            "tc_cargado": tc_cargado, "tc_bna": tc_bna, "fecha_bna": fecha_bna,
            "ajuste": ajuste(float(r.usd), tc_cargado, tc_bna),
        })
    return {"items": items, "sin_cotizacion": sin_cot}
