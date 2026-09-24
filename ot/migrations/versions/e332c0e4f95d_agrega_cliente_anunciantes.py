"""agrega_cliente_anunciantes

Revision ID: e332c0e4f95d
Revises: f3c8a2e1b9d4
Create Date: 2026-09-24 13:33:16.927316

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e332c0e4f95d'
down_revision: Union[str, None] = 'f3c8a2e1b9d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cliente_anunciantes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cliente_id", sa.Integer(), sa.ForeignKey("clientes.id"), nullable=False),
        sa.Column("anunciante", sa.String(200), nullable=False),
        sa.UniqueConstraint("cliente_id", "anunciante"),
    )
    # backfill: el unico valor previo por cliente pasa a ser su primer (y
    # unico) anunciante conocido -- clientes sin anunciante_advertys cargado
    # quedan sin filas acá, mismo estado ("no relevado todavía") que antes.
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "INSERT INTO cliente_anunciantes (cliente_id, anunciante) "
            "SELECT id, anunciante_advertys FROM clientes "
            "WHERE anunciante_advertys IS NOT NULL AND anunciante_advertys <> ''"
        )
    )
    op.drop_column("clientes", "anunciante_advertys")


def downgrade() -> None:
    op.add_column("clientes", sa.Column("anunciante_advertys", sa.String(200)))
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE clientes SET anunciante_advertys = ("
            "SELECT anunciante FROM cliente_anunciantes "
            "WHERE cliente_anunciantes.cliente_id = clientes.id "
            "ORDER BY cliente_anunciantes.id LIMIT 1)"
        )
    )
    op.drop_table("cliente_anunciantes")
