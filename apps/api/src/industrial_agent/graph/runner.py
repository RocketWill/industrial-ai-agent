import json
from collections.abc import Callable, Iterator, Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from industrial_agent.domain.routing import EvidenceKind, FallbackState, RouteIntent
from industrial_agent.graph.combined import (
    CombinedAnswerStatus,
    CombinedExchangeEvidence,
    combined_evidence_payload,
    stream_combined_evidence,
    synthesize_combined_answer,
)
from industrial_agent.graph.errors import GraphExecutionError
from industrial_agent.graph.state import EvidenceState, ExecutionEvent, GraphState
from industrial_agent.graph.workflow import (
    COMBINED_EVIDENCE_TOOL,
    DEFECT_DISTRIBUTION_TOOL,
    DOCUMENT_SEARCH_TOOL,
    EQUIPMENT_STATUS_TOOL,
    PRODUCTION_TOOL,
    Complete,
    CompleteWithTools,
    _is_defect_distribution_question,
    _is_document_question,
    _is_equipment_status_question,
    _messages_with_production_context,
    _tool_call_for_route,
    build_document_search_call,
    build_workflow,
    execute_defect_distribution_tool,
    execute_document_search_tool,
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
from industrial_agent.schemas.message import SuggestedAction
from industrial_agent.services import message as message_service
from industrial_agent.services.documents import DocumentCorpusService
from industrial_agent.services.evidence import (
    validate_answer,
    validate_combined_answer,
    validate_evidence,
)
from industrial_agent.services.message import MessageExchange
from industrial_agent.services.routing import RoutingOutcome

RouteExchange = Callable[[GraphState], RoutingOutcome]


def run_sync_exchange(
    session: Session,
    *,
    conversation_id: UUID,
    content: str,
    complete: Complete,
    complete_with_tools: CompleteWithTools | None = None,
    document_corpus_service: DocumentCorpusService | None = None,
    route_exchange: RouteExchange | None = None,
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
        document_corpus_service=document_corpus_service,
        route_exchange=route_exchange,
    ).invoke(initial_state)
    messages = message_service.list_messages(session, conversation_id)
    return MessageExchange(
        user_message=messages[-2],
        assistant_message=messages[-1],
        evidence=final_state.get("evidence"),
        combined_evidence=final_state.get("combined_evidence"),
    )


Stream = Callable[[Sequence[ChatMessage]], Iterator[str]]
ToolComplete = Callable[..., CompletionResult]
ToolStream = Callable[[Sequence[ChatMessage], ToolResult], Iterator[str]]
RoutedToolStream = Callable[[Sequence[ChatMessage], ToolResult, object], Iterator[str]]


def run_stream_routed_exchange(
    session: Session,
    *,
    conversation_id: UUID,
    content: str,
    route_exchange: RouteExchange,
    stream: Stream,
    stream_with_tool_result: RoutedToolStream,
    document_corpus_service: DocumentCorpusService | None = None,
    is_cancelled: Callable[[], bool] = lambda: False,
) -> Iterator[ExecutionEvent]:
    """Run SSE through the same authoritative route and evidence policy."""
    state = load_context(session, conversation_id=conversation_id, content=content)
    user_message = message_service.list_messages(session, conversation_id)[-1]
    yield ExecutionEvent(kind="user_message", payload=user_message)
    yield ExecutionEvent(
        kind="routing_started", payload={"label": "Understanding request"}
    )
    outcome = route_exchange(state)
    decision = outcome.decision
    if decision.retry_count:
        yield ExecutionEvent(
            kind="routing_retry",
            payload={
                "retry_count": decision.retry_count,
                "label": "Retrying request classification",
            },
        )
    if decision.fallback_state is FallbackState.USED:
        yield ExecutionEvent(
            kind="routing_fallback_used",
            payload={
                "reason_code": decision.reason_code.value,
                "label": "Using safe fallback",
            },
        )
    yield ExecutionEvent(
        kind="routing_decided",
        payload={
            "route": decision.intent.value,
            "reason_code": decision.reason_code.value,
            "retry_count": decision.retry_count,
            "label": _routing_label(decision.intent),
        },
    )
    if outcome.response_text is not None:
        if decision.intent is RouteIntent.CLARIFICATION:
            yield ExecutionEvent(
                kind="clarification_required",
                payload={
                    "reason_code": decision.reason_code.value,
                    "label": "Clarification required",
                },
            )
        yield from _persist_stream_text(
            session,
            state,
            outcome.response_text,
            suggested_actions=outcome.suggested_actions,
        )
        return
    if decision.intent is RouteIntent.GENERAL:
        parts = list(stream(state["messages"]))
        content_text = "".join(parts)
        for part in parts:
            if part:
                yield ExecutionEvent(kind="token", payload={"text": part})
        yield from _persist_stream_text(session, state, content_text, emit_token=False)
        return
    if decision.intent is RouteIntent.COMBINED:
        combined = None
        progress = stream_combined_evidence(
            decision=decision,
            original_query=state["messages"][-1].content,
            document_corpus_service=document_corpus_service,
            is_cancelled=is_cancelled,
        )
        manufacturing_names = {
            EvidenceKind.PRODUCTION: PRODUCTION_TOOL.name,
            EvidenceKind.EQUIPMENT_STATUS: EQUIPMENT_STATUS_TOOL.name,
            EvidenceKind.DEFECT_DISTRIBUTION: DEFECT_DISTRIBUTION_TOOL.name,
        }
        for step in progress:
            if step.phase == "started" and step.path == "manufacturing":
                yield ExecutionEvent(
                    kind="tool_call_started",
                    payload={
                        "path": "manufacturing",
                        "name": manufacturing_names[step.manufacturing_kind],
                        "arguments": decision.resolved_context.model_dump(mode="json"),
                    },
                )
            elif step.phase == "started" and step.path == "documents":
                yield ExecutionEvent(
                    kind="tool_call_started",
                    payload={
                        "path": "documents",
                        "name": DOCUMENT_SEARCH_TOOL.name,
                        "arguments": {"query": step.document_query, "limit": 3},
                    },
                )
            elif (
                step.phase == "completed"
                and step.path is not None
                and step.outcome is not None
                and step.manufacturing_kind is not None
            ):
                path_payload = (
                    combined_evidence_payload(step.completed)[step.path]
                    if step.completed is not None
                    else {
                        "status": step.outcome.status.value,
                        "result": step.outcome.result.model_dump(mode="json")
                        if step.outcome.result is not None
                        else None,
                        "error_code": step.outcome.error_code,
                    }
                )
                yield ExecutionEvent(
                    kind="combined_tool_result",
                    payload={
                        "path": step.path,
                        "manufacturing_kind": step.manufacturing_kind.value,
                        **path_payload,
                    },
                )
            elif step.completed is not None:
                combined = step.completed
        if combined is None:
            raise RuntimeError("combined execution ended without a result")
        parts: list[str] = []

        def generate(payload: dict[str, object]) -> str:
            tool_result = ToolResult(
                call_id="combined-evidence-route",
                name=COMBINED_EVIDENCE_TOOL.name,
                arguments={},
                content=json.dumps(payload, separators=(",", ":")),
            )
            parts.extend(
                stream_with_tool_result(
                    state["messages"], tool_result, COMBINED_EVIDENCE_TOOL
                )
            )
            return "".join(parts)

        answer = synthesize_combined_answer(
            combined, generate=generate, validate=validate_combined_answer
        )
        if answer.status is CombinedAnswerStatus.SUCCEEDED:
            for part in parts:
                if part:
                    yield ExecutionEvent(kind="token", payload={"text": part})
        combined_state = {
            **state,
            "combined_evidence": CombinedExchangeEvidence(
                evidence=combined, answer_status=answer.status
            ),
        }
        yield ExecutionEvent(
            kind="combined_evidence_completed",
            payload={"answer_status": answer.status.value},
        )
        yield from _persist_stream_text(
            session,
            combined_state,
            answer.text,
            emit_token=answer.status is CombinedAnswerStatus.FALLBACK,
        )
        return

    call = _tool_call_for_route(state, outcome)
    tool, tool_state = _execute_routed_tool(
        state,
        decision.intent,
        call,
        document_corpus_service=document_corpus_service,
    )
    yield ExecutionEvent(
        kind="tool_call_started",
        payload={"name": call.name, "arguments": call.arguments},
    )
    evidence = tool_state["evidence"] or EvidenceState()
    yield ExecutionEvent(kind="tool_result", payload=evidence)
    approval = validate_evidence(decision, evidence)
    if not approval.sufficient:
        yield from _persist_stream_text(
            session, tool_state, approval.response_text or ""
        )
        return
    result_payload = {
        RouteIntent.PRODUCTION_SUMMARY: evidence.production_summary,
        RouteIntent.EQUIPMENT_STATUS: evidence.equipment_status,
        RouteIntent.DEFECT_DISTRIBUTION: evidence.defect_distribution,
        RouteIntent.DOCUMENT_SEARCH: evidence.document_search,
    }[decision.intent]
    if result_payload is None:
        raise GraphExecutionError(code="empty_response")
    tool_result = ToolResult(
        call_id=call.call_id,
        name=call.name,
        arguments=call.arguments,
        content=result_payload.model_dump_json(),
    )
    parts = list(stream_with_tool_result(tool_state["messages"], tool_result, tool))
    answer = "".join(parts)
    post_check = validate_answer(decision, evidence, answer)
    if not post_check.sufficient:
        yield from _persist_stream_text(
            session, tool_state, post_check.response_text or ""
        )
        return
    for part in parts:
        if part:
            yield ExecutionEvent(kind="token", payload={"text": part})
    yield from _persist_stream_text(session, tool_state, answer, emit_token=False)


def _execute_routed_tool(
    state: GraphState,
    intent: RouteIntent,
    call,
    *,
    document_corpus_service: DocumentCorpusService | None,
):
    result = CompletionResult(content=None, tool_calls=(call,))
    if intent is RouteIntent.PRODUCTION_SUMMARY:
        return PRODUCTION_TOOL, execute_production_tool(state, result)
    if intent is RouteIntent.EQUIPMENT_STATUS:
        return EQUIPMENT_STATUS_TOOL, execute_equipment_status_tool(state, result)
    if intent is RouteIntent.DEFECT_DISTRIBUTION:
        return DEFECT_DISTRIBUTION_TOOL, execute_defect_distribution_tool(state, result)
    return DOCUMENT_SEARCH_TOOL, execute_document_search_tool(
        state, result, document_corpus_service=document_corpus_service
    )


def _persist_stream_text(
    session: Session,
    state: GraphState,
    content: str,
    *,
    emit_token: bool = True,
    suggested_actions: tuple[SuggestedAction, ...] = (),
) -> Iterator[ExecutionEvent]:
    persist_response(
        session,
        {
            **state,
            "assistant_content": content,
            "suggested_actions": suggested_actions,
        },
    )
    if emit_token:
        yield ExecutionEvent(kind="token", payload={"text": content})
    assistant_message = message_service.list_messages(
        session, state["conversation_id"]
    )[-1]
    yield ExecutionEvent(kind="assistant_message", payload=assistant_message)


def _routing_label(intent: RouteIntent) -> str:
    return {
        RouteIntent.GENERAL: "Generating response",
        RouteIntent.PRODUCTION_SUMMARY: "Selecting production summary",
        RouteIntent.EQUIPMENT_STATUS: "Selecting equipment status",
        RouteIntent.DEFECT_DISTRIBUTION: "Selecting defect distribution",
        RouteIntent.DOCUMENT_SEARCH: "Selecting document search",
        RouteIntent.COMBINED: "Selecting combined evidence",
        RouteIntent.CLARIFICATION: "Clarification required",
        RouteIntent.UNSUPPORTED: "Unsupported request",
    }[intent]


def run_stream_tool_exchange(
    session: Session,
    *,
    conversation_id: UUID,
    content: str,
    complete_with_tools: ToolComplete,
    stream_with_tool_result: ToolStream,
    document_corpus_service: DocumentCorpusService | None = None,
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
    is_document_search = _is_document_question(state["messages"])
    selected_tool = (
        DOCUMENT_SEARCH_TOOL
        if is_document_search
        else EQUIPMENT_STATUS_TOOL
        if is_equipment_status
        else DEFECT_DISTRIBUTION_TOOL
        if is_defect_distribution
        else PRODUCTION_TOOL
    )
    first = (
        CompletionResult(
            content=None,
            tool_calls=(build_document_search_call(state["messages"]),),
        )
        if is_document_search
        else complete_with_tools(
            _messages_with_production_context(state), (selected_tool,)
        )
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
    if is_document_search:
        tool_state = execute_document_search_tool(
            state,
            first,
            document_corpus_service=document_corpus_service,
        )
    elif is_equipment_status:
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
        evidence.document_search
        if is_document_search
        else evidence.equipment_status
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
