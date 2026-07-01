from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from industrial_agent.models.conversation import Conversation


class ConversationNotFoundError(Exception):
    pass


def create_conversation(
    session: Session,
    *,
    title: str,
) -> Conversation:
    conversation = Conversation(title=title)
    session.add(conversation)
    session.commit()
    session.refresh(conversation)
    return conversation


def list_conversations(session: Session) -> Sequence[Conversation]:
    statement = select(Conversation).order_by(
        Conversation.created_at.desc(),
        Conversation.id.desc(),
    )
    return session.scalars(statement).all()


def get_conversation(
    session: Session,
    conversation_id: UUID,
) -> Conversation:
    conversation = session.get(Conversation, conversation_id)
    if conversation is None:
        raise ConversationNotFoundError
    return conversation


def delete_conversation(
    session: Session,
    conversation_id: UUID,
) -> None:
    conversation = get_conversation(session, conversation_id)
    session.delete(conversation)
    session.commit()
