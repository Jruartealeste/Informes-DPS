"""agrega solicitudes_alta_estimado

Revision ID: f3c8a2e1b9d4
Revises: a5c9e2f4b8d1
Create Date: 2026-09-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3c8a2e1b9d4'
down_revision: Union[str, None] = 'a5c9e2f4b8d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "solicitudes_alta_estimado",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fecha_solicitada", sa.String(10), nullable=True),
        sa.Column("fecha_analisis", sa.String(10), nullable=True),
        sa.Column(
            "estado",
            sa.Enum("PENDIENTE", "RESUELTA", name="estadosolicitudaltaestimado"),
            nullable=False,
            server_default="PENDIENTE",
        ),
        sa.Column("creado_por_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resuelto_en", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "estimados",
        sa.Column("solicitud_alta_id", sa.Integer(), sa.ForeignKey("solicitudes_alta_estimado.id"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("estimados", "solicitud_alta_id")
    op.drop_table("solicitudes_alta_estimado")
    sa.Enum(name="estadosolicitudaltaestimado").drop(op.get_bind(), checkfirst=True)
