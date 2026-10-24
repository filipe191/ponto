"""App de celular no mesmo backend: chaves por funcionário, origem das batidas e solicitações.

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # De onde veio a batida: relógio (tablet), app (celular) ou admin (lançamento manual)
    op.add_column("punches", sa.Column("source", sa.Text, nullable=False, server_default="relogio"))
    op.execute("UPDATE punches SET source = 'admin' WHERE manual AND original_ts IS NULL")
    op.create_check_constraint("punches_source_check", "punches", "source IN ('relogio', 'app', 'admin')")
    # Dados que o celular manda: id gerado no aparelho (evita duplicar no reenvio), quando o
    # servidor recebeu, tempo desde o boot (detecta relógio adulterado) e nome do aparelho
    op.add_column("punches", sa.Column("client_id", sa.Text))
    op.create_unique_constraint("punches_client_id_key", "punches", ["client_id"])
    op.add_column("punches", sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.add_column("punches", sa.Column("device_uptime_ms", sa.BigInteger))
    op.add_column("punches", sa.Column("device", sa.Text))

    op.create_table(
        "employee_devices",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("employee_id", sa.Integer, sa.ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("key_hash", sa.Text, nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.Text, nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "punch_requests",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("employee_id", sa.Integer, sa.ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("device_id", sa.Integer, sa.ForeignKey("employee_devices.id", ondelete="RESTRICT")),
        sa.Column("punch_id", sa.Integer, sa.ForeignKey("punches.id", ondelete="RESTRICT")),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True)),
        sa.Column("type", sa.Text),
        sa.Column("client_id", sa.Text, unique=True),
        sa.Column("note", sa.Text),
        sa.Column("status", sa.Text, nullable=False, server_default="pendente"),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("decided_by", sa.Text),
        sa.Column("decision_note", sa.Text),
        sa.CheckConstraint("action IN ('incluir', 'alterar', 'excluir')", name="punch_requests_action_check"),
        sa.CheckConstraint("status IN ('pendente', 'aprovada', 'recusada')", name="punch_requests_status_check"),
    )
    op.create_index("idx_punch_requests_status", "punch_requests", ["status"])


def downgrade() -> None:
    op.drop_table("punch_requests")
    op.drop_table("employee_devices")
    op.drop_column("punches", "device")
    op.drop_column("punches", "device_uptime_ms")
    op.drop_column("punches", "received_at")
    op.drop_constraint("punches_client_id_key", "punches", type_="unique")
    op.drop_column("punches", "client_id")
    op.drop_constraint("punches_source_check", "punches", type_="check")
    op.drop_column("punches", "source")
