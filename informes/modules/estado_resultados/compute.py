"""
Calculo puro (sin Advertys, sin HTML) del Estado de Resultados mensual.

Entrada: DataFrame del export Balance Mensual ya normalizado (columnas
anio, mes, nombre, neto) + el dict de inputs.json. Salida: filas del EERR
listas para renderizar (ver generate_html_report.py) y los totales que
usan los stat tiles. Se mantiene separado para poder testearlo
(tests/test_estado_resultados.py) y para que la estructura sea la misma de
la planilla Google "EERR Nuevo".

Convencion de signos: ingresos positivos, costos negativos (igual que la
planilla: valor = -Neto Mes del libro).
"""
import numpy as np
import pandas as pd

from modules.estado_resultados import config

MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def parse_importe(valor) -> float:
    """Importe del export de Advertys: '$ 1.234,56' o '-$ 1.234,56'.

    OJO: common.normalizar_numero devuelve None para los negativos
    ('-$ 1.234,56' -> '- 1234.56' no parsea por el espacio), cosa que en
    este informe borraria justo los ingresos (saldo acreedor = negativo).
    Por eso este modulo tiene su propio parser."""
    if valor is None or (isinstance(valor, float) and np.isnan(valor)):
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    limpio = str(valor).replace("$", "").replace(" ", "").replace(".", "").replace(",", ".").strip()
    try:
        return float(limpio)
    except ValueError:
        return 0.0


def cargar_balance(path=None) -> pd.DataFrame:
    """Lee el CSV del export y devuelve anio, mes, codigo, nombre, neto
    (solo cuentas de resultado: codigo que empieza con 4 o 5)."""
    df = pd.read_csv(path or config.BALANCE_CSV, encoding="utf-8", sep=";", engine="python")
    # La primera columna es "Año"; se toma por posicion por si la
    # codificacion del export cambia el caracter.
    df = df.rename(columns={df.columns[0]: "anio"})
    df = df.rename(columns={"Mes": "mes", "Nombre": "nombre", "Neto Mes": "neto"})
    df["neto"] = df["neto"].apply(parse_importe)
    df["codigo"] = pd.to_numeric(df["nombre"].astype(str).str.split("-").str[0], errors="coerce")
    df = df[df["codigo"].notna()].copy()
    df["codigo"] = df["codigo"].astype(int)
    df = df[df["codigo"].astype(str).str[0].isin(["4", "5"])]
    return df[["anio", "mes", "codigo", "nombre", "neto"]]


def cuentas_del_anio(df: pd.DataFrame, anio: int) -> dict:
    """{codigo: {'nombre': str, 'v': array(12)}} con valor = -neto."""
    cuentas = {}
    sub = df[df["anio"] == anio]
    for r in sub.itertuples():
        c = cuentas.setdefault(r.codigo, {"nombre": r.nombre, "v": np.zeros(12)})
        c["v"][int(r.mes) - 1] += -r.neto
    return cuentas


def _suma(cuentas: dict, codigos) -> np.ndarray:
    total = np.zeros(12)
    for cod in codigos:
        if cod in cuentas:
            total = total + cuentas[cod]["v"]
    return total


def _ratio(num: np.ndarray, den: np.ndarray) -> np.ndarray:
    out = np.full(12, np.nan)
    ok = den != 0
    out[ok] = num[ok] / den[ok]
    return out


def staff_freelance_devengado(inputs: dict):
    """Staff freelance llevado al mes devengado.

    inputs['staff_freelance_facturado'] = {persona: [12 montos POSITIVOS por mes de
    factura]} -- copia de la tabla 'Staff Freelance' de 'Gastos RRHH' en la planilla,
    donde se corrigen a mano las facturas mal emitidas. Se corre
    'staff_freelance_desfase_meses' (default 1): lo facturado en el mes m+1 es el
    costo devengado del mes m. Lo facturado en enero (trabajo de diciembre del anio
    anterior) queda afuera, y diciembre queda en 0 hasta tener las facturas de enero.

    Devuelve (total_negativo[12], [{'nombre', 'devengado'(negativo), 'manual_dev'}]),
    donde manual_dev son los meses DEVENGADOS que vienen de una celda corregida a mano.
    Compatibilidad: si solo existe 'staff_freelance' (lista ya devengada, negativa),
    se usa tal cual sin detalle por persona."""
    fact = inputs.get("staff_freelance_facturado")
    if not fact:
        v = np.array(inputs.get("staff_freelance") or [0.0] * 12, dtype=float)
        return v, []
    k = int(inputs.get("staff_freelance_desfase_meses", 1))
    manual = inputs.get("staff_freelance_manual", {})
    total = np.zeros(12)
    personas = []
    for nombre, montos in fact.items():
        f = np.array(montos, dtype=float)
        dev = np.zeros(12)
        dev[: 12 - k] = f[k:]
        dev = -dev
        total = total + dev
        manual_dev = [m - k for m in manual.get(nombre, []) if 1 <= m - k <= 12]
        personas.append({"nombre": nombre, "devengado": dev, "manual_dev": manual_dev})
    return total, personas


MESES_NOMBRE = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
                "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def staff_sin_facturar(inputs: dict, anio: int, mes_actual: int) -> list[dict]:
    """Staff freelance que facturo en el mes m-2 pero NO en el m-1 (m = mes en
    curso, por mes de FACTURA, no devengado). Ej.: en noviembre, factura en
    septiembre y no en octubre -> alerta. Si ya lleva 2+ meses sin facturar se
    asume que dejo de trabajar con la agencia y no se alerta (criterio de
    Javier, 2026-11-26).

    Solo aplica al anio en curso y desde marzo (enero/febrero necesitarian el
    diciembre del anio anterior, que inputs.json no trae). Ojo: lee la copia de
    la planilla en inputs.json, asi que si no se re-sincronizo despues de que
    llegaron las facturas, la alerta puede ser falsa."""
    fact = inputs.get("staff_freelance_facturado") or {}
    if inputs.get("anio") != anio or mes_actual < 3:
        return []
    ult, ante = mes_actual - 1, mes_actual - 2  # 1-based
    out = []
    for nombre, montos in fact.items():
        if abs(montos[ult - 1]) <= 0.5 and montos[ante - 1] > 0.5:
            out.append({"nombre": nombre, "mes_falta": ult, "mes_ultima": ante,
                        "importe_ultima": float(montos[ante - 1])})
    return out


def calcular(df: pd.DataFrame, inputs: dict, anio: int, ajustes_usd: dict | None = None) -> dict:
    """`ajustes_usd`: salida de ajuste_usd.calcular_ajustes() (opcional). Si viene,
    se suma una linea 'Ajuste cotizacion compras USD' a los costos indirectos."""
    cuentas = cuentas_del_anio(df, anio)
    arr = lambda k: np.array(inputs.get(k) or [0.0] * 12, dtype=float)  # noqa: E731

    # Meses con datos en el libro (el resto se muestra como "—").
    actividad = np.zeros(12)
    for c in cuentas.values():
        actividad = actividad + np.abs(c["v"])
    meses_datos = [i + 1 for i in range(12) if actividad[i] > 0.005]

    filas = []

    def fila(id_, label, tipo, valores, *, pct=False, total=None, detalle=False, nota=None, marcas=None):
        v = np.asarray(valores, dtype=float)
        if total is None:
            total = float(np.nansum(v))
        filas.append({
            "id": id_, "label": label, "tipo": tipo, "pct": pct,
            "valores": [None if np.isnan(x) else float(x) for x in v],
            "total": None if (total is None or (isinstance(total, float) and np.isnan(total))) else float(total),
            "detalle": detalle, "nota": nota, "marcas": sorted(marcas or []),
        })

    def detalle_cuentas(codigos):
        for cod in sorted(codigos):
            if cod in cuentas and np.any(np.abs(cuentas[cod]["v"]) > 0.005):
                fila(f"cta-{cod}", cuentas[cod]["nombre"], "det", cuentas[cod]["v"], detalle=True)

    clasificadas = set()

    def usar(codigos):
        clasificadas.update(codigos)
        return codigos

    # ---------------- INGRESOS ----------------
    fila("h-ingresos", "INGRESOS", "sec", np.zeros(12), total=None)
    codigos_ing = {c for c in cuentas if str(c)[0] == "4"}
    prod_ing = codigos_ing & usar(config.INGRESOS_PRODUCCION)
    med_ing = codigos_ing & usar(config.INGRESOS_MEDIOS)
    otros_ing = codigos_ing - prod_ing - med_ing
    clasificadas.update(otros_ing)
    detalle_cuentas(prod_ing)
    ing_prod = _suma(cuentas, prod_ing)
    fila("ing-prod", "Producción", "grp", ing_prod)
    detalle_cuentas(med_ing)
    ing_med = _suma(cuentas, med_ing)
    fila("ing-med", "Medios", "grp", ing_med)
    detalle_cuentas(otros_ing)
    ing_otros = _suma(cuentas, otros_ing)
    fila("ing-otros", "Otros (dif. de cambio, intereses, etc.)", "grp", ing_otros)
    ingresos = ing_prod + ing_med + ing_otros
    fila("ingresos", "INGRESOS", "tot", ingresos)

    # ---------------- COSTOS DIRECTOS ----------------
    codigos_cos = {c for c in cuentas if str(c)[0] == "5"}
    cd_med = codigos_cos & usar(config.COSTOS_MEDIOS)
    cd_prod = codigos_cos & usar(config.COSTOS_PRODUCCION)
    fila("h-directos", "COSTOS DIRECTOS", "sec", np.zeros(12), total=None)
    detalle_cuentas(cd_med)
    costo_med = _suma(cuentas, cd_med)
    fila("cd-med", "Medios", "grp", costo_med)
    detalle_cuentas(cd_prod)
    costo_prod = _suma(cuentas, cd_prod)
    fila("cd-prod", "Producción", "grp", costo_prod)
    costos_directos = costo_med + costo_prod
    fila("costos-directos", "COSTOS DIRECTOS", "tot", costos_directos)

    mg_bruto = ingresos + costos_directos
    fila("mg-bruto", "MARGEN BRUTO", "tot", mg_bruto)
    fila("mg-pct", "% s/ ingresos", "pct", _ratio(mg_bruto, ingresos), pct=True,
         total=float(_ratio(np.array([mg_bruto.sum()] * 12), np.array([ingresos.sum()] * 12))[0]))

    # ---------------- RRHH (inputs manuales) ----------------
    staff_free, personas = staff_freelance_devengado(inputs)
    staff_blanco = arr("staff_blanco")
    rrhh = staff_free + staff_blanco
    fila("h-rrhh", "RRHH", "sec", np.zeros(12), total=None)
    for p in personas:
        if np.any(np.abs(p["devengado"]) > 0.5):
            fila(f"staff-{p['nombre']}", p["nombre"], "det", p["devengado"], detalle=True, marcas=p["manual_dev"])
    fila("rrhh-free", "Staff Freelance (devengado)", "grp", staff_free,
         nota="Imputado al mes devengado: la factura llega a principios del mes siguiente. "
              "Las correcciones de facturas mal emitidas se hacen en la planilla (Gastos RRHH).")
    fila("rrhh-blanco", "Staff en relación de dependencia", "grp", staff_blanco)
    fila("rrhh", "RRHH", "sub", rrhh)

    # ---------------- COSTOS FIJOS ----------------
    fila("h-fijos", "COSTOS FIJOS", "sec", np.zeros(12), total=None)
    fijos_total = np.zeros(12)
    varios = np.zeros(12)
    for grupo in config.ORDEN_GRUPOS_FIJOS:
        cods = codigos_cos & usar(config.GRUPOS_FIJOS[grupo])
        detalle_cuentas(cods)
        s = _suma(cuentas, cods)
        fijos_total = fijos_total + s
        if grupo == "Varios":
            varios = s
        fila(f"fj-{grupo}", grupo, "grp", s)

    # Cuentas de costo que no estan mapeadas: se incluyen en Costos Fijos
    # (para no perderlas en silencio) y el informe las avisa.
    usar(config.CUENTAS_STAFF_LIBRO)
    excluidas_staff = codigos_cos & config.CUENTAS_STAFF_LIBRO
    sueldos_libro = {c for c in codigos_cos if str(c).startswith(config.PREFIJO_SUELDOS_LIBRO)}
    sin_clasificar_cos = codigos_cos - clasificadas - sueldos_libro
    sin_clasificar_ing = set()  # los ingresos no mapeados ya caen en "Otros"
    s = _suma(cuentas, sin_clasificar_cos)
    if np.any(np.abs(s) > 0.5):
        detalle_cuentas(sin_clasificar_cos)
        fila("fj-sin-clasificar", "Sin clasificar (revisar mapeo)", "grp", s)
        fijos_total = fijos_total + s
    fila("fijos", "COSTOS FIJOS (sin RRHH)", "sub", fijos_total)

    retiro = arr("retiro_socio_estimado")
    # Ajuste de cotizacion de compras en USD (ver ajuste_usd.py): el libro tiene
    # la cotizacion que se cargo a mano; esto lo lleva al BNA comprador del dia.
    ajuste_total = np.zeros(12)
    items_usd = (ajustes_usd or {}).get("items", [])
    for n, it in enumerate(items_usd):
        v = np.zeros(12)
        v[it["mes"] - 1] = it["ajuste"]
        ajuste_total = ajuste_total + v
        usd_txt = f"{it['usd']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".").removesuffix(",00")
        fila(f"usd-{n}", f"{it['proveedor']} (USD {usd_txt})", "det", v, detalle=True)
    if items_usd:
        fila("ajuste-usd", "Diferencia de cotización compras USD", "grp", ajuste_total,
             nota="No es el costo de la compra (ese ya está en el libro): es la diferencia entre el dólar "
                  "cargado en Advertys y el oficial BNA comprador del día de la factura. "
                  "Positivo = el costo real fue menor. Detalle por compra debajo de la tabla.")
    fila("retiro", "Retiro socio (estimado)", "grp", retiro,
         nota="Número estimado para que el resultado sea más realista; no sale del libro.")
    indirectos = rrhh + fijos_total + retiro + ajuste_total
    fila("indirectos", "TOTAL COSTOS INDIRECTOS (RRHH + fijos + retiro)", "tot", indirectos)

    resultado = ingresos + costos_directos + indirectos
    fila("resultado", "RESULTADO", "tot", resultado)
    fila("resultado-pct", "% s/ ingresos", "pct", _ratio(resultado, ingresos), pct=True,
         total=float(_ratio(np.array([resultado.sum()] * 12), np.array([ingresos.sum()] * 12))[0]))
    fila("resultado-s-varios", "RESULTADO s/ VARIOS (sin gastos varios particulares)", "sub", resultado - varios)

    # ---------------- VISTA MEDIOS: bruto vs neto ----------------
    neto_cods = codigos_ing & config.INGRESOS_MEDIOS_NETO
    pass_cods = codigos_ing & config.INGRESOS_MEDIOS_PASSTHROUGH
    medios_neto = _suma(cuentas, neto_cods)
    pass_fact = _suma(cuentas, pass_cods)
    dif_pass = pass_fact + costo_med
    # Se lee de arriba hacia abajo: facturado - pagado = margen, y el margen se
    # abre en lo que gana la agencia (neto) + lo facturado que todavia no tiene
    # el costo del medio cargado (dif_pass; deberia tender a 0). Reordenado
    # 2026-11-26 porque la version "bruto vs neto" confundia.
    fila("h-medios", "MEDIOS: CUÁNTO LE QUEDA A LA AGENCIA", "sec", np.zeros(12), total=None)
    fila("m-bruto", "Facturado a clientes por medios", "grp", medios_neto + pass_fact)
    fila("m-costo", "Pagado a los medios", "grp", costo_med,
         nota="Órdenes de publicidad, compras de medios sin OP y ajustes.")
    fila("m-mg", "Margen de medios", "sub", medios_neto + dif_pass)
    fila("m-neto", "Comisión, markup y bonificaciones", "parte", medios_neto,
         nota="Lo que gana la agencia con medios.")
    fila("m-dif", "Diferencia todavía sin costo cargado", "parte", dif_pass,
         nota="Facturado al cliente cuyo costo del medio todavía no está cargado (o al revés). "
              "Debería tender a 0; la columna Total es el acumulado del año.")
    fila("m-resultado", "RESULTADO sin esa diferencia", "tot", resultado - dif_pass,
         nota="Resultado conservador: saca la diferencia, que todavía puede revertirse.")

    # ---------------- CONTROLES ----------------
    staff_libro = _suma(cuentas, excluidas_staff)
    fila("c-staff", "Control: Staff monotributista en el libro (515060)", "ctl", staff_libro,
         nota="Informativo: el EERR usa Staff Freelance devengado de inputs.json, no el libro.")
    fila("c-staff-dif", "Control: libro − Staff Freelance devengado", "ctl", staff_libro - staff_free)

    avisos = []
    if np.any(np.abs(s) > 0.5):
        avisos.append("Hay cuentas de costo sin mapear en config.py (se sumaron a Costos Fijos como 'Sin clasificar'): "
                      + ", ".join(cuentas[c]["nombre"] for c in sorted(sin_clasificar_cos) if np.any(np.abs(cuentas[c]['v']) > 0.5)))
    sueldos_con_saldo = [cuentas[c]["nombre"] for c in sorted(sueldos_libro) if np.any(np.abs(cuentas[c]["v"]) > 0.5)]
    if sueldos_con_saldo:
        avisos.append("El libro tiene cuentas de sueldos con saldo (" + ", ".join(sueldos_con_saldo)
                      + ") que NO se suman al EERR porque Staff Blanco sale de inputs.json: revisar no estar omitiendo costos.")
    avisos.extend((ajustes_usd or {}).get("sin_cotizacion", []))
    otros_ing_nombres = [cuentas[c]["nombre"] for c in sorted(otros_ing) if np.any(np.abs(cuentas[c]["v"]) > 0.5)]

    return {
        "anio": anio,
        "meses_datos": meses_datos,
        "meses_incompletos": [int(m) for m in inputs.get("meses_incompletos", [])],
        "filas": filas,
        "avisos": avisos,
        "compras_usd": sorted(items_usd, key=lambda it: it.get("fecha", "")),
        "otros_ingresos": otros_ing_nombres,
        "tot": {
            "ingresos": float(ingresos.sum()),
            "mg_bruto": float(mg_bruto.sum()),
            "resultado": float(resultado.sum()),
            "resultado_sin_dif": float((resultado - dif_pass).sum()),
            "dif_pass": float(dif_pass.sum()),
            "medios_neto": float(medios_neto.sum()),
        },
        "series": {
            "resultado": resultado.tolist(),
            "mg_bruto": mg_bruto.tolist(),
            "ingresos": ingresos.tolist(),
            "dif_pass_acum": np.cumsum(dif_pass).tolist(),
        },
    }
