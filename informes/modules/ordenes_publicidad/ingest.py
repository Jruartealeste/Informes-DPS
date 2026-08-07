"""
Carga un Excel exportado desde Advertys (modulo Orden Publicidad, vista
Navegacion) a la base local.

Uso:
    python -m modules.ordenes_publicidad.ingest ruta/al/export.xlsx

La tabla "ordenes_publicidad" vive en la misma base advertys.db. Clave
primaria compuesta (ano_op, numero_oc) -- ver docstring de config.py, el
numero de Orden solo no es unico (se reinicia cada año).
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
    ano_op INTEGER,
    numero_oc TEXT,
    mes_op TEXT,
    fecha TEXT,
    barra INTEGER,
    pauta TEXT,
    proveedor TEXT,
    cliente TEXT,
    anunciante TEXT,
    medio TEXT,
    alicuota_iva REAL,
    importe_sin_iva REAL,
    saldo REAL,
    importe_con_iva REAL,
    estado TEXT,
    facturado REAL,
    comprado REAL,
    cobrado REAL,
    pagado REAL,
    ajustado REAL,
    cartel_error TEXT,
    fecha_ingesta TEXT,
    PRIMARY KEY (ano_op, numero_oc)
);
"""

COLUMNAS_TABLA = [
    "ano_op", "numero_oc", "mes_op", "fecha", "barra", "pauta", "proveedor",
    "cliente", "anunciante", "medio", "alicuota_iva", "importe_sin_iva",
    "saldo", "importe_con_iva", "estado", "facturado", "comprado", "cobrado",
    "pagado", "ajustado", "cartel_error", "fecha_ingesta",
]


def init_db():
    with db.get_connection() as conn:
        conn.execute(SCHEMA)
        conn.commit()


def upsert_records(records: list[dict]) -> int:
    if not records:
        return 0
    placeholders = ", ".join("?" for _ in COLUMNAS_TABLA)
    updates = ", ".join(
        f"{c}=excluded.{c}" for c in COLUMNAS_TABLA if c not in config.UNIQUE_KEY_COLUMNS
    )
    sql = f"""
        INSERT INTO {config.DB_TABLE} ({", ".join(COLUMNAS_TABLA)})
        VALUES ({placeholders})
        ON CONFLICT(ano_op, numero_oc) DO UPDATE SET {updates}
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
    if "ano_op" in df.columns:
        df["ano_op"] = df["ano_op"].apply(lambda v: int(v) if pd.notna(v) else None)
    if "barra" in df.columns:
        df["barra"] = df["barra"].apply(lambda v: int(v) if pd.notna(v) else None)

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

    dup = df.duplicated(subset=config.UNIQUE_KEY_COLUMNS, keep="last")
    if dup.any():
        print(f"Aviso: {dup.sum()} filas comparten (Año OP, Orden) con otra fila -- Advertys permite esto en "
              "casos raros (ver docstring de config.py). Se conserva la ultima leida por cada combinacion.")

    return df


def main():
    parser = argparse.ArgumentParser(description="Carga un export de Orden Publicidad (Advertys) a la base local")
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
