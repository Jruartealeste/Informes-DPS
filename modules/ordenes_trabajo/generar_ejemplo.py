"""
Genera un Excel de ejemplo con la MISMA ESTRUCTURA que un export real de
"Orden Trabajo" desde Advertys, solo para probar el pipeline de punta a
punta sin depender del acceso al sistema real. Borralo cuando ya no lo
necesites.
"""
import random
from datetime import datetime, timedelta

import pandas as pd

random.seed(42)

anunciantes = ["Aluar Aluminio Argentino S.A.", "Fate S.A.I.C.I.", "Gihon Laboratorios Quimicos SRL", "Infa S.A."]
marcas = ["Institucional", "Linea Blanca", "Digital", None]
productos = ["Campaña Institucional", "Mantenimiento web", "Diseño de piezas", "Producción video"]
responsables = ["Javier Ruarte", "Bautista Zabaleta", "Veronica Di Meglio"]
equipos = ["Equipo A", "Equipo B", None]
estados = ["Abierta", "Cerrada", "Anulada"]
negocios = ["PRODUCCION", "MEDIOS"]

filas = []
base_date = datetime(2025, 1, 1)
for i in range(1, 121):
    fecha_abierta = base_date + timedelta(days=random.randint(0, 550))
    estado = random.choice(estados)
    fecha_cerrada = fecha_abierta + timedelta(days=random.randint(1, 60)) if estado != "Abierta" else None
    renta_teorica = round(random.uniform(0, 200), 2)
    renta_real = round(renta_teorica * random.uniform(0, 1.2), 2) if estado != "Abierta" else 0.0
    filas.append({
        "Negocio": random.choice(negocios),
        "Nro OT": 1000 + i,
        "Id": 2000 + i,
        "Anunciante": random.choice(anunciantes),
        "Marca": random.choice(marcas),
        "Producto": random.choice(productos),
        "Resumen": f"Orden de trabajo de ejemplo #{i}",
        "F.Abierta": fecha_abierta.strftime("%Y-%m-%d %H:%M:%S"),
        "F.Cerrada": fecha_cerrada.strftime("%Y-%m-%d %H:%M:%S") if fecha_cerrada else None,
        "Abierta por...": random.choice(responsables),
        "Equipo": random.choice(equipos),
        "Estado": estado,
        "Renta Teorica": renta_teorica,
        "Renta Real": renta_real,
    })

df = pd.DataFrame(filas)
out = "sample_data/advertys_export_ejemplo.xlsx"
df.to_excel(out, index=False)
print(f"Generado: {out} ({len(df)} filas)")
