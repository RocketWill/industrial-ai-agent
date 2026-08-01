from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from uuid import UUID

from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError
from sqlalchemy.orm import Session

from industrial_agent.graph.errors import GraphExecutionError
from industrial_agent.graph.state import (
    EvidenceState,
    ExecutionEvent,
    GraphState,
    ToolError,
)
from industrial_agent.llm.types import (
    ChatMessage,
    CompletionResult,
    ToolCall,
    ToolDefinition,
    ToolResult,
)
from industrial_agent.services import conversation as conversation_service
from industrial_agent.services import message as message_service
from industrial_agent.tools.production import (
    ProductionSummaryRequest,
    ProductionToolError,
    get_production_summary,
)

Complete = Callable[[Sequence[ChatMessage]], str]
CompleteWithTools = Callable[..., CompletionResult]


def _is_production_question(messages: Sequence[ChatMessage]) -> bool:
    question = messages[-1].content.lower()
    return any(
        term in question
        for term in ("yield", "defect", "alarm", "production", "inspection")
    )


def _messages_with_production_context(state: GraphState) -> list[ChatMessage]:
    """Give the tool-selection model the saved context without persisting it."""
    context = state["workspace_context"]
    details = [
        f"device={context.device or 'missing'}",
        f"lot={context.lot or 'missing'}",
        f"time_range={context.time_range or 'missing'}",
    ]
    if context.time_range in _DEMO_PRESET_HOURS:
        hours = _DEMO_PRESET_HOURS[context.time_range]
        start = _DEMO_SHIFT_END - timedelta(hours=hours)
        details.append(
            "resolved_utc="
            f"{start.isoformat().replace('+00:00', 'Z')}/"
            f"{_DEMO_SHIFT_END.isoformat().replace('+00:00', 'Z')}"
        )
    messages = list(state["messages"])
    last = messages[-1]
    messages[-1] = ChatMessage(
        role=last.role,
        content=(
            f"{last.content}\n\nSaved analysis context: {', '.join(details)}. "
            "Use this context to fill missing production tool arguments. "
            "Ask for clarification only when the required context is missing."
        ),
    )
    return messages

PRODUCTION_TOOL = ToolDefinition(
    name="get_production_summary",
    description="Read deterministic synthetic production evidence.",
    parameters={
        "type": "object",
        "properties": {
            "equipment_id": {"type": "string"},
            "lot_id": {"type": ["string", "null"]},
            "start": {"type": "string", "format": "date-time"},
            "end": {"type": "string", "format": "date-time"},
        },
        "required": [],
        "additionalProperties": False,
    },
)

_DEMO_SHIFT_END = datetime(2026, 1, 15, 17, tzinfo=UTC)
_DEMO_PRESET_HOURS = {
    "Last 1 hour": 1,
    "Last 4 hours": 4,
    "Last 8 hours": 8,
    "Last 24 hours": 24,
}


def resolve_production_request(
    state: GraphState,
    call: ToolCall,
) -> tuple[ProductionSummaryRequest | None, str | None]:
    """Merge explicit tool arguments with saved synthetic workspace context."""
    arguments = dict(call.arguments)
    context = state["workspace_context"]
    equipment_id = arguments.get("equipment_id") or context.device
    lot_id = arguments.get("lot_id") or context.lot
    start = arguments.get("start")
    end = arguments.get("end")
    if not start and not end and context.time_range in _DEMO_PRESET_HOURS:
        end_datetime = _DEMO_SHIFT_END
        start_datetime = end_datetime - timedelta(
            hours=_DEMO_PRESET_HOURS[context.time_range]
        )
        start = start_datetime.isoformat().replace("+00:00", "Z")
        end = end_datetime.isoformat().replace("+00:00", "Z")
    if not equipment_id:
        return None, (
            "Please specify an equipment ID or select a device in the analysis "
            "context."
        )
    if not start or not end:
        return None, (
            "Please specify a start and end time, or select a supported time "
            "range in the analysis context."
        )
    try:
        return ProductionSummaryRequest.model_validate(
            {
                "equipment_id": equipment_id,
                "lot_id": lot_id,
                "start": start,
                "end": end,
            }
        ), None
    except ValidationError:
        return None, (
            "Please provide a valid UTC start and end time for the production "
            "query."
        )


def load_context(
    session: Session,
    *,
    conversation_id: UUID,
    content: str | None = None,
) -> GraphState:
    if content is not None:
        message_service.create_user_message(
            session,
            conversation_id=conversation_id,
            content=content,
        )
    history = message_service.list_messages(session, conversation_id)
    return {
        "conversation_id": conversation_id,
        "messages": [
            ChatMessage(role=message.role, content=message.content)
            for message in history
        ],
        "workspace_context": conversation_service.get_workspace_context(
            session, conversation_id
        ),
        "assistant_content": "",
        "evidence": None,
        "tool_call": None,
        "execution_events": [
            ExecutionEvent(kind="node_completed", payload={"node": "load_context"})
        ],
    }


def execute_production_tool(
    state: GraphState,
    result: CompletionResult,
) -> GraphState:
    """Execute one parsed production Tool Call into Evidence State."""
    if len(result.tool_calls) != 1:
        return {
            **state,
            "evidence": EvidenceState(
                tool_error=ToolError(code="UNSUPPORTED_TOOL_CALL_PATTERN")
            ),
        }
    call = result.tool_calls[0]
    if call.name != PRODUCTION_TOOL.name:
        return {
            **state,
            "evidence": EvidenceState(
                tool_error=ToolError(code="UNSUPPORTED_TOOL_CALL_PATTERN")
            ),
        }
    request, clarification = resolve_production_request(state, call)
    if clarification is not None:
        return {
            **state,
            "assistant_content": clarification,
        }
    if request is None:
        return {
            **state,
            "evidence": EvidenceState(
                tool_error=ToolError(code="INVALID_INPUT")
            ),
        }
    try:
        summary = get_production_summary(request)
    except ProductionToolError as error:
        code = (
            "UNKNOWN_EQUIPMENT"
            if "Equipment" in str(error)
            else "UNKNOWN_PRODUCTION_LOT"
        )
        return {
            **state,
            "evidence": EvidenceState(tool_error=ToolError(code=code)),
        }
    return {
        **state,
        "evidence": EvidenceState(production_summary=summary),
        "tool_call": call,
        "execution_events": [
            *state["execution_events"],
            ExecutionEvent(
                kind="node_completed", payload={"node": "execute_production_tool"}
            ),
        ],
    }


def answer_with_production_evidence(
    state: GraphState,
    *,
    complete_with_tools: CompleteWithTools,
    tool_call: ToolCall,
) -> GraphState:
    """Ask the model for a final answer using one structured tool result."""
    evidence = state["evidence"]
    if evidence is None:
        raise GraphExecutionError(code="empty_response")
    if evidence.tool_error is not None:
        return {
            **state,
            "assistant_content": evidence.tool_error.message,
            "execution_events": [
                *state["execution_events"],
                ExecutionEvent(
                    kind="node_completed", payload={"node": "tool_error"}
                ),
            ],
        }
    if evidence.production_summary is None:
        raise GraphExecutionError(code="empty_response")
    result = complete_with_tools(
        state["messages"],
        (PRODUCTION_TOOL,),
        tool_call=ToolResult(
            call_id=tool_call.call_id,
            name=tool_call.name,
            arguments=tool_call.arguments,
            content=evidence.production_summary.model_dump_json(),
        ),
    )
    if result.tool_calls or not result.content or not result.content.strip():
        raise GraphExecutionError(code="empty_response")
    return {
        **state,
        "assistant_content": result.content.strip(),
        "execution_events": [
            *state["execution_events"],
            ExecutionEvent(
                kind="node_completed", payload={"node": "answer_with_evidence"}
            ),
        ],
    }


def _call_llm(
    state: GraphState,
    *,
    complete: Complete,
    complete_with_tools: CompleteWithTools | None = None,
) -> GraphState:
    if complete_with_tools is not None and _is_production_question(state["messages"]):
        first_result = complete_with_tools(
            _messages_with_production_context(state),
            (PRODUCTION_TOOL,),
        )
        if first_result.tool_calls:
            tool_state = execute_production_tool(state, first_result)
            if tool_state["assistant_content"]:
                return tool_state
            return answer_with_production_evidence(
                tool_state,
                complete_with_tools=complete_with_tools,
                tool_call=first_result.tool_calls[0],
            )
        if first_result.content and first_result.content.strip():
            return {
                **state,
                "assistant_content": first_result.content.strip(),
                "execution_events": [
                    *state["execution_events"],
                    ExecutionEvent(
                        kind="node_completed", payload={"node": "call_llm"}
                    ),
                ],
            }
        raise GraphExecutionError(code="empty_response")
    assistant_content = complete(state["messages"])
    return {
        **state,
        "assistant_content": assistant_content,
        "execution_events": [
            *state["execution_events"],
            ExecutionEvent(kind="node_completed", payload={"node": "call_llm"}),
        ],
    }


def persist_response(session: Session, state: GraphState) -> GraphState:
    assistant_content = state["assistant_content"].strip()
    if not assistant_content:
        raise GraphExecutionError(code="empty_response")
    message_service.create_message(
        session,
        conversation_id=state["conversation_id"],
        role="assistant",
        content=assistant_content,
    )
    return {
        **state,
        "assistant_content": assistant_content,
        "execution_events": [
            *state["execution_events"],
            ExecutionEvent(
                kind="node_completed", payload={"node": "persist_response"}
            ),
        ],
    }


def build_workflow(
    session: Session,
    complete: Complete,
    complete_with_tools: CompleteWithTools | None = None,
):
    graph = StateGraph(GraphState)
    graph.add_node(
        "load_context",
        lambda state: load_context(
            session,
            conversation_id=state["conversation_id"],
        ),
    )
    graph.add_node(
        "call_llm",
        lambda state: _call_llm(
            state,
            complete=complete,
            complete_with_tools=complete_with_tools,
        ),
    )
    graph.add_node("persist_response", lambda state: persist_response(session, state))
    graph.add_edge(START, "load_context")
    graph.add_edge("load_context", "call_llm")
    graph.add_edge("call_llm", "persist_response")
    graph.add_edge("persist_response", END)
    return graph.compile()
