"""
Carga un Excel de Notas de Credito automaticas de Ventas (Produccion, Medios
o Representante) a la tabla "facturas" de la base local, como filas con
importe negativo -- mismo criterio que Compras con su columna signada (ver
modules/compras/ingest.py). Asi los totales de generate_html_report.py y el
dashboard las netean sin ningun cambio ahi.

Estas vistas no comparten ObjectClassName con "Facturas" (DPS_Factura), asi
que nunca vienen mezcladas en ese export por mas que su filtro este en
"Todos" -- ver modules/facturas/export_nc.py y la nota "Notas de Credito de
Ventas" en README.md.

Uso:
    python -m modules.facturas.ingest_nc ruta/al/export.xlsx --segmento produccion
"""
import argparse
import sys
from datetime import datetime, timezone

import pandas as pd

import db
from common import normalizar_fecha, normalizar_numero
from . import config
from .ingest import init_db, upsert_records


def cargar_excel_nc(path: str, segmento: str, hoja=0) -> pd.DataFrame:
    if segmento not in config.NC_SEGMENTOS:
        print(f"ERROR: segmento desconocido '{segmento}'. Opciones: {list(config.NC_SEGMENTOS)}")
        sys.exit(1)

    df = pd.read_excel(path, sheet_name=hoja, dtype=object)
    df = df.rename(columns=config.NC_COLUMN_MAP)

    columnas_esperadas = set(config.NC_COLUMN_MAP.values())
    columnas_presentes = set(df.columns) & columnas_esperadas
    faltantes = columnas_esperadas - columnas_presentes - {"anunciante"}
    if faltantes:
        print(f"Aviso: no se encontraron estas columnas mapeadas en el Excel de NC {segmento}: {sorted(faltantes)}")

    df = df[[c for c in df.columns if c in columnas_esperadas]]

    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].apply(lambda v: v.strip() if isinstance(v, str) else v)

    for col in config.NC_DATE_COLUMNS:
        if col in df.columns:
            df[col] = df[col].apply(normalizar_fecha)

    for col in config.NC_NUMERIC_COLUMNS:
        if col in df.columns:
            df[col] = df[col].apply(normalizar_numero)

    faltan_obligatorias = [c for c in config.NC_REQUIRED_COLUMNS if c not in df.columns]
    if faltan_obligatorias:
        print(f"ERROR: faltan columnas obligatorias {faltan_obligatorias} en el export de NC {segmento}. Revisa NC_COLUMN_MAP en config.py.")
        sys.exit(1)

    antes = len(df)
    df = df.dropna(subset=config.NC_REQUIRED_COLUMNS)
    if len(df) < antes:
        print(f"Aviso: se descartaron {antes - len(df)} filas de NC {segmento} por faltarles datos obligatorios.")

    # Importe negativo: la nota de credito resta del total facturado. La
    # vista de Advertys trae Subtotal/Impuestos/Total siempre en positivo.
    for col in config.NC_NUMERIC_COLUMNS:
        if col in df.columns:
            df[col] = df[col].apply(lambda v: -abs(v) if v is not None else None)

    if "anunciante" not in df.columns:
        # Medios y Representante no traen "Anunciante" en el Excel -- mismo
        # criterio que ya rige para las facturas reales de esos segmentos
        # (anunciante == cliente, ver README).
        df["anunciante"] = df["cliente"]

    df["periodo"] = df["fecha"].str.replace("-", "", regex=False).str[:6]
    df["tipo_asiento"] = config.NC_SEGMENTOS[segmento]["tipo_asiento"]

    df["clave_factura"] = df[config.CLAVE_COMPUESTA].apply(
        lambda fila: "-".join(str(v) for v in fila), axis=1
    )

    return df


def main():
    parser = argparse.ArgumentParser(description="Carga un export de Notas de Credito de Ventas (Advertys) a la tabla facturas")
    parser.add_argument("archivo", help="Ruta al archivo .xlsx exportado de Advertys")
    parser.add_argument("--segmento", required=True, choices=list(config.NC_SEGMENTOS), help="produccion, medios o representante")
    parser.add_argument("--hoja", default=0, help="Nombre o indice de la hoja (default: primera)")
    args = parser.parse_args()

    init_db()
    df = cargar_excel_nc(args.archivo, args.segmento, hoja=args.hoja)

    ahora = datetime.now(timezone.utc).isoformat()
    registros = df.to_dict(orient="records")
    for r in registros:
        r["fecha_ingesta"] = ahora

    cantidad = upsert_records(registros)
    print(f"OK: {cantidad} notas de credito ({args.segmento}) procesadas desde '{args.archivo}' hacia {db.DB_PATH} (tabla {config.DB_TABLE})")


if __name__ == "__main__":
    main()
