"""Várias empresas no mesmo servidor.

Os dados que já existem viram a empresa nº 1 (nome e contato vindos de EMPRESA_NOME e
PRIVACIDADE_CONTATO). O admin mais antigo vira superadmin. Os relógios já liberados continuam
valendo: o segredo deles passa a ser o da empresa nº 1.

Revision ID: 0008
Revises: 0007
"""

import secrets

import sqlalchemy as sa
from alembic import op

from app.core.config import settings

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("privacy_contact", sa.Text, nullable=False, server_default=""),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("TRUE")),
        sa.Column("kiosk_secret", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    conn = op.get_bind()
    in_use = conn.execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM employees) OR EXISTS (SELECT 1 FROM admin_account)")
    ).scalar()
    first = None
    if in_use:
        kiosk_secret = conn.execute(sa.text("SELECT value FROM app_settings WHERE key = 'kiosk_secret'")).scalar()
        first = conn.execute(
            sa.text(
                "INSERT INTO companies (name, privacy_contact, kiosk_secret) VALUES (:name, :contact, :secret) RETURNING id"
            ),
            {
                "name": settings.empresa_nome.strip() or "Minha empresa",
                "contact": settings.privacidade_contato.strip(),
                "secret": kiosk_secret or secrets.token_hex(32),
            },
        ).scalar()
    # O segredo dos relógios agora é de cada empresa
    conn.execute(sa.text("DELETE FROM app_settings WHERE key = 'kiosk_secret'"))

    # Funcionários: o PIN passa a ser único só dentro da empresa
    op.add_column("employees", sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id", ondelete="RESTRICT")))
    conn.execute(sa.text("UPDATE employees SET company_id = :c"), {"c": first})
    op.alter_column("employees", "company_id", nullable=False)
    op.create_index("ix_employees_company_id", "employees", ["company_id"])
    op.drop_constraint("employees_pin_hash_key", "employees", type_="unique")
    op.create_unique_constraint("employees_company_pin_key", "employees", ["company_id", "pin_hash"])

    # Feriados cadastrados: cada empresa tem os seus (municipais, estaduais, facultativos)
    op.add_column("holidays", sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id", ondelete="RESTRICT")))
    conn.execute(sa.text("UPDATE holidays SET company_id = :c"), {"c": first})
    op.alter_column("holidays", "company_id", nullable=False)
    op.drop_constraint("holidays_pkey", "holidays", type_="primary")
    op.create_primary_key("holidays_pkey", "holidays", ["company_id", "date"])

    # Admins: cada um da sua empresa; o mais antigo vira superadmin (continua na empresa nº 1)
    op.add_column(
        "admin_account", sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id", ondelete="RESTRICT"))
    )
    op.add_column("admin_account", sa.Column("superadmin", sa.Boolean, nullable=False, server_default=sa.text("FALSE")))
    conn.execute(sa.text("UPDATE admin_account SET company_id = :c"), {"c": first})
    conn.execute(sa.text("UPDATE admin_account SET superadmin = TRUE WHERE id = (SELECT min(id) FROM admin_account)"))
    op.add_column(
        "admin_sessions", sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id", ondelete="SET NULL"))
    )
    conn.execute(sa.text("UPDATE admin_sessions SET company_id = :c"), {"c": first})

    # Auditoria: o trigger recusa UPDATE, mas ADD COLUMN com DEFAULT preenche as linhas antigas sem
    # reescrevê-las; tirar o DEFAULT depois não muda o valor delas
    op.add_column("audit_log", sa.Column("company_id", sa.Integer, server_default=sa.text(str(first or "NULL"))))
    op.alter_column("audit_log", "company_id", server_default=None)
    op.create_index("idx_audit_log_company", "audit_log", ["company_id", "at"])


def downgrade() -> None:
    conn = op.get_bind()
    if conn.execute(sa.text("SELECT count(*) FROM companies")).scalar() > 1:
        raise RuntimeError("Há mais de uma empresa cadastrada: não dá para voltar para a versão de empresa única")
    op.drop_index("idx_audit_log_company", "audit_log")
    op.drop_column("audit_log", "company_id")
    op.drop_column("admin_sessions", "company_id")
    op.drop_column("admin_account", "superadmin")
    op.drop_column("admin_account", "company_id")
    op.drop_constraint("holidays_pkey", "holidays", type_="primary")
    op.create_primary_key("holidays_pkey", "holidays", ["date"])
    op.drop_column("holidays", "company_id")
    op.drop_constraint("employees_company_pin_key", "employees", type_="unique")
    op.create_unique_constraint("employees_pin_hash_key", "employees", ["pin_hash"])
    op.drop_index("ix_employees_company_id", "employees")
    op.drop_column("employees", "company_id")
    secret = conn.execute(sa.text("SELECT kiosk_secret FROM companies ORDER BY id LIMIT 1")).scalar()
    if secret:
        conn.execute(sa.text("INSERT INTO app_settings (key, value) VALUES ('kiosk_secret', :s)"), {"s": secret})
    op.drop_table("companies")
