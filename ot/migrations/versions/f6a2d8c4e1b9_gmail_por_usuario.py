"""mail de tareas desde la cuenta de cada usuario: token Gmail por usuario y remitente en tarea_mails

Revision ID: f6a2d8c4e1b9
Revises: e8b2f5c1a7d3
Create Date: 2026-10-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6a2d8c4e1b9'
down_revision: Union[str, None] = 'e8b2f5c1a7d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("usuarios", sa.Column("gmail_refresh_token_enc", sa.Text(), nullable=True))
    op.add_column("usuarios", sa.Column("gmail_conectado_en", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tarea_mails", sa.Column("remitente", sa.String(200), nullable=True))
    # Hasta acá todo salía del remitente único fijo del .env.
    op.execute("UPDATE tarea_mails SET remitente = 'javier@aleste.ar' WHERE estado = 'ENVIADO'")


def downgrade() -> None:
    op.drop_column("tarea_mails", "remitente")
    op.drop_column("usuarios", "gmail_conectado_en")
    op.drop_column("usuarios", "gmail_refresh_token_enc")
