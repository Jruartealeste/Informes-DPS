"""agrega ordenes_trabajo_espejo y sync_log

Revision ID: c4e8a1f5d2b7
Revises: 9b4fb67a828c
Create Date: 2026-09-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4e8a1f5d2b7'
down_revision: Union[str, None] = '9b4fb67a828c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ordenes_trabajo_espejo",
        sa.Column("numero_ot", sa.String(20), primary_key=True),
        sa.Column("id_advertys", sa.String(20), nullable=True),
        sa.Column("negocio", sa.String(80), nullable=True),
        sa.Column("anunciante", sa.String(300), nullable=True),
        sa.Column("marca", sa.String(200), nullable=True),
        sa.Column("producto", sa.String(300), nullable=True),
        sa.Column("resumen", sa.Text(), nullable=True),
        sa.Column("fecha_abierta", sa.Date(), nullable=True),
        sa.Column("fecha_cerrada", sa.Date(), nullable=True),
        sa.Column("responsable", sa.String(200), nullable=True),
        sa.Column("equipo", sa.String(200), nullable=True),
        sa.Column("estado", sa.String(40), nullable=True),
        sa.Column("renta_teorica", sa.Float(), nullable=True),
        sa.Column("renta_real", sa.Float(), nullable=True),
        sa.Column("sincronizado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "sync_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("origen", sa.String(40), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column("ok", sa.Boolean(), nullable=False),
        sa.Column("detalle", sa.Text(), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("sync_log")
    op.drop_table("ordenes_trabajo_espejo")
