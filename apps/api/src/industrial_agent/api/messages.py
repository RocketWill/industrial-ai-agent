import json
from collections.abc import Sequence
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
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
from industrial_agent.services.conversation import (
    ConversationNotFoundError,
    get_conversation,
)

router = APIRouter(
    prefix="/conversations/{conversation_id}/messages",
    tags=["messages"],
)
DatabaseSession = Annotated[Session, Depends(get_db_session)]


def _sse_event(event: str, payload: object) -> str:
    return (
        f"event: {event}\n"
        f"data: {json.dumps(payload, separators=(',', ':'))}\n\n"
    )


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


@router.post("/stream")
def stream_user_message(
    conversation_id: UUID,
    payload: MessageCreate,
    session: DatabaseSession,
) -> StreamingResponse:
    try:
        get_conversation(session, conversation_id)
    except ConversationNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        ) from error

    def stream_events():
        def stream(messages: Sequence[ChatMessage]):
            with OpenAICompatibleChatAdapter.from_settings(
                Settings()
            ) as adapter:
                yield from adapter.stream(messages)

        try:
            events = message_service.stream_message_exchange(
                session,
                conversation_id=conversation_id,
                content=payload.content,
                stream=stream,
            )
            for event in events:
                if event.kind == "user_message":
                    message = MessageRead.model_validate(event.value)
                    yield _sse_event(
                        "message_started",
                        {"user_message": message.model_dump(mode="json")},
                    )
                elif event.kind == "token":
                    yield _sse_event("token", {"text": event.value})
                elif event.kind == "assistant_message":
                    message = MessageRead.model_validate(event.value)
                    yield _sse_event(
                        "message_completed",
                        {"assistant_message": message.model_dump(mode="json")},
                    )
        except (
            LLMConfigurationError,
            LLMConnectionError,
            LLMResponseError,
            LLMServiceError,
        ):
            yield _sse_event(
                "error",
                {
                    "code": "assistant_unavailable",
                    "message": "Assistant response is temporarily unavailable",
                },
            )
        except ValueError:
            yield _sse_event(
                "error",
                {
                    "code": "empty_response",
                    "message": "Assistant returned an empty response",
                },
            )

    return StreamingResponse(
        stream_events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
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
