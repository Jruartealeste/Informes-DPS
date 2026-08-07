from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routers import ordenes_trabajo, tareas

app = FastAPI(title="Órdenes de trabajo")

app.mount(
    "/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static"
)

app.include_router(tareas.router)
app.include_router(ordenes_trabajo.router)
