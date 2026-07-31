from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from industrial_agent.graph.state import EvidenceState
from industrial_agent.llm.types import ChatMessage
from industrial_agent.models.message import Message, MessageRole
from industrial_agent.schemas.message import SuggestedAction
from industrial_agent.services.conversation import get_conversation


@dataclass(frozen=True)
class MessageExchange:
    user_message: Message
    assistant_message: Message
    evidence: EvidenceState | None = None


@dataclass(frozen=True)
class MessageStreamEvent:
    kind: str
    value: Message | str


def create_message(
    session: Session,
    *,
    conversation_id: UUID,
    role: MessageRole,
    content: str,
    suggested_actions: Sequence[SuggestedAction] = (),
) -> Message:
    if role == "user" and suggested_actions:
        raise ValueError("user messages cannot contain suggested actions")
    get_conversation(session, conversation_id)
    message = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        suggested_actions=[
            action.model_dump(mode="json") for action in suggested_actions
        ],
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
