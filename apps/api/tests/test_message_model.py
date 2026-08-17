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


def _message_payload(
    *, role: str = "assistant", evidence_snapshot: object = None
) -> dict[str, object]:
    return {
        "id": "00000000-0000-0000-0000-000000000013",
        "conversation_id": "00000000-0000-0000-0000-000000000001",
        "role": role,
        "content": "Response",
        "created_at": datetime.now(UTC),
        "evidence_snapshot": evidence_snapshot,
    }


def _production_snapshot() -> dict[str, object]:
    return {
        "status": "available",
        "schema_version": 1,
        "kind": "production_summary",
        "production_summary": {
            "equipment_id": "AOI-01",
            "lot_id": None,
            "start": "2026-01-15T08:00:00Z",
            "end": "2026-01-15T17:00:00Z",
            "inspected_wafers": 10,
            "passed_wafers": 9,
            "failed_wafers": 1,
            "yield_rate": 0.9,
            "defect_counts": [],
            "alarm_events": [],
            "limitations": [],
        },
    }


def _combined_snapshot() -> dict[str, object]:
    return {
        "status": "available",
        "schema_version": 1,
        "kind": "combined",
        "manufacturing_kind": "production",
        "manufacturing": {
            "status": "succeeded",
            "result": _production_snapshot()["production_summary"],
        },
        "documents": {"status": "not_run"},
        "document_query": "",
        "answer_status": "succeeded",
    }


def _equipment_snapshot() -> dict[str, object]:
    return {
        "status": "available",
        "schema_version": 1,
        "kind": "equipment_status",
        "equipment_status": {
            "equipment_id": "AOI-01",
            "observed_at": "2026-01-15T12:00:00Z",
            "status": "running",
            "effective_start": "2026-01-15T08:00:00Z",
            "effective_end": "2026-01-15T17:00:00Z",
            "source_event_id": "state-001",
            "reason_code": None,
            "limitations": [],
        },
    }


def _defect_snapshot() -> dict[str, object]:
    return {
        "status": "available",
        "schema_version": 1,
        "kind": "defect_distribution",
        "defect_distribution": {
            "equipment_id": "AOI-01",
            "lot_id": None,
            "start": "2026-01-15T08:00:00Z",
            "end": "2026-01-15T17:00:00Z",
            "failed_wafers": 0,
            "classified_defect_count": 0,
            "unclassified_failed_wafers": 0,
            "items": [],
            "limitations": [],
        },
    }


def _document_snapshot() -> dict[str, object]:
    return {
        "status": "available",
        "schema_version": 1,
        "kind": "document_search",
        "document_search": {
            "query": "alarm recovery",
            "sources": [],
            "limitations": [],
        },
    }


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


def test_message_read_accepts_native_production_snapshot() -> None:
    response = MessageRead.model_validate(
        _message_payload(evidence_snapshot=_production_snapshot())
    )

    assert response.evidence_snapshot.kind == "production_summary"


def test_message_read_accepts_combined_snapshot_with_native_path_result() -> None:
    response = MessageRead.model_validate(
        _message_payload(evidence_snapshot=_combined_snapshot())
    )

    assert response.evidence_snapshot.kind == "combined"
    assert response.evidence_snapshot.manufacturing.status == "succeeded"
    assert response.evidence_snapshot.documents.status == "not_run"


@pytest.mark.parametrize(
    ("snapshot", "kind"),
    [
        (_equipment_snapshot(), "equipment_status"),
        (_defect_snapshot(), "defect_distribution"),
        (_document_snapshot(), "document_search"),
    ],
)
def test_message_read_accepts_each_remaining_native_snapshot_kind(
    snapshot: dict[str, object], kind: str
) -> None:
    response = MessageRead.model_validate(
        _message_payload(evidence_snapshot=snapshot)
    )

    assert response.evidence_snapshot.kind == kind


@pytest.mark.parametrize(
    "snapshot",
    [
        {**_production_snapshot(), "kind": "unknown"},
        {**_production_snapshot(), "schema_version": 2},
        {
            **_production_snapshot(),
            "production_summary": _production_snapshot()["production_summary"],
            "equipment_status": {},
        },
    ],
)
def test_message_read_rejects_unknown_or_contradictory_snapshot_shape(
    snapshot: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        MessageRead.model_validate(_message_payload(evidence_snapshot=snapshot))


def test_message_read_rejects_snapshot_on_user_message() -> None:
    with pytest.raises(ValidationError):
        MessageRead.model_validate(
            _message_payload(role="user", evidence_snapshot=_production_snapshot())
        )


@pytest.mark.parametrize(
    "snapshot",
    [
        {"status": "unavailable"},
        {"status": "unavailable", "code": "other"},
    ],
)
def test_message_read_rejects_missing_or_invalid_unavailable_code(
    snapshot: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        MessageRead.model_validate(_message_payload(evidence_snapshot=snapshot))


def test_message_read_allows_missing_snapshot() -> None:
    response = MessageRead.model_validate(_message_payload())

    assert response.evidence_snapshot is None


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
