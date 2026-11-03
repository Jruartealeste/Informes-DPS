"""estimados: Google Sheet con los items (link, pestaña, fila inicial, modo de precio)

Revision ID: a9d4e7b2c5f1
Revises: f6a2d8c4e1b9
Create Date: 2026-11-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a9d4e7b2c5f1'
down_revision: Union[str, None] = 'f6a2d8c4e1b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('estimados') as batch:
        batch.add_column(sa.Column('sheet_url', sa.String(length=500), nullable=True))
        batch.add_column(sa.Column('sheet_pestana', sa.String(length=80), nullable=True))
        batch.add_column(sa.Column('sheet_fila_inicio', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('items_modo', sa.String(length=10), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('estimados') as batch:
        batch.drop_column('items_modo')
        batch.drop_column('sheet_fila_inicio')
        batch.drop_column('sheet_pestana')
        batch.drop_column('sheet_url')
