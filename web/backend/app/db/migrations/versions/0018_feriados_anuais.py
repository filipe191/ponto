"""Feriados da empresa que se repetem todo ano (mesmo dia e mês), com o último ano em que valem.

Revision ID: 0018
Revises: 0017
"""

import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("holidays", sa.Column("yearly", sa.Boolean, nullable=False, server_default=sa.false()))
    op.add_column("holidays", sa.Column("until_year", sa.Integer))


def downgrade() -> None:
    op.drop_column("holidays", "until_year")
    op.drop_column("holidays", "yearly")
