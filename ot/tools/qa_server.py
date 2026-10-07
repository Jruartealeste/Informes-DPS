"""Servidor descartable de QA visual/funcional para las pantallas de `ot/`.

Nunca toca el `.env` real ni la base de Neon. Por defecto usa un Postgres
local descartable en Docker (contenedor `ot-qa-pg`, 127.0.0.1:54329, levantado
con `.claude/skills/qa-ot/scripts/levantar-entorno.sh`) con el schema creado
por `alembic upgrade head` — así se prueban también las migraciones y las
diferencias Postgres/sqlite. `--sqlite` usa el sqlite viejo en
`tools/.qa_data/qa_ot.db` (gitignorado via el `*.db`). Guardarraíl: se niega
a correr si la base no es localhost. Usa una sesión Google OAuth simulada (mismo mecanismo de cookie firmada que
`tests/conftest.py::cookie_sesion`) para poder navegar sin login real.

Los datos son los ~30 OT/tareas reales de `scripts/seed.py` (misma fuente
que ya se usa para probar la app en desarrollo) — variedad real de estados,
OT ambiguas ("4086/4110", "sin número") y OT que comparten
`numero_ot_advertys` ("4134"/hermana), útil para ejercitar tanto la lista de
tareas como las vistas de `ordenes_trabajo/` (detalle + reasignar).

Uso (normalmente vía `preview_start({name: "ot-qa"})`, ver
`.claude/launch.json`):
    python tools/qa_server.py [--reset]

`--reset` borra los datos (schema public en Postgres, o el archivo sqlite) y
vuelve a migrar y sembrar desde cero — usarlo después de un cambio de
modelo/migración para no arrastrar un schema viejo.
Una vez arriba, entrar por http://127.0.0.1:8123/auth/qa-login (setea la
sesión y redirige a /ordenes-trabajo) en vez de /auth/login real.
"""
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

OT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(__file__).resolve().parent / ".qa_data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "qa_ot.db"
PG_URL = "postgresql+psycopg://postgres:qa_local_only@127.0.0.1:54329/ot_qa"

USAR_SQLITE = "--sqlite" in sys.argv
RESET = "--reset" in sys.argv
DB_URL = "sqlite:///" + str(DB_PATH).replace("\\", "/") if USAR_SQLITE else PG_URL

# Guardarraíl: nunca contra una base que no sea local.
_host = urlparse(DB_URL).hostname
if DB_URL.startswith("postgresql") and _host not in ("127.0.0.1", "localhost", "::1"):
    sys.exit(f"ABORTO: la base de QA apunta a {_host!r}, no es local.")

if RESET and USAR_SQLITE and DB_PATH.exists():
    DB_PATH.unlink()

sys.path.insert(0, str(OT_DIR))
os.environ["DATABASE_URL"] = DB_URL
os.environ["SESSION_SECRET"] = "qa-local-secret-not-real"
os.environ["AUTH_GOOGLE_CLIENT_ID"] = "qa-client-id"
os.environ["AUTH_GOOGLE_CLIENT_SECRET"] = "qa-client-secret"
os.environ["SYNC_TOKEN"] = "qa-local-sync-token-not-real"

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.models import Cliente, Usuario  # noqa: E402

if USAR_SQLITE:
    Base.metadata.create_all(engine)
else:
    from sqlalchemy import text  # noqa: E402

    try:
        if RESET:
            with engine.begin() as conn:
                conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public"))
        os.chdir(OT_DIR)
        from alembic import command  # noqa: E402
        from alembic.config import Config  # noqa: E402

        command.upgrade(Config(str(OT_DIR / "alembic.ini")), "head")
    except Exception as exc:  # base apagada, migración rota, etc.
        sys.exit(
            f"ABORTO: no pude migrar el Postgres de QA ({type(exc).__name__}: {exc}). "
            "¿Corriste .claude/skills/qa-ot/scripts/levantar-entorno.sh?"
        )

db = SessionLocal()
db_recien_creada = db.query(Cliente).first() is None
if db_recien_creada:
    from scripts.seed import main as seed_main  # noqa: E402

    seed_main()
if not db.query(Usuario).filter_by(email="qa@aleste.ar").first():
    db.add(Usuario(email="qa@aleste.ar", nombre="QA Visual"))
    db.commit()
db.close()

print("QA_DB_READY" + (" (recien sembrada)" if db_recien_creada else " (ya existia)"))

import uvicorn  # noqa: E402
from starlette.requests import Request  # noqa: E402
from starlette.responses import RedirectResponse  # noqa: E402

from app.db import SessionLocal as _SessionLocal  # noqa: E402
from app.main import app  # noqa: E402


@app.get("/auth/qa-login")
def qa_login(request: Request):
    """Solo en este servidor descartable de QA — nunca existe en el
    codebase real (no se registra en app/main.py). Simula un login ya
    hecho, mismo patrón que tests/conftest.py::client, para navegar sin
    pasar por el OAuth real de Google."""
    db = _SessionLocal()
    try:
        usuario = db.query(Usuario).filter_by(email="qa@aleste.ar").one()
        request.session["user_id"] = usuario.id
        request.session["email"] = usuario.email
        request.session["nombre"] = usuario.nombre
        request.session["rol"] = "MIEMBRO"
    finally:
        db.close()
    return RedirectResponse("/ordenes-trabajo")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8123)
