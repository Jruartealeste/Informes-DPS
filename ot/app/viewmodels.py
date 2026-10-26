import hashlib
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException

from app.labels import ESTADO_LABELS, ESTADOS_FACTURADOS, FACTURACION_LABELS, TIPO_TAREA_LABELS
from app.models import (
    Estimado,
    EstadoFacturacion,
    EstadoSolicitudAltaEstimado,
    EstadoSolicitudAltaOt,
    EstadoTarea,
    OtInterna,
    SolicitudAltaEstimado,
    SolicitudAltaOt,
    Tarea,
)


def parsear_estado(enum_cls, valor: str, nombre: str, *, vacio_es_none: bool = False):
    """Convierte el valor de un form al miembro del enum; 422 si no existe
    (en vez de KeyError -> 500). Con `vacio_es_none`, '' es "sin estado"."""
    if not valor and vacio_es_none:
        return None
    try:
        return enum_cls[valor]
    except KeyError:
        raise HTTPException(422, f"{nombre} inválido.")


def grupo_key(t: Tarea) -> str:
    if t.ot_interna_id and t.ot_interna:
        return t.ot_interna.numero_interno
    return t.ot_ambigua or "sin número"


def motivo_no_anulable(t: Tarea) -> str | None:
    """Por qué la tarea no se puede anular, o None si se puede. Una tarea
    facturada o marcada para facturar no se anula (decisión de Javier, 2026-10-07);
    las finalizadas sí, con advertencia (ver advertencia_anular)."""
    if t.estado_tarea == EstadoTarea.ANULADA:
        return "Ya anulada"
    if t.estado_facturacion == EstadoFacturacion.FACTURADO:
        return "Facturada: no se puede anular"
    if t.estado_facturacion == EstadoFacturacion.PARA_FACTURAR:
        return "Para facturar: no se puede anular"
    if t.estimado_id is not None:
        return "Está en un Estimado: quitala del Estimado antes de anularla"
    return None


def puede_anular(t: Tarea) -> bool:
    return motivo_no_anulable(t) is None


def advertencia_anular(t: Tarea) -> str:
    texto = "¿Anular esta tarea? No se puede deshacer."
    if t.estado_tarea == EstadoTarea.FINALIZADO:
        return "⚠ Esta tarea ya está FINALIZADA. " + texto
    return texto


def mail_vm(m) -> dict:
    return {
        "id": m.id,
        "destinatarios": m.destinatarios,
        "remitente": m.remitente,
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


_AR = timezone(timedelta(hours=-3))  # Argentina, UTC-3 fijo (sin horario de verano)
# "Por vencer" = vence hoy o en los próximos DIAS_POR_VENCER días.
DIAS_POR_VENCER = 3
# Tareas cerradas: su vencimiento ya no se sigue.
_ESTADOS_SIN_SEGUIMIENTO = {EstadoTarea.FINALIZADO, EstadoTarea.APROBADO, EstadoTarea.ANULADA}


def links_de(texto: str | None) -> list[str]:
    """Vínculos de una tarea (tareas.link_drive guarda uno por línea)."""
    return [x.strip() for x in (texto or "").splitlines() if x.strip()]


def unir_links(valores: list[str]) -> str | None:
    """Inverso de links_de para guardar lo que vino del form (varios inputs
    link_drive); descarta vacíos y repetidos, respeta el orden."""
    vistos: list[str] = []
    for v in valores:
        for x in links_de(v):
            if x not in vistos:
                vistos.append(x)
    return "\n".join(vistos) or None


def hoy_ar() -> date:
    """Hoy en Argentina (el server corre en UTC: después de las 21 h AR ya
    sería mañana)."""
    return datetime.now(_AR).date()


def estado_vencimiento(t: Tarea, hoy: date | None = None) -> str | None:
    """"vencida", "por_vencer" o None (sin vencimiento, lejos, o tarea cerrada)."""
    if t.fecha_vencimiento is None or t.estado_tarea in _ESTADOS_SIN_SEGUIMIENTO:
        return None
    hoy = hoy or hoy_ar()
    if t.fecha_vencimiento < hoy:
        return "vencida"
    if t.fecha_vencimiento <= hoy + timedelta(days=DIAS_POR_VENCER):
        return "por_vencer"
    return None


def version_tarea(t: Tarea) -> str:
    """Huella del contenido editable de la tarea (campos + tipos + responsables).
    El drawer la manda al guardar: si cambió desde que se abrió, otra persona
    editó la tarea y guardar pisaría su trabajo (409). Se calcula por contenido
    y no con `actualizado_en`, que no cambia al editar solo tipos o responsables."""
    partes = (
        t.ot_interna_id, t.detalle, t.fecha_pedido, t.fecha_vencimiento, t.pedido_por, t.link_drive, t.presupuestado,
        t.estado_tarea, t.estado_facturacion,
        sorted(tt.tipo_tarea_id for tt in t.tipos), sorted(r.responsable_id for r in t.responsables),
    )
    return hashlib.sha1(repr(partes).encode()).hexdigest()[:16]


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
        "version": version_tarea(t),
        "fecha_pedido": t.fecha_pedido.strftime("%d/%m") if t.fecha_pedido else "—",
        "fecha_pedido_iso": t.fecha_pedido.isoformat() if t.fecha_pedido else "",
        "fecha_pedido_dma": t.fecha_pedido.strftime("%d/%m/%Y") if t.fecha_pedido else "",
        "fecha_vencimiento": t.fecha_vencimiento.strftime("%d/%m") if t.fecha_vencimiento else "—",
        "fecha_vencimiento_dma": t.fecha_vencimiento.strftime("%d/%m/%Y") if t.fecha_vencimiento else "",
        "vencimiento": estado_vencimiento(t),
        "tipos": tipos,
        "tipos_label": ", ".join(TIPO_TAREA_LABELS.get(n, n) for n in tipos) if tipos else "—",
        "pedido_por": t.pedido_por or "—",
        "responsables": responsables,
        "responsables_label": " / ".join(responsables) if responsables else "—",
        "responsable_ids": [r.responsable_id for r in t.responsables],
        "link_drive": t.link_drive,
        "links_drive": links_de(t.link_drive),
        "presup_label": presup_label,
        "estado_tarea": t.estado_tarea.name if t.estado_tarea else "SIN_ESTADO",
        "estado_tarea_label": ESTADO_LABELS.get(t.estado_tarea, "SIN ESTADO"),
        "estado_facturacion": t.estado_facturacion.name,
        "estado_facturacion_label": FACTURACION_LABELS[t.estado_facturacion],
        "necesita_revision": necesita_revision,
        "ot_ambigua": t.ot_ambigua,
        "detalle": t.detalle,
        "otN": grupo_key(t),
        "ot_dps": t.ot_interna.numero_ot_advertys if t.ot_interna else None,
        "ot_numero_form": t.ot_interna.numero_interno if t.ot_interna else (t.ot_ambigua or ""),
        "ot_cliente": t.ot_interna.cliente.nombre if t.ot_interna else "ALUAR",
        "ot_titulo": t.ot_interna.titulo if t.ot_interna else None,
        "ot_bloqueada": bool(t.ot_interna_id),
        "ot_asignada": bool(t.ot_interna_id or t.ot_ambigua),
        "puede_anular": puede_anular(t),
        "motivo_no_anulable": motivo_no_anulable(t) or "",
        "advertencia_anular": advertencia_anular(t),
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
        "titulo": ot.titulo if ot else None,
        "cliente_id": ot.cliente_id if ot else None,
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
        # Semáforo del listado de OT internas: qué estados de facturación
        # tienen sus tareas (el estado es de cada tarea, no de la OT).
        "semaforo_fac": desglose_facturacion_vm(tareas_orm),
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
            "titulo": ot.titulo,
            "cliente_id": ot.cliente_id,
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
            "semaforo_fac": [],
        }
    return grupo_vm(ot.numero_interno, ot.tareas)


def _arg_shell(valor: str) -> str:
    """Entre comillas simples, que no expanden `$var`, backticks ni `$(...)` ni en
    PowerShell ni en bash; una comilla simple interna se duplica (PowerShell). Los
    saltos de línea se pasan a espacios para que el comando siga siendo una línea."""
    limpio = " ".join(valor.split())
    return "'" + limpio.replace("'", "''") + "'"


def _comando_crear_ot(s: SolicitudAltaOt) -> str:
    """Línea lista para copiar y correr a mano desde `informes/` (ver
    workflow `crear_ot.md`) -- esta app nunca ejecuta el script ella
    misma. Los textos son libres (los carga el equipo), así que se escapan."""
    partes = [
        "python -m modules.ordenes_trabajo.crear_ot",
        _arg_shell(s.anunciante),
        _arg_shell(s.resumen),
        _arg_shell(s.producto),
        _arg_shell(s.centro_costo),
    ]
    if s.equipo:
        partes.append(f"--equipo {_arg_shell(s.equipo)}")
    return " ".join(partes)


def solicitud_alta_vm(s: SolicitudAltaOt) -> dict:
    return {
        "id": s.id,
        "anunciante": s.anunciante,
        "resumen": s.resumen,
        "producto": s.producto,
        "centro_costo": s.centro_costo,
        "equipo": s.equipo,
        "estado": s.estado.name,
        "es_pendiente": s.estado == EstadoSolicitudAltaOt.PENDIENTE,
        "numero_ot_advertys": s.numero_ot_advertys,
        "comando": _comando_crear_ot(s),
        "ots": [ot.numero_interno for ot in s.ots],
        "creado_en": s.creado_en.strftime("%d/%m/%Y %H:%M"),
    }


def _comando_crear_estimado(s: SolicitudAltaEstimado, estimado: Estimado) -> str:
    """Línea lista para copiar y correr a mano desde `informes/` -- esta app
    nunca ejecuta `crear_estimado.py` ella misma (mismo criterio que
    `_comando_crear_ot`). OT de sistema y título no viajan en la solicitud:
    ya viven en el `Estimado` local que referencia."""
    partes = [
        "python -m modules.estimados_costos.crear_estimado",
        _arg_shell(estimado.numero_ot_advertys),
        _arg_shell(estimado.titulo),
    ]
    if s.fecha_solicitada:
        partes.append(f"--fecha-solicitada {_arg_shell(s.fecha_solicitada)}")
    if s.fecha_analisis:
        partes.append(f"--fecha-analisis {_arg_shell(s.fecha_analisis)}")
    return " ".join(partes)


def solicitud_alta_estimado_vm(s: SolicitudAltaEstimado) -> dict:
    estimado = s.estimados[0] if s.estimados else None
    return {
        "id": s.id,
        "estimado_id": estimado.id if estimado else None,
        "estimado_titulo": estimado.titulo if estimado else "—",
        "numero_ot_advertys": estimado.numero_ot_advertys if estimado else "—",
        "numero_estimado": estimado.numero_estimado if estimado else None,
        "fecha_solicitada": s.fecha_solicitada,
        "fecha_analisis": s.fecha_analisis,
        "estado": s.estado.name,
        "es_pendiente": s.estado == EstadoSolicitudAltaEstimado.PENDIENTE,
        "comando": _comando_crear_estimado(s, estimado) if estimado else "",
        "creado_en": s.creado_en.strftime("%d/%m/%Y %H:%M"),
    }


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
