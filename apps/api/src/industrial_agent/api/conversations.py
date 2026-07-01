from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from industrial_agent.database.session import get_db_session
from industrial_agent.schemas.conversation import (
    ConversationCreate,
    ConversationRead,
)
from industrial_agent.services import conversation as conversation_service
from industrial_agent.services.conversation import ConversationNotFoundError

router = APIRouter(prefix="/conversations", tags=["conversations"])
DatabaseSession = Annotated[Session, Depends(get_db_session)]


@router.post(
    "",
    response_model=ConversationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation(
    payload: ConversationCreate,
    session: DatabaseSession,
) -> ConversationRead:
    conversation = conversation_service.create_conversation(
        session,
        title=payload.title,
    )
    return ConversationRead.model_validate(conversation)


@router.get("", response_model=list[ConversationRead])
def list_conversations(
    session: DatabaseSession,
) -> list[ConversationRead]:
    conversations = conversation_service.list_conversations(session)
    return [
        ConversationRead.model_validate(conversation)
        for conversation in conversations
    ]


@router.get(
    "/{conversation_id}",
    response_model=ConversationRead,
)
def get_conversation(
    conversation_id: UUID,
    session: DatabaseSession,
) -> ConversationRead:
    try:
        conversation = conversation_service.get_conversation(
            session,
            conversation_id,
        )
    except ConversationNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        ) from error
    return ConversationRead.model_validate(conversation)


@router.delete(
    "/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_conversation(
    conversation_id: UUID,
    session: DatabaseSession,
) -> Response:
    try:
        conversation_service.delete_conversation(
            session,
            conversation_id,
        )
    except ConversationNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        ) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
