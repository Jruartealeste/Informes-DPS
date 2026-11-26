"""agrega CERRADO a estado_facturacion

Revision ID: c4a9e2f7b1d8
Revises: b7e1c4d9a2f6
Create Date: 2026-11-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c4a9e2f7b1d8'
down_revision: Union[str, None] = 'b7e1c4d9a2f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # CERRADO: solo lo fija el agente de IA (Estimado facturado en Advertys).
    op.execute("ALTER TYPE estadofacturacion ADD VALUE IF NOT EXISTS 'CERRADO'")


def downgrade() -> None:
    # Postgres no soporta sacar un valor de un enum sin recrear el tipo.
    pass
