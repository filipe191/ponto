"""Regras de jornada, fuso e prazo das batidas sem conexão por empresa.

Cada empresa existente recebe as regras que estavam no .env, valendo desde sempre: nenhum
espelho nem banco de horas muda com a migração.

Revision ID: 0009
Revises: 0008
"""

from datetime import date

import sqlalchemy as sa
from alembic import op

from app.core.config import settings

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

# Vigência da primeira regra: anterior a qualquer batida possível
SINCE_ALWAYS = date(2000, 1, 1)


def upgrade() -> None:
    op.add_column("companies", sa.Column("timezone", sa.Text, nullable=False, server_default=settings.tz))
    op.add_column(
        "companies",
        sa.Column("offline_max_hours", sa.Integer, nullable=False, server_default=str(settings.offline_max_hours)),
    )
    op.alter_column("companies", "timezone", server_default=None)
    op.alter_column("companies", "offline_max_hours", server_default=None)

    op.create_table(
        "company_rules",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("valid_from", sa.Date, nullable=False),
        sa.Column("tolerance_minutes", sa.Integer, nullable=False),
        sa.Column("night_start_hour", sa.Integer, nullable=False),
        sa.Column("night_end_hour", sa.Integer, nullable=False),
        sa.Column("night_hour_minutes", sa.Float, nullable=False),
        sa.Column("max_shift_hours", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.Text, nullable=False),
        sa.UniqueConstraint("company_id", "valid_from", name="company_rules_company_from_key"),
    )
    op.execute(
        sa.text(
            """
            INSERT INTO company_rules (company_id, valid_from, tolerance_minutes, night_start_hour,
                                       night_end_hour, night_hour_minutes, max_shift_hours, created_by)
            SELECT id, :since, :tolerance, :night_start, :night_end, :night_minutes, :max_shift, 'sistema'
            FROM companies
            """
        ).bindparams(
            since=SINCE_ALWAYS,
            tolerance=settings.tolerance_minutes,
            night_start=settings.night_start_hour,
            night_end=settings.night_end_hour,
            night_minutes=settings.night_hour_minutes,
            max_shift=settings.max_shift_hours,
        )
    )


def downgrade() -> None:
    op.drop_table("company_rules")
    op.drop_column("companies", "offline_max_hours")
    op.drop_column("companies", "timezone")
