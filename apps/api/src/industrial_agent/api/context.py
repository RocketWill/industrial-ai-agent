from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from industrial_agent.database.session import get_db_session
from industrial_agent.schemas.context import (
    WorkspaceContextRead,
    WorkspaceContextUpdate,
)
from industrial_agent.services import conversation as conversation_service
from industrial_agent.services.conversation import ConversationNotFoundError

router = APIRouter(prefix="/conversations/{conversation_id}/context", tags=["context"])
DatabaseSession = Annotated[Session, Depends(get_db_session)]


@router.get("", response_model=WorkspaceContextRead)
def get_context(
    conversation_id: UUID, session: DatabaseSession
) -> WorkspaceContextRead:
    try:
        return conversation_service.get_workspace_context(session, conversation_id)
    except ConversationNotFoundError as error:
        raise HTTPException(status_code=404, detail="Conversation not found") from error


@router.patch("", response_model=WorkspaceContextRead)
def update_context(
    conversation_id: UUID,
    payload: WorkspaceContextUpdate,
    session: DatabaseSession,
) -> WorkspaceContextRead:
    try:
        return conversation_service.update_workspace_context(
            session, conversation_id, payload
        )
    except ConversationNotFoundError as error:
        raise HTTPException(status_code=404, detail="Conversation not found") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
