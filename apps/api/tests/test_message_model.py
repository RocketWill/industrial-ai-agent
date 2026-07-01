from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from industrial_agent.models.message import Message
from industrial_agent.schemas.message import MessageCreate, MessageRead


def test_message_create_trims_content() -> None:
    payload = MessageCreate(content="  Check chamber pressure  ")

    assert payload.content == "Check chamber pressure"


@pytest.mark.parametrize("content", ["", "   ", "x" * 10_001])
def test_message_create_rejects_invalid_content(content: str) -> None:
    with pytest.raises(ValidationError):
        MessageCreate(content=content)


def test_message_create_rejects_role_selection() -> None:
    with pytest.raises(ValidationError):
        MessageCreate.model_validate(
            {"content": "Hello", "role": "assistant"}
        )


def test_message_read_normalizes_naive_sqlite_timestamp_to_utc() -> None:
    message = Message(
        id=UUID("00000000-0000-0000-0000-000000000011"),
        conversation_id=UUID("00000000-0000-0000-0000-000000000001"),
        role="user",
        content="Hello",
        created_at=datetime(2026, 7, 30, 6, 0, 0),
    )

    response = MessageRead.model_validate(message)

    assert response.created_at == datetime(
        2026,
        7,
        30,
        6,
        0,
        0,
        tzinfo=UTC,
    )


def test_message_read_accepts_assistant_role() -> None:
    message = Message(
        id=UUID("00000000-0000-0000-0000-000000000012"),
        conversation_id=UUID("00000000-0000-0000-0000-000000000001"),
        role="assistant",
        content="Response",
        created_at=datetime.now(UTC),
    )

    response = MessageRead.model_validate(message)

    assert response.role == "assistant"
