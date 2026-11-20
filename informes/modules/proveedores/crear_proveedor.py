"""
Script de ESCRITURA en Advertys (ver salvaguarda "Advertys es de solo
lectura" en CLAUDE.md). Da de alta un PROVEEDOR (Entidades > Generales >
Proveedores > Proveedor) con los datos de la constancia de inscripcion ARCA.

Por defecto corre en MODO PRUEBA: completa el formulario, saca captura y
cierra SIN guardar. Solo con `--guardar` hace click en "Guardar". Nunca
correr con --guardar sin confirmacion explicita de Javier para esa corrida.

Formulario relevado el 2026-11-19 (explore_nuevo_proveedor.py,
explore_popups_proveedor.py):

- N° de proveedor y Habilitado: los maneja Advertys, no se tocan.
- Proveedor: Nombre (razon social, constancia), Direccion (popup "Datos
  Generales": direccion, CP, localidad, provincia). Grupo Proveedor:
  desestimado (queda N / D). Fantasia/Orden De/Atencion: no se tocan.
- Datos Impositivos: Tipo IVA (constancia), Tipo Documento = CUIT, CUIT
  (solo digitos).
- Ganancias e Iva: "Es Inscripto Ganancias" (viene tildado; se verifica y,
  si la constancia dice que NO esta inscripto, se destilda con
  --no-inscripto-ganancias), Retencion Ganancia (la elige el usuario: NO
  RETENER / ENAJENACION / LOCACION DE OBRAS Y SERVICIOS / etc.), SUSS =
  "No Retener" por defecto.
- IIBB: desestimado (no se toca).
- Parametros: Tipo Proveedor (AGENCIA/MEDIOS/PRODUCCION/VARIOS) y Condicion
  Pago, ambos elegidos por el usuario; Cuenta a imputar es opcional
  (base: "GASTOS VARIOS (PART)").

Uso (parado en informes/):
    python -m modules.proveedores.crear_proveedor "<nombre>" "<cuit>" \
        --direccion "<calle y nro>" --cp 7600 --localidad "<localidad>" --provincia "<provincia>" \
        --tipo-proveedor VARIOS --retencion-ganancia "NO RETENER" \
        [--tipo-iva "IVA Responsable Inscripto"] [--suss "No Retener"] \
        [--condicion-pago "30 DIAS SIN DPP"] [--cuenta "GASTOS VARIOS"] \
        [--no-inscripto-ganancias] [--guardar]
"""
import argparse
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from tools.advertys_session import AdvertysLoginError, base_url, esperar_postback, login

OUT_DIR = Path("exploracion")
SCREENSHOT_DIR = OUT_DIR / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

LIST_URL_SUFFIX = "Default.aspx#ViewID=Proveedor_ListView&ObjectClassName=DPS_SAS_SR.Module.Proveedor"

TIPOS_PROVEEDOR = ["AGENCIA", "MEDIOS", "PRODUCCION", "VARIOS"]
RETENCIONES_GANANCIA = [
    "ALQUILERES", "ENAJENACION", "FACTURAS M - GANANCIAS", "INTERESES",
    "LOCACION DE OBRAS Y SERVICIOS", "MONOTRIBUTO", "NO RETENER",
]
SUSS_VALIDOS = ["Aportes Patronales", "No Retener", "Personal de Limpieza", "Personal de Seguridad"]


class CrearProveedorError(RuntimeError):
    pass


def shot(page, nombre):
    destino = SCREENSHOT_DIR / f"{nombre}.png"
    page.screenshot(path=str(destino), full_page=True)
    print(f"  -> {destino}")


def click_visible(ctx, texto, timeout=5000):
    cands = ctx.get_by_text(texto, exact=True)
    for i in range(cands.count()):
        c = cands.nth(i)
        try:
            if c.is_visible():
                c.click(timeout=timeout)
                return True
        except Exception:
            continue
    return False


def _dialogs(page):
    return [f for f in page.frames if "Dialog=true" in f.url]


def esperar_popup(page, previos=0, timeout_ms=12000):
    """Devuelve el iframe del popup mas reciente (Dialog=true) apenas aparece.
    `previos` = cantidad de popups ya abiertos (para lookups anidados)."""
    for _ in range(timeout_ms // 500):
        fr = _dialogs(page)
        if len(fr) > previos:
            page.wait_for_timeout(800)
            return fr[-1]
        page.wait_for_timeout(500)
    return None


def ir_a_pestana(page, nombre):
    # .last: "Parámetros" también es un nodo del menú lateral (viene antes en el DOM)
    page.get_by_text(nombre, exact=True).locator("visible=true").last.click(timeout=8000)
    esperar_postback(page)
    page.wait_for_timeout(700)


def seleccionar_combo(ctx, page, campo, texto_opcion):
    """ASPxComboBox: abre la lista y clickea la opcion de texto exacto (la
    primera fila de la lista es un artefacto de virtual-scroll con todas las
    opciones juntas; el match exacto la descarta)."""
    inp = ctx.locator(f"input[id$='_xaf_{campo}_Edit_dropdown_DD_I']")
    if inp.count() == 0:
        raise CrearProveedorError(f"No se encontro el combo {campo}.")
    input_id = inp.first.get_attribute("id")
    ctx.locator("#" + input_id.replace("_DD_I", "_DD_B-1")).click(timeout=5000)
    page.wait_for_timeout(700)
    lista_id = input_id.replace("_DD_I", "_DD_DDD_L")
    filas = ctx.locator("#" + lista_id + " td")
    opciones = []
    # La lista usa virtual-scroll (~9 filas visibles): se recorre scrolleando.
    for _ in range(25):
        for i in range(filas.count()):
            t = filas.nth(i).inner_text().strip()
            if t.upper() == texto_opcion.strip().upper():
                filas.nth(i).click()
                page.wait_for_timeout(500)
                return
            if t and "\n" not in t and t not in opciones:
                opciones.append(t)
        antes = len(opciones)
        ctx.locator("#" + lista_id + "_D").evaluate("e => { e.scrollTop = e.scrollTop + e.clientHeight; }")
        page.wait_for_timeout(500)
        for i in range(filas.count()):
            t = filas.nth(i).inner_text().strip()
            if t and "\n" not in t and t not in opciones:
                opciones.append(t)
        if len(opciones) == antes:
            break
    page.keyboard.press("Escape")
    raise CrearProveedorError(
        f"'{texto_opcion}' no esta entre las opciones de {campo}. Opciones: {', '.join(opciones)}"
    )


def elegir_en_lookup(page, frame, busqueda, que):
    """Dentro del popup de un lookup (buscador + grilla): busca `busqueda`,
    exige exactamente una fila (o un match exacto entre varias) y la acepta."""
    buscador = frame.locator("input[id$='_Ed_I']").first
    buscador.click()
    buscador.fill(busqueda)
    buscador.press("Enter")
    page.wait_for_timeout(1500)
    filas = frame.locator("tr[id*='DXDataRow']")
    n = filas.count()
    if n == 0:
        raise CrearProveedorError(f"No se encontro ningun/a {que} para '{busqueda}'.")
    textos = [filas.nth(i).inner_text().replace("\n", " | ").strip() for i in range(n)]
    elegida = 0
    if n > 1:
        obj = busqueda.strip().upper()
        exactas = [i for i, t in enumerate(textos) if any(x.strip().upper() == obj for x in t.split("|"))]
        if len(exactas) != 1:
            raise CrearProveedorError(
                f"'{busqueda}' matcheo {n} ({que}) y ninguno es exacto: " + " // ".join(textos[:8])
            )
        elegida = exactas[0]
    filas.nth(elegida).click(timeout=5000)
    page.wait_for_timeout(400)
    try:
        click_visible(frame, "Aceptar")
    except Exception:
        pass  # el click en la fila puede cerrar el popup solo
    esperar_postback(page)
    page.wait_for_timeout(800)


def cargar_direccion(page, direccion, cp, localidad, provincia, pais):
    n0 = len(_dialogs(page))
    page.locator("td[id$='_xaf_dviDatosGenerales_Edit_B0']").first.click(timeout=8000)
    frame = esperar_popup(page, n0)
    if frame is None:
        shot(page, "crear_proveedor_error_sin_popup_direccion")
        raise CrearProveedorError("No se abrio el popup de Direccion (Datos Generales).")
    frame.locator("input[id$='_xaf_dviDireccion_Edit_I']").first.fill(direccion)
    frame.locator("input[id$='_xaf_dviCodigoPostal_Edit_I']").first.fill(cp)
    frame.locator("input[id$='_xaf_dviLocalidad_Edit_I']").first.fill(localidad)
    seleccionar_combo(frame, page, "dviProvincia", provincia)
    # Pais es obligatorio y es un lookup (popup anidado con buscador).
    n1 = len(_dialogs(page))
    frame.locator("td[id$='_xaf_dviPais_Edit_find_Edit_B0']").first.click(timeout=8000)
    sub = esperar_popup(page, n1)
    if sub is None:
        raise CrearProveedorError("No se abrio el popup de Pais.")
    elegir_en_lookup(page, sub, pais, "pais")
    shot(page, "crear_proveedor_popup_direccion_completo")
    if not click_visible(frame, "Aceptar"):
        raise CrearProveedorError("No se encontro 'Aceptar' en el popup de Direccion.")
    esperar_postback(page)
    page.wait_for_timeout(1500)
    if _dialogs(page):
        shot(page, "crear_proveedor_error_popup_direccion")
        raise CrearProveedorError(
            "El popup de Direccion no cerro: Advertys rechazo la validacion (ver captura "
            "crear_proveedor_error_popup_direccion.png)."
        )


def seleccionar_cuenta(page, busqueda):
    """Lookup Plan Cuenta (pestana Parametros)."""
    n0 = len(_dialogs(page))
    page.locator("td[id$='_xaf_dviCuenta_Edit_find_Edit_B0']").first.click(timeout=8000)
    frame = esperar_popup(page, n0)
    if frame is None:
        raise CrearProveedorError("No se abrio el popup de Plan Cuenta.")
    elegir_en_lookup(page, frame, busqueda, "cuenta")
    valor = page.locator("input[id$='_xaf_dviCuenta_Edit_find_Edit_I']").first.input_value()
    if not valor or valor.strip() in ("", "N / D"):
        raise CrearProveedorError("La Cuenta no quedo seleccionada (sigue en N / D).")
    return valor.strip()


def inscripto_ganancias(page, esperado):
    """Verifica (y corrige si hace falta) el check 'Es Inscripto Ganancias'."""
    span = page.locator("span[id$='_xaf_dviEsInscriptoGanancias_Edit_S_D']").first
    tildado = "CheckBoxChecked" in (span.get_attribute("class") or "")
    if tildado != esperado:
        span.click()
        page.wait_for_timeout(500)


def crear_proveedor(a) -> str | None:
    cuit = re.sub(r"\D", "", a.cuit)
    if len(cuit) != 11:
        raise CrearProveedorError(f"CUIT invalido ({a.cuit!r}): debe tener 11 digitos.")
    if not a.nombre.strip():
        raise CrearProveedorError("El nombre no puede estar vacio.")
    if a.tipo_proveedor not in TIPOS_PROVEEDOR:
        raise CrearProveedorError(f"Tipo proveedor invalido. Opciones: {', '.join(TIPOS_PROVEEDOR)}")
    if a.retencion_ganancia not in RETENCIONES_GANANCIA:
        raise CrearProveedorError(f"Retencion Ganancia invalida. Opciones: {', '.join(RETENCIONES_GANANCIA)}")
    if a.suss not in SUSS_VALIDOS:
        raise CrearProveedorError(f"SUSS invalido. Opciones: {', '.join(SUSS_VALIDOS)}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 1000})
        page.on("dialog", lambda d: d.accept())  # "¿salir sin guardar?" al cancelar
        try:
            try:
                login(page)
            except AdvertysLoginError as e:
                raise CrearProveedorError(str(e)) from e

            url = base_url() + LIST_URL_SUFFIX
            page.goto(url, wait_until="networkidle", timeout=30000)
            esperar_postback(page)

            # Anti-duplicado: el CUIT no debe existir ya (el filtro del listado
            # es "Habilitados"; un inhabilitado se detecta en Advertys a mano).
            buscador = page.locator("input[id$='_Ed_I']").first
            if buscador.count():
                buscador.click()
                buscador.fill(cuit)
                buscador.press("Enter")
                esperar_postback(page)
                page.wait_for_timeout(1000)
                if page.locator("tr[id*='DXDataRow']").count() > 0:
                    shot(page, "crear_proveedor_duplicado")
                    raise CrearProveedorError(
                        f"Ya existe un proveedor con CUIT {cuit} (ver captura crear_proveedor_duplicado.png)."
                    )
                page.goto(url, wait_until="networkidle", timeout=30000)
                esperar_postback(page)

            print("Abriendo formulario 'Nuevo'...")
            page.locator('a[title="Nuevo"], span:has-text("Nuevo")').first.click()
            esperar_postback(page)
            page.wait_for_timeout(1200)

            print(f"Nombre: {a.nombre!r}")
            page.locator("input[id$='_xaf_dviNombre_Edit_I']").first.fill(a.nombre.strip())

            print("Direccion...")
            cargar_direccion(page, a.direccion, a.cp, a.localidad, a.provincia, a.pais)

            print("Datos Impositivos...")
            ir_a_pestana(page, "Datos Impositivos")
            seleccionar_combo(page, page, "dviTipoIva", a.tipo_iva)
            seleccionar_combo(page, page, "dviTipoDocumento", "CUIT")
            page.locator("input[id$='_xaf_dviCuit_Edit_I']").first.fill(cuit)

            print("Ganancias e Iva...")
            ir_a_pestana(page, "Ganancias e Iva")
            inscripto_ganancias(page, not a.no_inscripto_ganancias)
            seleccionar_combo(page, page, "dviRetencionGanancia", a.retencion_ganancia)
            seleccionar_combo(page, page, "dviRetencionSUSS", a.suss)

            print("Parametros...")
            ir_a_pestana(page, "Parámetros")
            seleccionar_combo(page, page, "dviTipoProveedor", a.tipo_proveedor)
            if a.condicion_pago:
                seleccionar_combo(page, page, "dviCondicionPago", a.condicion_pago)
            if a.cuenta:
                print(f"  Cuenta: {seleccionar_cuenta(page, a.cuenta)}")

            # Captura de cada pestana completada, para revision antes de guardar.
            for pest in ["Proveedor", "Datos Impositivos", "Ganancias e Iva", "Parámetros"]:
                ir_a_pestana(page, pest)
                shot(page, f"crear_proveedor_{pest.split()[0].lower()}")

            if not a.guardar:
                print("MODO PRUEBA: formulario completado, se cierra SIN guardar.")
                click_visible(page, "Cancelar")
                esperar_postback(page)
                return None

            print("Clickeando 'Guardar'...")
            if not click_visible(page, "Guardar"):
                raise CrearProveedorError("No se encontro el boton 'Guardar'.")
            esperar_postback(page)
            page.wait_for_timeout(1500)
            shot(page, "crear_proveedor_guardado")
            # El N° se autoasigna al abrir "Nuevo", asi que NO prueba que se
            # guardo: la señal de rechazo es el cartel de validacion de Advertys.
            cartel = page.get_by_text("Problemas fueron detectados", exact=False)
            if cartel.count() and cartel.first.is_visible():
                detalle = cartel.first.locator("xpath=ancestor::*[self::div or self::table][1]").inner_text()
                raise CrearProveedorError(
                    "Advertys rechazo el Guardar (NO se creo el proveedor): "
                    + " ".join(detalle.split())[:300]
                    + " (ver captura crear_proveedor_guardado.png)"
                )
            ir_a_pestana(page, "Proveedor")
            numero = page.locator("input[id$='_xaf_dviIdProveedor_Edit_I']").first.input_value().strip()
            print(f"OK: proveedor {numero} creado ({a.nombre}, CUIT {cuit}).")
            return numero
        finally:
            browser.close()


def main():
    ap = argparse.ArgumentParser(description="Alta de Proveedor en Advertys desde la constancia ARCA")
    ap.add_argument("nombre", help="Razon social tal como figura en la constancia")
    ap.add_argument("cuit", help="CUIT (con o sin guiones)")
    ap.add_argument("--direccion", required=True)
    ap.add_argument("--cp", required=True)
    ap.add_argument("--localidad", required=True)
    ap.add_argument("--provincia", required=True, help="Como figura en el combo de Advertys (ej. 'Buenos Aires')")
    ap.add_argument("--pais", default="ARGENTINA")
    ap.add_argument("--tipo-iva", default="IVA Responsable Inscripto")
    ap.add_argument("--tipo-proveedor", required=True, help=f"Uno de: {', '.join(TIPOS_PROVEEDOR)}")
    ap.add_argument("--retencion-ganancia", required=True, help=f"Uno de: {', '.join(RETENCIONES_GANANCIA)}")
    ap.add_argument("--suss", default="No Retener", help=f"Uno de: {', '.join(SUSS_VALIDOS)}")
    ap.add_argument("--condicion-pago", required=True, help="Obligatoria: Advertys rechaza el Guardar sin ella")
    ap.add_argument("--cuenta", default=None, help="Texto a buscar en Plan Cuenta (base: 'GASTOS VARIOS')")
    ap.add_argument("--no-inscripto-ganancias", action="store_true")
    ap.add_argument("--guardar", action="store_true", help="Sin este flag corre en modo prueba (no guarda)")
    a = ap.parse_args()
    try:
        crear_proveedor(a)
    except CrearProveedorError as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
