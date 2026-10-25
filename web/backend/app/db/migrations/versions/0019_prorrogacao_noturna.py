"""Prorrogação do horário noturno (Súmula 60 do TST) nas regras de jornada.

As regras existentes ficam sem a prorrogação, como calculavam até aqui: nenhum espelho nem banco de
horas muda. As empresas novas (e as próximas regras) já vêm com ela ligada.

Revision ID: 0019
Revises: 0018
"""

import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("company_rules", sa.Column("night_extension", sa.Boolean, nullable=False, server_default=sa.false()))
    op.alter_column("company_rules", "night_extension", server_default=sa.true())


def downgrade() -> None:
    op.drop_column("company_rules", "night_extension")
