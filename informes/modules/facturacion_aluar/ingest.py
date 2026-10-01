"""
Arma la tabla `facturacion_aluar`: ventas a ALUAR por mes, tipo de venta y
cuenta contable, a partir de Imputaciones + Facturas ya cargadas (ver
config.py e imputaciones.py para el detalle completo de las decisiones).

No lee ningun Excel nuevo -- requiere:
    1. `facturas` al dia (modules/facturas/ingest.py, via tools.actualizar_todo)
    2. Export crudo reciente de Imputaciones: `python -m modules.iibb.export`
    3. `python -m modules.facturacion_aluar.crawl_facturas_relacionadas`
       (para poder excluir con exactitud los pares factura+cancelacion
       que cruzan de mes -- ver su docstring). Si no corriste el paso 3
       todavia, este ingest igual funciona (excluye solo las
       cancelaciones, sin poder excluir la factura original que
       cancelan), pero puede sobrestimar meses puntuales -- avisa por
       consola cuantas cancelaciones quedaron sin resolver.

Se REEMPLAZA la tabla entera en cada corrida (igual que iibb/oc_pendientes_
generar/etc.): es un recorte con logica de negocio aplicada, no el libro
mayor crudo, no tiene sentido mantener historial de upserts.

Uso:
    python -m modules.facturacion_aluar.ingest
"""
import sys
from datetime import datetime, timezone

import pandas as pd

import db
from . import config
from .imputaciones import imputaciones_aluar, _cargar_facturas_aluar

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS {config.DB_TABLE} (
    mes TEXT,
    tipo_venta TEXT,
    cuenta INTEGER,
    concepto TEXT,
    categoria TEXT,
    monto REAL,
    reclasificado INTEGER,
    ajuste_manual INTEGER,
    fecha_carga TEXT
);
"""

COLUMNAS = ["mes", "tipo_venta", "cuenta", "concepto", "categoria", "monto", "reclasificado", "ajuste_manual", "fecha_carga"]


def init_db():
    with db.get_connection() as conn:
        conn.execute(SCHEMA)
        conn.commit()


def reemplazar_todo(records: list[dict]) -> int:
    with db.get_connection() as conn:
        conn.execute(f"DELETE FROM {config.DB_TABLE}")
        if records:
            placeholders = ", ".join("?" for _ in COLUMNAS)
            sql = f"INSERT INTO {config.DB_TABLE} ({', '.join(COLUMNAS)}) VALUES ({placeholders})"
            conn.executemany(sql, [tuple(r.get(c) for c in COLUMNAS) for r in records])
        conn.commit()
    return len(records)


def _cargar_relaciones() -> pd.DataFrame:
    with db.get_connection() as conn:
        try:
            return pd.read_sql(f"SELECT * FROM {config.DB_TABLE_RELACIONADAS}", conn)
        except Exception:
            return pd.DataFrame(columns=["clave", "tipo_asiento", "numero_referencia", "factura_relacionada", "fecha_crawl"])


def _claves_a_excluir(df: pd.DataFrame, relaciones: pd.DataFrame, facturas: pd.DataFrame) -> tuple[set, int]:
    """Devuelve (claves_a_excluir, cantidad_sin_resolver). Excluye siempre
    los documentos TR='CA' (nunca son venta real), y ademas la factura
    ORIGINAL que cada cancelacion revierte cuando se pudo resolver via el
    crawl (ver docstring del modulo) -- si no se pudo, la cancelacion se
    excluye igual pero puede quedar un remanente si esa factura se
    reemitio en otro mes."""
    claves_ca = set(df.loc[df["TR"] == "CA", "clave"])
    excluir = set(claves_ca)

    sin_resolver = 0
    facturas_fa = facturas[facturas["tipo_referencia"] == "FA"]
    for _, r in relaciones.iterrows():
        candidatos = facturas_fa[
            (facturas_fa["tipo_asiento"] == r["tipo_asiento"])
            & (facturas_fa["numero_referencia"] == r["factura_relacionada"])
        ]
        if candidatos.empty:
            sin_resolver += 1
            continue
        excluir.update(candidatos["clave"])

    resueltas = set(relaciones["clave"]) if not relaciones.empty else set()
    sin_resolver += len(claves_ca - resueltas)
    return excluir, sin_resolver


def _concepto_por_cuenta(df: pd.DataFrame) -> dict:
    return (
        df.groupby("Cuenta")["Nombre Cuenta"]
        .agg(lambda s: s.mode().iloc[0].strip() if not s.mode().empty else "")
        .to_dict()
    )


def _ajuste_manual_usd(facturas: pd.DataFrame) -> dict | None:
    """Ver config.AJUSTE_MANUAL_USD_HOSTING -- solo se agrega si esa
    factura sigue existiendo (si se anula alguna vez, deja de sumarse)."""
    ajuste = config.AJUSTE_MANUAL_USD_HOSTING
    fila = facturas[
        (facturas["numero_referencia"] == ajuste["numero_referencia"])
        & (facturas["tipo_asiento"] == ajuste["tipo_asiento"])
    ]
    if fila.empty:
        return None
    mes = fila.iloc[0]["mes"]
    return {
        "mes": mes,
        "tipo_venta": config.TA_TIPO_VENTA[ajuste["tipo_asiento"]],
        "cuenta": 510010,
        "concepto": ajuste["concepto"],
        "categoria": ajuste["categoria"],
        "monto": ajuste["monto"],
        "reclasificado": 0,
        "ajuste_manual": 1,
    }


def construir_registros() -> list[dict]:
    facturas = _cargar_facturas_aluar()
    df = imputaciones_aluar(solo_cuentas_ingreso=True)
    relaciones = _cargar_relaciones()

    excluir, sin_resolver = _claves_a_excluir(df, relaciones, facturas)
    if sin_resolver:
        print(
            f"AVISO: {sin_resolver} documento(s) de cancelacion sin 'Factura Relacionada' resuelta "
            "-- correr 'python -m modules.facturacion_aluar.crawl_facturas_relacionadas' para precision total."
        )

    kept = df[~df["clave"].isin(excluir)].copy()
    concepto_por_cuenta = _concepto_por_cuenta(df)

    grp = kept.groupby(["mes", "tipo_venta", "Cuenta"])["Importe"].sum().reset_index()
    grp["monto"] = (-grp["Importe"]).round(2)
    grp = grp.rename(columns={"Cuenta": "cuenta"})

    # Reclasificacion dinamica: si en un (mes, tipo_venta) aparecio algo en
    # CUENTA_RECLASIFICACION, todas las filas de las cuentas afectadas de
    # ese mismo (mes, tipo_venta) se marcan reclasificado=True (ver config.py).
    grupos_reclasificados = set(
        grp.loc[(grp["cuenta"] == config.CUENTA_RECLASIFICACION) & (grp["monto"] != 0), ["mes", "tipo_venta"]]
        .apply(tuple, axis=1)
    )

    registros = []
    for _, fila in grp.iterrows():
        if fila["cuenta"] not in config.CATEGORIA_POR_CUENTA:
            continue
        reclasificado = (
            fila["cuenta"] in config.CUENTAS_AFECTADAS_POR_RECLASIFICACION
            and (fila["mes"], fila["tipo_venta"]) in grupos_reclasificados
        )
        registros.append({
            "mes": fila["mes"],
            "tipo_venta": fila["tipo_venta"],
            "cuenta": int(fila["cuenta"]),
            "concepto": concepto_por_cuenta.get(fila["cuenta"], ""),
            "categoria": config.CATEGORIA_POR_CUENTA[fila["cuenta"]],
            "monto": float(fila["monto"]),
            "reclasificado": int(reclasificado),
            "ajuste_manual": 0,
        })

    ajuste = _ajuste_manual_usd(facturas)
    if ajuste:
        registros.append(ajuste)

    ahora = datetime.now(timezone.utc).isoformat()
    for r in registros:
        r["fecha_carga"] = ahora
    return registros


def main():
    init_db()
    try:
        registros = construir_registros()
    except FileNotFoundError:
        print(f"ERROR: falta {config.IMPUTACIONES_EXPORT_PATH}. Corre 'python -m modules.iibb.export' primero.")
        sys.exit(1)

    cantidad = reemplazar_todo(registros)
    total = sum(r["monto"] for r in registros)
    print(f"OK: {cantidad} fila(s) guardadas en {config.DB_TABLE}. Total facturado: $ {total:,.2f}")


if __name__ == "__main__":
    main()
