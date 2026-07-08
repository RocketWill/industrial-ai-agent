"""Add workspace context to conversations.

Revision ID: 0004_add_workspace_context
Revises: 0003_create_messages
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_add_workspace_context"
down_revision: str | None = "0003_create_messages"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column(
            "environment", sa.String(20), server_default="synthetic", nullable=False
        ),
    )
    op.add_column("conversations", sa.Column("device", sa.String(200), nullable=True))
    op.add_column("conversations", sa.Column("lot", sa.String(200), nullable=True))
    op.add_column(
        "conversations", sa.Column("time_range", sa.String(100), nullable=True)
    )
    op.add_column(
        "conversations",
        sa.Column(
            "data_source",
            sa.String(30),
            server_default="synthetic_demo",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("conversations", "data_source")
    op.drop_column("conversations", "time_range")
    op.drop_column("conversations", "lot")
    op.drop_column("conversations", "device")
    op.drop_column("conversations", "environment")
