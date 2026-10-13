"""
Sincroniza la tabla `ordenes_trabajo` de advertys.db (ya cargada por
`python -m modules.ordenes_trabajo.ingest ...`) hacia el espejo de solo
lectura `ordenes_trabajo_espejo` de la app `ot/` (roadmap item 5, ver
"Relacion con Informes/ y con Advertys" en ot/CLAUDE.md).

Esto NO es un script de escritura contra Advertys -- lee de la base local
con db.get_connection() y hace un POST autenticado a otra app propia
(ot/). La salvaguarda "Advertys es de solo lectura" no aplica acá porque
Advertys ni se toca.

Autenticacion: bearer token fijo (OT_SYNC_TOKEN), no OAuth de usuario --
es un flujo server a server, no hay una persona logueada del lado de ot/
para este POST (ver app/routers/sync.py alla). OT_SYNC_URL/OT_SYNC_TOKEN
viven en el .env de la RAIZ del repo (mismo criterio que ADVERTYS_*, ver
.env.example ahi -- load_dotenv() los encuentra buscando hacia arriba
aunque este script corra parado en informes/).

Tambien empuja el catalogo de Productos (tabla `productos`, ver
`modules/productos/`) a /api/sync/productos, que `ot/` usa para precargar el
combo Producto del alta de OT; ahi es reemplazo total.

Se corre a mano despues de un ingest de ordenes_trabajo, igual de manual
que el resto del pipeline hoy -- no esta sumado a tools/actualizar_todo.py
todavia (evaluar si conviene una vez que se use en la practica).

Uso:
    python -m modules.sync_tareas_app.push
"""
import os
import sqlite3
import sys

import httpx
from dotenv import load_dotenv

import db

load_dotenv()

OT_SYNC_URL = os.environ.get("OT_SYNC_URL")
OT_SYNC_TOKEN = os.environ.get("OT_SYNC_TOKEN")

COLUMNAS = [
    "numero_ot", "id_advertys", "negocio", "anunciante", "marca", "producto",
    "resumen", "fecha_abierta", "fecha_cerrada", "responsable", "equipo",
    "estado", "renta_teorica", "renta_real",
]


class PushError(RuntimeError):
    pass


def _leer_ordenes_trabajo() -> list[dict]:
    with db.get_connection() as conn:
        filas = conn.execute(f"SELECT {', '.join(COLUMNAS)} FROM ordenes_trabajo").fetchall()
    return [dict(fila) for fila in filas]


def _post(ruta: str, registros: list[dict]) -> dict:
    url = f"{OT_SYNC_URL.rstrip('/')}{ruta}"
    try:
        resp = httpx.post(
            url,
            json=registros,
            headers={"Authorization": f"Bearer {OT_SYNC_TOKEN}"},
            timeout=30,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise PushError(f"ot/ rechazo el sync ({e.response.status_code}): {e.response.text[:500]}") from e
    except httpx.HTTPError as e:
        raise PushError(f"No se pudo conectar a {url}: {e}") from e
    return resp.json()


def _leer_productos() -> list[dict]:
    with db.get_connection() as conn:
        try:
            filas = conn.execute(
                "SELECT id_advertys, nombre, anunciante, categoria, marca FROM productos"
            ).fetchall()
        except sqlite3.OperationalError:  # tabla inexistente: todavia no se corrio el ingest
            return []
    return [dict(fila) for fila in filas]


def push_productos() -> int:
    registros = _leer_productos()
    if not registros:
        print("No hay productos locales (correr python -m modules.productos.export y .ingest primero): se saltea.")
        return 0
    data = _post("/api/sync/productos", registros)
    cantidad = data.get("cantidad", len(registros))
    print(f"OK: {cantidad} productos sincronizados hacia {OT_SYNC_URL.rstrip('/')}/api/sync/productos")
    return cantidad


def push() -> int:
    if not OT_SYNC_URL or not OT_SYNC_TOKEN:
        raise PushError("Completa OT_SYNC_URL y OT_SYNC_TOKEN en el .env de la raiz del repo.")

    registros = _leer_ordenes_trabajo()
    if not registros:
        print("No hay registros en ordenes_trabajo local (correr el ingest de ordenes_trabajo primero).")
        return 0

    data = _post("/api/sync/ordenes-trabajo", registros)
    cantidad = data.get("cantidad", len(registros))
    print(f"OK: {cantidad} ordenes de trabajo sincronizadas hacia {OT_SYNC_URL.rstrip('/')}/api/sync/ordenes-trabajo")
    return cantidad


def main():
    try:
        push()
        push_productos()
    except PushError as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
