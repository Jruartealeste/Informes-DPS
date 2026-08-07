"""
Carga un Excel exportado desde Advertys (modulo Orden Compra Produccion) a
la base local.

Uso:
    python -m modules.ordenes_compra.ingest ruta/al/export.xlsx

La tabla "ordenes_compra_produccion" vive en la misma base advertys.db,
vinculada a "estimados_costos" por numero_estimado (parseado de la columna
de texto libre "Estimado Costos" del export -- ver config.py).
"""
import argparse
import re
import sys
from datetime import datetime, timezone

import pandas as pd

import db
from common import normalizar_fecha, normalizar_numero
from . import config

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS {config.DB_TABLE} (
    numero_oc TEXT PRIMARY KEY,
    detalle TEXT,
    rubro TEXT,
    proveedor TEXT,
    cliente TEXT,
    anunciante TEXT,
    grupo_anunciante TEXT,
    periodo TEXT,
    estimado_costos_raw TEXT,
    numero_estimado TEXT,
    fecha TEXT,
    importe_sin_iva REAL,
    saldo REAL,
    ajustado REAL,
    facturado REAL,
    comprado REAL,
    cobrado REAL,
    pagado REAL,
    estado TEXT,
    fecha_ingesta TEXT
);
"""

COLUMNAS_TABLA = [
    "numero_oc", "detalle", "rubro", "proveedor", "cliente", "anunciante",
    "grupo_anunciante", "periodo", "estimado_costos_raw", "numero_estimado",
    "fecha", "importe_sin_iva", "saldo", "ajustado", "facturado", "comprado",
    "cobrado", "pagado", "estado", "fecha_ingesta",
]

_RE_NUMERO_ESTIMADO = re.compile(r"^(\d+)-")


def init_db():
    with db.get_connection() as conn:
        conn.execute(SCHEMA)
        conn.commit()


def upsert_records(records: list[dict]) -> int:
    if not records:
        return 0
    placeholders = ", ".join("?" for _ in COLUMNAS_TABLA)
    updates = ", ".join(f"{c}=excluded.{c}" for c in COLUMNAS_TABLA if c != "numero_oc")
    sql = f"""
        INSERT INTO {config.DB_TABLE} ({", ".join(COLUMNAS_TABLA)})
        VALUES ({placeholders})
        ON CONFLICT(numero_oc) DO UPDATE SET {updates}
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

    if "numero_oc" in df.columns:
        df["numero_oc"] = df["numero_oc"].apply(lambda v: str(int(v)) if pd.notna(v) else None)

    def _parsear_numero_estimado(texto):
        if not isinstance(texto, str):
            return None
        m = _RE_NUMERO_ESTIMADO.match(texto)
        return m.group(1) if m else None

    if "estimado_costos_raw" in df.columns:
        df["numero_estimado"] = df["estimado_costos_raw"].apply(_parsear_numero_estimado)
    else:
        df["numero_estimado"] = None

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
    parser = argparse.ArgumentParser(description="Carga un export de Orden Compra Produccion (Advertys) a la base local")
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
    sin_estimado = sum(1 for r in registros if not r.get("numero_estimado"))
    if sin_estimado:
        print(f"Aviso: {sin_estimado} ordenes de compra sin numero_estimado parseable (columna 'Estimado Costos' vacia o con formato distinto).")


if __name__ == "__main__":
    main()
