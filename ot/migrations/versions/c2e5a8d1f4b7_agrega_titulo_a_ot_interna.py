"""agrega titulo a ot_interna

Revision ID: c2e5a8d1f4b7
Revises: b7d3f9a1c5e2
Create Date: 2026-10-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c2e5a8d1f4b7'
down_revision: Union[str, None] = 'b7d3f9a1c5e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable: las OT internas existentes no tienen título (se carga desde el detalle).
    op.add_column("ot_interna", sa.Column("titulo", sa.String(60), nullable=True))


def downgrade() -> None:
    op.drop_column("ot_interna", "titulo")
