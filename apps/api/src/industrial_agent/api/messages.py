import json
from collections.abc import Callable, Sequence
from typing import Annotated
from uuid import UUID

from anyio import from_thread
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from industrial_agent.config.settings import Settings
from industrial_agent.database.session import get_db_session
from industrial_agent.domain.routing import ExtractedContext, TimePreset
from industrial_agent.graph.combined import CombinedExecutionCancelled
from industrial_agent.graph.errors import GraphExecutionError
from industrial_agent.graph.runner import (
    StreamingExecutionCancelled,
    run_stream_routed_exchange,
    run_sync_exchange,
)
from industrial_agent.graph.state import GraphState
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
from industrial_agent.services.device import list_synthetic_devices
from industrial_agent.services.documents import DocumentCorpusService
from industrial_agent.services.routing import (
    RoutingOutcome,
    route_deterministically,
    route_exchange,
)
from industrial_agent.services.routing_classifier import (
    PriorExchange,
    RoutingClassificationCancelled,
    RoutingClassifier,
)

_WORKSPACE_TIME_PRESETS = {
    "Last 1 hour": TimePreset.LAST_1_HOUR,
    "Last 4 hours": TimePreset.LAST_4_HOURS,
    "Last 8 hours": TimePreset.LAST_8_HOURS,
    "Last 24 hours": TimePreset.LAST_24_HOURS,
}

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


def _route_graph_state(
    state: GraphState,
    *,
    is_cancelled: Callable[[], bool] = lambda: False,
) -> RoutingOutcome:
    """Route one loaded graph state through the shared application policy."""
    messages = state["messages"]
    prior = None
    if len(messages) >= 3:
        prior = PriorExchange(
            user=messages[-3].content,
            assistant=messages[-2].content,
        )
    workspace = state["workspace_context"]
    saved_context = ExtractedContext(
        equipment_id=workspace.device,
        lot_id=workspace.lot,
        time_preset=_WORKSPACE_TIME_PRESETS.get(workspace.time_range),
    )
    deterministic = route_deterministically(
        latest_question=messages[-1].content,
        saved_context=saved_context,
        conversation_id=str(state["conversation_id"]),
    )
    if deterministic is not None:
        return deterministic
    settings = Settings()
    with OpenAICompatibleChatAdapter.router_from_settings(settings) as adapter:
        return route_exchange(
            latest_question=messages[-1].content,
            classifier=RoutingClassifier(adapter),
            prior_exchange=prior,
            is_cancelled=is_cancelled,
            saved_context=saved_context,
            supported_equipment_ids=tuple(
                device.id for device in list_synthetic_devices()
            ),
            capability_metadata=(
                "general conversation",
                "synthetic production summary",
                "recorded synthetic equipment status",
                "synthetic defect distribution",
                "fictional local document search",
            ),
            conversation_id=str(state["conversation_id"]),
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
    request: Request,
) -> MessageExchangeRead:
    document_corpus_service: DocumentCorpusService = (
        request.app.state.document_corpus_service
    )
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
            document_corpus_service=document_corpus_service,
            route_exchange=_route_graph_state,
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
    )


@router.post("/stream")
def stream_user_message(
    conversation_id: UUID,
    payload: MessageCreate,
    session: DatabaseSession,
    request: Request,
) -> StreamingResponse:
    document_corpus_service: DocumentCorpusService = (
        request.app.state.document_corpus_service
    )
    try:
        get_conversation(session, conversation_id)
    except ConversationNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        ) from error

    def stream_events():
        def route_state(state: GraphState) -> RoutingOutcome:
            return _route_graph_state(
                state,
                is_cancelled=lambda: from_thread.run(request.is_disconnected),
            )

        def stream(messages: Sequence[ChatMessage]):
            with OpenAICompatibleChatAdapter.from_settings(
                Settings()
            ) as adapter:
                yield from adapter.stream(messages, include_reasoning=True)

        try:
            def stream_with_tool_result(messages, tool_call, selected_tool):
                with OpenAICompatibleChatAdapter.from_settings(
                    Settings()
                ) as adapter:
                    yield from adapter.stream_with_tool_result(
                        messages,
                        tools=(selected_tool,),
                        tool_call=tool_call,
                        include_reasoning=True,
                    )

            events = run_stream_routed_exchange(
                session,
                conversation_id=conversation_id,
                content=payload.content,
                route_exchange=route_state,
                stream=stream,
                stream_with_tool_result=stream_with_tool_result,
                document_corpus_service=document_corpus_service,
                is_cancelled=lambda: from_thread.run(request.is_disconnected),
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
                elif event.kind in {"reasoning_delta", "reasoning_truncated"}:
                    yield _sse_event(event.kind, event.payload)
                elif event.kind == "tool_call_started":
                    yield _sse_event("tool_call_started", event.payload)
                elif event.kind == "tool_result":
                    evidence = EvidenceRead.model_validate(
                        event.payload, from_attributes=True
                    )
                    yield _sse_event("tool_result", evidence.model_dump(mode="json"))
                elif event.kind == "combined_tool_result":
                    yield _sse_event("combined_tool_result", event.payload)
                elif event.kind == "combined_evidence_completed":
                    yield _sse_event("combined_evidence_completed", event.payload)
                elif event.kind in {
                    "routing_started",
                    "routing_retry",
                    "routing_decided",
                    "clarification_required",
                    "routing_fallback_used",
                }:
                    yield _sse_event(event.kind, event.payload)
                elif event.kind == "assistant_message":
                    message = MessageRead.model_validate(event.payload)
                    yield _sse_event(
                        "message_completed",
                        {"assistant_message": message.model_dump(mode="json")},
                    )
        except (
            RoutingClassificationCancelled,
            CombinedExecutionCancelled,
            StreamingExecutionCancelled,
        ):
            return
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
