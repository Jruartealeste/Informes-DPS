"""agrega productos_advertys

Revision ID: b7d3f9a1c5e2
Revises: a1d4c7e9b2f6
Create Date: 2026-10-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7d3f9a1c5e2'
down_revision: Union[str, None] = 'a1d4c7e9b2f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "productos_advertys",
        sa.Column("id_advertys", sa.String(20), primary_key=True),
        sa.Column("nombre", sa.String(300), nullable=False),
        sa.Column("anunciante", sa.String(300), nullable=False),
        sa.Column("categoria", sa.String(200), nullable=True),
        sa.Column("marca", sa.String(200), nullable=True),
        sa.Column("sincronizado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_productos_advertys_anunciante", "productos_advertys", ["anunciante"])


def downgrade() -> None:
    op.drop_index("ix_productos_advertys_anunciante", table_name="productos_advertys")
    op.drop_table("productos_advertys")
