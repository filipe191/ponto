"""Código público de cada empresa, para o link do aviso de privacidade (/privacidade?e=<código>).

Aleatório: o link mostra só a empresa dele e não permite listar as demais.

Revision ID: 0010
Revises: 0009
"""

import secrets

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("public_code", sa.Text))
    conn = op.get_bind()
    for (company_id,) in conn.execute(sa.text("SELECT id FROM companies")).all():
        conn.execute(
            sa.text("UPDATE companies SET public_code = :c WHERE id = :id"),
            {"c": secrets.token_urlsafe(9), "id": company_id},
        )
    op.alter_column("companies", "public_code", nullable=False)
    op.create_unique_constraint("companies_public_code_key", "companies", ["public_code"])


def downgrade() -> None:
    op.drop_constraint("companies_public_code_key", "companies", type_="unique")
    op.drop_column("companies", "public_code")
