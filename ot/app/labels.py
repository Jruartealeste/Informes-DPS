from app.models import EstadoFacturacion, EstadoTarea

ESTADO_LABELS: dict[EstadoTarea, str] = {
    EstadoTarea.PARA_INICIAR: "PARA INICIAR",
    EstadoTarea.EN_PROCESO: "EN PROCESO",
    EstadoTarea.PAUSADO: "PAUSADO",
    EstadoTarea.PENDIENTE_OK: "PENDIENTE OK",
    EstadoTarea.FINALIZADO: "FINALIZADO",
    EstadoTarea.APROBADO: "APROBADO",
    EstadoTarea.ANULADA: "ANULADA",
}

FACTURACION_LABELS: dict[EstadoFacturacion, str] = {
    EstadoFacturacion.SIN_FACTURAR: "SIN FACTURAR",
    EstadoFacturacion.PARA_FACTURAR: "PARA FACTURAR",
    EstadoFacturacion.FALTA_OK_CLIENTE: "FALTA OK CLIENTE",
    EstadoFacturacion.FACTURADO: "FACTURADO",
    EstadoFacturacion.NO_CORRESPONDE: "NO CORRESPONDE",
}

ESTADOS_FACTURADOS = {EstadoFacturacion.FACTURADO, EstadoFacturacion.NO_CORRESPONDE}
ESTADOS_TAREA_CERRADA = {EstadoTarea.FINALIZADO, EstadoTarea.APROBADO}

# Etiquetas lindas para el dropdown fijo de "Tipo de tarea" (pedido de
# Javier, 2026-09-23) — las claves son los `nombre` reales del catálogo
# `tipos_tarea` (ver ot/CLAUDE.md), heredados tal cual de la migración del
# Sheet, así que no se tocan para no romper datos/tests existentes. "otro"
# queda fuera a propósito: no está en la lista que pidió Javier.
TIPO_TAREA_LABELS: dict[str, str] = {
    "pautas_medios": "Pauta en medios",
    "diseño": "Diseños",
    "estrategia": "Estrategías",
    "gestion": "Gestión",
    "redaccion": "Redacción",
    "produccion": "Producción",
    "campania": "Campaña",
    "mant_web": "Mantenimiento WEB",
}
