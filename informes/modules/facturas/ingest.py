"""
Carga un Excel exportado desde Advertys (modulo Facturas) a la base local.

Uso:
    python -m modules.facturas.ingest ruta/al/export.xlsx

Importante: exportar desde Advertys con el filtro de la vista en "Todos"
(no el default "Mes Actual"), si no el export solo trae el mes en curso.
Ver modules/facturas/explore.py.

La tabla "facturas" vive en la misma base advertys.db, separada de
"ordenes_trabajo" y "compras".
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
    clave_factura TEXT PRIMARY KEY,
    periodo TEXT,
    fecha TEXT,
    fce TEXT,
    tipo_referencia TEXT,
    numero_referencia TEXT,
    anunciante TEXT,
    cliente TEXT,
    cuit TEXT,
    tipo_asiento TEXT,
    numero_asiento TEXT,
    cai TEXT,
    producto TEXT,
    subtotal_ml REAL,
    impuestos_ml REAL,
    total_ml REAL,
    moneda TEXT,
    cotizacion REAL,
    subtotal_me REAL,
    impuestos_me REAL,
    total_me REAL,
    estado TEXT,
    tiene_ncnd TEXT,
    tiene_ic TEXT,
    tiene_items_impresion TEXT,
    fecha_ingesta TEXT
);
"""

COLUMNAS_TABLA = [
    "clave_factura", "periodo", "fecha", "fce", "tipo_referencia",
    "numero_referencia", "anunciante", "cliente", "cuit", "tipo_asiento",
    "numero_asiento", "cai", "producto", "subtotal_ml", "impuestos_ml",
    "total_ml", "moneda", "cotizacion", "subtotal_me", "impuestos_me",
    "total_me", "estado", "tiene_ncnd", "tiene_ic", "tiene_items_impresion",
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
    updates = ", ".join(f"{c}=excluded.{c}" for c in COLUMNAS_TABLA if c != "clave_factura")
    sql = f"""
        INSERT INTO {config.DB_TABLE} ({", ".join(COLUMNAS_TABLA)})
        VALUES ({placeholders})
        ON CONFLICT(clave_factura) DO UPDATE SET {updates}
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

    df["clave_factura"] = df[config.CLAVE_COMPUESTA].apply(
        lambda fila: "-".join(str(v) for v in fila), axis=1
    )

    return df


def main():
    parser = argparse.ArgumentParser(description="Carga un export de Facturas (Advertys) a la base local")
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
