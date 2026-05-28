"""Phase 5 tables: scheduled_extractions

Migration ID: 003
Create Date: 2026-05-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scheduled_extractions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("cron_expression", sa.String(100), nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("schema_json", sa.Text, nullable=False),
        sa.Column("webhook_url", sa.Text, nullable=True),
        sa.Column("email_on_complete", sa.String(255), nullable=True),
        sa.Column(
            "status",
            sa.Enum("active", "paused", "completed", "error", name="schedule_status"),
            nullable=False,
            server_default="active",
        ),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_job_id", sa.String(100), nullable=True),
        sa.Column("total_runs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_runs", sa.Integer(), nullable=False, server_default="0"),
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


def downgrade() -> None:
    op.execute("DROP TYPE IF EXISTS schedule_status CASCADE")
    op.drop_table("scheduled_extractions")
