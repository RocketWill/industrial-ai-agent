from collections.abc import Sequence
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from industrial_agent.config.settings import Settings
from industrial_agent.database.session import get_db_session
from industrial_agent.llm.errors import (
    LLMConfigurationError,
    LLMConnectionError,
    LLMResponseError,
    LLMServiceError,
)
from industrial_agent.llm.openai_compatible import (
    OpenAICompatibleChatAdapter,
)
from industrial_agent.llm.types import ChatMessage
from industrial_agent.schemas.message import (
    MessageCreate,
    MessageExchangeRead,
    MessageRead,
)
from industrial_agent.services import message as message_service
from industrial_agent.services.conversation import ConversationNotFoundError

router = APIRouter(
    prefix="/conversations/{conversation_id}/messages",
    tags=["messages"],
)
DatabaseSession = Annotated[Session, Depends(get_db_session)]


@router.post(
    "",
    response_model=MessageExchangeRead,
    status_code=status.HTTP_201_CREATED,
)
def create_user_message(
    conversation_id: UUID,
    payload: MessageCreate,
    session: DatabaseSession,
) -> MessageExchangeRead:
    def complete(messages: Sequence[ChatMessage]) -> str:
        with OpenAICompatibleChatAdapter.from_settings(
            Settings()
        ) as adapter:
            return adapter.complete(messages)

    try:
        exchange = message_service.create_message_exchange(
            session,
            conversation_id=conversation_id,
            content=payload.content,
            complete=complete,
        )
    except ConversationNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        ) from error
    except (
        LLMConfigurationError,
        LLMConnectionError,
        LLMResponseError,
        LLMServiceError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Assistant response is temporarily unavailable",
        ) from error
    return MessageExchangeRead(
        user_message=MessageRead.model_validate(exchange.user_message),
        assistant_message=MessageRead.model_validate(
            exchange.assistant_message
        ),
    )


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
