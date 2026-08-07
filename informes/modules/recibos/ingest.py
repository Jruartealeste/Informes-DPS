"""
Carga un Excel exportado desde Advertys (modulo Recibo Cliente, cabecera) a
la base local.

Uso:
    python -m modules.recibos.ingest ruta/al/export.xlsx

Importante: exportar desde Advertys con el filtro de la vista en "Todas"
(ver modules/recibos/explore.py). La tabla "recibos" solo trae la cabecera
de cada recibo -- para el detalle de que factura(s) cancela cada uno, correr
ademas modules/recibos/crawl_referencias_canceladas.py.
"""
import argparse
import sys
from datetime import datetime, timezone

import pandas as pd

import db
from common import normalizar_fecha, normalizar_numero
from . import config

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS {config.DB_TABLE} (
    numero_recibo TEXT PRIMARY KEY,
    periodo TEXT,
    fecha TEXT,
    numero_asiento TEXT,
    cliente TEXT,
    moneda TEXT,
    anticipo REAL,
    cancelaciones REAL,
    retenciones REAL,
    ch_terceros REAL,
    ch_dif_cliente REAL,
    efvo_otros REAL,
    estado TEXT,
    fecha_timbrado TEXT,
    dif_cambio REAL,
    es_moneda_local TEXT,
    fecha_ingesta TEXT
);
"""

COLUMNAS_TABLA = [
    "numero_recibo", "periodo", "fecha", "numero_asiento", "cliente",
    "moneda", "anticipo", "cancelaciones", "retenciones", "ch_terceros",
    "ch_dif_cliente", "efvo_otros", "estado", "fecha_timbrado", "dif_cambio",
    "es_moneda_local", "fecha_ingesta",
]


def init_db():
    with db.get_connection() as conn:
        conn.execute(SCHEMA)
        conn.commit()


def upsert_records(records: list[dict]) -> int:
    if not records:
        return 0
    placeholders = ", ".join("?" for _ in COLUMNAS_TABLA)
    updates = ", ".join(f"{c}=excluded.{c}" for c in COLUMNAS_TABLA if c != "numero_recibo")
    sql = f"""
        INSERT INTO {config.DB_TABLE} ({", ".join(COLUMNAS_TABLA)})
        VALUES ({placeholders})
        ON CONFLICT(numero_recibo) DO UPDATE SET {updates}
    """
    with db.get_connection() as conn:
        conn.executemany(sql, [tuple(r.get(c) for c in COLUMNAS_TABLA) for r in records])
        conn.commit()
    return len(records)


def cargar_excel(path: str, hoja=0) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=hoja, dtype=object)
    df = df.rename(columns=config.COLUMN_MAP)

    columnas_esperadas = set(config.COLUMN_MAP.values())
    columnas_presentes = set(df.columns) & columnas_esperadas
    faltantes = columnas_esperadas - columnas_presentes
    if faltantes:
        print(f"Aviso: no se encontraron estas columnas mapeadas en el Excel: {sorted(faltantes)}")
        print(f"Columnas que SI se detectaron: {sorted(columnas_presentes)}")

    df = df[[c for c in df.columns if c in columnas_esperadas]]

    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].apply(lambda v: v.strip() if isinstance(v, str) else v)

    if "numero_recibo" in df.columns:
        df["numero_recibo"] = df["numero_recibo"].apply(lambda v: str(int(v)) if pd.notna(v) else None)

    for col in config.DATE_COLUMNS:
        if col in df.columns:
            df[col] = df[col].apply(normalizar_fecha)

    for col in config.NUMERIC_COLUMNS:
        if col in df.columns:
            df[col] = df[col].apply(normalizar_numero)

    faltan_obligatorias = [c for c in config.REQUIRED_COLUMNS if c not in df.columns]
    if faltan_obligatorias:
        print(f"ERROR: faltan columnas obligatorias {faltan_obligatorias}. Revisa COLUMN_MAP en config.py.")
        sys.exit(1)

    antes = len(df)
    df = df.dropna(subset=config.REQUIRED_COLUMNS)
    if len(df) < antes:
        print(f"Aviso: se descartaron {antes - len(df)} filas por faltarles datos obligatorios.")

    return df


def main():
    parser = argparse.ArgumentParser(description="Carga un export de Recibo Cliente (Advertys) a la base local")
    parser.add_argument("archivo", help="Ruta al archivo .xlsx exportado de Advertys")
    parser.add_argument("--hoja", default=0, help="Nombre o indice de la hoja (default: primera)")
    args = parser.parse_args()

    init_db()
    df = cargar_excel(args.archivo, hoja=args.hoja)

    ahora = datetime.now(timezone.utc).isoformat()
    registros = df.to_dict(orient="records")
    for r in registros:
        r["fecha_ingesta"] = ahora

    cantidad = upsert_records(registros)
    print(f"OK: {cantidad} registros procesados desde '{args.archivo}' hacia {db.DB_PATH} (tabla {config.DB_TABLE})")


if __name__ == "__main__":
    main()
