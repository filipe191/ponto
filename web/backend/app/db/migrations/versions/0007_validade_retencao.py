"""Validade das chaves de celular e anonimização de ex-funcionários após o prazo de guarda.

Revision ID: 0007
Revises: 0006
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Chaves já geradas valem 1 ano a partir da criação
    op.add_column("employee_devices", sa.Column("expires_at", sa.DateTime(timezone=True)))
    op.execute("UPDATE employee_devices SET expires_at = created_at + interval '365 days'")
    op.alter_column("employee_devices", "expires_at", nullable=False)

    op.add_column("employees", sa.Column("anonymized_at", sa.DateTime(timezone=True)))

    # A auditoria continua só aceitando inclusões, com uma exceção: a anonimização de quem passou
    # do prazo de guarda apaga os registros dessa pessoa, dentro de uma transação marcada para isso
    op.execute(
        """
        CREATE OR REPLACE FUNCTION audit_log_somente_inclusao() RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'DELETE' AND current_setting('ponto.retencao', true) = 'on' THEN
                RETURN NULL;
            END IF;
            RAISE EXCEPTION 'audit_log só aceita inclusões';
        END;
        $$ LANGUAGE plpgsql
        """
    )


def downgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION audit_log_somente_inclusao() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log só aceita inclusões';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.drop_column("employees", "anonymized_at")
    op.drop_column("employee_devices", "expires_at")
