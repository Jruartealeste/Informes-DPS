"""tareas.link_drive pasa a Text: varios vínculos, uno por línea

Revision ID: e8b2f5c1a7d3
Revises: b7e3d1a9c4f2
Create Date: 2026-10-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e8b2f5c1a7d3'
down_revision: Union[str, None] = 'b7e3d1a9c4f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('tareas') as batch:
        batch.alter_column('link_drive', type_=sa.Text(), existing_type=sa.String(300), existing_nullable=True)


def downgrade() -> None:
    # Vuelve a String(300) quedándose con el primer vínculo de cada tarea.
    if op.get_bind().dialect.name == 'postgresql':
        op.execute(
            "UPDATE tareas SET link_drive = substr(split_part(link_drive, chr(10), 1), 1, 300) "
            "WHERE link_drive IS NOT NULL"
        )
    with op.batch_alter_table('tareas') as batch:
        batch.alter_column('link_drive', type_=sa.String(300), existing_type=sa.Text(), existing_nullable=True)
