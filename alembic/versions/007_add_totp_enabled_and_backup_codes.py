"""Add totp_enabled and backup_codes columns to users table.

Migration ID: 007
Create Date: 2026-05-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("totp_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "users",
        sa.Column("backup_codes", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "backup_codes")
    op.drop_column("users", "totp_enabled")
