"""Administrador só de consulta (ex.: contabilidade): vê tudo da empresa, não altera nada.

Revision ID: 0017
Revises: 0016
"""

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("admin_account", sa.Column("read_only", sa.Boolean, nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("admin_account", "read_only")
