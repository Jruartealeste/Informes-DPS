"""Carga los 6 Anunciantes con los que se esta trabajando actualmente en la
base de PRODUCCION -- un proyecto Neon nuevo y limpio, a proposito separado
de cualquier dato de dev/QA (lee DATABASE_URL de ot/.env.prod, nunca de
ot/.env). Solo carga `clientes`/`cliente_anunciantes` (entidades reales) --
nunca tareas ni ot_interna, para no ensuciar la base limpia con nada de
prueba.

Anunciantes reales relevados en modo lectura contra la tabla maestra
"Clientes" de Advertys (2026-09-25, ver ot/CLAUDE.md). Fundacion Aurora
Austral no tiene ningun Anunciante real cargado en Advertys todavia
(confirmado, no se inventa un valor) -- se crea el Cliente igual, sin fila
en cliente_anunciantes.

Idempotente: usa ON CONFLICT DO NOTHING, se puede correr mas de una vez sin
duplicar nada.

Uso (parado en ot/):
    python -m scripts.cargar_anunciantes_prod_20260925
"""
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import create_engine, text

ENV_PROD = Path(__file__).resolve().parent.parent / ".env.prod"

CLIENTES = {
    "ALUAR": "ALUAR ALUMINIO ARGENTINO SOCIEDAD ANONIM",
    # Fundacion Aurora Austral ya existia como Cliente "FAA" -- no se repite
    # acá (ver limpieza del duplicado mas abajo, correccion puntual del
    # 2026-09-28).
    "INFA": "Infa S.A.",
    "Consultatio": "CONSULTATIO S.A.",
    "Gihon": "GIHON - LABORATORIOS QUIMICOS SRL",
    "INCAA": "INCAA",
}


def limpiar_duplicado_faa(conn) -> None:
    """Correccion puntual (2026-09-28): una corrida anterior de este script
    creo un Cliente "Fundacion Aurora Austral" (con un problema de encoding
    de paso) que duplica al "FAA" que ya existia. Borra ese duplicado si
    existe y no tiene nada real colgado (ni cliente_anunciantes ni
    ot_interna) -- si tuviera algo, no toca nada y avisa."""
    dup = conn.execute(
        text("SELECT id, nombre FROM clientes WHERE nombre LIKE 'Fundaci%Aurora Austral' AND nombre <> 'FAA'")
    ).fetchall()
    for row in dup:
        n_ot = conn.execute(
            text("SELECT count(*) FROM ot_interna WHERE cliente_id = :id"), {"id": row.id}
        ).scalar()
        n_anun = conn.execute(
            text("SELECT count(*) FROM cliente_anunciantes WHERE cliente_id = :id"), {"id": row.id}
        ).scalar()
        if n_ot or n_anun:
            print(f"NO se borra Cliente id={row.id} ({row.nombre!r}): tiene {n_ot} ot_interna / {n_anun} anunciantes colgando.")
            continue
        conn.execute(text("DELETE FROM clientes WHERE id = :id"), {"id": row.id})
        print(f"Borrado duplicado: Cliente id={row.id} ({row.nombre!r}).")


def main() -> None:
    database_url = dotenv_values(ENV_PROD)["DATABASE_URL"]
    engine = create_engine(database_url)
    with engine.begin() as conn:
        limpiar_duplicado_faa(conn)
        for nombre in CLIENTES:
            conn.execute(
                text("INSERT INTO clientes (nombre) VALUES (:nombre) ON CONFLICT (nombre) DO NOTHING"),
                {"nombre": nombre},
            )
        for nombre, anunciante in CLIENTES.items():
            if anunciante is None:
                continue
            conn.execute(
                text(
                    "INSERT INTO cliente_anunciantes (cliente_id, anunciante) "
                    "SELECT id, :anunciante FROM clientes WHERE nombre = :nombre "
                    "ON CONFLICT (cliente_id, anunciante) DO NOTHING"
                ),
                {"nombre": nombre, "anunciante": anunciante},
            )
        rows = conn.execute(
            text(
                "SELECT c.nombre, a.anunciante FROM clientes c "
                "LEFT JOIN cliente_anunciantes a ON a.cliente_id = c.id "
                "ORDER BY c.nombre, a.anunciante"
            )
        ).fetchall()

    print("Estado final de clientes/anunciantes en produccion:")
    for r in rows:
        print(" ", r.nombre, "->", r.anunciante)


if __name__ == "__main__":
    main()
