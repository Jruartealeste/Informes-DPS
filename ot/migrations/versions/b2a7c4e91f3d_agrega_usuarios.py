"""agrega usuarios

Revision ID: b2a7c4e91f3d
Revises: d3f8a1b4e6c9
Create Date: 2026-08-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2a7c4e91f3d'
down_revision: Union[str, None] = 'd3f8a1b4e6c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(200), nullable=False, unique=True),
        sa.Column("nombre", sa.String(120), nullable=False),
        sa.Column(
            "rol",
            sa.Enum("MIEMBRO", "APROBADOR_FACTURACION", "ADMIN", name="rolusuario"),
            nullable=False,
            server_default="MIEMBRO",
        ),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("ultimo_login", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("usuarios")
    sa.Enum(name="rolusuario").drop(op.get_bind(), checkfirst=True)
