"""agrega fecha_vencimiento (opcional) a tareas

Revision ID: b7e3d1a9c4f2
Revises: d4a7c9e2b5f1
Create Date: 2026-10-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7e3d1a9c4f2'
down_revision: Union[str, None] = 'd4a7c9e2b5f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tareas', sa.Column('fecha_vencimiento', sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column('tareas', 'fecha_vencimiento')
