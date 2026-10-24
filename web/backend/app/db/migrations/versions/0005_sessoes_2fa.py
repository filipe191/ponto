"""Sessões do admin no servidor, verificação em duas etapas e troca obrigatória de senha fraca.

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "admin_account", sa.Column("must_change_password", sa.Boolean, nullable=False, server_default=sa.text("FALSE"))
    )
    op.add_column("admin_account", sa.Column("totp_secret", sa.Text))
    op.add_column("admin_account", sa.Column("totp_pending", sa.Text))
    op.add_column("admin_account", sa.Column("totp_last_step", sa.BigInteger))

    op.create_table(
        "admin_sessions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("admin_id", sa.Integer, sa.ForeignKey("admin_account.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.Text, nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("ip", sa.Text),
        sa.Column("user_agent", sa.Text),
    )
    op.create_index("idx_admin_sessions_admin", "admin_sessions", ["admin_id"])

    op.create_table(
        "admin_recovery_codes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("admin_id", sa.Integer, sa.ForeignKey("admin_account.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code_hash", sa.Text, nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
    )
    op.create_index("idx_admin_recovery_admin", "admin_recovery_codes", ["admin_id"])


def downgrade() -> None:
    op.drop_table("admin_recovery_codes")
    op.drop_table("admin_sessions")
    op.drop_column("admin_account", "totp_last_step")
    op.drop_column("admin_account", "totp_pending")
    op.drop_column("admin_account", "totp_secret")
    op.drop_column("admin_account", "must_change_password")
