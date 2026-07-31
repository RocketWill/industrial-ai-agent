from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from industrial_agent.models.message import Message
from industrial_agent.schemas.message import (
    MessageCreate,
    MessageRead,
    SuggestedAction,
    SuggestedActionId,
)


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
    assert response.suggested_actions == ()


@pytest.mark.parametrize(
    ("action_id", "label", "message"),
    [
        (
            SuggestedActionId.PRODUCTION_EVIDENCE_FIRST,
            "Production evidence",
            "Show the production evidence first.",
        ),
        (
            SuggestedActionId.DOCUMENT_EVIDENCE_FIRST,
            "Document evidence",
            "Search the documents first.",
        ),
    ],
)
def test_suggested_action_accepts_only_canonical_application_actions(
    action_id: SuggestedActionId,
    label: str,
    message: str,
) -> None:
    action = SuggestedAction(id=action_id, label=label, message=message)

    assert action.model_dump(mode="json") == {
        "id": action_id.value,
        "label": label,
        "message": message,
    }
    with pytest.raises(ValidationError):
        action.label = "Changed"


@pytest.mark.parametrize(
    "payload",
    [
        {
            "id": "unknown",
            "label": "Production evidence",
            "message": "Show the production evidence first.",
        },
        {
            "id": "production_evidence_first",
            "label": "Changed label",
            "message": "Show the production evidence first.",
        },
        {
            "id": "document_evidence_first",
            "label": "Document evidence",
            "message": "Changed message",
        },
        {
            "id": "document_evidence_first",
            "label": "Document evidence",
            "message": "Search the documents first.",
            "extra": True,
        },
    ],
)
def test_suggested_action_rejects_unknown_or_noncanonical_payload(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        SuggestedAction.model_validate(payload)
