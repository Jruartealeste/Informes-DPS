import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, Text, UniqueConstraint, func
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

    cliente: Mapped["Cliente"] = relationship(back_populates="ots")
    tareas: Mapped[list["Tarea"]] = relationship(back_populates="ot_interna")


class Tarea(Base):
    __tablename__ = "tareas"

    id: Mapped[int] = mapped_column(primary_key=True)
    ot_interna_id: Mapped[int | None] = mapped_column(ForeignKey("ot_interna.id"))
    ot_ambigua: Mapped[str | None] = mapped_column(String(60))
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
    tipos: Mapped[list["TareaTipoTarea"]] = relationship(
        back_populates="tarea", cascade="all, delete-orphan"
    )
    responsables: Mapped[list["TareaResponsable"]] = relationship(
        back_populates="tarea", cascade="all, delete-orphan"
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
    __table_args__ = (UniqueConstraint("tarea_id", "nombre_libre"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tarea_id: Mapped[int] = mapped_column(ForeignKey("tareas.id"))
    nombre_libre: Mapped[str] = mapped_column(String(80))

    tarea: Mapped["Tarea"] = relationship(back_populates="responsables")
