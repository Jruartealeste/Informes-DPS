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
