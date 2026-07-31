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

Antes de intentar 'Finalizado', chequea en modo lectura (sin clickear
Editar) si el estimado esta completo segun la regla acordada con Javier
(2026-07-21): todo item con Proveedor tiene que tener una O.C. vigente
(no anulada), y tiene que haber al menos una factura 'Contabilizada'. Si
no se cumple, aborta con un motivo claro en vez de gastar un intento
contra Advertys (ver `chequear_estimado_completo`).

Ademas incluye `listar_candidatos()`, de SOLO LECTURA (no clickea "Editar"
ni "Guardar" en ningun momento): recorre TODAS las OT abiertas y estimados
no terminales usando la misma logica de semaforo que ya calcula
`modules/pendientes/generate_html_report.py` sobre los datos locales de
`advertys.db`, y para los estimados que todavia no estan en un estado
terminal corre `chequear_estimado_completo` en vivo contra Advertys (un
solo login/browser para todos, a diferencia de correr `chequear-estimado`
una vez por estimado). Sirve para armar de un saque la propuesta de que
cerrar, sin gastar un intento de escritura a ciegas. Ver
`workflows/cerrar_pendientes.md` para el flujo completo (incluye el paso de
confirmacion explicita de Javier antes de ejecutar cualquier escritura).

Uso:
    python -m modules.ordenes_trabajo.cerrar_ot finalizar-estimado <numero_estimado>
    python -m modules.ordenes_trabajo.cerrar_ot cerrar-ot <numero_ot>
    python -m modules.ordenes_trabajo.cerrar_ot chequear-estimado <numero_ot> <numero_estimado>
    python -m modules.ordenes_trabajo.cerrar_ot listar-candidatos
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

OUT_DIR = Path("exploracion") / "screenshots"
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


def normalizar_num_oc(texto):
    """Normaliza un numero de O.C. para comparar entre pestanas: en 'Items
    del Estimado' aparece sin ceros a la izquierda (ej. '149') pero en
    'Ordenes Compra' aparece con ellos (ej. '00149')."""
    texto = (texto or "").strip()
    try:
        return str(int(texto))
    except ValueError:
        return texto


def leer_grid_visible(page):
    """Lee la grilla ASPxGridView actualmente visible (la pestana activa) y
    devuelve una lista de dicts {nombre_columna: texto}. Alinea celdas de
    datos con el texto del header por posicion -- verificado contra un
    estimado real (OT 235 / Estimado 439, 2026-07-21) que header y filas
    tienen exactamente la misma cantidad de celdas en el mismo orden.
    Selector de header: `td[class*='dxgvHeader']` (no `td.dxgvHeader`: esta
    instalacion de Advertys usa la clase 'dxgvHeader_Office2010Blue')."""
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
        return []

    headers_loc = tabla.locator("td[class*='dxgvHeader']")
    headers = [headers_loc.nth(i).inner_text().strip() for i in range(headers_loc.count())]
    if not headers:
        return []

    filas_loc = tabla.locator("tr[id*='DXDataRow']")
    filas = []
    for i in range(filas_loc.count()):
        celdas = filas_loc.nth(i).locator("td")
        n = celdas.count()
        fila = {nombre: (celdas.nth(j).inner_text().strip() if j < n else "") for j, nombre in enumerate(headers)}
        filas.append(fila)
    return filas


def _col(fila, *nombres_posibles):
    """Busca el valor de una columna por coincidencia parcial del nombre de
    header (evita depender de un indice fijo, y evita problemas de encoding
    con 'N° O.C.' buscando solo la parte estable 'O.C.')."""
    for clave, valor in fila.items():
        for nombre in nombres_posibles:
            if nombre in clave:
                return valor
    return ""


def chequear_estimado_completo(page, numero_estimado):
    """Chequeo de SOLO LECTURA (nunca clickea 'Editar' ni 'Guardar'):
    replica la regla de negocio acordada con Javier (2026-07-21) para saber
    si un Estimado de Costos puede pasar a 'Finalizado':

      a) Todo item con Proveedor cargado tiene que tener una Orden de
         Compra vigente (numero de O.C. cargado en el item, y esa O.C. no
         puede estar en estado 'Anulada' en la pestana Ordenes Compra).
      b) Tiene que haber al menos una factura en estado 'Contabilizada' en
         la pestana Facturas.

    Se corre ANTES de clickear 'Editar', para poder abortar con un motivo
    claro en vez de intentar la transicion a ciegas y depender del rechazo
    generico de Advertys ("Los importes tercerizados no estan CANCELADOS").

    OJO: esto cubre las dos causas mas comunes, pero no todas -- ver la nota
    "Caso real confirmado por Javier (OT 235 / Estimado 439)" en el README:
    un desfasaje de imputaciones tras reemplazar una O.C. anulada por otra
    tambien bloquea la finalizacion y esta funcion NO lo detecta (el item
    ya apunta a la O.C. nueva y la factura ya esta Contabilizada, pero
    Advertys igual rechaza por el lado contable). Un 'ok' aca es una
    condicion necesaria, no suficiente.

    Devuelve (ok: bool, motivos: list[str])."""
    motivos = []

    if not click_boton_visible(page, "Items del Estimado"):
        motivos.append("No se pudo abrir la pestana 'Items del Estimado' para chequear proveedores/OC.")
    else:
        esperar_postback(page)
        page.wait_for_timeout(600)
        items = leer_grid_visible(page)
        items_sin_oc = []
        ocs_referenciadas = set()
        for fila in items:
            proveedor = _col(fila, "Proveedor").strip()
            num_oc = _col(fila, "O.C.").strip()
            if proveedor:
                if not num_oc:
                    titulo = _col(fila, "Titulo") or _col(fila, "Nro")
                    items_sin_oc.append(f"'{titulo}' (proveedor: {proveedor})")
                else:
                    ocs_referenciadas.add(normalizar_num_oc(num_oc))
        if items_sin_oc:
            motivos.append(
                f"{len(items_sin_oc)} item(s) con proveedor sin O.C. cargada: " + "; ".join(items_sin_oc)
            )

        if ocs_referenciadas:
            if not click_boton_visible(page, "Ordenes Compra"):
                motivos.append("No se pudo abrir la pestana 'Ordenes Compra' para validar el estado de las O.C. referenciadas.")
            else:
                esperar_postback(page)
                page.wait_for_timeout(600)
                ocs = leer_grid_visible(page)
                estado_por_oc = {normalizar_num_oc(_col(fila, "O.C.")): _col(fila, "Estado") for fila in ocs}
                oc_anuladas = [oc for oc in ocs_referenciadas if estado_por_oc.get(oc, "").strip() == "Anulada"]
                if oc_anuladas:
                    motivos.append(
                        f"La(s) O.C. {', '.join(sorted(oc_anuladas))} referenciada(s) por items del estimado "
                        "esta(n) en estado 'Anulada' (no cuenta como emitida)."
                    )

    if not click_boton_visible(page, "Facturas"):
        motivos.append("No se pudo abrir la pestana 'Facturas' para chequear si hay factura contabilizada.")
    else:
        esperar_postback(page)
        page.wait_for_timeout(600)
        facturas = leer_grid_visible(page)
        hay_contabilizada = any(_col(f, "Estado").strip() == "Contabilizada" for f in facturas)
        if not hay_contabilizada:
            motivos.append("No tiene ninguna factura en estado 'Contabilizada' en la pestana Facturas.")

    return (len(motivos) == 0, motivos)


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

        print("  Chequeando si el estimado esta completo (proveedores con O.C., factura contabilizada)...")
        completo, motivos = chequear_estimado_completo(page, numero_estimado)
        if not completo:
            print(f"  BLOQUEADO: el estimado {numero_estimado} esta incompleto, no se va a intentar Finalizar:")
            for m in motivos:
                print(f"    - {m}")
            shot(page, f"est_{numero_estimado}_00_bloqueado_incompleto")
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


def chequear_estimado(numero_ot, numero_estimado):
    """Diagnostico de SOLO LECTURA: informa si el estimado esta completo
    (proveedores con O.C. vigente + factura contabilizada) sin clickear
    'Editar' en ningun momento. Sirve para revisar varios estimados de
    varias OT antes de intentar cerrarlas, sin gastar intentos contra
    Advertys."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(accept_downloads=True)
        login(page)

        print(f"Navegando a OT {numero_ot} > Estimados Costo > {numero_estimado} (modo vista)...")
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

        completo, motivos = chequear_estimado_completo(page, numero_estimado)
        if completo:
            print(f"OK: estimado {numero_estimado} esta completo (proveedores con O.C. vigente, factura contabilizada).")
        else:
            print(f"INCOMPLETO (estado amarillo): estimado {numero_estimado} no se puede finalizar todavia:")
            for m in motivos:
                print(f"  - {m}")

        browser.close()


def listar_candidatos():
    """SOLO LECTURA: arma la propuesta de que estimados/OT se podrian cerrar
    ahora mismo, reusando el semaforo ya calculado por
    modules/pendientes/generate_html_report.py sobre los datos locales de
    advertys.db (correr refresh-dashboard antes si esos datos no estan al
    dia -- ver workflows/cerrar_pendientes.md paso 1)."""
    from modules.pendientes.generate_html_report import (
        cargar_datos,
        _combinar_items_pendientes,
        _resumen_por_ot,
        ESTIMADO_ESTADOS_TERMINALES,
    )

    ot, estimados, oc, oc_pendientes, estimados_pend_facturar, items_crawl = cargar_datos()
    if ot.empty:
        print("No hay OT abiertas en la base local (correr antes el ingest de ordenes_trabajo).")
        return

    items_pendientes = _combinar_items_pendientes(oc_pendientes, items_crawl)
    resumen = _resumen_por_ot(ot, estimados, oc, items_pendientes, estimados_pend_facturar)

    ots_listas_directo = sorted(resumen.loc[resumen["semaforo"] == "good", "numero_ot"].tolist())

    # Umbral de higiene de datos (2026-07-30, cross-referenciado con
    # modules/pendientes/generate_html_report.UMBRAL_MUCHOS_ESTIMADOS): la
    # pestana "Estimados Costo" de una OT pagina de a 20 filas (confirmado
    # en vivo contra la OT 144, "Pagina 1 de 2 (40 elementos)"). Este script
    # busca el estimado por texto exacto en lo ya renderizado en pantalla,
    # asi que un estimado que cae en la pagina 2+ nunca aparece -- en vez de
    # reportar eso como "bloqueado" (lo cual sugiere una causa de negocio),
    # se separa como "no evaluable" antes de gastar el intento en vivo.
    UMBRAL_MUCHOS_ESTIMADOS = 20
    cant_estimados_por_ot = estimados.groupby("numero_ot")["numero_estimado"].count()
    ots_muchos_estimados = set(cant_estimados_por_ot[cant_estimados_por_ot > UMBRAL_MUCHOS_ESTIMADOS].index)

    ots_con_estimados = set(resumen.loc[resumen["cant_estimados"] > 0, "numero_ot"])
    candidatos_estimado_todos = estimados[
        (~estimados["estado"].isin(ESTIMADO_ESTADOS_TERMINALES))
        & (estimados["numero_ot"].isin(ots_con_estimados))
    ]
    candidatos_no_evaluables = candidatos_estimado_todos[candidatos_estimado_todos["numero_ot"].isin(ots_muchos_estimados)]
    candidatos_estimado = candidatos_estimado_todos[~candidatos_estimado_todos["numero_ot"].isin(ots_muchos_estimados)]

    print(f"OT abiertas: {len(resumen)}")
    print(f"\nOT listas para 'cerrar-ot' directamente (estimados y OC ya resueltos): {len(ots_listas_directo)}")
    for numero_ot in ots_listas_directo:
        print(f"  - OT {numero_ot}")

    if ots_muchos_estimados:
        print(
            f"\nOT con mas de {UMBRAL_MUCHOS_ESTIMADOS} estimados cargados (NO evaluables por este script -- "
            "la grilla pagina y solo lee lo visible en pantalla, revisar a mano en Advertys; "
            "ver badge 'Muchos estimados' en informe_pendientes.html): "
            f"{len(ots_muchos_estimados)}"
        )
        for numero_ot in sorted(ots_muchos_estimados):
            n = int(cant_estimados_por_ot.get(numero_ot, 0))
            print(f"  - OT {numero_ot} ({n} estimados)")

    print(f"\nEstimados no terminales a chequear en vivo contra Advertys: {len(candidatos_estimado)}")
    if candidatos_estimado.empty:
        return

    listos = []
    bloqueados = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(accept_downloads=True)
        login(page)

        for fila in candidatos_estimado.to_dict(orient="records"):
            numero_ot = fila["numero_ot"]
            numero_estimado = fila["numero_estimado"]
            titulo = fila.get("titulo") or ""
            print(f"  Chequeando estimado {numero_estimado} (OT {numero_ot})...")
            try:
                ir_a_ot(page, numero_ot)
                if not click_boton_visible(page, "Estimados Costo"):
                    bloqueados.append((numero_ot, numero_estimado, titulo, ["No se pudo abrir la pestana 'Estimados Costo'"]))
                    continue
                esperar_postback(page)
                page.wait_for_timeout(600)

                fila_est = page.get_by_text(str(numero_estimado), exact=True)
                if fila_est.count() == 0:
                    bloqueados.append((numero_ot, numero_estimado, titulo, ["No se encontro el estimado en la grilla"]))
                    continue
                fila_est.first.click(timeout=5000)
                esperar_postback(page)
                page.wait_for_timeout(600)

                completo, motivos = chequear_estimado_completo(page, numero_estimado)
                if completo:
                    listos.append((numero_ot, numero_estimado, titulo))
                else:
                    bloqueados.append((numero_ot, numero_estimado, titulo, motivos))
            except Exception as e:
                bloqueados.append((numero_ot, numero_estimado, titulo, [f"Error durante el chequeo: {e}"]))

        browser.close()

    print(f"\nEstimados LISTOS para 'finalizar-estimado': {len(listos)}")
    for numero_ot, numero_estimado, titulo in listos:
        print(f"  - OT {numero_ot} / Estimado {numero_estimado} ({titulo})")

    print(f"\nEstimados BLOQUEADOS (no se pueden finalizar todavia): {len(bloqueados)}")
    for numero_ot, numero_estimado, titulo, motivos in bloqueados:
        print(f"  - OT {numero_ot} / Estimado {numero_estimado} ({titulo}): {'; '.join(motivos)}")

    ots_bloqueadas = {numero_ot for numero_ot, _, _, _ in bloqueados}
    ots_con_pendientes = set(candidatos_estimado["numero_ot"])
    ots_potenciales = sorted((ots_con_pendientes - ots_bloqueadas) - set(ots_listas_directo))
    print(f"\nOT que quedarian listas para 'cerrar-ot' despues de finalizar sus estimados pendientes: {len(ots_potenciales)}")
    for numero_ot in ots_potenciales:
        print(f"  - OT {numero_ot}")


def main():
    if not URL or not USER or not PASSWORD:
        print("ERROR: completa ADVERTYS_URL, ADVERTYS_USER y ADVERTYS_PASSWORD en .env")
        sys.exit(1)
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    accion = sys.argv[1]
    if accion == "listar-candidatos":
        listar_candidatos()
    elif accion == "finalizar-estimado":
        if len(sys.argv) < 3:
            print(__doc__)
            sys.exit(1)
        numero_ot, numero_estimado = "235", sys.argv[2]
        if len(sys.argv) > 3:
            numero_ot, numero_estimado = sys.argv[2], sys.argv[3]
        finalizar_estimado(numero_ot, numero_estimado)
    elif accion == "cerrar-ot":
        if len(sys.argv) < 3:
            print(__doc__)
            sys.exit(1)
        cerrar_ot(sys.argv[2])
    elif accion == "chequear-estimado":
        if len(sys.argv) < 4:
            print(__doc__)
            sys.exit(1)
        chequear_estimado(sys.argv[2], sys.argv[3])
    else:
        print(f"Accion desconocida: {accion}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
