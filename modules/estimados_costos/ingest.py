"""
Carga un Excel exportado desde Advertys (modulo Estimado Costos) a la base
local.

Uso:
    python -m modules.estimados_costos.ingest ruta/al/export.xlsx

La tabla "estimados_costos" vive en la misma base advertys.db, separada de
"ordenes_trabajo" pero vinculada por numero_ot.
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
    numero_estimado TEXT PRIMARY KEY,
    numero_ot TEXT,
    periodo TEXT,
    fecha_solicita TEXT,
    anunciante TEXT,
    grupo_anunciante TEXT,
    cliente TEXT,
    producto TEXT,
    titulo TEXT,
    moneda TEXT,
    sub_total REAL,
    neto REAL,
    total_comprado REAL,
    total_facturado REAL,
    total_ordenado REAL,
    estado TEXT,
    fecha_ingesta TEXT
);
"""

COLUMNAS_TABLA = [
    "numero_estimado", "numero_ot", "periodo", "fecha_solicita", "anunciante",
    "grupo_anunciante", "cliente", "producto", "titulo", "moneda", "sub_total",
    "neto", "total_comprado", "total_facturado", "total_ordenado", "estado",
    "fecha_ingesta",
]


def init_db():
    with db.get_connection() as conn:
        conn.execute(SCHEMA)
        conn.commit()


def upsert_records(records: list[dict]) -> int:
    if not records:
        return 0
    placeholders = ", ".join("?" for _ in COLUMNAS_TABLA)
    updates = ", ".join(f"{c}=excluded.{c}" for c in COLUMNAS_TABLA if c != "numero_estimado")
    sql = f"""
        INSERT INTO {config.DB_TABLE} ({", ".join(COLUMNAS_TABLA)})
        VALUES ({placeholders})
        ON CONFLICT(numero_estimado) DO UPDATE SET {updates}
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

    # numero_estimado / numero_ot llegan como int desde Excel; se normalizan
    # a texto antes de tocar DATE/NUMERIC para que el join con
    # ordenes_trabajo.numero_ot (columna TEXT) funcione por igualdad exacta.
    for col in ("numero_estimado", "numero_ot"):
        if col in df.columns:
            df[col] = df[col].apply(lambda v: str(int(v)) if pd.notna(v) else None)

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
    parser = argparse.ArgumentParser(description="Carga un export de Estimado Costos (Advertys) a la base local")
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
