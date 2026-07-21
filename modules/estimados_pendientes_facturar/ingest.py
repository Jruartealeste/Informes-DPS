"""
Carga un Excel exportado desde Advertys (vista "Estim.Pendientes Facturar")
a la base local.

Uso:
    python -m modules.estimados_pendientes_facturar.ingest ruta/al/export.xlsx

Igual que modules/oc_pendientes_generar, esta tabla se REEMPLAZA entera en
cada corrida (DELETE + INSERT) en vez de hacer upsert: es un snapshot de
"que esta pendiente ahora mismo" (ver config.py) y un estimado que se
termina de facturar desaparece del export.
"""
import argparse
import sys
from datetime import datetime, timezone

import pandas as pd

import db
from common import normalizar_numero
from . import config

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS {config.DB_TABLE} (
    periodo TEXT,
    numero_estimado TEXT,
    numero_cliente TEXT,
    numero_ot TEXT,
    anunciante TEXT,
    producto TEXT,
    titulo TEXT,
    total_costo REAL,
    total_ganancia REAL,
    total_facturado REAL,
    pendiente_facturar REAL,
    estado TEXT,
    moneda TEXT,
    fecha_ingesta TEXT
);
"""

COLUMNAS_TABLA = [
    "periodo", "numero_estimado", "numero_cliente", "numero_ot", "anunciante",
    "producto", "titulo", "total_costo", "total_ganancia", "total_facturado",
    "pendiente_facturar", "estado", "moneda", "fecha_ingesta",
]


def init_db():
    with db.get_connection() as conn:
        conn.execute(SCHEMA)
        conn.commit()


def reemplazar_todo(records: list[dict]) -> int:
    """Vacia la tabla y carga los registros del export actual (ver
    docstring del modulo: esta tabla es un snapshot, no un historico)."""
    with db.get_connection() as conn:
        conn.execute(f"DELETE FROM {config.DB_TABLE}")
        if records:
            placeholders = ", ".join("?" for _ in COLUMNAS_TABLA)
            sql = f"INSERT INTO {config.DB_TABLE} ({', '.join(COLUMNAS_TABLA)}) VALUES ({placeholders})"
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

    # numero_estimado/numero_cliente/numero_ot llegan como int/float desde
    # Excel; se normalizan a texto para cruzar por igualdad exacta con
    # estimados_costos.numero_estimado / ordenes_trabajo.numero_ot.
    for col in ("numero_estimado", "numero_cliente", "numero_ot"):
        if col in df.columns:
            df[col] = df[col].apply(lambda v: str(int(v)) if pd.notna(v) else None)

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
    parser = argparse.ArgumentParser(description="Carga un export de 'Estim.Pendientes Facturar' (Advertys) a la base local")
    parser.add_argument("archivo", help="Ruta al archivo .xlsx exportado de Advertys")
    parser.add_argument("--hoja", default=0, help="Nombre o indice de la hoja (default: primera)")
    args = parser.parse_args()

    init_db()
    df = cargar_excel(args.archivo, hoja=args.hoja)

    ahora = datetime.now(timezone.utc).isoformat()
    registros = df.to_dict(orient="records")
    for r in registros:
        r["fecha_ingesta"] = ahora

    cantidad = reemplazar_todo(registros)
    print(f"OK: {cantidad} registros reemplazados desde '{args.archivo}' hacia {db.DB_PATH} (tabla {config.DB_TABLE})")


if __name__ == "__main__":
    main()
