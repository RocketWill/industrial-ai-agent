from collections.abc import Callable, Iterator, Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from industrial_agent.graph.errors import GraphExecutionError
from industrial_agent.graph.state import ExecutionEvent, GraphState
from industrial_agent.graph.workflow import (
    DEFECT_DISTRIBUTION_TOOL,
    EQUIPMENT_STATUS_TOOL,
    PRODUCTION_TOOL,
    Complete,
    CompleteWithTools,
    _is_defect_distribution_question,
    _is_equipment_status_question,
    _messages_with_production_context,
    build_workflow,
    execute_defect_distribution_tool,
    execute_equipment_status_tool,
    execute_production_tool,
    load_context,
    persist_response,
)
from industrial_agent.llm.types import (
    ChatMessage,
    CompletionResult,
    ToolResult,
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
ToolStream = Callable[[Sequence[ChatMessage], ToolResult], Iterator[str]]


def run_stream_tool_exchange(
    session: Session,
    *,
    conversation_id: UUID,
    content: str,
    complete_with_tools: ToolComplete,
    stream_with_tool_result: ToolStream,
) -> Iterator[ExecutionEvent]:
    """Run one production tool exchange and expose its stages as SSE events."""
    state = load_context(
        session,
        conversation_id=conversation_id,
        content=content,
    )
    user_message = message_service.list_messages(session, conversation_id)[-1]
    yield ExecutionEvent(kind="user_message", payload=user_message)
    is_equipment_status = _is_equipment_status_question(state["messages"])
    is_defect_distribution = _is_defect_distribution_question(state["messages"])
    selected_tool = (
        EQUIPMENT_STATUS_TOOL
        if is_equipment_status
        else DEFECT_DISTRIBUTION_TOOL
        if is_defect_distribution
        else PRODUCTION_TOOL
    )
    first = complete_with_tools(
        _messages_with_production_context(state), (selected_tool,)
    )
    if not first.tool_calls:
        content = first.content or ""
        completed = persist_response(session, {**state, "assistant_content": content})
        assistant_message = message_service.list_messages(session, conversation_id)[-1]
        yield ExecutionEvent(
            kind="token", payload={"text": completed["assistant_content"]}
        )
        yield ExecutionEvent(kind="assistant_message", payload=assistant_message)
        return
    if is_equipment_status:
        tool_state = execute_equipment_status_tool(state, first)
    elif is_defect_distribution:
        tool_state = execute_defect_distribution_tool(state, first)
    else:
        tool_state = execute_production_tool(state, first)
    call = first.tool_calls[0]
    yield ExecutionEvent(
        kind="tool_call_started",
        payload={"name": call.name, "arguments": call.arguments},
    )
    if tool_state["evidence"] is not None:
        yield ExecutionEvent(kind="tool_result", payload=tool_state["evidence"])
    evidence = tool_state["evidence"]
    if evidence is None or evidence.tool_error is not None:
        assistant_content = (
            evidence.tool_error.message
            if evidence is not None and evidence.tool_error is not None
            else tool_state["assistant_content"]
        )
        completed = persist_response(
            session, {**tool_state, "assistant_content": assistant_content}
        )
        assistant_message = message_service.list_messages(session, conversation_id)[-1]
        yield ExecutionEvent(
            kind="token", payload={"text": completed["assistant_content"]}
        )
        yield ExecutionEvent(kind="assistant_message", payload=assistant_message)
        return
    result_payload = (
        evidence.equipment_status
        if is_equipment_status
        else evidence.defect_distribution
        if is_defect_distribution
        else evidence.production_summary
    )
    if result_payload is None:
        raise GraphExecutionError(code="empty_response")
    tool_result = ToolResult(
        call_id=call.call_id,
        name=call.name,
        arguments=call.arguments,
        content=result_payload.model_dump_json(),
    )
    parts: list[str] = []
    for delta in stream_with_tool_result(tool_state["messages"], tool_result):
        parts.append(delta)
        yield ExecutionEvent(kind="token", payload={"text": delta})
    completed = persist_response(
        session, {**tool_state, "assistant_content": "".join(parts)}
    )
    assistant_message = message_service.list_messages(session, conversation_id)[-1]
    yield ExecutionEvent(kind="assistant_message", payload=assistant_message)


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
