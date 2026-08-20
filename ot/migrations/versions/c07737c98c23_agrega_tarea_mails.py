"""agrega tarea_mails

Revision ID: c07737c98c23
Revises: 0bad7901fb21
Create Date: 2026-08-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c07737c98c23'
down_revision: Union[str, None] = '0bad7901fb21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tarea_mails",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tarea_id", sa.Integer(), sa.ForeignKey("tareas.id"), nullable=False),
        sa.Column("destinatarios", sa.String(500), nullable=False),
        sa.Column("asunto", sa.String(300), nullable=False),
        sa.Column("cuerpo", sa.Text(), nullable=False),
        sa.Column(
            "estado",
            sa.Enum("ENVIADO", "ERROR", name="estadomail"),
            nullable=False,
            server_default="ENVIADO",
        ),
        sa.Column("error_detalle", sa.Text(), nullable=True),
        sa.Column("gmail_message_id", sa.String(100), nullable=True),
        sa.Column("enviado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("tarea_mails")
    sa.Enum(name="estadomail").drop(op.get_bind(), checkfirst=True)
