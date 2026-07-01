from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from industrial_agent.models.message import Message, MessageRole
from industrial_agent.services.conversation import get_conversation


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
