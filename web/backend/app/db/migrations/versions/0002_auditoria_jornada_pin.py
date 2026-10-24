"""Histórico de correções, exclusão lógica, jornada prevista e PIN com chave.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

from app.core.security import rehash_legacy_pin

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Jornada prevista de cada funcionário (padrão: 8h, segunda a sexta)
    op.add_column("employees", sa.Column("daily_minutes", sa.Integer, nullable=False, server_default="480"))
    op.add_column("employees", sa.Column("workdays", sa.Text, nullable=False, server_default="12345"))

    # Batidas: horário original preservado e exclusão lógica
    op.add_column("punches", sa.Column("original_ts", sa.DateTime(timezone=True)))
    op.add_column("punches", sa.Column("original_type", sa.Text))
    op.add_column("punches", sa.Column("deleted_at", sa.DateTime(timezone=True)))

    # Excluir um funcionário não pode mais apagar as batidas dele
    op.drop_constraint("punches_employee_id_fkey", "punches", type_="foreignkey")
    op.create_foreign_key(
        "punches_employee_id_fkey", "punches", "employees", ["employee_id"], ["id"], ondelete="RESTRICT"
    )

    op.create_table(
        "punch_changes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("punch_id", sa.Integer, sa.ForeignKey("punches.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("user", sa.Text, nullable=False),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("old_ts", sa.DateTime(timezone=True)),
        sa.Column("old_type", sa.Text),
        sa.Column("new_ts", sa.DateTime(timezone=True)),
        sa.Column("new_type", sa.Text),
        sa.Column("note", sa.Text),
        sa.CheckConstraint(
            "action IN ('criada', 'alterada', 'excluida', 'restaurada')", name="punch_changes_action_check"
        ),
    )
    op.create_index("idx_punch_changes_punch", "punch_changes", ["punch_id"])

    # PINs: o hash antigo vira HMAC(PIN_KEY, hash antigo), sem precisar recadastrar ninguém
    conn = op.get_bind()
    for emp_id, legacy in conn.execute(sa.text("SELECT id, pin_hash FROM employees")).all():
        conn.execute(
            sa.text("UPDATE employees SET pin_hash = :h WHERE id = :id"),
            {"h": rehash_legacy_pin(legacy), "id": emp_id},
        )


def downgrade() -> None:
    # O hash dos PINs não volta ao formato antigo: os PINs teriam de ser recadastrados
    op.drop_table("punch_changes")
    op.drop_constraint("punches_employee_id_fkey", "punches", type_="foreignkey")
    op.create_foreign_key(
        "punches_employee_id_fkey", "punches", "employees", ["employee_id"], ["id"], ondelete="CASCADE"
    )
    op.drop_column("punches", "deleted_at")
    op.drop_column("punches", "original_type")
    op.drop_column("punches", "original_ts")
    op.drop_column("employees", "workdays")
    op.drop_column("employees", "daily_minutes")
