"""agrega BORRADOR a estado_mail

Revision ID: d3f8a1b4e6c9
Revises: c07737c98c23
Create Date: 2026-08-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd3f8a1b4e6c9'
down_revision: Union[str, None] = 'c07737c98c23'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE estadomail ADD VALUE IF NOT EXISTS 'BORRADOR'")


def downgrade() -> None:
    # Postgres no soporta sacar un valor de un enum sin recrear el tipo
    # (y reescribir toda columna que lo use) — no hay downgrade limpio.
    pass
