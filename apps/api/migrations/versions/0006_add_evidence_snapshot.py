"""Add evidence snapshots to messages.

Revision ID: 0006_add_evidence_snapshot
Revises: 0005_add_suggested_actions
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_add_evidence_snapshot"
down_revision: str | None = "0005_add_suggested_actions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column("evidence_snapshot", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("messages", "evidence_snapshot")
