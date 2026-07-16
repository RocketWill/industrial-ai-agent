from collections.abc import Callable, Sequence
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
        "required": ["equipment_id", "start", "end"],
        "additionalProperties": False,
    },
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
    try:
        request = ProductionSummaryRequest.model_validate(call.arguments)
    except ValidationError:
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


def _call_llm(state: GraphState, *, complete: Complete) -> GraphState:
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


def build_workflow(session: Session, complete: Complete):
    graph = StateGraph(GraphState)
    graph.add_node(
        "load_context",
        lambda state: load_context(
            session,
            conversation_id=state["conversation_id"],
        ),
    )
    graph.add_node("call_llm", lambda state: _call_llm(state, complete=complete))
    graph.add_node("persist_response", lambda state: persist_response(session, state))
    graph.add_edge(START, "load_context")
    graph.add_edge("load_context", "call_llm")
    graph.add_edge("call_llm", "persist_response")
    graph.add_edge("persist_response", END)
    return graph.compile()
