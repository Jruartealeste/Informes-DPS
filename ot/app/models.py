import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class EstadoTarea(str, enum.Enum):
    PARA_INICIAR = "PARA_INICIAR"
    EN_PROCESO = "EN_PROCESO"
    PAUSADO = "PAUSADO"
    PENDIENTE_OK = "PENDIENTE_OK"
    FINALIZADO = "FINALIZADO"
    APROBADO = "APROBADO"
    ANULADA = "ANULADA"


class EstadoFacturacion(str, enum.Enum):
    SIN_FACTURAR = "SIN_FACTURAR"
    PARA_FACTURAR = "PARA_FACTURAR"
    FALTA_OK_CLIENTE = "FALTA_OK_CLIENTE"
    FACTURADO = "FACTURADO"
    NO_CORRESPONDE = "NO_CORRESPONDE"


class EstadoOtInterna(str, enum.Enum):
    ABIERTA = "ABIERTA"
    CERRADA = "CERRADA"


class EstadoEstimado(str, enum.Enum):
    BORRADOR = "BORRADOR"
    GENERADO = "GENERADO"


class EstadoSolicitudAltaOt(str, enum.Enum):
    PENDIENTE = "PENDIENTE"
    RESUELTA = "RESUELTA"


class EstadoSolicitudAltaEstimado(str, enum.Enum):
    PENDIENTE = "PENDIENTE"
    RESUELTA = "RESUELTA"


class EstadoMail(str, enum.Enum):
    BORRADOR = "BORRADOR"
    ENVIADO = "ENVIADO"
    ERROR = "ERROR"


class RolUsuario(str, enum.Enum):
    MIEMBRO = "MIEMBRO"
    APROBADOR_FACTURACION = "APROBADOR_FACTURACION"
    ADMIN = "ADMIN"


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True)
    nombre: Mapped[str] = mapped_column(String(120))
    rol: Mapped[RolUsuario] = mapped_column(default=RolUsuario.MIEMBRO)
    activo: Mapped[bool] = mapped_column(default=True)
    ultimo_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Cliente(Base):
    __tablename__ = "clientes"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(80), unique=True)
    anunciante_advertys: Mapped[str | None] = mapped_column(String(200))

    ots: Mapped[list["OtInterna"]] = relationship(back_populates="cliente")


class TipoTarea(Base):
    __tablename__ = "tipos_tarea"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(40), unique=True)


class Responsable(Base):
    __tablename__ = "responsables"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(80), unique=True)
    activo: Mapped[bool] = mapped_column(default=True)
    mail: Mapped[str | None] = mapped_column(String(200))


class OtInterna(Base):
    __tablename__ = "ot_interna"

    id: Mapped[int] = mapped_column(primary_key=True)
    numero_interno: Mapped[str] = mapped_column(String(20), unique=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id"))
    fecha_apertura: Mapped[date | None] = mapped_column(Date)
    estado: Mapped[EstadoOtInterna] = mapped_column(
        default=EstadoOtInterna.ABIERTA
    )
    numero_ot_advertys: Mapped[str | None] = mapped_column(String(20))
    solicitud_alta_id: Mapped[int | None] = mapped_column(ForeignKey("solicitudes_alta_ot.id"))

    cliente: Mapped["Cliente"] = relationship(back_populates="ots")
    tareas: Mapped[list["Tarea"]] = relationship(back_populates="ot_interna")
    solicitud_alta: Mapped["SolicitudAltaOt | None"] = relationship(back_populates="ots")


class SolicitudAltaOt(Base):
    """Pedido de alta de encabezado de OT en Advertys, generado desde el
    botón "Generar OT en Advertys" (ver ot/CLAUDE.md, decisión 2026-09-23:
    "solicitud + corrida manual"). La app nunca corre `crear_ot.py` ella
    misma -- no tiene ni va a tener las credenciales de Advertys (ver
    salvaguarda en el CLAUDE.md raíz) -- solo junta acá los datos ya
    confirmados con Javier para que él corra el script a mano desde
    `Informes/` y después pegue el número resultante, que se propaga a
    todas las `ot_interna` agrupadas bajo este pedido."""

    __tablename__ = "solicitudes_alta_ot"

    id: Mapped[int] = mapped_column(primary_key=True)
    anunciante: Mapped[str] = mapped_column(String(200))
    resumen: Mapped[str] = mapped_column(String(300))
    producto: Mapped[str] = mapped_column(String(200))
    centro_costo: Mapped[str] = mapped_column(String(60))
    equipo: Mapped[str | None] = mapped_column(String(60))
    estado: Mapped[EstadoSolicitudAltaOt] = mapped_column(default=EstadoSolicitudAltaOt.PENDIENTE)
    numero_ot_advertys: Mapped[str | None] = mapped_column(String(20))
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resuelto_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    creado_por: Mapped["Usuario | None"] = relationship()
    ots: Mapped[list["OtInterna"]] = relationship(back_populates="solicitud_alta")


class Estimado(Base):
    """Agrupador local de tareas para armar un Estimado de Costo en
    Advertys. La app nunca escribe items/montos del Estimado (eso sigue
    100% manual en Advertys, decisión confirmada 2026-09-21) — solo agrupa
    tareas para mostrar un resumen y, opcionalmente, dispara el alta del
    encabezado (`numero_estimado` queda nulo hasta que eso pasa)."""

    __tablename__ = "estimados"

    id: Mapped[int] = mapped_column(primary_key=True)
    titulo: Mapped[str] = mapped_column(String(300))
    numero_ot_advertys: Mapped[str] = mapped_column(String(20))
    numero_estimado: Mapped[str | None] = mapped_column(String(20))
    estado: Mapped[EstadoEstimado] = mapped_column(default=EstadoEstimado.BORRADOR)
    solicitud_alta_id: Mapped[int | None] = mapped_column(ForeignKey("solicitudes_alta_estimado.id"))
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    creado_por: Mapped["Usuario | None"] = relationship()
    tareas: Mapped[list["Tarea"]] = relationship(back_populates="estimado")
    solicitud_alta: Mapped["SolicitudAltaEstimado | None"] = relationship(back_populates="estimados")


class SolicitudAltaEstimado(Base):
    """Pedido de alta de encabezado de Estimado de Costo en Advertys,
    generado desde el botón "Generar Estimado en Advertys" del detalle de
    un Estimado local -- mismo patrón "solicitud + corrida manual" que
    `SolicitudAltaOt` (ver ot/CLAUDE.md, decisión 2026-09-23), la app nunca
    corre `crear_estimado.py` ella misma. A diferencia de `SolicitudAltaOt`,
    no duplica título ni OT de sistema: esos datos ya viven en el `Estimado`
    local que referencia (siempre 1 a 1 en la práctica -- una OT de sistema
    puede tener varios Estimados en paralelo, pero cada uno arma su propio
    pedido por separado, ver ot/CLAUDE.md 2026-09-24)."""

    __tablename__ = "solicitudes_alta_estimado"

    id: Mapped[int] = mapped_column(primary_key=True)
    fecha_solicitada: Mapped[str | None] = mapped_column(String(10))
    fecha_analisis: Mapped[str | None] = mapped_column(String(10))
    estado: Mapped[EstadoSolicitudAltaEstimado] = mapped_column(default=EstadoSolicitudAltaEstimado.PENDIENTE)
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resuelto_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    creado_por: Mapped["Usuario | None"] = relationship()
    estimados: Mapped[list["Estimado"]] = relationship(back_populates="solicitud_alta")


class OrdenTrabajoEspejo(Base):
    """Espejo de solo lectura de la tabla `ordenes_trabajo` de
    Informes/advertys.db (roadmap ítem 5, ver "Relación con Informes/ y con
    Advertys" en CLAUDE.md). Poblado únicamente por
    POST /api/sync/ordenes-trabajo (bearer token SYNC_TOKEN, ver
    app/routers/sync.py) -- ningún router de esta app escribe acá excepto
    ese. `ot_interna.numero_ot_advertys` referencia este `numero_ot` una
    vez que la OT de sistema ya existe, pero sin FK real todavía: una OT
    interna puede apuntar a un `numero_ot_advertys` recién creado con
    `crear_ot.py` antes de que corra el próximo sync."""

    __tablename__ = "ordenes_trabajo_espejo"

    numero_ot: Mapped[str] = mapped_column(String(20), primary_key=True)
    id_advertys: Mapped[str | None] = mapped_column(String(20))
    negocio: Mapped[str | None] = mapped_column(String(80))
    anunciante: Mapped[str | None] = mapped_column(String(300))
    marca: Mapped[str | None] = mapped_column(String(200))
    producto: Mapped[str | None] = mapped_column(String(300))
    resumen: Mapped[str | None] = mapped_column(Text)
    fecha_abierta: Mapped[date | None] = mapped_column(Date)
    fecha_cerrada: Mapped[date | None] = mapped_column(Date)
    responsable: Mapped[str | None] = mapped_column(String(200))
    equipo: Mapped[str | None] = mapped_column(String(200))
    estado: Mapped[str | None] = mapped_column(String(40))
    renta_teorica: Mapped[float | None] = mapped_column(Float)
    renta_real: Mapped[float | None] = mapped_column(Float)
    sincronizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SyncLog(Base):
    """Auditoría de cada sync recibido en /api/sync/* (ver
    app/routers/sync.py). `origen` identifica qué se sincronizó
    ("ordenes_trabajo" por ahora, más adelante "facturas" si se suma ese
    sync)."""

    __tablename__ = "sync_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    origen: Mapped[str] = mapped_column(String(40))
    cantidad: Mapped[int] = mapped_column()
    ok: Mapped[bool] = mapped_column()
    detalle: Mapped[str | None] = mapped_column(Text)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Tarea(Base):
    __tablename__ = "tareas"

    id: Mapped[int] = mapped_column(primary_key=True)
    ot_interna_id: Mapped[int | None] = mapped_column(ForeignKey("ot_interna.id"))
    ot_ambigua: Mapped[str | None] = mapped_column(String(60))
    estimado_id: Mapped[int | None] = mapped_column(ForeignKey("estimados.id"))
    fecha_pedido: Mapped[date | None] = mapped_column(Date)
    detalle: Mapped[str] = mapped_column(Text)
    pedido_por: Mapped[str | None] = mapped_column(String(80))
    link_drive: Mapped[str | None] = mapped_column(String(300))
    presupuestado: Mapped[bool | None] = mapped_column()
    estado_tarea: Mapped[EstadoTarea | None] = mapped_column()
    estado_facturacion: Mapped[EstadoFacturacion] = mapped_column(
        default=EstadoFacturacion.SIN_FACTURAR
    )
    fila_sheet_original: Mapped[int | None] = mapped_column()
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    ot_interna: Mapped["OtInterna | None"] = relationship(back_populates="tareas")
    estimado: Mapped["Estimado | None"] = relationship(back_populates="tareas")
    tipos: Mapped[list["TareaTipoTarea"]] = relationship(
        back_populates="tarea", cascade="all, delete-orphan"
    )
    responsables: Mapped[list["TareaResponsable"]] = relationship(
        back_populates="tarea", cascade="all, delete-orphan"
    )
    mails: Mapped[list["TareaMail"]] = relationship(
        back_populates="tarea", cascade="all, delete-orphan", order_by="TareaMail.enviado_en.desc()"
    )


class TareaTipoTarea(Base):
    __tablename__ = "tarea_tipos_tarea"

    tarea_id: Mapped[int] = mapped_column(ForeignKey("tareas.id"), primary_key=True)
    tipo_tarea_id: Mapped[int] = mapped_column(
        ForeignKey("tipos_tarea.id"), primary_key=True
    )

    tarea: Mapped["Tarea"] = relationship(back_populates="tipos")
    tipo_tarea: Mapped["TipoTarea"] = relationship()


class TareaResponsable(Base):
    __tablename__ = "tarea_responsables"
    __table_args__ = (UniqueConstraint("tarea_id", "responsable_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tarea_id: Mapped[int] = mapped_column(ForeignKey("tareas.id"))
    responsable_id: Mapped[int] = mapped_column(ForeignKey("responsables.id"))

    tarea: Mapped["Tarea"] = relationship(back_populates="responsables")
    responsable: Mapped["Responsable"] = relationship()


class TareaMail(Base):
    """Registro de cada mail redactado y mandado a los responsables de una
    tarea — queda guardado el cuerpo completo, no solo que "se mandó"."""

    __tablename__ = "tarea_mails"

    id: Mapped[int] = mapped_column(primary_key=True)
    tarea_id: Mapped[int] = mapped_column(ForeignKey("tareas.id"))
    destinatarios: Mapped[str] = mapped_column(String(500))
    asunto: Mapped[str] = mapped_column(String(300))
    cuerpo: Mapped[str] = mapped_column(Text)
    estado: Mapped[EstadoMail] = mapped_column(default=EstadoMail.ENVIADO)
    error_detalle: Mapped[str | None] = mapped_column(Text)
    gmail_message_id: Mapped[str | None] = mapped_column(String(100))
    enviado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tarea: Mapped["Tarea"] = relationship(back_populates="mails")
