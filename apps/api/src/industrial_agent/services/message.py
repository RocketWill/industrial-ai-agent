from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from uuid import UUID

from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.orm import Session

from industrial_agent.graph.combined import (
    CombinedExchangeEvidence,
    EvidencePathOutcome,
)
from industrial_agent.graph.state import EvidenceState
from industrial_agent.llm.types import ChatMessage
from industrial_agent.models.message import Message, MessageRole
from industrial_agent.schemas.message import (
    EvidenceSnapshotRead,
    SuggestedAction,
)
from industrial_agent.services.conversation import get_conversation

_evidence_snapshot_adapter = TypeAdapter(EvidenceSnapshotRead)


@dataclass(frozen=True)
class MessageExchange:
    user_message: Message
    assistant_message: Message
    evidence: EvidenceState | None = None
    combined_evidence: CombinedExchangeEvidence | None = None


@dataclass(frozen=True)
class MessageStreamEvent:
    kind: str
    value: Message | str


def current_evidence_to_snapshot(
    evidence: EvidenceState | None = None,
    combined_evidence: CombinedExchangeEvidence | None = None,
) -> dict[str, object] | None:
    """Convert one validated current-evidence outcome to canonical JSON."""
    if combined_evidence is not None:
        def path_payload(path: EvidencePathOutcome) -> dict[str, object]:
            return {
                "status": path.status.value,
                "result": path.result,
                "error_code": path.error_code,
            }

        payload: dict[str, object] = {
            "status": "available",
            "schema_version": 1,
            "kind": "combined",
            "manufacturing_kind": combined_evidence.manufacturing_kind.value,
            "manufacturing": path_payload(combined_evidence.manufacturing),
            "documents": path_payload(combined_evidence.documents),
            "document_query": combined_evidence.document_query,
            "answer_status": combined_evidence.answer_status.value,
        }
    elif evidence is not None and evidence.production_summary is not None:
        payload = {
            "status": "available",
            "schema_version": 1,
            "kind": "production_summary",
            "production_summary": evidence.production_summary,
        }
    elif evidence is not None and evidence.equipment_status is not None:
        payload = {
            "status": "available",
            "schema_version": 1,
            "kind": "equipment_status",
            "equipment_status": evidence.equipment_status,
        }
    elif evidence is not None and evidence.defect_distribution is not None:
        payload = {
            "status": "available",
            "schema_version": 1,
            "kind": "defect_distribution",
            "defect_distribution": evidence.defect_distribution,
        }
    elif evidence is not None and evidence.document_search is not None:
        payload = {
            "status": "available",
            "schema_version": 1,
            "kind": "document_search",
            "document_search": evidence.document_search,
        }
    else:
        return None

    return _evidence_snapshot_adapter.validate_python(payload).model_dump(
        mode="json"
    )


def create_message(
    session: Session,
    *,
    conversation_id: UUID,
    role: MessageRole,
    content: str,
    suggested_actions: Sequence[SuggestedAction] = (),
    evidence_snapshot: object | None = None,
) -> Message:
    if role == "user" and suggested_actions:
        raise ValueError("user messages cannot contain suggested actions")
    if role == "user" and evidence_snapshot is not None:
        raise ValueError("user messages cannot contain evidence snapshots")
    get_conversation(session, conversation_id)
    message = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        suggested_actions=[
            action.model_dump(mode="json") for action in suggested_actions
        ],
        evidence_snapshot=(
            None
            if evidence_snapshot is None
            else _evidence_snapshot_adapter.validate_python(
                evidence_snapshot
            ).model_dump(mode="json")
        ),
    )
    session.add(message)
    session.commit()
    session.refresh(message)
    return message


def create_user_message(
    session: Session,
    *,
    conversation_id: UUID,
    content: str,
) -> Message:
    return create_message(
        session,
        conversation_id=conversation_id,
        role="user",
        content=content,
    )


def create_message_exchange(
    session: Session,
    *,
    conversation_id: UUID,
    content: str,
    complete: Callable[[Sequence[ChatMessage]], str],
) -> MessageExchange:
    user_message = create_user_message(
        session,
        conversation_id=conversation_id,
        content=content,
    )
    history = list_messages(session, conversation_id)
    assistant_content = complete(
        [
            ChatMessage(role=message.role, content=message.content)
            for message in history
        ]
    )
    assistant_message = create_message(
        session,
        conversation_id=conversation_id,
        role="assistant",
        content=assistant_content,
    )
    return MessageExchange(
        user_message=user_message,
        assistant_message=assistant_message,
    )


def stream_message_exchange(
    session: Session,
    *,
    conversation_id: UUID,
    content: str,
    stream: Callable[[Sequence[ChatMessage]], Iterator[str]],
) -> Iterator[MessageStreamEvent]:
    """Yield a message exchange while persisting only completed output."""
    user_message = create_user_message(
        session,
        conversation_id=conversation_id,
        content=content,
    )
    yield MessageStreamEvent("user_message", user_message)
    history = list_messages(session, conversation_id)
    assistant_parts: list[str] = []
    for delta in stream(
        [
            ChatMessage(role=message.role, content=message.content)
            for message in history
        ]
    ):
        if not isinstance(delta, str) or not delta:
            continue
        assistant_parts.append(delta)
        yield MessageStreamEvent("token", delta)
    assistant_content = "".join(assistant_parts).strip()
    if not assistant_content:
        raise ValueError("Assistant stream returned empty content")
    assistant_message = create_message(
        session,
        conversation_id=conversation_id,
        role="assistant",
        content=assistant_content,
    )
    yield MessageStreamEvent("assistant_message", assistant_message)


def list_messages(
    session: Session,
    conversation_id: UUID,
) -> Sequence[Message]:
    get_conversation(session, conversation_id)
    statement = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc(), Message.id.asc())
    )
    return session.scalars(statement).all()
