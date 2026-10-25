"""Horas extras nas regras de jornada: banco de horas ou pagas no mês, com os adicionais.

As regras existentes ficam no modo "banco", que é o cálculo de antes: nenhum saldo muda.

Revision ID: 0016
Revises: 0015
"""

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("company_rules", sa.Column("overtime_mode", sa.Text, nullable=False, server_default="banco"))
    op.add_column("company_rules", sa.Column("overtime_pct", sa.Integer, nullable=False, server_default="50"))
    op.add_column("company_rules", sa.Column("rest_overtime_pct", sa.Integer, nullable=False, server_default="100"))


def downgrade() -> None:
    op.drop_column("company_rules", "rest_overtime_pct")
    op.drop_column("company_rules", "overtime_pct")
    op.drop_column("company_rules", "overtime_mode")
