"""
Resolucion compartida de N Orden Compra/Publicidad a Proveedor + Monto sin
IVA real, a partir del numero_oc + texto crudo ("<numero> - <proveedor>
-$<monto> - <estado>", tal como lo trae la columna "Orden Compra" de
Advertys en la grilla de items de una factura -- ver
modules/*/crawl_oc_por_factura.py) cruzando ordenes_compra_produccion
(Produccion) y ordenes_publicidad (Medios).

Compartido entre modules/cobranza_proveedores y modules/iibb: ambos
crawlean la misma pestana "Items Facturas"/"Items Facturas Medios" con su
propio crawl_oc_por_factura.py (ventanas distintas), pero el cruce contra
ordenes_compra/ordenes_publicidad -- incluida la desambiguacion de Orden
de Publicidad por año/proveedor -- es identico y vivia duplicado solo en
cobranza_proveedores. Ver modules/cobranza_proveedores/generate_html_report.py
para el detalle historico del gap Produccion/Publicidad (2026-08-04) y el
gotcha de "Orden" no siendo clave unica por si sola.
"""
import re

import pandas as pd

from common import normalizar_numero

# "198 - SADAIC -$677000,00 - Autorizada" -> ("SADAIC", "677000,00", "Autorizada")
_RE_OC_TEXTO = re.compile(r"^\s*\d+\s*-\s*(.+?)\s*-\$\s*([\d.,]+)\s*-\s*(.+?)\s*$")

COLUMNAS_RESUELTAS = ["proveedor", "oc_importe_sin_iva", "oc_saldo", "oc_estado", "oc_origen"]


def parsear_oc_texto(texto: str) -> dict | None:
    m = _RE_OC_TEXTO.match(texto or "")
    if not m:
        return None
    proveedor, monto_txt, estado = m.groups()
    return {"proveedor": proveedor.strip(), "monto": normalizar_numero(monto_txt), "estado": estado.strip()}


def _normalizar_proveedor(nombre) -> str | None:
    return nombre.strip().upper() if isinstance(nombre, str) and nombre.strip() else None


def _resolver_op(numero_oc: str, proveedor_txt: str | None, ordenes_publicidad: pd.DataFrame) -> tuple[pd.Series | None, str]:
    """Busca la OP real por numero_oc, desambiguando por proveedor cuando el
    numero solo (sin año) matchea mas de una fila. Devuelve (fila o None,
    origen: 'Publicidad' | 'Publicidad (año ambiguo)' | None)."""
    candidatos = ordenes_publicidad[ordenes_publicidad["numero_oc"] == numero_oc]
    if candidatos.empty:
        return None, None
    if len(candidatos) == 1:
        return candidatos.iloc[0], "Publicidad"

    prov_norm = _normalizar_proveedor(proveedor_txt)
    por_proveedor = candidatos[candidatos["proveedor"].apply(_normalizar_proveedor) == prov_norm]
    if len(por_proveedor) == 1:
        return por_proveedor.iloc[0], "Publicidad"

    restantes = por_proveedor if not por_proveedor.empty else candidatos
    return restantes.sort_values("ano_op", ascending=False).iloc[0], "Publicidad (año ambiguo)"


def resolver_proveedor_monto(items_oc: pd.DataFrame, ordenes_compra: pd.DataFrame,
                              ordenes_publicidad: pd.DataFrame) -> pd.DataFrame:
    """Agrega las columnas COLUMNAS_RESUELTAS a una copia de items_oc (que
    debe tener 'numero_oc' y 'orden_compra_raw'), cruzando primero contra
    ordenes_compra (Produccion) y, para lo que no matcheo, contra
    ordenes_publicidad (Medios). 'oc_saldo' = importe sin IVA de la OC/OP,
    siempre, sin importar el estado (pedido explicito de Javier,
    2026-08-04: no es el "saldo" que calcula Advertys)."""
    con_oc = items_oc.copy()
    if con_oc.empty:
        for c in COLUMNAS_RESUELTAS:
            con_oc[c] = None
        return con_oc

    if not ordenes_compra.empty:
        detalle_oc = ordenes_compra[["numero_oc", "proveedor", "importe_sin_iva", "estado"]].rename(
            columns={"importe_sin_iva": "oc_importe_sin_iva", "estado": "oc_estado"}
        )
        con_oc = con_oc.merge(detalle_oc, on="numero_oc", how="left")
    else:
        con_oc["proveedor"] = None
        con_oc["oc_importe_sin_iva"] = None
        con_oc["oc_estado"] = None
    con_oc["oc_origen"] = con_oc["proveedor"].notna().map({True: "Producción", False: None})

    sin_match = con_oc["proveedor"].isna()
    if sin_match.any():
        parseado = con_oc.loc[sin_match, "orden_compra_raw"].apply(parsear_oc_texto)
        proveedor_txt = parseado.apply(lambda d: d["proveedor"] if d else None)
        estado_txt = parseado.apply(lambda d: d["estado"] if d else None)
        monto_txt = parseado.apply(lambda d: d["monto"] if d else None)

        for idx in con_oc.loc[sin_match].index:
            fila_op, origen = _resolver_op(
                con_oc.at[idx, "numero_oc"], proveedor_txt.loc[idx], ordenes_publicidad
            )
            if fila_op is not None:
                con_oc.at[idx, "proveedor"] = fila_op["proveedor"]
                con_oc.at[idx, "oc_importe_sin_iva"] = fila_op["importe_sin_iva"]
                con_oc.at[idx, "oc_estado"] = fila_op["estado"]
                con_oc.at[idx, "oc_origen"] = origen
            else:
                # Ultimo recurso: la OP referenciada no esta en
                # ordenes_publicidad (dato desactualizado) -- usar el texto
                # crudo tal cual.
                con_oc.at[idx, "proveedor"] = proveedor_txt.loc[idx]
                con_oc.at[idx, "oc_importe_sin_iva"] = monto_txt.loc[idx]
                con_oc.at[idx, "oc_estado"] = estado_txt.loc[idx]
                con_oc.at[idx, "oc_origen"] = "Publicidad (estimado)" if proveedor_txt.loc[idx] else None

    con_oc["oc_saldo"] = con_oc["oc_importe_sin_iva"]
    return con_oc
