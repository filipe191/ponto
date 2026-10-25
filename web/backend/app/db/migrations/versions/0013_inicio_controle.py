"""Início do controle de ponto (empresa e funcionário) e saldo inicial do banco de horas.

As empresas e os funcionários existentes ficam sem data: o controle continua começando na
admissão, como antes, e nenhum espelho nem banco de horas muda com a migração.

Revision ID: 0013
Revises: 0012
"""

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("control_start", sa.Date))
    op.add_column("employees", sa.Column("control_start", sa.Date))
    op.add_column("employees", sa.Column("initial_balance_minutes", sa.Integer, nullable=False, server_default="0"))
    op.add_column("employees", sa.Column("initial_balance_note", sa.Text, nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("employees", "initial_balance_note")
    op.drop_column("employees", "initial_balance_minutes")
    op.drop_column("employees", "control_start")
    op.drop_column("companies", "control_start")
