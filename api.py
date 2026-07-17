"""
API minima de solo lectura sobre los datos ya cargados. Util para que
Claude Code (u otra herramienta) consulte los datos sin tener que leer
el Excel ni tocar SQLite directamente.

Uso:
    python api.py
    (queda escuchando en http://localhost:5000)

Ejemplos:
    curl http://localhost:5000/ordenes
    curl "http://localhost:5000/ordenes?anunciante=Aluar&estado=Abierta"
    curl http://localhost:5000/resumen/por-anunciante
    curl http://localhost:5000/resumen/por-mes
"""
import pandas as pd
from flask import Flask, jsonify, request

import db
from modules.ordenes_trabajo import config
from modules.ordenes_trabajo.ingest import init_db

app = Flask(__name__)


def query_df(sql, params=()):
    with db.get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=params)


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/ordenes")
def ordenes():
    filtros = []
    params = []
    for campo in ["anunciante", "estado", "responsable", "equipo", "negocio"]:
        valor = request.args.get(campo)
        if valor:
            filtros.append(f"{campo} = ?")
            params.append(valor)
    where = f"WHERE {' AND '.join(filtros)}" if filtros else ""
    df = query_df(f"SELECT * FROM {config.DB_TABLE} {where}", params)
    return jsonify(df.to_dict(orient="records"))


@app.get("/resumen/por-anunciante")
def resumen_anunciante():
    df = query_df(f"SELECT * FROM {config.DB_TABLE}")
    resumen = (
        df.groupby("anunciante")
        .agg(ordenes=("numero_ot", "count"), renta_real=("renta_real", "sum"))
        .reset_index()
        .sort_values("renta_real", ascending=False)
    )
    return jsonify(resumen.to_dict(orient="records"))


@app.get("/resumen/por-mes")
def resumen_mes():
    df = query_df(f"SELECT * FROM {config.DB_TABLE}")
    df["fecha_abierta"] = pd.to_datetime(df["fecha_abierta"], errors="coerce")
    df["mes"] = df["fecha_abierta"].dt.to_period("M").astype(str)
    resumen = (
        df.groupby("mes")
        .agg(ordenes=("numero_ot", "count"), renta_real=("renta_real", "sum"))
        .reset_index()
        .sort_values("mes")
    )
    return jsonify(resumen.to_dict(orient="records"))


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
