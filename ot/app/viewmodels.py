from app.labels import ESTADO_LABELS, ESTADOS_FACTURADOS, FACTURACION_LABELS
from app.models import EstadoFacturacion, EstadoTarea, OtInterna, Tarea


def grupo_key(t: Tarea) -> str:
    if t.ot_interna_id and t.ot_interna:
        return t.ot_interna.numero_interno
    return t.ot_ambigua or "sin número"


def puede_anular(t: Tarea) -> bool:
    if t.estado_tarea in (EstadoTarea.FINALIZADO, EstadoTarea.ANULADA):
        return False
    return t.estado_facturacion not in (EstadoFacturacion.FACTURADO, EstadoFacturacion.PARA_FACTURAR)


def mail_vm(m) -> dict:
    return {
        "id": m.id,
        "destinatarios": m.destinatarios,
        "asunto": m.asunto,
        "cuerpo": m.cuerpo,
        "estado": m.estado.name,
        "error_detalle": m.error_detalle,
        "enviado_en_label": m.enviado_en.strftime("%d/%m %H:%M"),
    }


def responsables_con_mail(t: Tarea) -> list[dict]:
    """Responsables de la tarea con su mail — separa los que tienen mail
    cargado (destinatarios posibles) de los que no (para avisar en el
    composer en vez de mandarles nada)."""
    return [
        {"id": r.responsable_id, "nombre": r.responsable.nombre, "mail": r.responsable.mail}
        for r in t.responsables
    ]


def tarea_vm(t: Tarea) -> dict:
    responsables = [r.responsable.nombre for r in t.responsables]
    tipos = [tt.tipo_tarea.nombre for tt in t.tipos]
    presup_label = "—"
    if t.presupuestado is True:
        presup_label = "Si"
    elif t.presupuestado is False:
        presup_label = "No"

    necesita_revision = bool(t.ot_ambigua) or t.fecha_pedido is None or not tipos

    return {
        "id": t.id,
        "fecha_pedido": t.fecha_pedido.strftime("%d/%m") if t.fecha_pedido else "—",
        "fecha_pedido_iso": t.fecha_pedido.isoformat() if t.fecha_pedido else "",
        "tipos": tipos,
        "tipos_label": ", ".join(tipos) if tipos else "—",
        "pedido_por": t.pedido_por or "—",
        "responsables": responsables,
        "responsables_label": " / ".join(responsables) if responsables else "—",
        "responsable_ids": [r.responsable_id for r in t.responsables],
        "link_drive": t.link_drive,
        "presup_label": presup_label,
        "estado_tarea": t.estado_tarea.name if t.estado_tarea else "SIN_ESTADO",
        "estado_tarea_label": ESTADO_LABELS.get(t.estado_tarea, "SIN ESTADO"),
        "estado_facturacion": t.estado_facturacion.name,
        "estado_facturacion_label": FACTURACION_LABELS[t.estado_facturacion],
        "necesita_revision": necesita_revision,
        "ot_ambigua": t.ot_ambigua,
        "detalle": t.detalle,
        "otN": grupo_key(t),
        "ot_numero_form": t.ot_interna.numero_interno if t.ot_interna else (t.ot_ambigua or ""),
        "ot_cliente": t.ot_interna.cliente.nombre if t.ot_interna else "ALUAR",
        "ot_bloqueada": bool(t.ot_interna_id),
        "ot_asignada": bool(t.ot_interna_id or t.ot_ambigua),
        "puede_anular": puede_anular(t),
        "presupuestado": t.presupuestado,
        "fila_sheet_original": t.fila_sheet_original,
        "mails": [mail_vm(m) for m in t.mails],
        "responsables_con_mail": responsables_con_mail(t),
    }


def grupo_vm(key: str, tareas_orm: list[Tarea]) -> dict:
    ot = tareas_orm[0].ot_interna
    amb = not tareas_orm[0].ot_interna_id
    tareas = [tarea_vm(t) for t in tareas_orm]
    total = len(tareas)
    facturadas = sum(1 for t in tareas_orm if t.estado_facturacion in ESTADOS_FACTURADOS)

    return {
        "n": key,
        "amb": amb,
        "dps": ot.numero_ot_advertys if ot else None,
        "dps_label": f"OT sistema {ot.numero_ot_advertys}" if ot and ot.numero_ot_advertys else "sin OT de sistema",
        "ot_estado": ot.estado.value if ot else None,
        "apertura_label": (
            "abierta el " + ot.fecha_apertura.strftime("%d/%m")
            if ot and ot.fecha_apertura
            else "sin fecha de apertura"
        ),
        "tareas": tareas,
        "total": total,
        "facturadas": facturadas,
        "pct": round((facturadas / total) * 100) if total else 0,
        "progreso": f"{facturadas}/{total}",
    }


def ot_interna_vm(ot: OtInterna) -> dict:
    """Resumen de una OT interna para la vista de listado y de detalle —
    reusa grupo_vm cuando tiene tareas (misma forma que la fila de grupo de
    Tareas agrupada); una OT interna recién creada sin tareas todavía no
    debería poder existir hoy (solo se crea al guardar una tarea), pero se
    contempla igual para no romper si algún dato legado queda huérfano."""
    if not ot.tareas:
        return {
            "n": ot.numero_interno,
            "amb": False,
            "dps": ot.numero_ot_advertys,
            "dps_label": f"OT sistema {ot.numero_ot_advertys}" if ot.numero_ot_advertys else "sin OT de sistema",
            "ot_estado": ot.estado.value,
            "apertura_label": (
                "abierta el " + ot.fecha_apertura.strftime("%d/%m")
                if ot.fecha_apertura
                else "sin fecha de apertura"
            ),
            "tareas": [],
            "total": 0,
            "facturadas": 0,
            "pct": 0,
            "progreso": "0/0",
        }
    return grupo_vm(ot.numero_interno, ot.tareas)


def desglose_facturacion_vm(tareas: list[Tarea]) -> list[dict]:
    """Conteo de tareas por estado de facturación, solo los estados con al
    menos una tarea (ver README de diseño: 'sólo los que tienen > 0')."""
    conteos = {f: 0 for f in EstadoFacturacion}
    for t in tareas:
        conteos[t.estado_facturacion] += 1
    return [
        {"valor": f.name, "label": FACTURACION_LABELS[f], "n": conteos[f]}
        for f in EstadoFacturacion
        if conteos[f] > 0
    ]


def construir_grupos(tareas_orm: list[Tarea]) -> list[dict]:
    orden: list[str] = []
    por_clave: dict[str, list[Tarea]] = {}
    for t in tareas_orm:
        key = grupo_key(t)
        if key not in por_clave:
            por_clave[key] = []
            orden.append(key)
        por_clave[key].append(t)
    return [grupo_vm(k, por_clave[k]) for k in orden]
