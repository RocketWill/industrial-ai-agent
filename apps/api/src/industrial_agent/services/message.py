from collections.abc import Callable, Sequence
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from industrial_agent.llm.types import ChatMessage
from industrial_agent.models.message import Message, MessageRole
from industrial_agent.services.conversation import get_conversation


@dataclass(frozen=True)
class MessageExchange:
    user_message: Message
    assistant_message: Message


def create_message(
    session: Session,
    *,
    conversation_id: UUID,
    role: MessageRole,
    content: str,
) -> Message:
    get_conversation(session, conversation_id)
    message = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
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
