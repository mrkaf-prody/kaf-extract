"""Phase 4b: Add audit_logs, feature_flags, user_feature_overrides

Migration ID: 003
Create Date: 2026-06-09
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
    # --- audit_logs ---
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "admin_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("target_type", sa.String(100), nullable=False),
        sa.Column("target_id", sa.String(255), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_audit_logs_admin_id", "audit_logs", ["admin_id"])

    # --- feature_flags ---
    op.create_table(
        "feature_flags",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("key", sa.String(100), unique=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "default_enabled",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column("requires_plan", sa.String(50), nullable=True),
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

    # --- user_feature_overrides ---
    op.create_table(
        "user_feature_overrides",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("feature_key", sa.String(100), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
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
    # Unique constraint: user_id + feature_key
    from sqlalchemy import UniqueConstraint
    with op.batch_alter_table("user_feature_overrides") as batch_op:
        batch_op.create_unique_constraint(
            "uq_user_feature_override",
            ["user_id", "feature_key"],
        )
    op.create_index(
        "ix_user_feature_overrides_user_id", "user_feature_overrides", ["user_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_user_feature_overrides_user_id", table_name="user_feature_overrides")
    op.drop_constraint("uq_user_feature_override", "user_feature_overrides", type_="unique")
    op.drop_table("user_feature_overrides")
    op.drop_table("feature_flags")
    op.drop_index("ix_audit_logs_admin_id", table_name="audit_logs")
    op.drop_table("audit_logs")
