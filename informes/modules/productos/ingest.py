"""
Carga el Excel exportado de Productos (ver `modules/productos/export.py`) a
la tabla `productos` de advertys.db, por REEMPLAZO TOTAL (ver config.py).

Uso:
    python -m modules.productos.ingest [ruta/al/export.xlsx]

Sin argumento usa exploracion/productos_export.xlsx (la ruta que deja
export.py).
"""
import sys
from datetime import datetime, timezone

import pandas as pd

import db
from . import config
from .export import DESTINO

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS {config.DB_TABLE} (
    id_advertys TEXT PRIMARY KEY,
    nombre TEXT NOT NULL,
    anunciante TEXT NOT NULL,
    categoria TEXT,
    marca TEXT,
    fecha_ingesta TEXT
);
"""

COLUMNAS_TABLA = ["id_advertys", "nombre", "anunciante", "categoria", "marca", "fecha_ingesta"]


def _texto(valor) -> str | None:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    valor = str(valor).strip()
    return valor or None


def cargar_excel(path) -> list[dict]:
    df = pd.read_excel(path, sheet_name=0, dtype=object).rename(columns=config.COLUMN_MAP)
    faltantes = [c for c in config.REQUIRED_COLUMNS if c not in df.columns]
    if faltantes:
        raise SystemExit(f"ERROR: faltan columnas {faltantes} en {path}. Columnas: {list(df.columns)}")

    ahora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    registros, vistos = [], set()
    for fila in df.to_dict("records"):
        r = {c: _texto(fila.get(c)) for c in COLUMNAS_TABLA if c != "fecha_ingesta"}
        if not all(r[c] for c in config.REQUIRED_COLUMNS):
            continue  # fila sin Id / Nombre / Anunciante: no sirve para el combo
        if r["id_advertys"] in vistos:
            raise SystemExit(f"ERROR: Id repetido en el export: {r['id_advertys']}")
        vistos.add(r["id_advertys"])
        r["fecha_ingesta"] = ahora
        registros.append(r)
    return registros


def reemplazar(registros: list[dict]) -> int:
    if not registros:
        raise SystemExit("ERROR: el export no trae productos; no se pisa la tabla con un resultado vacio.")
    placeholders = ", ".join("?" for _ in COLUMNAS_TABLA)
    with db.get_connection() as conn:
        conn.execute(SCHEMA)
        conn.execute(f"DELETE FROM {config.DB_TABLE}")
        conn.executemany(
            f"INSERT INTO {config.DB_TABLE} ({', '.join(COLUMNAS_TABLA)}) VALUES ({placeholders})",
            [tuple(r.get(c) for c in COLUMNAS_TABLA) for r in registros],
        )
        conn.commit()
    return len(registros)


def main():
    ruta = sys.argv[1] if len(sys.argv) > 1 else str(DESTINO)
    n = reemplazar(cargar_excel(ruta))
    print(f"OK: {n} productos cargados en la tabla '{config.DB_TABLE}' desde {ruta}")


if __name__ == "__main__":
    main()
