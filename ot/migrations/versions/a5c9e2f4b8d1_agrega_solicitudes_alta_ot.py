"""agrega solicitudes_alta_ot

Revision ID: a5c9e2f4b8d1
Revises: c4e8a1f5d2b7
Create Date: 2026-09-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a5c9e2f4b8d1'
down_revision: Union[str, None] = 'c4e8a1f5d2b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "solicitudes_alta_ot",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("anunciante", sa.String(200), nullable=False),
        sa.Column("resumen", sa.String(300), nullable=False),
        sa.Column("producto", sa.String(200), nullable=False),
        sa.Column("centro_costo", sa.String(60), nullable=False),
        sa.Column("equipo", sa.String(60), nullable=True),
        sa.Column(
            "estado",
            sa.Enum("PENDIENTE", "RESUELTA", name="estadosolicitudaltaot"),
            nullable=False,
            server_default="PENDIENTE",
        ),
        sa.Column("numero_ot_advertys", sa.String(20), nullable=True),
        sa.Column("creado_por_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resuelto_en", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "ot_interna",
        sa.Column("solicitud_alta_id", sa.Integer(), sa.ForeignKey("solicitudes_alta_ot.id"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ot_interna", "solicitud_alta_id")
    op.drop_table("solicitudes_alta_ot")
    sa.Enum(name="estadosolicitudaltaot").drop(op.get_bind(), checkfirst=True)
