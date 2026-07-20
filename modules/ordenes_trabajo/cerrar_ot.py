"""
Script de ESCRITURA en Advertys (unico en este proyecto -- ver salvaguarda
"Advertys es de solo lectura" en CLAUDE.md, aprobado explicitamente por
Javier 2026-07-20 para este flujo puntual, relevado antes con
explore_cerrar_ot.py).

Cierra una Orden de Trabajo que ya no tiene pendientes:
  1. Para cada Estimado de Costo de la OT que no este en 'Finalizado' ni
     'Anulado': lo abre, entra en modo edicion, clickea el boton de accion
     'Cambiar estado a: Finalizado' (NUNCA 'Provisorio' ni otro estado) y
     guarda.
  2. Una vez todos los estimados en 'Finalizado'/'Anulado', abre la OT,
     entra en modo edicion, clickea 'Cambiar estado a: Cerrada' (NUNCA
     'Anulada') y guarda.

En Advertys el campo "Estado" no es un combo libre: son botones de accion
("Cambiar estado a: X") que solo permiten la transicion de cierre, no
cualquier estado -- por eso este script nunca escribe un valor arbitrario,
solo clickea esos botones puntuales.

Cada paso es explicito y se corre por separado (no hay un "cerrar todo de
un saque"): se ejecuta un estimado o la OT por vez y se revisa la captura
resultante antes de seguir con el siguiente.

Uso:
    python -m modules.ordenes_trabajo.cerrar_ot finalizar-estimado <numero_estimado>
    python -m modules.ordenes_trabajo.cerrar_ot cerrar-ot <numero_ot>
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

URL = os.environ.get("ADVERTYS_URL")
USER = os.environ.get("ADVERTYS_USER")
PASSWORD = os.environ.get("ADVERTYS_PASSWORD")

OUT_DIR = Path("exploracion") / "cerrar_ot"
OUT_DIR.mkdir(parents=True, exist_ok=True)


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


def shot(page, nombre):
    destino = OUT_DIR / f"{nombre}.png"
    page.screenshot(path=str(destino), full_page=True)
    print(f"  -> {destino}")


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


# Transiciones de estado que este script tiene PROHIBIDO ejecutar (acordado
# con Javier 2026-07-20): jamas anular un estimado ni una OT, ni dejar un
# estimado en 'Provisorio'. Las unicas transiciones permitidas son
# Estimado -> Finalizado y OT -> Cerrada. Bloqueo duro ademas de que el
# flujo del script ya no llame a estas acciones.
ESTADOS_PROHIBIDOS = {"Anulado", "Anulada", "Provisorio"}


def boton_visible(page, texto):
    """True si hay un elemento VISIBLE con este texto exacto (sin clickearlo).
    Se usa para chequear si una accion de 'Cambiar estado a: X' sigue
    disponible tras un click -- si desaparece de las opciones es la senal
    mas confiable de que la transicion se aplico (mas confiable que leer el
    campo Estado por texto, que en algunos layouts matchea el label sin el
    valor)."""
    candidatos = page.get_by_text(texto, exact=True)
    for i in range(candidatos.count()):
        try:
            if candidatos.nth(i).is_visible():
                return True
        except Exception:
            continue
    return False


def click_boton_visible(page, texto, timeout=5000):
    """Clickea el primer elemento VISIBLE con este texto exacto (evita
    matchear items de menu lateral / opciones ocultas con el mismo texto)."""
    if texto in ESTADOS_PROHIBIDOS:
        raise RuntimeError(
            f"Bloqueado: este script no tiene permitido clickear '{texto}' "
            "(solo Estimado->Finalizado y OT->Cerrada estan autorizados)"
        )
    candidatos = page.get_by_text(texto, exact=True)
    n = candidatos.count()
    for i in range(n):
        cand = candidatos.nth(i)
        try:
            if cand.is_visible():
                cand.click(timeout=timeout)
                return True
        except Exception:
            continue
    return False


def login(page):
    print(f"Abriendo {URL}")
    page.goto(URL, wait_until="networkidle", timeout=30000)
    user_input = page.locator('input[id$="xaf_dviUserName_Edit_I"]')
    pass_input = page.locator('input[id$="xaf_dviPassword_Edit_I"]')
    user_input.wait_for(state="visible", timeout=15000)
    user_input.click()
    user_input.fill(USER)
    pass_input.click()
    pass_input.fill(PASSWORD)
    pass_input.press("Enter")
    esperar_postback(page)
    if "Login.aspx" in page.url:
        login_link = page.locator('a[title="Iniciar sesión"], a[title="Iniciar sesion"]')
        if login_link.count() > 0:
            login_link.first.click(force=True, timeout=10000)
            esperar_postback(page)
    if "Login.aspx" in page.url:
        print("ERROR: no se pudo hacer login. Revisa usuario/contraseña en .env")
        shot(page, "00_error_login")
        sys.exit(1)
    print("Login OK.")


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
    base_url = URL.split("Login.aspx")[0]
    direct_url = f"{base_url}Default.aspx#ViewID=OrdenTrabajo_ListView&ObjectClassName=DPS_SAS_SR.Module.OrdenTrabajo"
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
        raise RuntimeError("No se encontro el buscador 'Texto a buscar...'")
    esperar_postback(page)
    page.wait_for_timeout(800)

    fila = page.get_by_text(str(numero_ot), exact=True)
    if fila.count() == 0:
        raise RuntimeError(f"No se encontro la OT {numero_ot} en la grilla")
    fila.first.click(timeout=5000)
    esperar_postback(page)
    page.wait_for_timeout(800)


def guardar_y_confirmar(page, nombre_screenshot_previo):
    """Clickea 'Guardar', y si aparece un dialogo nativo o un popup de
    confirmacion en pantalla, lo acepta (segun lo acordado con Javier:
    siempre confirmar tras cambiar de estado)."""
    def on_dialog(dialog):
        print(f"  Dialogo nativo detectado: {dialog.message!r} -> aceptando")
        dialog.accept()

    page.on("dialog", on_dialog)
    if not click_boton_visible(page, "Guardar"):
        raise RuntimeError("No se encontro el boton 'Guardar' visible")
    page.wait_for_timeout(500)

    # Popup de confirmacion propio de la app (no siempre es un dialog nativo)
    for etiqueta in ("Sí", "Si", "Aceptar", "OK", "Yes", "Confirmar"):
        boton = page.get_by_text(etiqueta, exact=True)
        if boton.count() > 0 and boton.first.is_visible():
            print(f"  Popup de confirmacion detectado, clickeando '{etiqueta}'")
            boton.first.click(timeout=3000)
            break

    esperar_postback(page)
    page.wait_for_timeout(800)
    page.remove_listener("dialog", on_dialog)
    shot(page, nombre_screenshot_previo)


def finalizar_estimado(numero_ot, numero_estimado):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(accept_downloads=True)
        login(page)

        print(f"Navegando a OT {numero_ot} > Estimados Costo > {numero_estimado}...")
        ir_a_ot(page, numero_ot)
        if not click_boton_visible(page, "Estimados Costo"):
            raise RuntimeError("No se encontro la pestana 'Estimados Costo'")
        esperar_postback(page)
        page.wait_for_timeout(800)

        fila_est = page.get_by_text(str(numero_estimado), exact=True)
        if fila_est.count() == 0:
            raise RuntimeError(f"No se encontro el estimado {numero_estimado} en la grilla")
        fila_est.first.click(timeout=5000)
        esperar_postback(page)
        page.wait_for_timeout(800)
        shot(page, f"est_{numero_estimado}_01_antes")

        estado_actual = page.locator("text=Estado:").locator("xpath=..").inner_text()
        print(f"  Estado actual (antes de editar): {estado_actual.strip()}")
        if "Finalizado" in estado_actual or "Anulado" in estado_actual:
            print(f"  Ya esta en un estado terminal permitido, no hace falta tocarlo.")
            browser.close()
            return

        if not click_boton_visible(page, "Editar"):
            raise RuntimeError("No se encontro el boton 'Editar' del estimado")
        esperar_postback(page)
        page.wait_for_timeout(800)

        print("  Clickeando 'Cambiar estado a: Finalizado'...")
        if not click_boton_visible(page, "Finalizado"):
            raise RuntimeError("No se encontro el boton de accion 'Finalizado'")
        esperar_postback(page)
        page.wait_for_timeout(800)
        shot(page, f"est_{numero_estimado}_02_finalizado_click")

        # Senal confiable de que la transicion se aplico: el boton de accion
        # 'Finalizado' deja de estar disponible (ya no tiene sentido pasar a
        # un estado en el que ya esta). Si sigue visible, Advertys rechazo
        # el cambio (ej. "Los importes tercerizados no estan CANCELADOS").
        if boton_visible(page, "Finalizado"):
            raise RuntimeError(
                "El boton 'Finalizado' sigue disponible tras el click: Advertys probablemente "
                f"rechazo la transicion (ver captura est_{numero_estimado}_02_finalizado_click.png "
                "por el motivo exacto). Abortando antes de guardar."
            )

        print("  Guardando...")
        guardar_y_confirmar(page, f"est_{numero_estimado}_03_guardado")

        print(f"OK: estimado {numero_estimado} procesado. Revisar captura est_{numero_estimado}_03_guardado.png")
        browser.close()


def cerrar_ot(numero_ot):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(accept_downloads=True)
        login(page)

        print(f"Navegando a OT {numero_ot}...")
        ir_a_ot(page, numero_ot)
        shot(page, f"ot_{numero_ot}_01_antes")

        if not click_boton_visible(page, "Editar"):
            raise RuntimeError("No se encontro el boton 'Editar' de la OT")
        esperar_postback(page)
        page.wait_for_timeout(800)

        print("  Clickeando 'Cambiar estado a: Cerrada'...")
        if not click_boton_visible(page, "Cerrada"):
            raise RuntimeError("No se encontro el boton de accion 'Cerrada'")
        esperar_postback(page)
        page.wait_for_timeout(800)
        shot(page, f"ot_{numero_ot}_02_cerrada_click")

        if boton_visible(page, "Cerrada"):
            raise RuntimeError(
                "El boton 'Cerrada' sigue disponible tras el click: Advertys probablemente "
                f"rechazo la transicion (ver captura ot_{numero_ot}_02_cerrada_click.png "
                "por el motivo exacto). Abortando antes de guardar."
            )

        print("  Guardando...")
        guardar_y_confirmar(page, f"ot_{numero_ot}_03_guardado")

        print(f"OK: OT {numero_ot} procesada. Revisar captura ot_{numero_ot}_03_guardado.png")
        browser.close()


def main():
    if not URL or not USER or not PASSWORD:
        print("ERROR: completa ADVERTYS_URL, ADVERTYS_USER y ADVERTYS_PASSWORD en .env")
        sys.exit(1)
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    accion = sys.argv[1]
    if accion == "finalizar-estimado":
        numero_ot, numero_estimado = "235", sys.argv[2]
        if len(sys.argv) > 3:
            numero_ot, numero_estimado = sys.argv[2], sys.argv[3]
        finalizar_estimado(numero_ot, numero_estimado)
    elif accion == "cerrar-ot":
        cerrar_ot(sys.argv[2])
    else:
        print(f"Accion desconocida: {accion}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
