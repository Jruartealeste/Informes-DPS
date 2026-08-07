# OTs — quickstart

Primer corte: modelo de datos + CRUD de tareas + pantalla **Tareas** con el
diseño de `Seguimiento de órdenes de trabajo/design_handoff_ots/`. Sin auth,
sin sync real a Advertys todavía — ver `CLAUDE.md` para el alcance completo
y el roadmap.

## Setup

```
cd ot
python -m venv .venv
.venv\Scripts\activate          # PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
copy .env.example .env          # completar DATABASE_URL con la rama de dev de Neon
```

## Migraciones y datos de prueba

```
alembic upgrade head
python -m scripts.seed          # carga las ~30 tareas reales de ALUAR (ver scripts/seed.py)
```

## Correr la app

```
uvicorn app.main:app --reload
```

Abrir http://127.0.0.1:8000/tareas — comparar contra
`Seguimiento de órdenes de trabajo/design_handoff_ots/design/Seguimiento de OTs.dc.html`
(dark/light, densidad compacta/cómoda) antes de dar por cerrada cualquier
etapa visual.

## Tests

```
pytest
```

Los tests corren contra SQLite en memoria (no necesitan la conexión a Neon).
