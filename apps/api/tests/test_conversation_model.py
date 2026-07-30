from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from industrial_agent.models.conversation import Conversation
from industrial_agent.schemas.conversation import (
    ConversationCreate,
    ConversationRead,
)


def test_conversation_create_uses_default_title() -> None:
    payload = ConversationCreate()

    assert payload.title == "New conversation"


def test_conversation_create_trims_title() -> None:
    payload = ConversationCreate(title="  Yield investigation  ")

    assert payload.title == "Yield investigation"


@pytest.mark.parametrize("title", ["", "   ", "x" * 201])
def test_conversation_create_rejects_invalid_title(title: str) -> None:
    with pytest.raises(ValidationError):
        ConversationCreate(title=title)


def test_conversation_read_normalizes_naive_sqlite_timestamp_to_utc() -> None:
    conversation = Conversation(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        title="Yield investigation",
        created_at=datetime(2026, 7, 30, 6, 0, 0),
    )

    response = ConversationRead.model_validate(conversation)

    assert isinstance(response.id, UUID)
    assert response.created_at == datetime(2026, 7, 30, 6, 0, 0, tzinfo=UTC)


def test_conversation_read_converts_aware_timestamp_to_utc() -> None:
    conversation = Conversation(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        title="Yield investigation",
        created_at=datetime.fromisoformat("2026-07-30T14:00:00+08:00"),
    )

    response = ConversationRead.model_validate(conversation)

    assert response.created_at == datetime(2026, 7, 30, 6, 0, 0, tzinfo=UTC)
