"""esquema inicial: clientes, tipos_tarea, ot_interna, tareas

Revision ID: 9ac6a079db3f
Revises:
Create Date: 2026-08-03 13:30:25.019856

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9ac6a079db3f'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

estado_ot_interna = sa.Enum("ABIERTA", "CERRADA", name="estadootinterna")
estado_tarea = sa.Enum(
    "PARA_INICIAR", "EN_PROCESO", "PAUSADO", "PENDIENTE_OK", "FINALIZADO", "APROBADO",
    name="estadotarea",
)
estado_facturacion = sa.Enum(
    "SIN_FACTURAR", "PARA_FACTURAR", "FALTA_OK_CLIENTE", "FACTURADO", "NO_CORRESPONDE",
    name="estadofacturacion",
)


def upgrade() -> None:
    op.create_table(
        "clientes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nombre", sa.String(80), nullable=False, unique=True),
        sa.Column("anunciante_advertys", sa.String(200)),
    )

    op.create_table(
        "tipos_tarea",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nombre", sa.String(40), nullable=False, unique=True),
    )

    op.create_table(
        "ot_interna",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("numero_interno", sa.String(20), nullable=False, unique=True),
        sa.Column("cliente_id", sa.Integer(), sa.ForeignKey("clientes.id"), nullable=False),
        sa.Column("fecha_apertura", sa.Date()),
        sa.Column("estado", estado_ot_interna, nullable=False, server_default="ABIERTA"),
        sa.Column("numero_ot_advertys", sa.String(20)),
    )

    op.create_table(
        "tareas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ot_interna_id", sa.Integer(), sa.ForeignKey("ot_interna.id")),
        sa.Column("ot_ambigua", sa.String(60)),
        sa.Column("fecha_pedido", sa.Date()),
        sa.Column("detalle", sa.Text(), nullable=False),
        sa.Column("pedido_por", sa.String(80)),
        sa.Column("link_drive", sa.String(300)),
        sa.Column("presupuestado", sa.Boolean()),
        sa.Column("estado_tarea", estado_tarea),
        sa.Column(
            "estado_facturacion", estado_facturacion, nullable=False, server_default="SIN_FACTURAR"
        ),
        sa.Column("fila_sheet_original", sa.Integer()),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "actualizado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    op.create_table(
        "tarea_tipos_tarea",
        sa.Column("tarea_id", sa.Integer(), sa.ForeignKey("tareas.id"), primary_key=True),
        sa.Column("tipo_tarea_id", sa.Integer(), sa.ForeignKey("tipos_tarea.id"), primary_key=True),
    )

    op.create_table(
        "tarea_responsables",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tarea_id", sa.Integer(), sa.ForeignKey("tareas.id"), nullable=False),
        sa.Column("nombre_libre", sa.String(80), nullable=False),
        sa.UniqueConstraint("tarea_id", "nombre_libre"),
    )


def downgrade() -> None:
    op.drop_table("tarea_responsables")
    op.drop_table("tarea_tipos_tarea")
    op.drop_table("tareas")
    op.drop_table("ot_interna")
    op.drop_table("tipos_tarea")
    op.drop_table("clientes")
    estado_facturacion.drop(op.get_bind(), checkfirst=True)
    estado_tarea.drop(op.get_bind(), checkfirst=True)
    estado_ot_interna.drop(op.get_bind(), checkfirst=True)
