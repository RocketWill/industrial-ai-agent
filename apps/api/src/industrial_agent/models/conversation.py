from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from industrial_agent.database.base import Base

if TYPE_CHECKING:
    from industrial_agent.models.message import Message


def utc_now() -> datetime:
    return datetime.now(UTC)


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        CheckConstraint(
            "length(trim(title)) BETWEEN 1 AND 200",
            name="ck_conversations_title_length",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        default="New conversation",
    )
    environment: Mapped[str] = mapped_column(
        String(20), nullable=False, default="synthetic", server_default="synthetic"
    )
    device: Mapped[str | None] = mapped_column(String(200), nullable=True)
    lot: Mapped[str | None] = mapped_column(String(200), nullable=True)
    time_range: Mapped[str | None] = mapped_column(String(100), nullable=True)
    data_source: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="synthetic_demo",
        server_default="synthetic_demo",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.current_timestamp(),
    )
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
