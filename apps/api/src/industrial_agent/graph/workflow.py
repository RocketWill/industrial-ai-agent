from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from uuid import UUID

from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError
from sqlalchemy.orm import Session

from industrial_agent.domain.routing import RouteIntent, TimePreset
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
from industrial_agent.services.documents import DocumentCorpusService
from industrial_agent.services.evidence import validate_answer, validate_evidence
from industrial_agent.services.routing import RoutingOutcome
from industrial_agent.tools.defect_distribution import (
    DefectDistributionRequest,
    DefectDistributionToolError,
    get_defect_distribution,
)
from industrial_agent.tools.document_search import (
    DocumentSearchRequest,
    search_documents,
)
from industrial_agent.tools.equipment_status import (
    EquipmentStatusRequest,
    EquipmentStatusToolError,
    get_equipment_status,
)
from industrial_agent.tools.production import (
    ProductionSummaryRequest,
    ProductionToolError,
    get_production_summary,
)

Complete = Callable[[Sequence[ChatMessage]], str]
CompleteWithTools = Callable[..., CompletionResult]
RouteExchange = Callable[[GraphState], RoutingOutcome]


def _is_production_question(messages: Sequence[ChatMessage]) -> bool:
    question = messages[-1].content.lower()
    return any(
        term in question
        for term in ("yield", "defect", "alarm", "production", "inspection")
    )


def _is_equipment_status_question(messages: Sequence[ChatMessage]) -> bool:
    question = messages[-1].content.lower()
    explicit_status_term = any(
        term in question
        for term in (
            "equipment status",
            "machine status",
            "equipment running",
            "equipment down",
            "machine running",
            "machine down",
        )
    )
    state_about_named_equipment = (
        any(
            term in question
            for term in ("running", "idle", "warning", "down", "maintenance")
        )
        and any(term in question for term in ("equipment", "machine", "aoi-wafer"))
    )
    return explicit_status_term or state_about_named_equipment


def _is_defect_distribution_question(messages: Sequence[ChatMessage]) -> bool:
    question = messages[-1].content.lower()
    return any(
        term in question
        for term in (
            "defect distribution",
            "defect breakdown",
            "defect categories",
            "top defect",
        )
    )


def _is_document_question(messages: Sequence[ChatMessage]) -> bool:
    question = messages[-1].content.lower()
    procedural = any(
        term in question
        for term in (
            "operator check",
            "troubleshoot",
            "manual",
            "procedure",
            "recovery boundary",
        )
    )
    known_alarm_procedure = "optical-signal-low" in question and any(
        term in question for term in ("check", "should", "recover", "respond")
    )
    return procedural or known_alarm_procedure


def build_document_search_call(messages: Sequence[ChatMessage]) -> ToolCall:
    """Build the selected retrieval call from the exact user question."""
    return ToolCall(
        call_id="document-search-route",
        name="search_documents",
        arguments={"query": messages[-1].content, "limit": 3},
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
            "Use this context to fill missing manufacturing tool arguments. "
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

EQUIPMENT_STATUS_TOOL = ToolDefinition(
    name="get_equipment_status",
    description="Read a recorded deterministic synthetic equipment state.",
    parameters={
        "type": "object",
        "properties": {
            "equipment_id": {"type": "string"},
            "at": {"type": "string", "format": "date-time"},
        },
        "required": [],
        "additionalProperties": False,
    },
)

DEFECT_DISTRIBUTION_TOOL = ToolDefinition(
    name="get_defect_distribution",
    description="Read deterministic synthetic defect distribution evidence.",
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

DOCUMENT_SEARCH_TOOL = ToolDefinition(
    name="search_documents",
    description="Retrieve evidence from fictional local equipment documents.",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 3},
        },
        "required": ["query"],
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


def resolve_equipment_status_request(
    state: GraphState,
    call: ToolCall,
) -> tuple[EquipmentStatusRequest | None, str | None]:
    """Merge explicit status arguments with saved synthetic workspace context."""
    arguments = dict(call.arguments)
    context = state["workspace_context"]
    equipment_id = arguments.get("equipment_id") or context.device
    observed_at = arguments.get("at")
    if not observed_at and context.time_range in _DEMO_PRESET_HOURS:
        observed_at = _DEMO_SHIFT_END.isoformat().replace("+00:00", "Z")
    if not equipment_id:
        return None, (
            "Please specify an equipment ID or select a device in the analysis "
            "context."
        )
    if not observed_at:
        return None, (
            "Please specify a UTC observation time, or select a supported time "
            "range in the analysis context."
        )
    try:
        return EquipmentStatusRequest.model_validate(
            {"equipment_id": equipment_id, "at": observed_at}
        ), None
    except ValidationError:
        return None, "Please provide a valid UTC equipment-status time."


def resolve_defect_distribution_request(
    state: GraphState,
    call: ToolCall,
) -> tuple[DefectDistributionRequest | None, str | None]:
    """Resolve defect-distribution arguments through production context rules."""
    request, clarification = resolve_production_request(state, call)
    if request is None:
        return None, clarification
    return DefectDistributionRequest.model_validate(request.model_dump()), None


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


def execute_equipment_status_tool(
    state: GraphState,
    result: CompletionResult,
) -> GraphState:
    """Execute one parsed equipment-status Tool Call into Evidence State."""
    if len(result.tool_calls) != 1:
        return {
            **state,
            "evidence": EvidenceState(
                tool_error=ToolError(code="UNSUPPORTED_TOOL_CALL_PATTERN")
            ),
        }
    call = result.tool_calls[0]
    if call.name != EQUIPMENT_STATUS_TOOL.name:
        return {
            **state,
            "evidence": EvidenceState(
                tool_error=ToolError(code="UNSUPPORTED_TOOL_CALL_PATTERN")
            ),
        }
    request, clarification = resolve_equipment_status_request(state, call)
    if clarification is not None:
        return {**state, "assistant_content": clarification}
    if request is None:
        return {
            **state,
            "evidence": EvidenceState(tool_error=ToolError(code="INVALID_INPUT")),
        }
    try:
        equipment_status = get_equipment_status(request)
    except EquipmentStatusToolError:
        return {
            **state,
            "evidence": EvidenceState(
                tool_error=ToolError(code="UNKNOWN_EQUIPMENT")
            ),
        }
    return {
        **state,
        "evidence": EvidenceState(equipment_status=equipment_status),
        "tool_call": call,
        "execution_events": [
            *state["execution_events"],
            ExecutionEvent(
                kind="node_completed",
                payload={"node": "execute_equipment_status_tool"},
            ),
        ],
    }


def execute_defect_distribution_tool(
    state: GraphState,
    result: CompletionResult,
) -> GraphState:
    """Execute one parsed defect-distribution Tool Call into Evidence State."""
    if len(result.tool_calls) != 1:
        return {
            **state,
            "evidence": EvidenceState(
                tool_error=ToolError(code="UNSUPPORTED_TOOL_CALL_PATTERN")
            ),
        }
    call = result.tool_calls[0]
    if call.name != DEFECT_DISTRIBUTION_TOOL.name:
        return {
            **state,
            "evidence": EvidenceState(
                tool_error=ToolError(code="UNSUPPORTED_TOOL_CALL_PATTERN")
            ),
        }
    request, clarification = resolve_defect_distribution_request(state, call)
    if clarification is not None:
        return {**state, "assistant_content": clarification}
    if request is None:
        return {
            **state,
            "evidence": EvidenceState(tool_error=ToolError(code="INVALID_INPUT")),
        }
    try:
        distribution = get_defect_distribution(request)
    except DefectDistributionToolError as error:
        code = (
            "UNKNOWN_EQUIPMENT"
            if "Equipment" in str(error)
            else "UNKNOWN_PRODUCTION_LOT"
        )
        return {**state, "evidence": EvidenceState(tool_error=ToolError(code=code))}
    return {
        **state,
        "evidence": EvidenceState(defect_distribution=distribution),
        "tool_call": call,
        "execution_events": [
            *state["execution_events"],
            ExecutionEvent(
                kind="node_completed",
                payload={"node": "execute_defect_distribution_tool"},
            ),
        ],
    }


def execute_document_search_tool(
    state: GraphState,
    result: CompletionResult,
    *,
    document_corpus_service: DocumentCorpusService | None = None,
) -> GraphState:
    """Execute one parsed document-search Tool Call into Evidence State."""
    if len(result.tool_calls) != 1:
        return {
            **state,
            "evidence": EvidenceState(
                tool_error=ToolError(code="UNSUPPORTED_TOOL_CALL_PATTERN")
            ),
        }
    call = result.tool_calls[0]
    if call.name != DOCUMENT_SEARCH_TOOL.name:
        return {
            **state,
            "evidence": EvidenceState(
                tool_error=ToolError(code="UNSUPPORTED_TOOL_CALL_PATTERN")
            ),
        }
    try:
        request = DocumentSearchRequest.model_validate(call.arguments)
    except ValidationError:
        return {
            **state,
            "evidence": EvidenceState(tool_error=ToolError(code="INVALID_INPUT")),
        }
    document_search = search_documents(
        request,
        service=document_corpus_service,
    )
    return {
        **state,
        "evidence": EvidenceState(document_search=document_search),
        "tool_call": call,
        "execution_events": [
            *state["execution_events"],
            ExecutionEvent(
                kind="node_completed",
                payload={"node": "execute_document_search_tool"},
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


def answer_with_equipment_status_evidence(
    state: GraphState,
    *,
    complete_with_tools: CompleteWithTools,
    tool_call: ToolCall,
) -> GraphState:
    """Ask the model for a final answer using recorded status evidence."""
    evidence = state["evidence"]
    if evidence is None:
        raise GraphExecutionError(code="empty_response")
    if evidence.tool_error is not None:
        return {
            **state,
            "assistant_content": evidence.tool_error.message,
            "execution_events": [
                *state["execution_events"],
                ExecutionEvent(kind="node_completed", payload={"node": "tool_error"}),
            ],
        }
    if evidence.equipment_status is None:
        raise GraphExecutionError(code="empty_response")
    result = complete_with_tools(
        state["messages"],
        (EQUIPMENT_STATUS_TOOL,),
        tool_call=ToolResult(
            call_id=tool_call.call_id,
            name=tool_call.name,
            arguments=tool_call.arguments,
            content=evidence.equipment_status.model_dump_json(),
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


def answer_with_defect_distribution_evidence(
    state: GraphState,
    *,
    complete_with_tools: CompleteWithTools,
    tool_call: ToolCall,
) -> GraphState:
    """Ask the model for a final answer using defect distribution evidence."""
    evidence = state["evidence"]
    if evidence is None:
        raise GraphExecutionError(code="empty_response")
    if evidence.tool_error is not None:
        return {
            **state,
            "assistant_content": evidence.tool_error.message,
            "execution_events": [
                *state["execution_events"],
                ExecutionEvent(kind="node_completed", payload={"node": "tool_error"}),
            ],
        }
    if evidence.defect_distribution is None:
        raise GraphExecutionError(code="empty_response")
    result = complete_with_tools(
        state["messages"],
        (DEFECT_DISTRIBUTION_TOOL,),
        tool_call=ToolResult(
            call_id=tool_call.call_id,
            name=tool_call.name,
            arguments=tool_call.arguments,
            content=evidence.defect_distribution.model_dump_json(),
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


def answer_with_document_search_evidence(
    state: GraphState,
    *,
    complete_with_tools: CompleteWithTools,
    tool_call: ToolCall,
) -> GraphState:
    """Ask the model for a final answer using retrieved fictional sources."""
    evidence = state["evidence"]
    if evidence is None:
        raise GraphExecutionError(code="empty_response")
    if evidence.tool_error is not None:
        return {**state, "assistant_content": evidence.tool_error.message}
    if evidence.document_search is None:
        raise GraphExecutionError(code="empty_response")
    result = complete_with_tools(
        state["messages"],
        (DOCUMENT_SEARCH_TOOL,),
        tool_call=ToolResult(
            call_id=tool_call.call_id,
            name=tool_call.name,
            arguments=tool_call.arguments,
            content=evidence.document_search.model_dump_json(),
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
    document_corpus_service: DocumentCorpusService | None = None,
    route_exchange: RouteExchange | None = None,
) -> GraphState:
    if route_exchange is not None:
        return _call_routed_exchange(
            state,
            outcome=route_exchange(state),
            complete=complete,
            complete_with_tools=complete_with_tools,
            document_corpus_service=document_corpus_service,
        )
    if complete_with_tools is not None and _is_document_question(state["messages"]):
        call = build_document_search_call(state["messages"])
        tool_state = execute_document_search_tool(
            state,
            CompletionResult(content=None, tool_calls=(call,)),
            document_corpus_service=document_corpus_service,
        )
        return answer_with_document_search_evidence(
            tool_state,
            complete_with_tools=complete_with_tools,
            tool_call=call,
        )
    if complete_with_tools is not None and _is_equipment_status_question(
        state["messages"]
    ):
        first_result = complete_with_tools(
            _messages_with_production_context(state),
            (EQUIPMENT_STATUS_TOOL,),
        )
        if first_result.tool_calls:
            tool_state = execute_equipment_status_tool(state, first_result)
            if tool_state["assistant_content"]:
                return tool_state
            return answer_with_equipment_status_evidence(
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
    if complete_with_tools is not None and _is_defect_distribution_question(
        state["messages"]
    ):
        first_result = complete_with_tools(
            _messages_with_production_context(state),
            (DEFECT_DISTRIBUTION_TOOL,),
        )
        if first_result.tool_calls:
            tool_state = execute_defect_distribution_tool(state, first_result)
            if tool_state["assistant_content"]:
                return tool_state
            return answer_with_defect_distribution_evidence(
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


def _call_routed_exchange(
    state: GraphState,
    *,
    outcome: RoutingOutcome,
    complete: Complete,
    complete_with_tools: CompleteWithTools | None,
    document_corpus_service: DocumentCorpusService | None,
) -> GraphState:
    decision = outcome.decision
    if outcome.response_text is not None:
        return {**state, "assistant_content": outcome.response_text}
    if decision.intent is RouteIntent.GENERAL:
        return {**state, "assistant_content": complete(state["messages"])}
    if complete_with_tools is None:
        raise GraphExecutionError(code="empty_response")

    call = _tool_call_for_route(state, outcome)
    if decision.intent is RouteIntent.PRODUCTION_SUMMARY:
        tool_state = execute_production_tool(
            state, CompletionResult(content=None, tool_calls=(call,))
        )
        answer = answer_with_production_evidence
    elif decision.intent is RouteIntent.EQUIPMENT_STATUS:
        tool_state = execute_equipment_status_tool(
            state, CompletionResult(content=None, tool_calls=(call,))
        )
        answer = answer_with_equipment_status_evidence
    elif decision.intent is RouteIntent.DEFECT_DISTRIBUTION:
        tool_state = execute_defect_distribution_tool(
            state, CompletionResult(content=None, tool_calls=(call,))
        )
        answer = answer_with_defect_distribution_evidence
    elif decision.intent is RouteIntent.DOCUMENT_SEARCH:
        tool_state = execute_document_search_tool(
            state,
            CompletionResult(content=None, tool_calls=(call,)),
            document_corpus_service=document_corpus_service,
        )
        answer = answer_with_document_search_evidence
    else:
        raise GraphExecutionError(code="empty_response")

    evidence = tool_state["evidence"] or EvidenceState()
    approval = validate_evidence(decision, evidence)
    if not approval.sufficient:
        return {**tool_state, "assistant_content": approval.response_text or ""}
    answered = answer(
        tool_state,
        complete_with_tools=complete_with_tools,
        tool_call=call,
    )
    post_check = validate_answer(
        decision, evidence, answered["assistant_content"]
    )
    if not post_check.sufficient:
        return {**answered, "assistant_content": post_check.response_text or ""}
    return answered


def _tool_call_for_route(
    state: GraphState, outcome: RoutingOutcome
) -> ToolCall:
    decision = outcome.decision
    context = decision.resolved_context
    arguments: dict[str, object] = {}
    if context.equipment_id is not None:
        arguments["equipment_id"] = context.equipment_id
    if context.lot_id is not None:
        arguments["lot_id"] = context.lot_id
    if context.start is not None:
        arguments["start"] = context.start.isoformat()
        arguments["end"] = context.end.isoformat()
    elif context.time_preset is not None:
        end = _DEMO_SHIFT_END
        if context.time_preset is TimePreset.TODAY:
            start = end.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            hours = {
                TimePreset.LAST_1_HOUR: 1,
                TimePreset.LAST_4_HOURS: 4,
                TimePreset.LAST_8_HOURS: 8,
                TimePreset.LAST_24_HOURS: 24,
                TimePreset.LAST_7_DAYS: 24 * 7,
            }[context.time_preset]
            start = end - timedelta(hours=hours)
        arguments["start"] = start.isoformat()
        arguments["end"] = end.isoformat()
    if decision.intent is RouteIntent.EQUIPMENT_STATUS:
        arguments.pop("start", None)
        end = arguments.pop("end", None)
        if end is not None:
            arguments["at"] = end
    if decision.intent is RouteIntent.DOCUMENT_SEARCH:
        arguments = {
            "query": context.document_query or state["messages"][-1].content,
            "limit": 3,
        }
    name = {
        RouteIntent.PRODUCTION_SUMMARY: PRODUCTION_TOOL.name,
        RouteIntent.EQUIPMENT_STATUS: EQUIPMENT_STATUS_TOOL.name,
        RouteIntent.DEFECT_DISTRIBUTION: DEFECT_DISTRIBUTION_TOOL.name,
        RouteIntent.DOCUMENT_SEARCH: DOCUMENT_SEARCH_TOOL.name,
    }[decision.intent]
    return ToolCall(call_id="application-route", name=name, arguments=arguments)


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
    document_corpus_service: DocumentCorpusService | None = None,
    route_exchange: RouteExchange | None = None,
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
            document_corpus_service=document_corpus_service,
            route_exchange=route_exchange,
        ),
    )
    graph.add_node("persist_response", lambda state: persist_response(session, state))
    graph.add_edge(START, "load_context")
    graph.add_edge("load_context", "call_llm")
    graph.add_edge("call_llm", "persist_response")
    graph.add_edge("persist_response", END)
    return graph.compile()
