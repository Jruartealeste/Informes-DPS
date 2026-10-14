"""numeracion de OT interna por cliente + activo y numero inicial del cliente

Revision ID: d4a7c9e2b5f1
Revises: c2e5a8d1f4b7
Create Date: 2026-10-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4a7c9e2b5f1'
down_revision: Union[str, None] = 'c2e5a8d1f4b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# El unique de numero_interno se creó inline en el esquema inicial, sin nombre
# propio: en Postgres lo nombra el motor (normalmente
# ot_interna_numero_interno_key), así que se busca por columnas en vez de
# asumirlo. En sqlite no tiene nombre: se lo da esta convención en batch.
_CONVENCION = {"uq": "uq_%(table_name)s_%(column_0_name)s"}


def _unique_de_numero(bind) -> str:
    for uq in sa.inspect(bind).get_unique_constraints("ot_interna"):
        if uq["column_names"] == ["numero_interno"]:
            return uq["name"]
    raise RuntimeError("No se encontró el UNIQUE(numero_interno) de ot_interna.")


def upgrade() -> None:
    op.add_column("clientes", sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("clientes", sa.Column("numero_ot_inicial", sa.Integer(), nullable=True))
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_constraint(_unique_de_numero(bind), "ot_interna", type_="unique")
        op.create_unique_constraint("uq_ot_interna_cliente_numero", "ot_interna", ["cliente_id", "numero_interno"])
    else:
        with op.batch_alter_table("ot_interna", naming_convention=_CONVENCION) as batch:
            batch.drop_constraint("uq_ot_interna_numero_interno", type_="unique")
            batch.create_unique_constraint("uq_ot_interna_cliente_numero", ["cliente_id", "numero_interno"])


def downgrade() -> None:
    # Falla si ya hay números repetidos entre clientes (es el objetivo del upgrade).
    if op.get_bind().dialect.name == "postgresql":
        op.drop_constraint("uq_ot_interna_cliente_numero", "ot_interna", type_="unique")
        op.create_unique_constraint("ot_interna_numero_interno_key", "ot_interna", ["numero_interno"])
    else:
        with op.batch_alter_table("ot_interna") as batch:
            batch.drop_constraint("uq_ot_interna_cliente_numero", type_="unique")
            batch.create_unique_constraint("uq_ot_interna_numero_interno", ["numero_interno"])
    op.drop_column("clientes", "numero_ot_inicial")
    op.drop_column("clientes", "activo")
