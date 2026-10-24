"""Tabelas iniciais (as mesmas que o create_all criava antes do Alembic).

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_account",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("username", sa.String, nullable=False),
        sa.Column("password_hash", sa.String, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "employees",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("pin_hash", sa.Text, nullable=False, unique=True),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("TRUE")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "punches",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "employee_id",
            sa.Integer,
            sa.ForeignKey("employees.id", ondelete="CASCADE", name="punches_employee_id_fkey"),
            nullable=False,
        ),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("type", sa.Text, nullable=False),
        sa.Column("manual", sa.Boolean, nullable=False, server_default=sa.text("FALSE")),
        sa.Column("note", sa.Text),
        sa.CheckConstraint("type IN ('entrada', 'saida')", name="punches_type_check"),
    )
    op.create_index("idx_punches_emp_ts", "punches", ["employee_id", "ts"])


def downgrade() -> None:
    op.drop_table("punches")
    op.drop_table("employees")
    op.drop_table("admin_account")
