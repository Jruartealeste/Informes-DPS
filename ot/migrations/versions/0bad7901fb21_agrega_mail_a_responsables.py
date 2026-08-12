"""agrega mail a responsables

Revision ID: 0bad7901fb21
Revises: f81dd822b1e4
Create Date: 2026-08-12 11:50:10.246703

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0bad7901fb21'
down_revision: Union[str, None] = 'f81dd822b1e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("responsables", sa.Column("mail", sa.String(200), nullable=True))


def downgrade() -> None:
    op.drop_column("responsables", "mail")
