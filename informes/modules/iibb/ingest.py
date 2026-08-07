"""
Carga un Excel exportado desde Advertys (vista Imputaciones, Consultas >
Contabilidad > Imputaciones) a la base local, filtrado a las cuentas de
recupero de terceros (OC/OP) que interesan para el informe de IIBB -- ver
modules/iibb/config.py para el detalle de por que.

Uso:
    python -m modules.iibb.ingest ruta/al/export.xlsx

Importante: exportar desde Advertys con el filtro de la vista en "Todos"
(el default es "Mes Actual", que solo trae el mes en curso). Ver
modules/iibb/explore.py.

Igual que modules/estimados_pendientes_facturar, esta tabla se REEMPLAZA
entera en cada corrida (DELETE + INSERT): no hay columna de ID de linea en
el export de Imputaciones, y como ya se recorta a 2 cuentas puntuales no
tiene sentido mantener un historial de upserts con una clave sintetica.
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
    clase TEXT,
    sub_clase TEXT,
    rubro TEXT,
    sub_rubro TEXT,
    periodo TEXT,
    cuenta INTEGER,
    nombre_cuenta TEXT,
    sub_cta TEXT,
    fecha TEXT,
    tipo_asiento TEXT,
    fecha_analisis TEXT,
    numero_asiento TEXT,
    tipo_referencia TEXT,
    numero_referencia TEXT,
    moneda TEXT,
    centro_costo TEXT,
    cotizacion REAL,
    importe REAL,
    leyenda TEXT,
    fecha_ingesta TEXT
);
"""

COLUMNAS_TABLA = [
    "clase", "sub_clase", "rubro", "sub_rubro", "periodo", "cuenta",
    "nombre_cuenta", "sub_cta", "fecha", "tipo_asiento", "fecha_analisis",
    "numero_asiento", "tipo_referencia", "numero_referencia", "moneda",
    "centro_costo", "cotizacion", "importe", "leyenda", "fecha_ingesta",
]


def init_db():
    with db.get_connection() as conn:
        conn.execute(SCHEMA)
        conn.commit()


def reemplazar_todo(records: list[dict]) -> int:
    """Vacia la tabla y carga los registros del export actual (ver
    docstring del modulo: esta tabla es un recorte/snapshot, no un
    historico acumulado con upsert)."""
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

    # Cuenta llega como int/float de Excel (ej. 411040.0) -- normalizar a int
    # antes de filtrar contra config.CUENTAS_DEDUCIBLES.
    if "cuenta" in df.columns:
        df["cuenta"] = df["cuenta"].apply(lambda v: int(v) if pd.notna(v) else None)

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

    antes = len(df)
    df = df[df["cuenta"].isin(config.CUENTAS_DEDUCIBLES)]
    print(f"Filtrado a cuentas deducibles {config.CUENTAS_DEDUCIBLES}: {len(df)} de {antes} filas.")

    return df


def main():
    parser = argparse.ArgumentParser(description="Carga un export de Imputaciones (Advertys), filtrado a cuentas OC/OP deducibles")
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
