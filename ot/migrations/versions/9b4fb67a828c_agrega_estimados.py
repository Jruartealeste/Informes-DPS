"""agrega estimados

Revision ID: 9b4fb67a828c
Revises: b2a7c4e91f3d
Create Date: 2026-09-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9b4fb67a828c'
down_revision: Union[str, None] = 'b2a7c4e91f3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "estimados",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("titulo", sa.String(300), nullable=False),
        sa.Column("numero_ot_advertys", sa.String(20), nullable=False),
        sa.Column("numero_estimado", sa.String(20), nullable=True),
        sa.Column(
            "estado",
            sa.Enum("BORRADOR", "GENERADO", name="estadoestimado"),
            nullable=False,
            server_default="BORRADOR",
        ),
        sa.Column("creado_por_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.add_column("tareas", sa.Column("estimado_id", sa.Integer(), sa.ForeignKey("estimados.id"), nullable=True))


def downgrade() -> None:
    op.drop_column("tareas", "estimado_id")
    op.drop_table("estimados")
    sa.Enum(name="estadoestimado").drop(op.get_bind(), checkfirst=True)
