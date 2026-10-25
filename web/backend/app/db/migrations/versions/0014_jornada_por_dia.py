"""Jornada com minutos por dia da semana e escalas em ciclo (ex.: 12x36).

Cada jornada antiga (mesmos minutos em cada dia de trabalho) vira 7 valores, seg … dom: o
previsto de todos os dias continua igual.

Revision ID: 0014
Revises: 0013
"""

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("employee_schedules", sa.Column("kind", sa.Text, nullable=False, server_default="semana"))
    op.add_column("employee_schedules", sa.Column("day_minutes", sa.Text))
    op.add_column("employee_schedules", sa.Column("cycle_start", sa.Date))
    op.execute(
        """
        UPDATE employee_schedules SET day_minutes = (
            SELECT string_agg(CASE WHEN position(d::text IN workdays) > 0 THEN daily_minutes ELSE 0 END::text, ','
                              ORDER BY d)
            FROM generate_series(1, 7) AS d
        )
        """
    )
    op.alter_column("employee_schedules", "day_minutes", nullable=False)
    op.drop_column("employee_schedules", "daily_minutes")
    op.drop_column("employee_schedules", "workdays")


def downgrade() -> None:
    # Volta ao formato antigo com o maior dia como jornada (escalas em ciclo viram seg a sex)
    op.add_column("employee_schedules", sa.Column("daily_minutes", sa.Integer))
    op.add_column("employee_schedules", sa.Column("workdays", sa.Text))
    op.execute(
        """
        UPDATE employee_schedules SET
            daily_minutes = (SELECT max(m::int) FROM unnest(string_to_array(day_minutes, ',')) AS m),
            workdays = CASE WHEN kind = 'ciclo' THEN '12345' ELSE (
                SELECT string_agg(i::text, '' ORDER BY i)
                FROM unnest(string_to_array(day_minutes, ',')) WITH ORDINALITY AS t(m, i) WHERE m::int > 0
            ) END
        """
    )
    op.execute("UPDATE employee_schedules SET workdays = '' WHERE workdays IS NULL")
    op.alter_column("employee_schedules", "daily_minutes", nullable=False)
    op.alter_column("employee_schedules", "workdays", nullable=False)
    op.drop_column("employee_schedules", "cycle_start")
    op.drop_column("employee_schedules", "day_minutes")
    op.drop_column("employee_schedules", "kind")
