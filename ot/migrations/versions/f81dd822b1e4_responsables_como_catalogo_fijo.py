"""responsables como catálogo fijo (reemplaza nombre_libre)

Revision ID: f81dd822b1e4
Revises: e0f2e466d273
Create Date: 2026-08-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f81dd822b1e4'
down_revision: Union[str, None] = 'e0f2e466d273'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "responsables",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nombre", sa.String(80), nullable=False, unique=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    op.execute(
        "INSERT INTO responsables (nombre, activo) "
        "SELECT DISTINCT nombre_libre, true FROM tarea_responsables"
    )

    op.add_column("tarea_responsables", sa.Column("responsable_id", sa.Integer(), nullable=True))
    op.execute(
        "UPDATE tarea_responsables SET responsable_id = responsables.id "
        "FROM responsables WHERE responsables.nombre = tarea_responsables.nombre_libre"
    )

    op.drop_constraint(
        "tarea_responsables_tarea_id_nombre_libre_key", "tarea_responsables", type_="unique"
    )
    op.drop_column("tarea_responsables", "nombre_libre")
    op.alter_column("tarea_responsables", "responsable_id", nullable=False)
    op.create_foreign_key(
        "tarea_responsables_responsable_id_fkey",
        "tarea_responsables", "responsables", ["responsable_id"], ["id"],
    )
    op.create_unique_constraint(
        "tarea_responsables_tarea_id_responsable_id_key",
        "tarea_responsables", ["tarea_id", "responsable_id"],
    )


def downgrade() -> None:
    op.add_column("tarea_responsables", sa.Column("nombre_libre", sa.String(80), nullable=True))
    op.execute(
        "UPDATE tarea_responsables SET nombre_libre = responsables.nombre "
        "FROM responsables WHERE responsables.id = tarea_responsables.responsable_id"
    )

    op.drop_constraint(
        "tarea_responsables_tarea_id_responsable_id_key", "tarea_responsables", type_="unique"
    )
    op.drop_constraint(
        "tarea_responsables_responsable_id_fkey", "tarea_responsables", type_="foreignkey"
    )
    op.drop_column("tarea_responsables", "responsable_id")
    op.alter_column("tarea_responsables", "nombre_libre", nullable=False)
    op.create_unique_constraint(
        "tarea_responsables_tarea_id_nombre_libre_key",
        "tarea_responsables", ["tarea_id", "nombre_libre"],
    )

    op.drop_table("responsables")
