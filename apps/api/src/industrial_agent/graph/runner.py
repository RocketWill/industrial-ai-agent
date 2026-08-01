from collections.abc import Callable, Iterator, Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from industrial_agent.graph.state import ExecutionEvent, GraphState
from industrial_agent.graph.workflow import (
    Complete,
    CompleteWithTools,
    build_workflow,
    load_context,
    persist_response,
)
from industrial_agent.llm.types import (
    ChatMessage,
    CompletionResult,
    ToolDefinition,
)
from industrial_agent.services import message as message_service
from industrial_agent.services.message import MessageExchange


def run_sync_exchange(
    session: Session,
    *,
    conversation_id: UUID,
    content: str,
    complete: Complete,
    complete_with_tools: CompleteWithTools | None = None,
) -> MessageExchange:
    initial_state = load_context(
        session,
        conversation_id=conversation_id,
        content=content,
    )
    final_state = build_workflow(
        session,
        complete,
        complete_with_tools=complete_with_tools,
    ).invoke(initial_state)
    messages = message_service.list_messages(session, conversation_id)
    return MessageExchange(
        user_message=messages[-2],
        assistant_message=messages[-1],
        evidence=final_state.get("evidence"),
    )


Stream = Callable[[Sequence[ChatMessage]], Iterator[str]]
ToolComplete = Callable[..., CompletionResult]


def run_stream_tool_exchange(
    session: Session,
    *,
    conversation_id: UUID,
    content: str,
    complete_with_tools: ToolComplete,
    tool_definition: ToolDefinition,
) -> Iterator[ExecutionEvent]:
    """Run one production tool exchange and expose its stages as SSE events."""
    calls: list[CompletionResult] = []

    def instrumented_complete(*args, **kwargs):
        result = complete_with_tools(*args, **kwargs)
        calls.append(result)
        return result

    exchange = run_sync_exchange(
        session,
        conversation_id=conversation_id,
        content=content,
        complete=lambda _: "",
        complete_with_tools=instrumented_complete,
    )
    user_message = message_service.list_messages(session, conversation_id)[-2]
    yield ExecutionEvent(kind="user_message", payload=user_message)
    first = calls[0] if calls else None
    if first and first.tool_calls:
        call = first.tool_calls[0]
        yield ExecutionEvent(
            kind="tool_call_started",
            payload={"name": call.name, "arguments": call.arguments},
        )
        if exchange.evidence is not None:
            yield ExecutionEvent(
                kind="tool_result",
                payload=exchange.evidence,
            )
    yield ExecutionEvent(
        kind="token", payload={"text": exchange.assistant_message.content}
    )
    yield ExecutionEvent(kind="assistant_message", payload=exchange.assistant_message)


def run_stream_exchange(
    session: Session,
    *,
    conversation_id: UUID,
    content: str,
    stream: Stream,
) -> Iterator[ExecutionEvent]:
    state = load_context(
        session,
        conversation_id=conversation_id,
        content=content,
    )
    user_message = message_service.list_messages(session, conversation_id)[-1]
    yield ExecutionEvent(kind="user_message", payload=user_message)

    parts: list[str] = []
    for delta in stream(state["messages"]):
        if not isinstance(delta, str) or not delta:
            continue
        parts.append(delta)
        yield ExecutionEvent(kind="token", payload={"text": delta})

    completed_state: GraphState = {
        **state,
        "assistant_content": "".join(parts),
        "execution_events": [
            *state["execution_events"],
            ExecutionEvent(kind="node_completed", payload={"node": "call_llm"}),
        ],
    }
    persist_response(session, completed_state)
    assistant_message = message_service.list_messages(session, conversation_id)[-1]
    yield ExecutionEvent(kind="assistant_message", payload=assistant_message)
