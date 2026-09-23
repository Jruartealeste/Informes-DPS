"""
Script de RECONOCIMIENTO (no escribe nada en Advertys): abre el
formulario "Nuevo" de Orden Trabajo, selecciona un Anunciante real (mismo
flujo que crear_ot.py::seleccionar_anunciante) y releva las opciones del
combo Producto -- depende en cascada del Anunciante elegido, por eso
explore_nueva_ot.py (que lo releva ANTES de tocar Anunciante) siempre lo
vio vacio.

Motivo: confirmado 2026-09-23 en la primera corrida real de crear_ot.py
que Advertys exige completar Producto para poder Guardar una OT (ver
ot/CLAUDE.md, "Decisiones confirmadas con Javier (2026-09-23)") --
contradice el relevamiento original que asumia que quedaba siempre sin
completar. Como el catalogo de Productos es propio de cada Anunciante (no
hay un combo fijo global), hay que relevarlo cliente por cliente a medida
que se necesite -- este script arranca por ALUAR y guarda el resultado en
`productos_por_anunciante.json` (mismo directorio), que despues consume
`crear_ot.py` para validar el parametro `producto`.

Nunca clickea Guardar: abre el formulario, elige el Anunciante, lee el
combo Producto y cierra navegando fuera sin persistir nada.

Uso:
    python -m modules.ordenes_trabajo.explore_producto_por_anunciante "<anunciante>"

Ejemplo:
    python -m modules.ordenes_trabajo.explore_producto_por_anunciante "ALUAR"
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from modules.ordenes_trabajo.crear_ot import OT_LIST_URL_SUFFIX, CrearOtError, seleccionar_anunciante, shot
from modules.ordenes_trabajo.explore_nueva_ot import relevar_opciones_combo
from tools.advertys_session import AdvertysLoginError, base_url, esperar_postback, login

CATALOGO_PATH = Path(__file__).parent / "productos_por_anunciante.json"


def main():
    if len(sys.argv) < 2:
        print('Uso: python -m modules.ordenes_trabajo.explore_producto_por_anunciante "<anunciante>"')
        sys.exit(1)
    busqueda = sys.argv[1]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            try:
                login(page)
            except AdvertysLoginError as e:
                print(f"ERROR: {e}")
                sys.exit(1)

            direct_url = f"{base_url()}{OT_LIST_URL_SUFFIX}"
            page.goto(direct_url, wait_until="networkidle", timeout=30000)
            esperar_postback(page)

            print("Abriendo formulario 'Nuevo' (no se guarda nada)...")
            nuevo_btn = page.locator('a[title="Nuevo"], span:has-text("Nuevo")').first
            if nuevo_btn.count() == 0:
                print("ERROR: no se encontro el boton 'Nuevo'.")
                sys.exit(1)
            nuevo_btn.click()
            esperar_postback(page)

            print(f"Buscando Anunciante: {busqueda!r}")
            try:
                anunciante_resuelto = seleccionar_anunciante(page, busqueda)
            except CrearOtError as e:
                print(f"ERROR: {e}")
                shot(page, "explore_producto_error_anunciante")
                sys.exit(1)
            print(f"  Anunciante seleccionado: {anunciante_resuelto}")

            print("Relevando opciones de Producto (combo en cascada)...")
            opciones_crudas = relevar_opciones_combo(page, "dviProducto")
            # La primera fila suele ser un artefacto del virtual-scroll del
            # combo (todas las opciones concatenadas en un solo td, separadas
            # por salto de linea) -- mismo quirk documentado en
            # crear_ot.py::seleccionar_combo. Se descarta por no ser una
            # opcion real seleccionable.
            opciones = [o for o in opciones_crudas if "\n" not in o]
            print(f"  {len(opciones)} productos encontrados:")
            for o in opciones:
                print(f"   - {o}")

            catalogo = {}
            if CATALOGO_PATH.exists():
                catalogo = json.loads(CATALOGO_PATH.read_text(encoding="utf-8"))
            catalogo[anunciante_resuelto] = opciones
            CATALOGO_PATH.write_text(
                json.dumps(catalogo, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8"
            )
            print(f"OK: guardado en {CATALOGO_PATH}")

            print("Cerrando SIN guardar (navegando fuera del formulario)...")
            page.goto(direct_url, wait_until="networkidle", timeout=30000)
            esperar_postback(page)
        finally:
            browser.close()


if __name__ == "__main__":
    main()
