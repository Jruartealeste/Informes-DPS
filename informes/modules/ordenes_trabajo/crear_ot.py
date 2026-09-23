"""
Script de ESCRITURA en Advertys (ver salvaguarda "Advertys es de solo
lectura" en CLAUDE.md). Crea el ENCABEZADO de una OT nueva -- mismo
criterio que crear_estimado.py/cerrar_ot.py, unicos otros scripts de
escritura del proyecto.

ADVERTENCIA: no correr esto por primera vez contra Advertys real sin
confirmacion explicita de Javier -- no hay ambiente de prueba, cualquier
alta real es una OT real. No se corre como parte de ningun flujo
automatico (ni actualizar_todo, ni un cron).

Releva por explore_nueva_ot.py (2026-09-22, ver ot/CLAUDE.md "Decisiones
confirmadas con Javier (2026-09-22)"):

- Nro OT, Estado, F.Abierta, Abierta por: los autogenera Advertys, no se
  tocan.
- Negocio: combo con una sola opcion real ("PRODUCCION"), ya viene
  preseleccionado -- no se toca.
- Resumen: texto libre.
- Anunciante: NO es un combo simple, es un lookup con boton de busqueda
  (icono lupa) que abre un popup en un iframe propio (`Dialog=true` en la
  URL) con un buscador (mismo widget generico que buscar_texto() de
  crear_estimado.py, aunque aca el "Texto a buscar..." es un NullText
  visual, no el .value real del input) y una grilla de resultados
  (Id Anunciante / Nombre). Si la busqueda no devuelve exactamente una
  fila (o una fila con Nombre exacto entre varias), se corta con error --
  nunca se asume cual eligio el usuario.
- Producto depende del Anunciante elegido (cascada, vacio hasta ese
  momento) -- la decision original (Javier, 2026-09-22) era dejarlo SIN
  completar, pero la primera corrida real (2026-09-23, ver ot/CLAUDE.md
  "Decisiones confirmadas con Javier (2026-09-23)") mostro que Advertys
  exige completarlo para poder Guardar: "Falta Producto". Ahora es
  **obligatorio**, y se valida (si el Anunciante ya esta relevado) contra
  el catalogo por-cliente en `productos_por_anunciante.json` (mismo
  directorio), poblado a mano con
  `explore_producto_por_anunciante.py` cliente por cliente -- arranca con
  ALUAR, se suma el resto a medida que haga falta.
- Contacto Anunciante tambien depende del Anunciante (cascada) y queda
  SIN completar -- decision Javier (2026-09-22): se carga a mano en
  Advertys si hace falta, igual que los items de Estimados.
- Tag tambien queda siempre sin completar (decision Javier, 2026-09-22).
- Centro Costo es un combo fijo de 4 valores (ADMINISTRACION,
  AGENCIA - ESTRUCTURA, CREATIVIDAD - PRODUCCION, MEDIOS) -- **obligatorio**,
  se pide siempre como parametro (decision Javier, 2026-09-22: sin default
  seguro, lo elige quien genera la OT en el momento).
- Equipo es otro combo fijo (ALUAR-LA RESPUESTA, Area Beta, Equipo
  Grafica, Riadigos) pero es **opcional** (decision Javier, 2026-09-22):
  si no se pasa, se deja en N / D.

El numero de OT nuevo se lee directamente del campo Nro OT despues de
"Guardar" (deja de ser "0" y pasa a ser el numero real asignado por
Advertys) -- a diferencia de crear_estimado.py, ese campo esta en la
misma pagina asi que no hace falta comparar grillas antes/despues.

Uso:
    python -m modules.ordenes_trabajo.crear_ot "<anunciante>" "<resumen>" "<producto>" "<centro_costo>" [--equipo "<equipo>"]

Ejemplo:
    python -m modules.ordenes_trabajo.crear_ot "ALUAR" "Campaña institucional Setiembre" "INSTITUCIONAL" "CREATIVIDAD - PRODUCCION"
"""
import argparse
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from tools.advertys_session import AdvertysLoginError, base_url, esperar_postback, login

CATALOGO_PRODUCTOS_PATH = Path(__file__).parent / "productos_por_anunciante.json"

OUT_DIR = Path("exploracion")
OUT_DIR.mkdir(exist_ok=True)
SCREENSHOT_DIR = OUT_DIR / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)

OT_LIST_URL_SUFFIX = "Default.aspx#ViewID=OrdenTrabajo_ListView&ObjectClassName=DPS_SAS_SR.Module.OrdenTrabajo"

CENTROS_COSTO_VALIDOS = [
    "ADMINISTRACION",
    "AGENCIA - ESTRUCTURA",
    "CREATIVIDAD - PRODUCCION",
    "MEDIOS",
]


class CrearOtError(RuntimeError):
    pass


def shot(page, nombre):
    destino = SCREENSHOT_DIR / f"{nombre}.png"
    page.screenshot(path=str(destino), full_page=True)
    print(f"  -> {destino}")


def click_boton_visible(page_or_frame, texto, timeout=5000):
    """Clickea el primer elemento VISIBLE con este texto exacto. Mismo
    helper que cerrar_ot.py/crear_estimado.py -- sirve tanto para `page`
    como para un `Frame`."""
    candidatos = page_or_frame.get_by_text(texto, exact=True)
    for i in range(candidatos.count()):
        cand = candidatos.nth(i)
        try:
            if cand.is_visible():
                cand.click(timeout=timeout)
                return True
        except Exception:
            continue
    return False


def seleccionar_combo(page, campo: str, texto_opcion: str):
    """Abre un ASPxComboBox (dviCentroCosto, dviEquipo, etc.) y clickea la
    opcion cuyo texto matchea exacto. La primera fila de la lista suele ser
    un artefacto del virtual-scroll (todas las opciones concatenadas en un
    solo td) -- el match exacto la descarta sola."""
    input_loc = page.locator(f"input[id$='_xaf_{campo}_Edit_dropdown_DD_I']")
    if input_loc.count() == 0:
        raise CrearOtError(f"No se encontro el combo {campo} en el formulario.")
    input_id = input_loc.first.get_attribute("id")
    boton_id = input_id.replace("_DD_I", "_DD_B-1")
    page.locator(f"#{boton_id}").click(timeout=5000)
    page.wait_for_timeout(600)

    lista_id = input_id.replace("_DD_I", "_DD_DDD_L")
    filas = page.locator(f"#{lista_id} td")
    for i in range(filas.count()):
        if filas.nth(i).inner_text().strip() == texto_opcion:
            filas.nth(i).click()
            page.wait_for_timeout(400)
            return
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    raise CrearOtError(f"'{texto_opcion}' no esta entre las opciones disponibles de {campo}.")


def seleccionar_anunciante(page, busqueda: str) -> str:
    """Abre el popup de busqueda de Anunciante, busca `busqueda`, exige
    exactamente un resultado (o un match exacto de Nombre entre varios) y
    lo confirma con "Aceptar". Devuelve el Nombre tal como quedo cargado en
    el formulario."""
    boton = page.locator("td[id$='_xaf_dviAnunciante_Edit_find_Edit_B0']")
    if boton.count() == 0:
        raise CrearOtError("No se encontro el boton de busqueda de Anunciante.")
    boton.first.click(timeout=5000)
    page.wait_for_timeout(1000)

    frame = None
    for f in page.frames:
        if "Dialog=true" in f.url:
            frame = f
            break
    if frame is None:
        shot(page, "crear_ot_error_sin_popup_anunciante")
        raise CrearOtError("No se encontro el popup de busqueda de Anunciante (revisar si cambio la estructura).")

    campo_busqueda = frame.locator("input[id$='_Ed_I']").first
    if campo_busqueda.count() == 0:
        raise CrearOtError("No se encontro el buscador dentro del popup de Anunciante.")
    campo_busqueda.click()
    campo_busqueda.fill(busqueda)
    campo_busqueda.press("Enter")
    page.wait_for_timeout(1200)

    filas = frame.locator("tr[id*='DXDataRow']")
    n = filas.count()
    if n == 0:
        raise CrearOtError(f"No se encontro ningun Anunciante para '{busqueda}'.")

    fila = filas.first
    if n > 1:
        objetivo = busqueda.strip().upper()
        exactas = [
            i for i in range(n)
            if filas.nth(i).inner_text().strip().splitlines()[-1].strip().upper() == objetivo
        ]
        if len(exactas) != 1:
            raise CrearOtError(
                f"'{busqueda}' matcheo {n} Anunciantes y ninguno matchea exacto -- "
                "revisar a mano en Advertys antes de reintentar."
            )
        fila = filas.nth(exactas[0])

    fila.click(timeout=5000)
    page.wait_for_timeout(400)

    # El click en la fila puede dejar el popup esperando un click en
    # "Aceptar" (como asumia el relevamiento original), o puede disparar el
    # postback y cerrar el iframe solo -- confirmado 2026-09-23 en la
    # primera corrida real contra Advertys: el frame quedo detached antes
    # de llegar a buscar "Aceptar", cortando el script con un error de
    # Playwright en vez de uno de negocio. Se toleran ambos casos y se
    # valida el resultado real releyendo el campo del formulario principal.
    try:
        click_boton_visible(frame, "Aceptar")
    except Exception:
        pass
    esperar_postback(page)
    page.wait_for_timeout(800)

    valor = page.locator("input[id$='_xaf_dviAnunciante_Edit_find_Edit_I']").first.input_value()
    if not valor or valor.strip() in ("", "N / D"):
        shot(page, "crear_ot_error_anunciante_no_confirmado")
        raise CrearOtError("El Anunciante no quedo seleccionado tras el popup (sigue en N / D).")
    return valor.strip()


def _validar_producto(anunciante: str, producto: str) -> None:
    """Valida `producto` contra el catalogo por-cliente relevado a mano
    (ver explore_producto_por_anunciante.py). Si el Anunciante todavia no
    esta relevado ahi, no bloquea -- deja que Advertys sea la ultima
    palabra y avisa por consola, en vez de impedir altas de clientes
    nuevos por falta de relevamiento previo."""
    if not producto.strip():
        raise CrearOtError("El producto no puede estar vacio.")
    if not CATALOGO_PRODUCTOS_PATH.exists():
        print(f"  (aviso: no existe {CATALOGO_PRODUCTOS_PATH.name}, no se valida Producto contra un catalogo)")
        return
    catalogo = json.loads(CATALOGO_PRODUCTOS_PATH.read_text(encoding="utf-8"))
    opciones = catalogo.get(anunciante)
    if opciones is None:
        print(f"  (aviso: '{anunciante}' todavia no esta relevado en {CATALOGO_PRODUCTOS_PATH.name}, no se valida Producto)")
        return
    if producto not in opciones:
        raise CrearOtError(
            f"Producto '{producto}' invalido para '{anunciante}'. Opciones relevadas: {', '.join(opciones)}"
        )


def crear_ot(
    anunciante: str,
    resumen: str,
    producto: str,
    centro_costo: str,
    equipo: str | None = None,
) -> str:
    """Crea el encabezado de una OT nueva en Advertys. Devuelve el numero
    de OT nuevo (str), leido del campo Nro OT tras Guardar."""
    if not resumen.strip():
        raise CrearOtError("El resumen no puede estar vacio.")
    if centro_costo not in CENTROS_COSTO_VALIDOS:
        raise CrearOtError(
            f"Centro Costo '{centro_costo}' invalido. Opciones: {', '.join(CENTROS_COSTO_VALIDOS)}"
        )
    if not producto.strip():
        raise CrearOtError("El producto no puede estar vacio.")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            try:
                login(page)
            except AdvertysLoginError as e:
                raise CrearOtError(str(e)) from e

            direct_url = f"{base_url()}{OT_LIST_URL_SUFFIX}"
            page.goto(direct_url, wait_until="networkidle", timeout=30000)
            esperar_postback(page)

            print("Abriendo formulario 'Nuevo'...")
            nuevo_btn = page.locator('a[title="Nuevo"], span:has-text("Nuevo")').first
            if nuevo_btn.count() == 0:
                raise CrearOtError("No se encontro el boton 'Nuevo' en el listado de OT.")
            nuevo_btn.click()
            esperar_postback(page)
            shot(page, "crear_ot_00_formulario")

            print(f"Completando Resumen: {resumen!r}")
            page.locator("input[id$='_xaf_dviNombre_Edit_I']").first.fill(resumen.strip())

            print(f"Buscando Anunciante: {anunciante!r}")
            anunciante_resuelto = seleccionar_anunciante(page, anunciante)
            print(f"  Anunciante seleccionado: {anunciante_resuelto}")

            _validar_producto(anunciante_resuelto, producto)
            print(f"Seleccionando Producto: {producto!r}")
            seleccionar_combo(page, "dviProducto", producto)

            print(f"Seleccionando Centro Costo: {centro_costo!r}")
            seleccionar_combo(page, "dviCentroCosto", centro_costo)

            if equipo:
                print(f"Seleccionando Equipo: {equipo!r}")
                seleccionar_combo(page, "dviEquipo", equipo)

            shot(page, "crear_ot_01_completado")

            print("Clickeando 'Guardar'...")
            if not click_boton_visible(page, "Guardar"):
                raise CrearOtError("No se encontro el boton 'Guardar'.")
            esperar_postback(page)
            page.wait_for_timeout(1000)
            shot(page, "crear_ot_02_guardado")

            numero = page.locator("input[id$='_xaf_dviNroOrdenTrabajo_Edit_I']").first.input_value()
            if not numero or numero.strip() in ("", "0"):
                raise CrearOtError(
                    "No se pudo confirmar el numero de OT nuevo tras Guardar -- revisar a mano en Advertys "
                    "(ver captura crear_ot_02_guardado.png)."
                )

            numero = numero.strip()
            print(f"OK: OT {numero} creada (Anunciante: {anunciante_resuelto}, Resumen: {resumen!r}).")
            return numero
        finally:
            browser.close()


def main():
    parser = argparse.ArgumentParser(
        description="Crea el encabezado de una OT nueva en Advertys (alta, nunca items/estimados)"
    )
    parser.add_argument("anunciante", help="Texto a buscar en el popup de Anunciante (ej. 'ALUAR')")
    parser.add_argument("resumen", help="Texto del campo Resumen")
    parser.add_argument(
        "producto",
        help="Depende del Anunciante (cascada) -- ver productos_por_anunciante.json para los clientes ya relevados",
    )
    parser.add_argument(
        "centro_costo",
        help=f"Uno de: {', '.join(CENTROS_COSTO_VALIDOS)}",
    )
    parser.add_argument("--equipo", default=None, help="Opcional -- uno de los equipos ya cargados en Advertys")
    args = parser.parse_args()

    try:
        numero = crear_ot(args.anunciante, args.resumen, args.producto, args.centro_costo, args.equipo)
    except CrearOtError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    print(f"Numero de OT: {numero}")


if __name__ == "__main__":
    main()
