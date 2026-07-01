from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from industrial_agent.database.session import get_db_session
from industrial_agent.schemas.message import MessageCreate, MessageRead
from industrial_agent.services import message as message_service
from industrial_agent.services.conversation import ConversationNotFoundError

router = APIRouter(
    prefix="/conversations/{conversation_id}/messages",
    tags=["messages"],
)
DatabaseSession = Annotated[Session, Depends(get_db_session)]


@router.post(
    "",
    response_model=MessageRead,
    status_code=status.HTTP_201_CREATED,
)
def create_user_message(
    conversation_id: UUID,
    payload: MessageCreate,
    session: DatabaseSession,
) -> MessageRead:
    try:
        message = message_service.create_user_message(
            session,
            conversation_id=conversation_id,
            content=payload.content,
        )
    except ConversationNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        ) from error
    return MessageRead.model_validate(message)


@router.get("", response_model=list[MessageRead])
def list_messages(
    conversation_id: UUID,
    session: DatabaseSession,
) -> list[MessageRead]:
    try:
        messages = message_service.list_messages(
            session,
            conversation_id,
        )
    except ConversationNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        ) from error
    return [MessageRead.model_validate(message) for message in messages]
