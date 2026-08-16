from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from industrial_agent.domain.routing import EvidenceKind
from industrial_agent.graph.combined import (
    CombinedAnswerStatus,
    CombinedEvidenceOutcome,
    CombinedExchangeEvidence,
    EvidencePathOutcome,
    EvidencePathStatus,
)
from industrial_agent.graph.state import EvidenceState
from industrial_agent.llm.errors import LLMConnectionError
from industrial_agent.llm.types import ChatMessage
from industrial_agent.models.message import Message
from industrial_agent.schemas.message import SuggestedAction, SuggestedActionId
from industrial_agent.services.conversation import (
    ConversationNotFoundError,
    create_conversation,
    delete_conversation,
)
from industrial_agent.services.message import (
    create_message,
    create_message_exchange,
    create_user_message,
    current_evidence_to_snapshot,
    list_messages,
)
from industrial_agent.tools.production import ProductionSummaryResult

UNKNOWN_CONVERSATION_ID = UUID(
    "00000000-0000-0000-0000-000000000099"
)


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


def _production_result() -> ProductionSummaryResult:
    return ProductionSummaryResult(
        equipment_id="AOI-01",
        lot_id=None,
        start=datetime(2026, 1, 15, 8, tzinfo=UTC),
        end=datetime(2026, 1, 15, 17, tzinfo=UTC),
        inspected_wafers=10,
        passed_wafers=9,
        failed_wafers=1,
        yield_rate=0.9,
        defect_counts=(),
        alarm_events=(),
        limitations=(),
    )


def test_create_user_message_persists_with_user_role(
    database_session: Session,
    database_engine: Engine,
) -> None:
    conversation = create_conversation(
        database_session,
        title="Persistent messages",
    )

    created = create_user_message(
        database_session,
        conversation_id=conversation.id,
        content="Check chamber pressure",
    )

    factory = sessionmaker(bind=database_engine)
    with factory() as new_session:
        persisted = new_session.get(Message, created.id)

    assert persisted is not None
    assert persisted.conversation_id == conversation.id
    assert persisted.role == "user"
    assert persisted.content == "Check chamber pressure"


def test_internal_create_message_accepts_assistant_role(
    database_session: Session,
) -> None:
    conversation = create_conversation(
        database_session,
        title="Assistant storage",
    )

    created = create_message(
        database_session,
        conversation_id=conversation.id,
        role="assistant",
        content="Stored response",
    )

    assert created.role == "assistant"


def test_create_message_persists_validated_assistant_evidence_snapshot(
    database_session: Session,
) -> None:
    conversation = create_conversation(
        database_session,
        title="Assistant evidence snapshot",
    )
    snapshot = _production_snapshot()

    created = create_message(
        database_session,
        conversation_id=conversation.id,
        role="assistant",
        content="Production evidence",
        evidence_snapshot=snapshot,
    )

    database_session.expire_all()
    persisted = list_messages(database_session, conversation.id)[0]
    assert persisted.id == created.id
    assert persisted.evidence_snapshot == snapshot


def test_current_evidence_conversion_preserves_available_production_summary() -> None:
    snapshot = current_evidence_to_snapshot(
        evidence=EvidenceState(production_summary=_production_result()),
    )

    assert snapshot["kind"] == "production_summary"
    assert snapshot["status"] == "available"
    assert snapshot["production_summary"]["equipment_id"] == "AOI-01"


def test_current_evidence_conversion_preserves_combined_partial_failure() -> None:
    combined = CombinedExchangeEvidence(
        evidence=CombinedEvidenceOutcome(
            manufacturing_kind=EvidenceKind.PRODUCTION,
            manufacturing=EvidencePathOutcome(
                status=EvidencePathStatus.SUCCEEDED,
                result=_production_result(),
            ),
            documents=EvidencePathOutcome(
                status=EvidencePathStatus.FAILED,
                error_code="TOOL_UNAVAILABLE",
            ),
            document_query="alarm reset",
        ),
        answer_status=CombinedAnswerStatus.FALLBACK,
    )

    snapshot = current_evidence_to_snapshot(combined_evidence=combined)

    assert snapshot["kind"] == "combined"
    assert snapshot["status"] == "available"
    assert snapshot["manufacturing"]["status"] == "succeeded"
    assert snapshot["manufacturing"]["result"]["equipment_id"] == "AOI-01"
    assert snapshot["documents"]["status"] == "failed"
    assert snapshot["documents"]["error_code"] == "TOOL_UNAVAILABLE"


def test_create_message_rejects_evidence_snapshot_on_user_messages(
    database_session: Session,
) -> None:
    conversation = create_conversation(database_session, title="Invalid evidence")

    with pytest.raises(ValueError, match="user messages"):
        create_message(
            database_session,
            conversation_id=conversation.id,
            role="user",
            content="Invalid",
            evidence_snapshot=_production_snapshot(),
        )


def test_create_message_keeps_missing_assistant_evidence_snapshot_null(
    database_session: Session,
) -> None:
    conversation = create_conversation(database_session, title="No evidence")

    created = create_message(
        database_session,
        conversation_id=conversation.id,
        role="assistant",
        content="No production evidence",
    )

    assert created.evidence_snapshot is None


def test_create_message_persists_canonical_assistant_actions(
    database_session: Session,
) -> None:
    conversation = create_conversation(database_session, title="Guided choice")
    action = SuggestedAction(
        id=SuggestedActionId.PRODUCTION_EVIDENCE_FIRST,
        label="Production evidence",
        message="Show the production evidence first.",
    )

    created = create_message(
        database_session,
        conversation_id=conversation.id,
        role="assistant",
        content="Choose one evidence path.",
        suggested_actions=(action,),
    )

    database_session.expire_all()
    persisted = list_messages(database_session, conversation.id)[0]
    assert persisted.id == created.id
    assert persisted.suggested_actions == [action.model_dump(mode="json")]


def test_create_message_rejects_actions_on_user_messages(
    database_session: Session,
) -> None:
    conversation = create_conversation(database_session, title="Invalid action")
    action = SuggestedAction(
        id=SuggestedActionId.DOCUMENT_EVIDENCE_FIRST,
        label="Document evidence",
        message="Search the documents first.",
    )

    with pytest.raises(ValueError, match="user messages"):
        create_message(
            database_session,
            conversation_id=conversation.id,
            role="user",
            content="Invalid",
            suggested_actions=(action,),
        )


def test_create_message_exchange_persists_user_and_assistant(
    database_session: Session,
) -> None:
    conversation = create_conversation(
        database_session,
        title="Exchange",
    )
    received: list[ChatMessage] = []

    def complete(messages: list[ChatMessage]) -> str:
        received.extend(messages)
        return "Assistant answer"

    exchange = create_message_exchange(
        database_session,
        conversation_id=conversation.id,
        content="User question",
        complete=complete,
    )

    assert received == [
        ChatMessage(role="user", content="User question"),
    ]
    assert exchange.user_message.role == "user"
    assert exchange.assistant_message.role == "assistant"
    assert [
        message.content
        for message in list_messages(database_session, conversation.id)
    ] == ["User question", "Assistant answer"]


def test_create_message_exchange_keeps_user_message_when_completion_fails(
    database_session: Session,
) -> None:
    conversation = create_conversation(
        database_session,
        title="Failed exchange",
    )

    def complete(_: list[ChatMessage]) -> str:
        raise LLMConnectionError("unavailable")

    with pytest.raises(LLMConnectionError):
        create_message_exchange(
            database_session,
            conversation_id=conversation.id,
            content="Keep this question",
            complete=complete,
        )

    assert [
        (message.role, message.content)
        for message in list_messages(database_session, conversation.id)
    ] == [("user", "Keep this question")]


def test_list_messages_returns_chronological_deterministic_order(
    database_session: Session,
) -> None:
    conversation = create_conversation(
        database_session,
        title="Ordered messages",
    )
    base_time = datetime(2026, 7, 30, 6, 0, 0, tzinfo=UTC)
    later = create_user_message(
        database_session,
        conversation_id=conversation.id,
        content="Later",
    )
    equal_second = create_user_message(
        database_session,
        conversation_id=conversation.id,
        content="Equal second",
    )
    equal_first = create_user_message(
        database_session,
        conversation_id=conversation.id,
        content="Equal first",
    )
    later.created_at = base_time + timedelta(seconds=1)
    equal_second.id = UUID("00000000-0000-0000-0000-000000000012")
    equal_second.created_at = base_time
    equal_first.id = UUID("00000000-0000-0000-0000-000000000011")
    equal_first.created_at = base_time
    database_session.commit()

    messages = list_messages(database_session, conversation.id)

    assert [message.content for message in messages] == [
        "Equal first",
        "Equal second",
        "Later",
    ]


def test_list_messages_returns_empty_for_existing_conversation(
    database_session: Session,
) -> None:
    conversation = create_conversation(
        database_session,
        title="Empty history",
    )

    assert list_messages(database_session, conversation.id) == []


def test_create_message_rejects_unknown_conversation(
    database_session: Session,
) -> None:
    with pytest.raises(ConversationNotFoundError):
        create_user_message(
            database_session,
            conversation_id=UNKNOWN_CONVERSATION_ID,
            content="Orphan",
        )


def test_list_messages_rejects_unknown_conversation(
    database_session: Session,
) -> None:
    with pytest.raises(ConversationNotFoundError):
        list_messages(database_session, UNKNOWN_CONVERSATION_ID)


def test_delete_conversation_cascades_to_messages(
    database_session: Session,
    database_engine: Engine,
) -> None:
    conversation = create_conversation(
        database_session,
        title="Cascade",
    )
    create_user_message(
        database_session,
        conversation_id=conversation.id,
        content="Delete with parent",
    )

    delete_conversation(database_session, conversation.id)

    factory = sessionmaker(bind=database_engine)
    with factory() as new_session:
        remaining = new_session.scalar(
            select(func.count())
            .select_from(Message)
            .where(Message.conversation_id == conversation.id)
        )

    assert remaining == 0
