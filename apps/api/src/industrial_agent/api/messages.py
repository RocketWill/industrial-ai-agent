import json
from collections.abc import Sequence
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from industrial_agent.config.settings import Settings
from industrial_agent.database.session import get_db_session
from industrial_agent.graph.errors import GraphExecutionError
from industrial_agent.graph.runner import (
    run_stream_exchange,
    run_stream_tool_exchange,
    run_sync_exchange,
)
from industrial_agent.graph.workflow import (
    DEFECT_DISTRIBUTION_TOOL,
    DOCUMENT_SEARCH_TOOL,
    EQUIPMENT_STATUS_TOOL,
    PRODUCTION_TOOL,
    _is_defect_distribution_question,
    _is_document_question,
    _is_equipment_status_question,
    _is_production_question,
)
from industrial_agent.llm.errors import (
    LLMConfigurationError,
    LLMConnectionError,
    LLMResponseError,
    LLMServiceError,
)
from industrial_agent.llm.openai_compatible import (
    OpenAICompatibleChatAdapter,
)
from industrial_agent.llm.types import (
    ChatMessage,
    CompletionResult,
    ToolDefinition,
    ToolResult,
)
from industrial_agent.schemas.message import (
    EvidenceRead,
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

    def complete_with_tools(
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolDefinition],
        *,
        tool_call: ToolResult | None = None,
    ) -> CompletionResult:
        with OpenAICompatibleChatAdapter.from_settings(Settings()) as adapter:
            return adapter.complete_with_tools(
                messages,
                tools=tools,
                tool_call=tool_call,
            )

    try:
        exchange = run_sync_exchange(
            session,
            conversation_id=conversation_id,
            content=payload.content,
            complete=complete,
            complete_with_tools=complete_with_tools,
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
    except GraphExecutionError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Assistant response is temporarily unavailable",
        ) from error
    return MessageExchangeRead(
        user_message=MessageRead.model_validate(exchange.user_message),
        assistant_message=MessageRead.model_validate(
            exchange.assistant_message
        ),
        evidence=(
            EvidenceRead.model_validate(exchange.evidence, from_attributes=True)
            if exchange.evidence is not None
            else None
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
            question = [ChatMessage(role="user", content=payload.content)]
            is_equipment_status = _is_equipment_status_question(question)
            is_defect_distribution = _is_defect_distribution_question(question)
            is_document_search = _is_document_question(question)
            if (
                is_document_search
                or is_equipment_status
                or is_defect_distribution
                or _is_production_question(question)
            ):
                selected_tool = (
                    DOCUMENT_SEARCH_TOOL
                    if is_document_search
                    else EQUIPMENT_STATUS_TOOL
                    if is_equipment_status
                    else DEFECT_DISTRIBUTION_TOOL
                    if is_defect_distribution
                    else PRODUCTION_TOOL
                )
                def complete_with_tools(messages, tools, *, tool_call=None):
                    with OpenAICompatibleChatAdapter.from_settings(
                        Settings()
                    ) as adapter:
                        return adapter.complete_with_tools(
                            messages, tools=tools, tool_call=tool_call
                        )

                def stream_with_tool_result(messages, tool_call):
                    with OpenAICompatibleChatAdapter.from_settings(
                        Settings()
                    ) as adapter:
                        yield from adapter.stream_with_tool_result(
                            messages,
                            tools=(selected_tool,),
                            tool_call=tool_call,
                        )

                events = run_stream_tool_exchange(
                    session,
                    conversation_id=conversation_id,
                    content=payload.content,
                    complete_with_tools=complete_with_tools,
                    stream_with_tool_result=stream_with_tool_result,
                )
            else:
                events = run_stream_exchange(
                    session,
                    conversation_id=conversation_id,
                    content=payload.content,
                    stream=stream,
                )
            for event in events:
                if event.kind == "user_message":
                    message = MessageRead.model_validate(event.payload)
                    yield _sse_event(
                        "message_started",
                        {"user_message": message.model_dump(mode="json")},
                    )
                elif event.kind == "token":
                    yield _sse_event("token", event.payload)
                elif event.kind == "tool_call_started":
                    yield _sse_event("tool_call_started", event.payload)
                elif event.kind == "tool_result":
                    evidence = EvidenceRead.model_validate(
                        event.payload, from_attributes=True
                    )
                    yield _sse_event("tool_result", evidence.model_dump(mode="json"))
                elif event.kind == "assistant_message":
                    message = MessageRead.model_validate(event.payload)
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
        except GraphExecutionError as error:
            yield _sse_event(
                "error",
                {
                    "code": error.code,
                    "message": (
                        "Assistant returned an empty response"
                        if error.code == "empty_response"
                        else "Assistant response is temporarily unavailable"
                    ),
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
