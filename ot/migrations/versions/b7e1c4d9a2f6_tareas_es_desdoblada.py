"""tareas: marca es_desdoblada (copias creadas con "Desdoblar")

Revision ID: b7e1c4d9a2f6
Revises: a9d4e7b2c5f1
Create Date: 2026-11-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7e1c4d9a2f6'
down_revision: Union[str, None] = 'a9d4e7b2c5f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('tareas') as batch:
        batch.add_column(
            sa.Column('es_desdoblada', sa.Boolean(), nullable=False, server_default=sa.false())
        )
    # Las copias ya existentes se reconocen por el sufijo que les pone "Desdoblar".
    op.execute("UPDATE tareas SET es_desdoblada = TRUE WHERE detalle LIKE '% (desdoblada)'")


def downgrade() -> None:
    with op.batch_alter_table('tareas') as batch:
        batch.drop_column('es_desdoblada')
