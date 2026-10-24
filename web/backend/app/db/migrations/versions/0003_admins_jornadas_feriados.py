"""Vários admins, jornada com vigência, admissão/desligamento, feriados, fechamento do mês e batida offline.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op

from app.core.config import settings

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint("admin_account_username_key", "admin_account", ["username"])

    op.create_table(
        "app_settings",
        sa.Column("key", sa.Text, primary_key=True),
        sa.Column("value", sa.Text, nullable=False),
    )

    # Admissão: o que vier antes entre o cadastro e a primeira batida (no fuso configurado)
    op.add_column("employees", sa.Column("hired_on", sa.Date))
    op.add_column("employees", sa.Column("terminated_on", sa.Date))
    op.execute(
        sa.text(
            """
            UPDATE employees e SET hired_on = LEAST(
                (e.created_at AT TIME ZONE :tz)::date,
                COALESCE((SELECT min((p.ts AT TIME ZONE :tz)::date) FROM punches p WHERE p.employee_id = e.id),
                         (e.created_at AT TIME ZONE :tz)::date)
            )
            """
        ).bindparams(tz=settings.tz)
    )
    op.alter_column("employees", "hired_on", nullable=False)

    # Jornada passa a ter vigência: a atual vale desde a admissão
    op.create_table(
        "employee_schedules",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("employee_id", sa.Integer, sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("valid_from", sa.Date, nullable=False),
        sa.Column("daily_minutes", sa.Integer, nullable=False),
        sa.Column("workdays", sa.Text, nullable=False),
        sa.UniqueConstraint("employee_id", "valid_from", name="employee_schedules_emp_from_key"),
    )
    op.execute(
        "INSERT INTO employee_schedules (employee_id, valid_from, daily_minutes, workdays) "
        "SELECT id, hired_on, daily_minutes, workdays FROM employees"
    )
    op.drop_column("employees", "daily_minutes")
    op.drop_column("employees", "workdays")

    op.create_table(
        "holidays",
        sa.Column("date", sa.Date, primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
    )

    op.create_table(
        "month_closures",
        sa.Column("employee_id", sa.Integer, sa.ForeignKey("employees.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("month", sa.Text, primary_key=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("closed_by", sa.Text, nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
    )

    op.add_column("punches", sa.Column("offline", sa.Boolean, nullable=False, server_default=sa.text("FALSE")))


def downgrade() -> None:
    op.drop_column("punches", "offline")
    op.drop_table("month_closures")
    op.drop_table("holidays")
    op.add_column("employees", sa.Column("daily_minutes", sa.Integer, nullable=False, server_default="480"))
    op.add_column("employees", sa.Column("workdays", sa.Text, nullable=False, server_default="12345"))
    op.execute(
        """
        UPDATE employees e SET daily_minutes = s.daily_minutes, workdays = s.workdays
        FROM (SELECT DISTINCT ON (employee_id) * FROM employee_schedules ORDER BY employee_id, valid_from DESC) s
        WHERE s.employee_id = e.id
        """
    )
    op.drop_table("employee_schedules")
    op.drop_column("employees", "terminated_on")
    op.drop_column("employees", "hired_on")
    op.drop_table("app_settings")
    op.drop_constraint("admin_account_username_key", "admin_account", type_="unique")
