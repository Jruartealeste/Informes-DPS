"""
Carga compartida de Imputaciones cruzadas con Facturas de ALUAR -- usada
tanto por crawl_facturas_relacionadas.py (para saber que documentos CA hay
que crawlear) como por ingest.py (para armar la tabla final). Ver
docstring de config.py para el porque de este cruce.
"""
import pandas as pd

import db
from . import config


def _cargar_facturas_aluar() -> pd.DataFrame:
    with db.get_connection() as conn:
        df = pd.read_sql(
            """
            SELECT tipo_asiento, numero_asiento, tipo_referencia, numero_referencia,
                   periodo, fecha, cliente
            FROM facturas
            WHERE cliente LIKE ?
            """,
            conn,
            params=(config.CLIENTE_LIKE,),
        )
    df["clave"] = df["tipo_asiento"] + "|" + df["numero_asiento"] + "|" + df["tipo_referencia"] + "|" + df["numero_referencia"]
    periodo = df["periodo"].astype(str)
    df["mes"] = periodo.str[:4] + "-" + periodo.str[4:6]
    return df


def _cargar_imputaciones_crudo() -> pd.DataFrame:
    """Lee el export crudo de Imputaciones (todas las cuentas, sin filtrar
    -- ver config.IMPUTACIONES_EXPORT_PATH). El nombre de la columna de
    referencia llega con el simbolo de grados corrompido segun como se
    guardo el .xlsx (mismo gotcha que balance_mensual/generate_excel.py);
    se ubica por contenido ("Referencia") en vez de asumir el byte exacto."""
    df = pd.read_excel(config.IMPUTACIONES_EXPORT_PATH)
    ref_col = next(c for c in df.columns if "Referencia" in c)
    df = df.rename(columns={ref_col: "_numero_referencia_raw"})
    df["numero_referencia"] = df["_numero_referencia_raw"].apply(
        lambda v: f"{int(v):012d}" if pd.notna(v) else None
    )
    df["numero_asiento"] = df["Asiento"].apply(lambda v: f"{int(v):06d}" if pd.notna(v) else None)
    df["clave"] = df["TA"].astype(str) + "|" + df["numero_asiento"] + "|" + df["TR"].astype(str) + "|" + df["numero_referencia"]
    return df


def imputaciones_aluar(solo_cuentas_ingreso: bool = True) -> pd.DataFrame:
    """Filas de Imputaciones que pertenecen a una factura de ALUAR (via
    clave TA+Asiento+TR+N°Referencia), con tipo_venta y mes (periodo real
    de la factura, no el mes contable de la imputacion -- ver docstring de
    config.py) ya resueltos."""
    facturas = _cargar_facturas_aluar()
    imp = _cargar_imputaciones_crudo()
    df = imp[imp["clave"].isin(set(facturas["clave"]))].copy()
    if solo_cuentas_ingreso:
        df = df[df["Cuenta"].isin(config.CUENTAS_INGRESO)]
    df = df.merge(facturas[["clave", "mes"]], on="clave", how="left")
    df["tipo_venta"] = df["TA"].map(config.TA_TIPO_VENTA)
    return df


def documentos_cancelacion_aluar() -> list[tuple[str, str, str]]:
    """Documentos TR='CA' (cancelaciones) dentro de las cuentas de ingreso
    de ALUAR -- (clave, tipo_asiento, numero_referencia) unicos, para que
    crawl_facturas_relacionadas.py sepa que facturas abrir."""
    df = imputaciones_aluar(solo_cuentas_ingreso=True)
    ca = df[df["TR"] == "CA"][["clave", "TA", "numero_referencia"]].drop_duplicates()
    return list(ca.itertuples(index=False, name=None))
