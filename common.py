"""
Funciones de normalizacion compartidas entre todos los modulos (ingest.py
de cada uno las importa desde aca en vez de duplicarlas).
"""
from datetime import datetime

import pandas as pd


def normalizar_fecha(valor):
    if pd.isna(valor):
        return None
    if isinstance(valor, (datetime, pd.Timestamp)):
        return valor.strftime("%Y-%m-%d")
    return str(pd.to_datetime(valor, errors="coerce", dayfirst=True).date()) if pd.notna(
        pd.to_datetime(valor, errors="coerce", dayfirst=True)
    ) else None


def normalizar_numero(valor):
    if pd.isna(valor):
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    limpio = str(valor).replace("$", "").replace(".", "").replace(",", ".").strip()
    try:
        return float(limpio)
    except ValueError:
        return None
