"""Ausências justificadas: atestado, férias, licença, falta abonada e folga do banco de horas.

Revision ID: 0015
Revises: 0014
"""

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "absences",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("employee_id", sa.Integer, sa.ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("first_day", sa.Date, nullable=False),
        sa.Column("last_day", sa.Date, nullable=False),
        sa.Column("minutes", sa.Integer),
        sa.Column("note", sa.Text, nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.Text, nullable=False),
        sa.CheckConstraint("first_day <= last_day", name="absences_period_check"),
    )
    op.create_index("absences_employee_id_idx", "absences", ["employee_id"])


def downgrade() -> None:
    op.drop_table("absences")
