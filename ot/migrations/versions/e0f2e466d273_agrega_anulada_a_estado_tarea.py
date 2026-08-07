"""agrega ANULADA a estado_tarea

Revision ID: e0f2e466d273
Revises: 9ac6a079db3f
Create Date: 2026-08-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'e0f2e466d273'
down_revision: Union[str, None] = '9ac6a079db3f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE estadotarea ADD VALUE IF NOT EXISTS 'ANULADA'")


def downgrade() -> None:
    # Postgres no soporta sacar un valor de un enum sin recrear el tipo
    # (y reescribir toda columna que lo use) — no hay downgrade limpio.
    pass
