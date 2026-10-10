"""purchase order recovery cases

Revision ID: 0002_recovery_cases
Revises: 0001_initial
Create Date: 2026-10-10
"""

from alembic import op
import sqlalchemy as sa

from app.models.types import JSONDict

revision = "0002_recovery_cases"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "purchase_order_recovery_cases" in inspector.get_table_names():
        return
    op.create_table(
        "purchase_order_recovery_cases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("purchase_order_id", sa.Integer(), sa.ForeignKey("purchase_orders.id"), nullable=False),
        sa.Column("agent_run_id", sa.Integer(), sa.ForeignKey("agent_runs.id"), nullable=True),
        sa.Column("supplemental_purchase_order_id", sa.Integer(), sa.ForeignKey("purchase_orders.id"), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("decision", sa.String(length=40), nullable=True),
        sa.Column("requested_quantity", sa.Integer(), nullable=False),
        sa.Column("confirmed_quantity", sa.Integer(), nullable=False),
        sa.Column("shortfall_quantity", sa.Integer(), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("evidence_json", JSONDict, nullable=True),
        sa.Column("risks_json", JSONDict, nullable=True),
        sa.Column("missing_information_json", JSONDict, nullable=True),
        sa.Column("proposed_action_json", JSONDict, nullable=True),
        sa.Column("approved_by", sa.String(length=255), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("requested_quantity >= 0", name="ck_recovery_requested_non_negative"),
        sa.CheckConstraint("confirmed_quantity >= 0", name="ck_recovery_confirmed_non_negative"),
        sa.CheckConstraint("shortfall_quantity >= 0", name="ck_recovery_shortfall_non_negative"),
        sa.UniqueConstraint("purchase_order_id", name="uq_recovery_cases_purchase_order_id"),
    )
    op.create_index("ix_purchase_order_recovery_cases_purchase_order_id", "purchase_order_recovery_cases", ["purchase_order_id"])
    op.create_index("ix_purchase_order_recovery_cases_agent_run_id", "purchase_order_recovery_cases", ["agent_run_id"])
    op.create_index(
        "ix_purchase_order_recovery_cases_supplemental_purchase_order_id",
        "purchase_order_recovery_cases",
        ["supplemental_purchase_order_id"],
    )
    op.create_index("ix_purchase_order_recovery_cases_status", "purchase_order_recovery_cases", ["status"])
    op.create_index("ix_purchase_order_recovery_cases_decision", "purchase_order_recovery_cases", ["decision"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "purchase_order_recovery_cases" not in inspector.get_table_names():
        return
    op.drop_table("purchase_order_recovery_cases")
