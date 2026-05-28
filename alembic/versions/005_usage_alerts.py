"""Phase 5 tables: usage_alerts and quota tracking

Migration ID: 005
Create Date: 2026-05-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- usage_alerts ---
    op.create_table(
        "usage_alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("monthly_limit", sa.Integer(), nullable=False, default=1000),
        sa.Column("alert_80_sent", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("alert_90_sent", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("alert_100_sent", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("hard_cap", sa.Integer(), nullable=True),
        sa.Column("current_usage", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reset_date", sa.DateTime(timezone=True), nullable=False),
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
            nullable=False,
        ),
    )

    # --- Add usage counter to api_keys ---
    op.add_column(
        "api_keys",
        sa.Column("current_month_usage", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "api_keys",
        sa.Column("monthly_limit", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("api_keys", "monthly_limit")
    op.drop_column("api_keys", "current_month_usage")
    op.drop_table("usage_alerts")
