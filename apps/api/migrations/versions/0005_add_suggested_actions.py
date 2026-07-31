"""Add suggested actions to messages.

Revision ID: 0005_add_suggested_actions
Revises: 0004_add_workspace_context
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_add_suggested_actions"
down_revision: str | None = "0004_add_workspace_context"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column(
            "suggested_actions",
            sa.JSON(),
            server_default=sa.text("'[]'"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("messages", "suggested_actions")
