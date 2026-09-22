"""
Script de ESCRITURA en Advertys (ver salvaguarda "Advertys es de solo
lectura" en CLAUDE.md). Alcance aprobado explicitamente por Javier
(2026-09-21, ver ot/CLAUDE.md "Decisiones confirmadas con Javier
(2026-09-21) -- Estimados de Costo"): crea el ENCABEZADO de un Estimado de
Costo dentro de una OT ya existente en Advertys -- solo los 3 campos que
releva explore_nuevo_estimado.py (Fecha Solicitada, Fecha Analisis,
Titulo). Los items del Estimado (lineas de costo/proveedor) NO se
automatizan: siguen siendo 100% manuales en Advertys, misma decision.

ADVERTENCIA: antes de correr esto por primera vez contra una OT real, pedir
confirmacion explicita a Javier -- mismo criterio que crear_ot.py (sin
construir todavia) y cerrar_ot.py (unico otro script de escritura del
proyecto). No se corre como parte de ningun flujo automatico (ni
actualizar_todo, ni un cron).

Flujo (identico al relevado por explore_nuevo_estimado.py sobre la OT 289,
2026-09-18, confirmado que la grilla no cambio en esa corrida de solo
lectura): listado de OT -> abrir la OT -> pestana "Estimados Costo" ->
boton "Nuevo Estimado"/"Nuevo" -> completar el popup "Agregar Estimado"
(los 3 campos viven en un iframe propio del popup, hay que ubicarlo por
texto -- `document.querySelectorAll` sobre la pagina principal no los
encuentra) -> "Aceptar". El numero de Estimado nuevo lo asigna Advertys al
aceptar -- el popup no lo muestra, asi que este script lo recupera
comparando la columna N° de la grilla de Estimados antes/despues del
alta.

Nunca clickea nada mas que "Nuevo"/"Nuevo Estimado" y "Aceptar" -- ningun
Editar/Eliminar/cambio de estado de un estimado existente.

Pendiente (decision de Javier, 2026-09-22): como dispara esto el boton
"Generar Estimado en Advertys" de ot/ todavia no esta definido -- por ahora
este script se corre a mano, igual que cerrar_ot.py, y el numero de
Estimado resultante se carga a mano en ot/ (`Estimado.numero_estimado`).
Ver roadmap item 9 en ot/CLAUDE.md.

Uso:
    python -m modules.estimados_costos.crear_estimado <numero_ot> "<titulo>"
    python -m modules.estimados_costos.crear_estimado <numero_ot> "<titulo>" --fecha-analisis 1/9/2026
"""
import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from tools.advertys_session import AdvertysLoginError, base_url, esperar_postback, login

OUT_DIR = Path("exploracion")
OUT_DIR.mkdir(exist_ok=True)
SCREENSHOT_DIR = OUT_DIR / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)

OT_LIST_URL_SUFFIX = "Default.aspx#ViewID=OrdenTrabajo_ListView&ObjectClassName=DPS_SAS_SR.Module.OrdenTrabajo"

# Umbral de higiene de datos (mismo gotcha documentado en
# modules/ordenes_trabajo/cerrar_ot.py::UMBRAL_MUCHOS_ESTIMADOS): la
# pestana "Estimados Costo" de una OT pagina de a 20 filas. Si el Estimado
# nuevo no aparece en la grilla tras el alta, la causa mas probable es que
# esta OT ya tenia >=20 estimados y el nuevo cayo en la pagina 2+, no que
# el alta haya fallado.
UMBRAL_MUCHOS_ESTIMADOS = 20


class CrearEstimadoError(RuntimeError):
    pass


def shot(page, nombre):
    destino = SCREENSHOT_DIR / f"{nombre}.png"
    page.screenshot(path=str(destino), full_page=True)
    print(f"  -> {destino}")


def click_boton_visible(page_or_frame, texto, timeout=5000):
    """Clickea el primer elemento VISIBLE con este texto exacto (evita
    matchear items de menu lateral / opciones ocultas con el mismo texto).
    Mismo helper que cerrar_ot.py/explore_nuevo_estimado.py. Sirve tanto
    para `page` como para un `Frame` (misma API de locators)."""
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


def buscar_texto(page, texto):
    inputs = page.locator("input[id$='_Ed_I']")
    for i in range(inputs.count()):
        inp = inputs.nth(i)
        try:
            valor = inp.input_value(timeout=500)
        except Exception:
            continue
        if valor.strip() == "Texto a buscar...":
            inp.click()
            inp.fill(str(texto))
            inp.press("Enter")
            return True
    return False


def abrir_combo_filtro(page):
    inputs = page.locator("input[id$='_Cb_I']")
    for i in range(inputs.count()):
        inp = inputs.nth(i)
        try:
            valor = inp.input_value(timeout=500)
        except Exception:
            continue
        if valor.strip() in ("Mes Actual", "Abiertas"):
            btn_id = inp.get_attribute("id").replace("_Cb_I", "_Cb_B-1")
            page.locator(f"#{btn_id}").click(timeout=3000)
            return True
    return False


def ir_a_ot(page, numero_ot):
    """Identico a explore_nuevo_estimado.py::ir_a_ot / cerrar_ot.py::ir_a_ot
    -- listado de OT, filtro 'Todas', buscar por numero exacto, click en la
    fila para abrir el detalle."""
    direct_url = f"{base_url()}{OT_LIST_URL_SUFFIX}"
    page.goto(direct_url, wait_until="networkidle", timeout=30000)
    esperar_postback(page)
    page.wait_for_timeout(800)

    if abrir_combo_filtro(page):
        page.wait_for_timeout(500)
        item = page.get_by_text("Todas", exact=True)
        if item.count() > 0:
            item.first.click(timeout=3000)
            esperar_postback(page)
        else:
            page.keyboard.press("Escape")
        page.wait_for_timeout(500)

    if not buscar_texto(page, numero_ot):
        raise CrearEstimadoError("No se encontro el buscador 'Texto a buscar...'")
    esperar_postback(page)
    page.wait_for_timeout(800)

    fila = page.get_by_text(str(numero_ot), exact=True)
    if fila.count() == 0:
        raise CrearEstimadoError(f"No se encontro la OT {numero_ot} en la grilla")
    fila.first.click(timeout=5000)
    esperar_postback(page)
    page.wait_for_timeout(800)


def frame_del_popup(page):
    """Mismo criterio que explore_nuevo_estimado.py: el dialogo 'Agregar
    Estimado' se renderiza en un iframe propio -- se ubica buscando el
    frame que contiene 'Fecha Solicitada'. Devuelve `page` si no se
    encuentra ninguno (senal de que la estructura del popup cambio)."""
    for frame in page.frames:
        try:
            if frame.get_by_text("Fecha Solicitada", exact=False).count() > 0:
                return frame
        except Exception:
            continue
    return page


def leer_numeros_estimado(page) -> set[str]:
    """Lee la primera celda (columna N°) de cada fila de la grilla de
    Estimados Costo actualmente visible en la pestana. Se usa para detectar
    por diferencia el numero que Advertys le asigna al Estimado nuevo -- el
    popup de alta no lo muestra en ningun campo."""
    tablas = page.locator("table[id*='DXMainTable']")
    tabla = None
    for i in range(tablas.count()):
        candidata = tablas.nth(i)
        try:
            if candidata.is_visible():
                tabla = candidata
                break
        except Exception:
            continue
    if tabla is None:
        return set()

    filas_loc = tabla.locator("tr[id*='DXDataRow']")
    numeros = set()
    for i in range(filas_loc.count()):
        celdas = filas_loc.nth(i).locator("td")
        if celdas.count() == 0:
            continue
        texto = celdas.nth(0).inner_text().strip()
        if texto:
            numeros.add(texto)
    return numeros


def crear_estimado(
    numero_ot: str,
    titulo: str,
    fecha_solicitada: str | None = None,
    fecha_analisis: str | None = None,
) -> str:
    """Crea el encabezado de un Estimado de Costo en la OT `numero_ot`.
    Fecha Solicitada/Analisis quedan en el default de Advertys (hoy) si no
    se pasan explicitamente. Devuelve el numero de Estimado nuevo (str)."""
    if not titulo.strip():
        raise CrearEstimadoError("El titulo no puede estar vacio.")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(accept_downloads=True)
        try:
            try:
                login(page)
            except AdvertysLoginError as e:
                raise CrearEstimadoError(str(e)) from e

            print(f"Navegando a OT {numero_ot}...")
            ir_a_ot(page, numero_ot)

            print("Abriendo pestana 'Estimados Costo'...")
            if not click_boton_visible(page, "Estimados Costo"):
                raise CrearEstimadoError("No se encontro la pestana 'Estimados Costo' en esta OT.")
            esperar_postback(page)
            page.wait_for_timeout(800)

            numeros_antes = leer_numeros_estimado(page)
            hay_muchos_estimados = len(numeros_antes) >= UMBRAL_MUCHOS_ESTIMADOS
            shot(page, f"crear_est_{numero_ot}_00_antes")

            print("Abriendo 'Nuevo Estimado'...")
            nuevo_btn = page.locator('a[title="Nuevo Estimado"], a[title="Nuevo"]').first
            if nuevo_btn.count() > 0:
                nuevo_btn.click()
            elif not click_boton_visible(page, "Nuevo Estimado"):
                raise CrearEstimadoError("No se encontro un boton 'Nuevo Estimado' visible en esta pestana.")
            esperar_postback(page)
            page.wait_for_timeout(800)

            frame = frame_del_popup(page)
            if frame is page:
                shot(page, f"crear_est_{numero_ot}_01_error_sin_popup")
                raise CrearEstimadoError("No se encontro el popup 'Agregar Estimado' (revisar si cambio la estructura).")

            if fecha_solicitada:
                campo = frame.locator("input[id$='_xaf_dviFechaSolicitada_Edit_I']")
                campo.click()
                campo.fill(fecha_solicitada)
                page.keyboard.press("Escape")
            if fecha_analisis:
                campo = frame.locator("input[id$='_xaf_dviFechaAnalisis_Edit_I']")
                campo.click()
                campo.fill(fecha_analisis)
                page.keyboard.press("Escape")

            campo_titulo = frame.locator("input[id$='_xaf_dviTitulo_Edit_I']")
            campo_titulo.click()
            campo_titulo.fill(titulo.strip())

            shot(page, f"crear_est_{numero_ot}_02_completado")

            print("Clickeando 'Aceptar'...")
            if not click_boton_visible(frame, "Aceptar"):
                raise CrearEstimadoError("No se encontro el boton 'Aceptar' del popup.")
            esperar_postback(page)
            page.wait_for_timeout(1000)

            # La grilla se repinta de forma asincronica tras el postback del
            # popup -- un solo wait_for_timeout fijo no alcanza siempre
            # (confirmado en vivo: OT 258/Estimado 558 quedo bien creado en
            # Advertys pero la primera lectura todavia veia la grilla vieja).
            # Reintenta hasta 10s viendo si aparece una fila nueva antes de
            # darse por vencido.
            nuevos = set()
            for _ in range(20):
                numeros_despues = leer_numeros_estimado(page)
                nuevos = numeros_despues - numeros_antes
                if nuevos:
                    break
                page.wait_for_timeout(500)
            shot(page, f"crear_est_{numero_ot}_03_guardado")

            if len(nuevos) == 0:
                extra = (
                    f" Esta OT ya tenia {len(numeros_antes)} estimados visibles en esta pagina "
                    "(>= 20): la causa mas probable es que el Estimado nuevo cayo en la pagina 2+ "
                    "de la grilla, no que el alta haya fallado." if hay_muchos_estimados else
                    " No se detecto ninguna fila nueva -- revisar a mano en Advertys antes de "
                    "reintentar (podria haberse rechazado el alta)."
                )
                raise CrearEstimadoError(
                    f"No se pudo identificar el Estimado nuevo por diferencia de grilla.{extra} "
                    f"Ver captura crear_est_{numero_ot}_03_guardado.png"
                )
            if len(nuevos) > 1:
                raise CrearEstimadoError(
                    f"Se detecto mas de un candidato a Estimado nuevo ({sorted(nuevos)}) -- no se "
                    f"puede confirmar cual es. Revisar a mano en Advertys y captura "
                    f"crear_est_{numero_ot}_03_guardado.png antes de asumir nada."
                )

            numero_estimado = nuevos.pop()
            print(f"OK: Estimado {numero_estimado} creado en OT {numero_ot} (titulo: {titulo!r}).")
            return numero_estimado
        finally:
            browser.close()


def main():
    parser = argparse.ArgumentParser(
        description="Crea el encabezado de un Estimado de Costo en Advertys (alta, nunca items)"
    )
    parser.add_argument("numero_ot", help="Numero de OT de sistema (Advertys)")
    parser.add_argument("titulo", help="Titulo del Estimado")
    parser.add_argument("--fecha-solicitada", default=None, help="D/M/AAAA -- default: hoy (el que precarga Advertys)")
    parser.add_argument(
        "--fecha-analisis",
        default=None,
        help="D/M/AAAA -- default: hoy (el que precarga Advertys); es el periodo AAAAMM del pipeline de lectura",
    )
    args = parser.parse_args()

    try:
        numero_estimado = crear_estimado(args.numero_ot, args.titulo, args.fecha_solicitada, args.fecha_analisis)
    except CrearEstimadoError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    print(f"Numero de Estimado: {numero_estimado}")


if __name__ == "__main__":
    main()
