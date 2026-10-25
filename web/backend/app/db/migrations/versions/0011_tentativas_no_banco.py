"""Tentativas erradas e bloqueios no banco (PIN no relógio, senha no login, chave no app).

Antes ficavam na memória do backend: reiniciar zerava os bloqueios em andamento.

Revision ID: 0011
Revises: 0010
"""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "attempt_failures",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("scope", sa.Text, nullable=False),
        sa.Column("key", sa.Text, nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("attempt_failures_scope_key_at_idx", "attempt_failures", ["scope", "key", "at"])
    op.create_table(
        "attempt_blocks",
        sa.Column("scope", sa.Text, primary_key=True),
        sa.Column("key", sa.Text, primary_key=True),
        sa.Column("strikes", sa.Integer, nullable=False),
        sa.Column("until", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("attempt_blocks")
    op.drop_index("attempt_failures_scope_key_at_idx", "attempt_failures")
    op.drop_table("attempt_failures")
