"""agrega gmail_thread_id y rfc_message_id a tarea_mails

Revision ID: a1d4c7e9b2f6
Revises: e332c0e4f95d
Create Date: 2026-10-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1d4c7e9b2f6'
down_revision: Union[str, None] = 'e332c0e4f95d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tarea_mails", sa.Column("gmail_thread_id", sa.String(100), nullable=True))
    op.add_column("tarea_mails", sa.Column("rfc_message_id", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("tarea_mails", "rfc_message_id")
    op.drop_column("tarea_mails", "gmail_thread_id")
