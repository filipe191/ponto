"""E-mail de aviso das solicitações do app, por empresa.

Revision ID: 0012
Revises: 0011
"""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("notify_email", sa.Text, nullable=False, server_default=""))
    op.add_column("companies", sa.Column("requests_notified_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("companies", "requests_notified_at")
    op.drop_column("companies", "notify_email")
