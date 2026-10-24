"""Auditoria geral (só acrescenta, nunca altera nem apaga) e marcação dos PINs curtos.

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

from app.core.security import hash_pin

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("user", sa.Text, nullable=False),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("summary", sa.Text, nullable=False),
        # Sem chave estrangeira: o registro sobrevive à exclusão do funcionário e a tabela nunca é alterada
        sa.Column("employee_id", sa.Integer),
        sa.Column("details", JSONB),
        sa.Column("ip", sa.Text),
    )
    op.create_index("idx_audit_log_at", "audit_log", ["at"])
    op.create_index("idx_audit_log_employee", "audit_log", ["employee_id", "at"])
    op.create_index("idx_audit_log_action", "audit_log", ["action", "at"])
    # Nem o próprio sistema altera ou apaga o que foi registrado
    op.execute(
        """
        CREATE FUNCTION audit_log_somente_inclusao() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log só aceita inclusões';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_log_somente_inclusao
        BEFORE UPDATE OR DELETE OR TRUNCATE ON audit_log
        FOR EACH STATEMENT EXECUTE FUNCTION audit_log_somente_inclusao()
        """
    )

    # PINs de 4 ou 5 dígitos continuam valendo, mas ficam marcados para o admin trocar.
    # O hash não revela o tamanho do PIN, então compara com o hash de todos os PINs curtos possíveis.
    op.add_column("employees", sa.Column("pin_short", sa.Boolean, nullable=False, server_default=sa.text("FALSE")))
    conn = op.get_bind()
    stored = {h for (h,) in conn.execute(sa.text("SELECT pin_hash FROM employees")).all()}
    if stored:
        short = [h for n in (4, 5) for i in range(10**n) if (h := hash_pin(f"{i:0{n}d}")) in stored]
        if short:
            conn.execute(
                sa.text("UPDATE employees SET pin_short = TRUE WHERE pin_hash = ANY(:hashes)"), {"hashes": short}
            )


def downgrade() -> None:
    op.drop_column("employees", "pin_short")
    op.execute("DROP TABLE audit_log")
    op.execute("DROP FUNCTION audit_log_somente_inclusao()")
