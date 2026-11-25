"""Tests del calculo puro del Estado de Resultados (sin Advertys).
Correr: python -m tests.test_estado_resultados  (o pytest)

Parte A: parser de importes y calculo sobre un balance sintetico.
Parte B (si existe el export real): cruce contra las cifras de la planilla
Google "EERR Nuevo" verificadas el 2026-11-25 (enero y acumulado)."""
import json

import pandas as pd

from modules.estado_resultados import compute, config


def test_parse_importe_negativos():
    # Bug de common.normalizar_numero: '-$ 1.234,56' -> None
    assert compute.parse_importe("-$ 2.783.414,80") == -2783414.80
    assert compute.parse_importe("$ 1.234,56") == 1234.56
    assert compute.parse_importe("$ 0,00") == 0.0
    assert compute.parse_importe(None) == 0.0


def _balance_sintetico():
    filas = [
        # (mes, nombre, neto) -- ingresos en credito (negativo), costos en debito
        (1, "411010-FEE", -1000.0),
        (1, "411075-VTA SERVICIOS MEDIOS (OP)", -5000.0),
        (1, "411076-VENTA MARKUP MEDIOS", -500.0),
        (1, "510020-COSTO SERV DE MEDIOS (OP)", 4800.0),
        (1, "510010-COSTO PRODUCCIÓN DE TERCEROS (OC)", 300.0),
        (1, "517250-GASTOS PRODUCCION X CLIENTE", 100.0),   # grupo Produccion (bug historico de la planilla)
        (1, "517545-SISTEMA OPERATIVO (Softwares y Licencias)", 50.0),  # Sistema (omitido historicamente)
        (1, "517515-ALQUILER", 200.0),
        (1, "515060-COSTO STAFF MONOTRIBUTISTA", 900.0),     # excluida: sale de inputs
        (1, "599999-CUENTA NUEVA", 10.0),                    # sin mapear -> Sin clasificar
    ]
    df = pd.DataFrame(filas, columns=["mes", "nombre", "neto"])
    df["anio"] = 2026
    df["codigo"] = df["nombre"].str.split("-").str[0].astype(int)
    return df


def _fila(r, id_):
    return next(f for f in r["filas"] if f["id"] == id_)


def test_calculo_sintetico():
    inputs = {"staff_freelance": [-70] + [0] * 11, "staff_blanco": [-30] + [0] * 11,
              "retiro_socio_estimado": [-20] + [0] * 11, "meses_incompletos": []}
    r = compute.calcular(_balance_sintetico(), inputs, 2026)
    assert r["meses_datos"] == [1]
    assert _fila(r, "ingresos")["valores"][0] == 6500.0
    # 517250 entra en costos directos de Produccion (el rango de la planilla lo omitia)
    assert _fila(r, "cd-prod")["valores"][0] == -400.0
    assert _fila(r, "costos-directos")["valores"][0] == -5200.0
    assert _fila(r, "mg-bruto")["valores"][0] == 1300.0
    # Sistema entra a fijos; Staff 515060 NO (sale de inputs); sin clasificar SI y avisa
    assert _fila(r, "fj-Sistema")["valores"][0] == -50.0
    assert _fila(r, "fj-sin-clasificar")["valores"][0] == -10.0
    assert _fila(r, "fijos")["valores"][0] == -260.0
    assert r["avisos"] and "599999" in r["avisos"][0]
    # indirectos = rrhh(-100) + fijos(-260) + retiro(-20)
    assert _fila(r, "indirectos")["valores"][0] == -380.0
    assert _fila(r, "resultado")["valores"][0] == 1300.0 - 380.0
    # Medios: neto 500, pass-through 5000 vs costo 4800 -> diferencia +200
    assert _fila(r, "m-neto")["valores"][0] == 500.0
    assert _fila(r, "m-dif")["valores"][0] == 200.0
    assert _fila(r, "m-resultado")["valores"][0] == 1300.0 - 380.0 - 200.0
    # MG medios (neto + dif) == ingresos medios + costo medios
    assert _fila(r, "m-mg")["valores"][0] == (5000.0 + 500.0) - 4800.0


def test_ajuste_usd():
    from modules.estado_resultados import ajuste_usd as au
    # Energyear (3/9/26): cargado 1535, BNA comprador 1485 -> el costo real es 410.000 menor
    assert au.ajuste(8200, 1535, 1485) == 410_000
    # si el BNA es mayor al cargado, el costo real es mayor -> ajuste negativo
    assert au.ajuste(100, 1400, 1450) == -5_000
    cot = {"2026-03-13": 1360.0, "2026-03-16": 1365.0}
    assert au.tc_comprador("2026-03-16", cot) == (1365.0, "2026-03-16")
    # sabado 14/3: usa el viernes 13/3
    assert au.tc_comprador("2026-03-14", cot) == (1360.0, "2026-03-13")
    # clave: '030006' (texto con ceros) y 30006 (numero) tienen que cruzar
    assert au._clave("CP", "030006", "000101333623") == au._clave("CP", 30006, 101333623.0)


def test_ajuste_usd_entra_al_resultado():
    inputs = {"staff_freelance": [0] * 12, "staff_blanco": [0] * 12, "retiro_socio_estimado": [0] * 12}
    base = compute.calcular(_balance_sintetico(), inputs, 2026)
    ajustes = {"items": [{"mes": 1, "proveedor": "X", "referencia": "1", "usd": 10.0,
                          "tc_cargado": 1500.0, "tc_bna": 1400.0, "ajuste": 1000.0}], "sin_cotizacion": []}
    con = compute.calcular(_balance_sintetico(), inputs, 2026, ajustes)
    assert _fila(con, "ajuste-usd")["valores"][0] == 1000.0
    assert _fila(con, "resultado")["valores"][0] == _fila(base, "resultado")["valores"][0] + 1000.0
    # sin ajustes no cambia nada ni aparece la fila
    assert not any(f["id"] == "ajuste-usd" for f in base["filas"])


def test_contra_planilla_si_hay_export():
    if not config.BALANCE_CSV.exists() or not config.INPUTS_JSON.exists():
        return
    df = compute.cargar_balance()
    inputs = json.loads(config.INPUTS_JSON.read_text(encoding="utf-8"))
    r = compute.calcular(df, inputs, 2026)
    # Cifras de la planilla "EERR Nuevo" (enero 2026), ya corregida.
    assert abs(_fila(r, "ingresos")["valores"][0] - 359_882_340.56) < 1
    assert abs(_fila(r, "costos-directos")["valores"][0] - (-233_239_169.46)) < 1
    assert abs(_fila(r, "fijos")["valores"][0] - (-2_444_884.13)) < 1
    assert abs(_fila(r, "indirectos")["valores"][0] - (-30_565_383.97)) < 1
    assert abs(_fila(r, "resultado")["valores"][0] - 96_077_787.13) < 1


if __name__ == "__main__":
    test_parse_importe_negativos()
    test_calculo_sintetico()
    test_ajuste_usd()
    test_ajuste_usd_entra_al_resultado()
    test_contra_planilla_si_hay_export()
    print("OK: tests de estado_resultados")
