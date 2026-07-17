"""
Carga un Excel exportado desde Advertys (modulo Compras) a la base local.

Uso:
    python -m modules.compras.ingest ruta/al/export.xlsx

La tabla "compras" vive en la misma base advertys.db, separada de
"ordenes_trabajo".
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
    clave_compra TEXT PRIMARY KEY,
    periodo TEXT,
    tipo_compra TEXT,
    tipo_proveedor TEXT,
    proveedor TEXT,
    tipo_asiento TEXT,
    numero_asiento TEXT,
    tipo_referencia TEXT,
    numero_referencia TEXT,
    fecha_factura TEXT,
    importe_sin_iva REAL,
    importe_sin_iva_signado REAL,
    total_impositivo REAL,
    moneda TEXT,
    empleado TEXT,
    orden_compra_generica TEXT,
    leyenda TEXT,
    estado TEXT,
    tiene_adjunto TEXT,
    fecha_ingesta TEXT
);
"""

COLUMNAS_TABLA = [
    "clave_compra", "periodo", "tipo_compra", "tipo_proveedor", "proveedor",
    "tipo_asiento", "numero_asiento", "tipo_referencia", "numero_referencia",
    "fecha_factura", "importe_sin_iva", "importe_sin_iva_signado",
    "total_impositivo", "moneda", "empleado", "orden_compra_generica",
    "leyenda", "estado", "tiene_adjunto", "fecha_ingesta",
]


def init_db():
    with db.get_connection() as conn:
        conn.execute(SCHEMA)
        conn.commit()


def upsert_records(records: list[dict]) -> int:
    if not records:
        return 0
    placeholders = ", ".join("?" for _ in COLUMNAS_TABLA)
    updates = ", ".join(f"{c}=excluded.{c}" for c in COLUMNAS_TABLA if c != "clave_compra")
    sql = f"""
        INSERT INTO {config.DB_TABLE} ({", ".join(COLUMNAS_TABLA)})
        VALUES ({placeholders})
        ON CONFLICT(clave_compra) DO UPDATE SET {updates}
    """
    with db.get_connection() as conn:
        conn.executemany(sql, [tuple(r.get(c) for c in COLUMNAS_TABLA) for r in records])
        conn.commit()
    return len(records)


def cargar_excel(path: str, hoja=0) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=hoja, dtype=object)

    # Caso especial: hay dos columnas literalmente "Importe s/IVA" en el
    # export (la 2da viene con signo contable). Pandas ya le puso ".1" a la
    # segunda al leerla; la renombramos antes de aplicar el resto del mapeo.
    if "Importe s/IVA.1" in df.columns:
        df = df.rename(columns={"Importe s/IVA.1": config.COLUMNA_IMPORTE_SIGNADO})

    df = df.rename(columns=config.COLUMN_MAP)

    columnas_esperadas = set(config.COLUMN_MAP.values()) | {config.COLUMNA_IMPORTE_SIGNADO}
    columnas_presentes = set(df.columns) & columnas_esperadas
    faltantes = columnas_esperadas - columnas_presentes
    if faltantes:
        print(f"Aviso: no se encontraron estas columnas mapeadas en el Excel: {sorted(faltantes)}")
        print(f"Columnas que SI se detectaron: {sorted(columnas_presentes)}")

    df = df[[c for c in df.columns if c in columnas_esperadas]]

    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].apply(lambda v: v.strip() if isinstance(v, str) else v)

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

    df["clave_compra"] = df[config.CLAVE_COMPUESTA].apply(
        lambda fila: "-".join(str(v) for v in fila), axis=1
    )

    return df


def main():
    parser = argparse.ArgumentParser(description="Carga un export de Compras (Advertys) a la base local")
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
