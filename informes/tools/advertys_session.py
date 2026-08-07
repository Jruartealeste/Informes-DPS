"""
Login compartido contra Advertys, reusado por los export.py productivos de
cada modulo (ver modules/<modulo>/export.py y tools/actualizar_todo.py).

Se extrajo porque el bloque de login era identico byte a byte en los 7-8
explore.py de cada modulo -- no es una abstraccion nueva, es duplicacion ya
consumada y verificada contra Advertys real. La navegacion (arbol/URL/combo
de filtro) NO se comparte aca: cada vista tiene quirks reales y distintos,
eso vive en cada modules/<modulo>/export.py.

Alcance de solo-lectura (ver salvaguarda en CLAUDE.md): esto hace login y
nada mas -- ningun click sobre Nuevo/Agregar/Editar/Guardar/Eliminar.
"""
import os

from dotenv import load_dotenv

load_dotenv()

ADVERTYS_URL = os.environ.get("ADVERTYS_URL")
ADVERTYS_USER = os.environ.get("ADVERTYS_USER")
ADVERTYS_PASSWORD = os.environ.get("ADVERTYS_PASSWORD")


class AdvertysLoginError(RuntimeError):
    """Login fallido: credenciales faltantes/incorrectas, o Advertys no
    sale de Login.aspx despues del intento."""


def esperar_postback(page, timeout=25000):
    try:
        page.wait_for_selector(".dxlpLoadingDiv", state="visible", timeout=3000)
    except Exception:
        pass
    try:
        page.wait_for_selector(".dxlpLoadingDiv", state="hidden", timeout=timeout)
    except Exception:
        pass
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass


def login(page) -> None:
    """Hace login en Advertys con las credenciales de .env. Deja `page` en
    la pantalla post-login. Levanta AdvertysLoginError si algo falla."""
    if not ADVERTYS_URL or not ADVERTYS_USER or not ADVERTYS_PASSWORD:
        raise AdvertysLoginError(
            "Completa ADVERTYS_URL, ADVERTYS_USER y ADVERTYS_PASSWORD en .env"
        )

    page.goto(ADVERTYS_URL, wait_until="networkidle", timeout=30000)

    user_input = page.locator('input[id$="xaf_dviUserName_Edit_I"]')
    pass_input = page.locator('input[id$="xaf_dviPassword_Edit_I"]')
    user_input.wait_for(state="visible", timeout=15000)

    user_input.click()
    user_input.fill(ADVERTYS_USER)
    pass_input.click()
    pass_input.fill(ADVERTYS_PASSWORD)
    pass_input.press("Enter")
    esperar_postback(page)

    if "Login.aspx" in page.url:
        login_link = page.locator('a[title="Iniciar sesión"], a[title="Iniciar sesion"]')
        if login_link.count() > 0:
            login_link.first.click(force=True, timeout=10000)
            esperar_postback(page)

    if "Login.aspx" in page.url:
        raise AdvertysLoginError("No se pudo hacer login. Revisa usuario/contraseña en .env")


def base_url() -> str:
    """URL base (sin 'Login.aspx') para armar navegacion directa por
    ViewID, igual que ya hacian los explore.py de Estimados/OC/OT."""
    return ADVERTYS_URL.split("Login.aspx")[0]
