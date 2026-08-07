"""Datos de desarrollo para la pantalla Tareas.

Transcribe las ~30 filas reales de la pestaña ALUAR que ya estaban
embebidas (a modo de ejemplo) en el prototipo de diseño
(`Seguimiento de órdenes de trabajo/design_handoff_ots/design/Seguimiento de OTs.dc.html`,
array `OTS`), para poder probar la app con datos que se ven como los
reales. Esto NO reemplaza `scripts/migrar_sheet.py` (la migración real
del Sheet completo, con dry-run y revisión de Javier).

Uso: python -m scripts.seed   (parado en ot/, con DATABASE_URL configurado)
"""
import datetime as dt

from app.db import SessionLocal
from app.models import (
    Cliente,
    EstadoFacturacion,
    EstadoOtInterna,
    EstadoTarea,
    OtInterna,
    Tarea,
    TareaResponsable,
    TareaTipoTarea,
    TipoTarea,
)

TIPOS_TAREA = [
    "diseño", "redaccion", "produccion", "estrategia",
    "campania", "gestion", "mant_web", "pautas_medios", "otro",
]

TIPO_RAW_A_CATALOGO = {
    "diseños": "diseño",
    "producción": "produccion",
    "redacción": "redaccion",
    "estrategias": "estrategia",
    "gestión": "gestion",
}

ESTADOS_TAREA_CERRADA = {EstadoTarea.FINALIZADO, EstadoTarea.APROBADO}
ESTADOS_FAC_ABIERTOS = {
    EstadoFacturacion.SIN_FACTURAR,
    EstadoFacturacion.PARA_FACTURAR,
    EstadoFacturacion.FALTA_OK_CLIENTE,
}

# OT internas de la pestaña ALUAR (últimas ~30 filas del Sheet real).
# tarea: [fecha_pedido, tipos, detalle, pedido_por, responsables, drive, presup, estado, facturacion, fila]
OTS = [
    {"n": "4082", "dps": "", "ap": "18/09", "t": [
        ["—", "diseños", "Interiorismo > 01. sanfer", "marina", "pil", 1, "Si", "FINALIZADO", "SIN FACTURAR", 172]]},
    {"n": "4085", "dps": "", "ap": "22/09", "t": [
        ["17/07", "diseños", "diseño version ingles catalogo productos", "mica", "wan / pil", 1, "Si", "PENDIENTE OK", "SIN FACTURAR", 169],
        ["17/07", "diseños", "adaptar imágenes novedades", "mica", "wan / pil", 1, "Si", "FINALIZADO", "PARA FACTURAR", 170]]},
    {"n": "4086/4110", "dps": "", "ap": "23/12", "amb": "4086/4110", "t": [
        ["23/12", "—", "Video x2 / Brindis Empresas para Conecta", "cecilia", "wan", 1, "Si", "FINALIZADO", "SIN FACTURAR", 108]]},
    {"n": "4119", "dps": "", "ap": "02/02", "t": [
        ["02/07", "diseños", "Tarjetas personales - Diseño María Victoria Canullo", "marina", "pili", 0, "", "FINALIZADO", "PARA FACTURAR", 158],
        ["—", "diseños", "Tarjetas personales corporativas con todos los logos / nuevo diseño!", "marina", "pili", 0, "", "PENDIENTE OK", "SIN FACTURAR", 159]]},
    {"n": "4127", "dps": "", "ap": "04/03", "t": [
        ["04/03", "diseños", "FAA - FLYER", "marina", "fer", 1, "", "PENDIENTE OK", "SIN FACTURAR", 130]]},
    {"n": "4128", "dps": "", "ap": "10/03", "t": [
        ["26/06", "producción", "parque solar Abasto / video", "marina", "juli", 0, "No", "FINALIZADO", "NO CORRESPONDE", 156]]},
    {"n": "4132", "dps": "258", "ap": "26/03", "t": [
        ["26/03", "diseños", "lineamientos de comunicacion y diseño // ver de cobrar mas que una press", "maru", "todos", 0, "", "FINALIZADO", "PARA FACTURAR", 133]]},
    {"n": "4133", "dps": "259", "ap": "27/03", "t": [
        ["27/03", "diseños", "reporte de sostenibilidad 2025/2026", "mica", "fer", 0, "", "PENDIENTE OK", "SIN FACTURAR", 134]]},
    {"n": "4134", "dps": "260", "ap": "—", "t": [
        ["16/07", "producción", "Video final Mundial / conecta mp4 + pantallas avi // no se uso pero hay que cobrarlo", "ceci", "juli", 1, "Si", "FINALIZADO", "PARA FACTURAR", 167],
        ["22/07", "—", "Video RECAP Mundial 2026", "ceci", "—", 0, "Si", "PARA INICIAR", "SIN FACTURAR", 174]]},
    {"n": "4135", "dps": "263", "ap": "17/04", "t": [
        ["23/06", "diseños", "Feria de empleo > reentrega originales cambio qr", "juli", "fer", 1, "", "FINALIZADO", "PARA FACTURAR", 153]]},
    {"n": "4144", "dps": "", "ap": "12/06", "t": [
        ["12/06", "diseños", "cv pia", "juli", "—", 0, "", "FINALIZADO", "SIN FACTURAR", 146]]},
    {"n": "4148", "dps": "", "ap": "—", "t": [
        ["—", "producción", "Reglas que Salvan Vidas / pausado", "maru", "—", 0, "", "PAUSADO", "SIN FACTURAR", 150]]},
    {"n": "4149", "dps": "", "ap": "—", "t": [
        ["—", "estrategias, diseños", "Optimizacion redes", "—", "—", 0, "", "EN PROCESO", "SIN FACTURAR", 151]]},
    {"n": "4150", "dps": "", "ap": "—", "t": [
        ["—", "diseños", "PEAL > activaciones octubre", "—", "—", 0, "Si", "EN PROCESO", "SIN FACTURAR", 154],
        ["—", "diseños", "Stickers", "marina", "javi / juli / fer", 0, "Si", "PENDIENTE OK", "SIN FACTURAR", 155],
        ["—", "producción", "produccion testimoniales > sanfer + pm // presupuestar!!", "marina", "—", 0, "Si", "EN PROCESO", "SIN FACTURAR", 157]]},
    {"n": "4151", "dps": "", "ap": "—", "t": [
        ["—", "—", "fin de año ?? que se hace??", "—", "—", 0, "", "PARA INICIAR", "SIN FACTURAR", 152]]},
    {"n": "4152", "dps": "", "ap": "29/06", "t": [
        ["29/06", "diseños", "Simil manual de marca para elaborados", "juli", "fer", 0, "Si", "FINALIZADO", "PARA FACTURAR", 155]]},
    {"n": "4153", "dps": "", "ap": "02/07", "t": [
        ["02/07", "redacción", "Guía ESG / Apertura: textos", "juli", "flor / gato", 0, "", "FINALIZADO", "NO CORRESPONDE", 157]]},
    {"n": "4154", "dps": "285", "ap": "07/07", "t": [
        ["07/07", "producción", "Edicion video auspicio de programa TN / 8 seg", "maru", "juli", 0, "Si", "FINALIZADO", "PARA FACTURAR", 161]]},
    {"n": "4155", "dps": "", "ap": "06/07", "t": [
        ["06/07", "gestión", "Métricas para reporte de sostenibilidad - comunicaciones", "juli", "javi / flor", 0, "Si", "FINALIZADO", "SIN FACTURAR", 162]]},
    {"n": "4156", "dps": "", "ap": "07/07", "t": [
        ["07/07", "redacción, diseños", "adjudicacion licitación ALMASADI: conecta / nota web / gacetillas x2 / ig + in", "juli / maru", "flor / gato / fer", 0, "Si", "FINALIZADO", "SIN FACTURAR", 163]]},
    {"n": "4157", "dps": "", "ap": "14/07", "t": [
        ["14/07", "estrategias", "Clipping Gabriel Vendrell", "juli", "bau", 0, "", "EN PROCESO", "SIN FACTURAR", 164]]},
    {"n": "4158", "dps": "", "ap": "17/07", "t": [
        ["17/07", "redacción, diseños", "Anuncio 1/2pag en diario papel / aniversario Puerto Madryn", "pablo", "fer / gato / flor", 1, "Si", "FINALIZADO", "PARA FACTURAR", 165]]},
    {"n": "4159", "dps": "", "ap": "14/07", "t": [
        ["14/07", "producción", "Realización de retratos en la planta de San Fernando", "marina", "vero", 0, "Si", "EN PROCESO", "SIN FACTURAR", 166]]},
    {"n": "4160", "dps": "", "ap": "20/07", "t": [
        ["20/07", "diseños", "Pedido pieza interna", "juli", "pil", 1, "Si", "FINALIZADO", "PARA FACTURAR", 168]]},
    {"n": "4161", "dps": "", "ap": "24/07", "t": [
        ["—", "producción", "produccion retratos san fer", "marina", "—", 0, "Si", "PENDIENTE OK", "SIN FACTURAR", 171],
        ["24/07", "—", "Eventos - nuevos lineamientos", "maru", "emi / bauti", 0, "Si", "EN PROCESO", "SIN FACTURAR", 175]]},
    {"n": "4162", "dps": "", "ap": "27/07", "t": [
        ["27/07", "—", "grupo aluar", "—", "—", 0, "Si", "EN PROCESO", "SIN FACTURAR", 176]]},
    {"n": "4163", "dps": "", "ap": "29/07", "t": [
        ["29/07", "—", "logo lapicera", "mari", "fer", 0, "No", "FINALIZADO", "NO CORRESPONDE", 177]]},
    {"n": "sin número", "dps": "", "ap": "03/07", "amb": "sin número", "t": [
        ["03/07", "producción", "Edicion video conecta 9 de julio / 1 hs", "juli", "juli / flor", 0, "", "FINALIZADO", "NO CORRESPONDE", 160]]},
]


def parse_fecha(s: str) -> dt.date | None:
    if not s or s == "—":
        return None
    dia, mes = s.split("/")
    anio = 2025 if int(mes) >= 9 else 2026
    return dt.date(anio, int(mes), int(dia))


def parse_tipos(raw: str) -> list[str]:
    if not raw or raw == "—":
        return []
    return [TIPO_RAW_A_CATALOGO.get(x.strip(), x.strip()) for x in raw.split(",")]


def parse_responsables(raw: str) -> list[str]:
    if not raw or raw == "—":
        return []
    return [x.strip() for x in raw.split("/") if x.strip()]


def parse_presup(raw: str) -> bool | None:
    if raw == "Si":
        return True
    if raw == "No":
        return False
    return None


def main() -> None:
    db = SessionLocal()
    try:
        db.query(TareaResponsable).delete()
        db.query(TareaTipoTarea).delete()
        db.query(Tarea).delete()
        db.query(OtInterna).delete()
        db.query(TipoTarea).delete()
        db.query(Cliente).delete()
        db.flush()

        cliente = Cliente(nombre="ALUAR", anunciante_advertys="ALUAR ALUMINIO ARG.")
        db.add(cliente)
        db.flush()

        tipos_por_nombre = {}
        for nombre in TIPOS_TAREA:
            tipo = TipoTarea(nombre=nombre)
            db.add(tipo)
            tipos_por_nombre[nombre] = tipo
        db.flush()

        n_ots = 0
        n_tareas = 0

        for grupo in OTS:
            es_ambigua = "amb" in grupo
            ot_interna = None

            if not es_ambigua:
                filas = grupo["t"]
                abierta = any(
                    EstadoTarea[f[7].replace(" ", "_")] not in ESTADOS_TAREA_CERRADA
                    or EstadoFacturacion[f[8].replace(" ", "_")] in ESTADOS_FAC_ABIERTOS
                    for f in filas
                )
                ot_interna = OtInterna(
                    numero_interno=grupo["n"],
                    cliente_id=cliente.id,
                    fecha_apertura=parse_fecha(grupo["ap"]),
                    estado=EstadoOtInterna.ABIERTA if abierta else EstadoOtInterna.CERRADA,
                    numero_ot_advertys=grupo["dps"] or None,
                )
                db.add(ot_interna)
                db.flush()
                n_ots += 1

            for f in grupo["t"]:
                fecha, tipos_raw, detalle, pedido_por, responsables_raw, drive, presup, estado, fac, fila = f
                tarea = Tarea(
                    ot_interna_id=ot_interna.id if ot_interna else None,
                    ot_ambigua=grupo.get("amb") if es_ambigua else None,
                    fecha_pedido=parse_fecha(fecha),
                    detalle=detalle,
                    pedido_por=None if pedido_por == "—" else pedido_por,
                    link_drive="https://drive.google.com/drive/folders/…" if drive else None,
                    presupuestado=parse_presup(presup),
                    estado_tarea=EstadoTarea[estado.replace(" ", "_")],
                    estado_facturacion=EstadoFacturacion[fac.replace(" ", "_")],
                    fila_sheet_original=fila,
                )
                db.add(tarea)
                db.flush()

                for nombre_tipo in parse_tipos(tipos_raw):
                    tipo = tipos_por_nombre.get(nombre_tipo)
                    if tipo:
                        tarea.tipos.append(TareaTipoTarea(tipo_tarea_id=tipo.id))

                for nombre_resp in parse_responsables(responsables_raw):
                    tarea.responsables.append(TareaResponsable(nombre_libre=nombre_resp))

                n_tareas += 1

        db.commit()
        print(f"Seed OK: {n_ots} OT internas, {n_tareas} tareas.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
