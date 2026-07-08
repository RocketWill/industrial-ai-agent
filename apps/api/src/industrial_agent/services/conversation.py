from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from industrial_agent.models.conversation import Conversation
from industrial_agent.schemas.context import (
    WorkspaceContextRead,
    WorkspaceContextUpdate,
)
from industrial_agent.services.device import (
    SyntheticDeviceNotFoundError,
    get_synthetic_device,
)


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


def get_workspace_context(
    session: Session, conversation_id: UUID
) -> WorkspaceContextRead:
    return WorkspaceContextRead.model_validate(
        get_conversation(session, conversation_id)
    )


def update_workspace_context(
    session: Session,
    conversation_id: UUID,
    update: WorkspaceContextUpdate,
) -> WorkspaceContextRead:
    conversation = get_conversation(session, conversation_id)
    for field, value in update.model_dump(exclude_unset=True).items():
        if field == "device" and value is not None:
            try:
                get_synthetic_device(value)
            except SyntheticDeviceNotFoundError as error:
                raise ValueError("Unknown synthetic device") from error
        setattr(conversation, field, value)
    session.commit()
    session.refresh(conversation)
    return WorkspaceContextRead.model_validate(conversation)
