"""mails programados: PROGRAMADO en estado_mail + programado_para y misma_cadena

Revision ID: e5b9c3a7d1f2
Revises: c4a9e2f7b1d8
Create Date: 2026-11-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5b9c3a7d1f2'
down_revision: Union[str, None] = 'c4a9e2f7b1d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE estadomail ADD VALUE IF NOT EXISTS 'PROGRAMADO'")
    op.add_column("tarea_mails", sa.Column("programado_para", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "tarea_mails",
        sa.Column("misma_cadena", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("tarea_mails", "misma_cadena")
    op.drop_column("tarea_mails", "programado_para")
    # el valor PROGRAMADO queda en el enum: Postgres no permite sacarlo sin
    # recrear el tipo (ver d3f8a1b4e6c9)
