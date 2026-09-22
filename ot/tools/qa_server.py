"""Servidor descartable de QA visual/funcional para las pantallas de `ot/`.

Nunca toca el `.env` real ni la base de Neon: usa un sqlite propio en
`tools/.qa_data/qa_ot.db` (gitignorado via el `*.db` de `ot/.gitignore`) y
una sesión Google OAuth simulada (mismo mecanismo de cookie firmada que
`tests/conftest.py::cookie_sesion`) para poder navegar sin login real.

Los datos son los ~30 OT/tareas reales de `scripts/seed.py` (misma fuente
que ya se usa para probar la app en desarrollo) — variedad real de estados,
OT ambiguas ("4086/4110", "sin número") y OT que comparten
`numero_ot_advertys` ("4134"/hermana), útil para ejercitar tanto la lista de
tareas como las vistas de `ordenes_trabajo/` (detalle + reasignar).

Uso (normalmente vía `preview_start({name: "ot-qa"})`, ver
`.claude/launch.json`):
    python tools/qa_server.py [--reset]

`--reset` borra el sqlite existente y vuelve a sembrar desde cero — usarlo
después de un cambio de modelo/migración para no arrastrar un schema viejo.
Una vez arriba, entrar por http://127.0.0.1:8123/auth/qa-login (setea la
sesión y redirige a /ordenes-trabajo) en vez de /auth/login real.
"""
import os
import sys
from pathlib import Path

OT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(__file__).resolve().parent / ".qa_data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "qa_ot.db"

if "--reset" in sys.argv and DB_PATH.exists():
    DB_PATH.unlink()

sys.path.insert(0, str(OT_DIR))
os.environ["DATABASE_URL"] = "sqlite:///" + str(DB_PATH).replace("\\", "/")
os.environ["SESSION_SECRET"] = "qa-local-secret-not-real"
os.environ["AUTH_GOOGLE_CLIENT_ID"] = "qa-client-id"
os.environ["AUTH_GOOGLE_CLIENT_SECRET"] = "qa-client-secret"
os.environ["SYNC_TOKEN"] = "qa-local-sync-token-not-real"

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.models import Cliente, Usuario  # noqa: E402

Base.metadata.create_all(engine)

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
