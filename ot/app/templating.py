from pathlib import Path

from fastapi.templating import Jinja2Templates

STATIC_DIR = Path(__file__).parent / "static"

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


def static_version(rel_path: str) -> int:
    """mtime de un archivo estático, para invalidar el cache del browser en cada
    cambio (StaticFiles no manda Cache-Control propio; sin esto, un CSS editado
    puede quedar cacheado con contenido viejo hasta un hard-refresh manual)."""
    try:
        return int((STATIC_DIR / rel_path).stat().st_mtime)
    except FileNotFoundError:
        return 0


templates.env.globals["static_version"] = static_version
