"""Phase 4 tables: trials, subscriptions, invoices, vouchers, voucher_redemptions

Migration ID: 002
Create Date: 2026-05-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- trials ---
    op.create_table(
        "trials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("active", "expired", "extended", name="trial_status"),
            nullable=False,
            server_default="active",
        ),
        sa.Column("extractions_total", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("extractions_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reminder_sent_day3", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("reminder_sent_day6", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "extended_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("extended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_trials_user_id", "trials", ["user_id"])

    # --- subscriptions ---
    op.create_table(
        "subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "plan",
            sa.Enum("hobby", "pro", "enterprise", name="subscription_plan"),
            nullable=False,
            server_default="hobby",
        ),
        sa.Column(
            "status",
            sa.Enum(
                "active", "canceled", "expired", "past_due", "paused",
                name="subscription_status",
            ),
            nullable=False,
            server_default="active",
        ),
        sa.Column("provider", sa.String(50), nullable=False, server_default="manual"),
        sa.Column("provider_subscription_id", sa.String(255), nullable=True),
        sa.Column("provider_customer_id", sa.String(255), nullable=True),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])

    # --- invoices ---
    op.create_table(
        "invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "subscription_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("subscriptions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="usd"),
        sa.Column(
            "status",
            sa.Enum("pending", "paid", "void", "refunded", name="invoice_status"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("provider", sa.String(50), nullable=False, server_default="manual"),
        sa.Column("provider_invoice_id", sa.String(255), nullable=True),
        sa.Column("plan", sa.String(50), nullable=False),
        sa.Column("html_path", sa.Text(), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_invoices_user_id", "invoices", ["user_id"])

    # --- vouchers ---
    op.create_table(
        "vouchers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(64), unique=True, nullable=False),
        sa.Column("plan", sa.String(50), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("extraction_credits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("max_uses", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("used_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.Enum("active", "expired", "exhausted", "revoked", name="voucher_status"),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_vouchers_code", "vouchers", ["code"])

    # --- voucher_redemptions ---
    op.create_table(
        "voucher_redemptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "voucher_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vouchers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "redeemed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("ip_address", sa.String(45), nullable=True),
    )
    op.create_index("ix_voucher_redemptions_voucher_id", "voucher_redemptions", ["voucher_id"])
    op.create_index("ix_voucher_redemptions_user_id", "voucher_redemptions", ["user_id"])


def downgrade() -> None:
    op.drop_table("voucher_redemptions")
    op.execute("DROP TYPE IF EXISTS voucher_status")
    op.drop_table("vouchers")
    op.drop_table("invoices")
    op.execute("DROP TYPE IF EXISTS invoice_status")
    op.drop_table("subscriptions")
    op.execute("DROP TYPE IF EXISTS subscription_status")
    op.execute("DROP TYPE IF EXISTS subscription_plan")
    op.drop_table("trials")
    op.execute("DROP TYPE IF EXISTS trial_status")
