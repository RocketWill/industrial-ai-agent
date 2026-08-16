from industrial_agent.domain.routing import (
    DecisionSource,
    ExtractedContext,
    ReasonCode,
    RouteDecision,
    RouteIntent,
    SafeAction,
)
from industrial_agent.graph.runner import run_sync_exchange
from industrial_agent.graph.state import EvidenceState
from industrial_agent.graph.workflow import (
    answer_with_production_evidence,
    execute_equipment_status_tool,
    execute_production_tool,
    load_context,
    resolve_equipment_status_request,
    resolve_production_request,
)
from industrial_agent.llm.types import (
    ChatMessage,
    CompletionResult,
    ToolCall,
)
from industrial_agent.schemas.context import WorkspaceContextUpdate
from industrial_agent.services.conversation import (
    create_conversation,
    update_workspace_context,
)
from industrial_agent.services.documents import (
    DocumentCorpusService,
    LocalDocumentStore,
)
from industrial_agent.services.message import list_messages
from industrial_agent.services.routing import RoutingOutcome


def test_load_context_reads_history_and_workspace_context(database_session) -> None:
    conversation = create_conversation(database_session, title="Graph")
    update_workspace_context(
        database_session,
        conversation.id,
        update=WorkspaceContextUpdate(
            device="AOI-WAFER-01", time_range="Last 4 hours"
        ),
    )

    state = load_context(
        database_session,
        conversation_id=conversation.id,
        content="Check history",
    )

    assert state["conversation_id"] == conversation.id
    assert [message.content for message in state["messages"]] == [
        "Check history"
    ]
    assert state["workspace_context"].device == "AOI-WAFER-01"
    assert state["workspace_context"].time_range == "Last 4 hours"
    assert state["assistant_content"] == ""


def test_sync_runner_includes_new_question_and_persists_one_exchange(
    database_session,
) -> None:
    conversation = create_conversation(database_session, title="Graph")
    received: list[list[ChatMessage]] = []

    def complete(messages: list[ChatMessage]) -> str:
        received.append(messages)
        return "The assistant response."

    exchange = run_sync_exchange(
        database_session,
        conversation_id=conversation.id,
        content="Check history",
        complete=complete,
    )

    assert exchange.user_message.content == "Check history"
    assert exchange.assistant_message.content == "The assistant response."
    assert [message.content for message in received[0]] == ["Check history"]
    persisted = list_messages(database_session, conversation.id)
    assert [message.role for message in persisted] == ["user", "assistant"]


def test_sync_runner_persists_deterministic_routing_clarification(
    database_session,
) -> None:
    conversation = create_conversation(database_session, title="Routing")

    def route(_state):
        return RoutingOutcome(
            decision=RouteDecision(
                intent=RouteIntent.CLARIFICATION,
                resolved_context=ExtractedContext(),
                decision_source=DecisionSource.CLASSIFIER,
                reason_code=ReasonCode.CLARIFICATION_REQUIRED,
                safe_action=SafeAction.REQUEST_CLARIFICATION,
            ),
            response_text="Which fictional equipment should I use?",
        )

    exchange = run_sync_exchange(
        database_session,
        conversation_id=conversation.id,
        content="Show yield",
        complete=lambda _messages: (_ for _ in ()).throw(
            AssertionError("clarification must skip final model")
        ),
        route_exchange=route,
    )

    assert exchange.assistant_message.content == (
        "Which fictional equipment should I use?"
    )


def test_sync_runner_uses_authoritative_general_route(database_session) -> None:
    conversation = create_conversation(database_session, title="Routing")

    def route(_state):
        return RoutingOutcome(
            RouteDecision(
                intent=RouteIntent.GENERAL,
                decision_source=DecisionSource.DETERMINISTIC_GATE,
                reason_code=ReasonCode.GENERAL_REQUEST,
                safe_action=SafeAction.ANSWER_GENERAL,
            )
        )

    exchange = run_sync_exchange(
        database_session,
        conversation_id=conversation.id,
        content="Hello",
        complete=lambda _messages: "Hello from the model.",
        route_exchange=route,
    )

    assert exchange.assistant_message.content == "Hello from the model."


def test_sync_runner_sends_previous_history_in_order(database_session) -> None:
    conversation = create_conversation(database_session, title="Graph")
    received: list[list[ChatMessage]] = []

    def complete(messages: list[ChatMessage]) -> str:
        received.append(messages)
        return "Second response."

    run_sync_exchange(
        database_session,
        conversation_id=conversation.id,
        content="First question",
        complete=lambda _: "First response.",
    )
    run_sync_exchange(
        database_session,
        conversation_id=conversation.id,
        content="Second question",
        complete=complete,
    )

    assert [message.content for message in received[0]] == [
        "First question",
        "First response.",
        "Second question",
    ]


def test_execute_production_tool_puts_summary_in_evidence_state(
    database_session,
) -> None:
    conversation = create_conversation(database_session, title="Production")
    state = load_context(
        database_session,
        conversation_id=conversation.id,
        content="Show production yield",
    )

    result = execute_production_tool(
        state,
        CompletionResult(
            content=None,
            tool_calls=(
                ToolCall(
                    call_id="call-001",
                    name="get_production_summary",
                    arguments={
                        "equipment_id": "AOI-WAFER-01",
                        "lot_id": "LOT-DEMO-001",
                        "start": "2026-01-15T15:00:00Z",
                        "end": "2026-01-15T18:00:00Z",
                    },
                ),
            ),
        ),
    )

    assert isinstance(result["evidence"], EvidenceState)
    assert result["evidence"].production_summary is not None
    assert result["evidence"].production_summary.yield_rate == 257 / 300
    assert result["assistant_content"] == ""


def test_execute_equipment_status_tool_puts_recorded_state_in_evidence(
    database_session,
) -> None:
    conversation = create_conversation(database_session, title="Status")
    state = load_context(
        database_session,
        conversation_id=conversation.id,
        content="Is AOI-WAFER-01 down?",
    )

    result = execute_equipment_status_tool(
        state,
        CompletionResult(
            content=None,
            tool_calls=(
                ToolCall(
                    call_id="call-status",
                    name="get_equipment_status",
                    arguments={
                        "equipment_id": "AOI-WAFER-01",
                        "at": "2026-01-15T15:30:00Z",
                    },
                ),
            ),
        ),
    )

    assert result["evidence"].equipment_status is not None
    assert result["evidence"].equipment_status.status == "warning"
    assert result["assistant_content"] == ""


def test_resolve_production_request_fills_missing_values_from_context(
    database_session,
) -> None:
    conversation = create_conversation(database_session, title="Production")
    update_workspace_context(
        database_session,
        conversation.id,
        update=WorkspaceContextUpdate(
            device="AOI-WAFER-01", lot="LOT-DEMO-001", time_range="Last 4 hours"
        ),
    )
    state = load_context(
        database_session,
        conversation_id=conversation.id,
        content="Show production yield",
    )

    request, clarification = resolve_production_request(
        state,
        ToolCall(call_id="call-001", name="get_production_summary", arguments={}),
    )

    assert clarification is None
    assert request is not None
    assert request.equipment_id == "AOI-WAFER-01"
    assert request.lot_id == "LOT-DEMO-001"
    assert request.start.isoformat() == "2026-01-15T13:00:00+00:00"
    assert request.end.isoformat() == "2026-01-15T17:00:00+00:00"


def test_resolve_production_request_asks_for_missing_context(database_session) -> None:
    conversation = create_conversation(database_session, title="Production")
    state = load_context(
        database_session,
        conversation_id=conversation.id,
        content="Show production yield",
    )

    request, clarification = resolve_production_request(
        state,
        ToolCall(call_id="call-001", name="get_production_summary", arguments={}),
    )

    assert request is None
    assert clarification == (
        "Please specify an equipment ID or select a device in the analysis context."
    )


def test_resolve_equipment_status_request_uses_context_range_end(
    database_session,
) -> None:
    conversation = create_conversation(database_session, title="Status")
    update_workspace_context(
        database_session,
        conversation.id,
        update=WorkspaceContextUpdate(
            device="AOI-WAFER-01", time_range="Last 4 hours"
        ),
    )
    state = load_context(
        database_session,
        conversation_id=conversation.id,
        content="What is the equipment status?",
    )

    request, clarification = resolve_equipment_status_request(
        state,
        ToolCall(call_id="call-status", name="get_equipment_status", arguments={}),
    )

    assert clarification is None
    assert request is not None
    assert request.equipment_id == "AOI-WAFER-01"
    assert request.at.isoformat() == "2026-01-15T17:00:00+00:00"


def test_execute_production_tool_rejects_unknown_tool_without_execution(
    database_session,
) -> None:
    conversation = create_conversation(database_session, title="Production")
    state = load_context(
        database_session,
        conversation_id=conversation.id,
        content="Show production yield",
    )

    result = execute_production_tool(
        state,
        CompletionResult(
            content=None,
            tool_calls=(
                ToolCall(
                    call_id="call-001",
                    name="unknown_tool",
                    arguments={},
                ),
            ),
        ),
    )

    assert result["evidence"].tool_error.code == "UNSUPPORTED_TOOL_CALL_PATTERN"


def test_answer_with_evidence_persists_only_final_model_content(
    database_session,
) -> None:
    conversation = create_conversation(database_session, title="Production")
    state = load_context(
        database_session,
        conversation_id=conversation.id,
        content="Show production yield",
    )
    tool_call = ToolCall(
        call_id="call-001",
        name="get_production_summary",
        arguments={
            "equipment_id": "AOI-WAFER-01",
            "start": "2026-01-15T15:00:00Z",
            "end": "2026-01-15T18:00:00Z",
        },
    )
    state = execute_production_tool(
        state,
        CompletionResult(content=None, tool_calls=(tool_call,)),
    )
    received = []

    def complete_with_tools(messages, tools, *, tool_call):
        received.append((messages, tools, tool_call))
        return CompletionResult(content="Yield is 85.67%.")

    answered = answer_with_production_evidence(
        state,
        complete_with_tools=complete_with_tools,
        tool_call=tool_call,
    )

    assert answered["assistant_content"] == "Yield is 85.67%."
    assert len(received) == 1
    assert received[0][2].content


def test_sync_runner_executes_one_production_tool_then_persists_final_answer(
    database_session,
) -> None:
    conversation = create_conversation(database_session, title="Production")
    update_workspace_context(
        database_session,
        conversation.id,
        update=WorkspaceContextUpdate(
            device="AOI-WAFER-01", time_range="Last 4 hours"
        ),
    )
    calls = []
    first_messages = []

    def complete(messages):
        raise AssertionError("production question should use tools")

    def complete_with_tools(messages, tools, *, tool_call=None):
        calls.append(tool_call)
        if tool_call is None:
            first_messages.extend(messages)
            return CompletionResult(
                content=None,
                tool_calls=(
                    ToolCall(
                        call_id="call-001",
                        name="get_production_summary",
                        arguments={
                            "equipment_id": "AOI-WAFER-01",
                            "start": "2026-01-15T15:00:00Z",
                            "end": "2026-01-15T18:00:00Z",
                        },
                    ),
                ),
            )
        return CompletionResult(content="The synthetic Yield Rate is 85.67%.")

    exchange = run_sync_exchange(
        database_session,
        conversation_id=conversation.id,
        content="What is the production yield for AOI-WAFER-01?",
        complete=complete,
        complete_with_tools=complete_with_tools,
    )

    assert exchange.assistant_message.content == (
        "The synthetic Yield Rate is 85.67%."
    )
    assert exchange.evidence is not None
    assert exchange.evidence.production_summary is not None
    assert exchange.evidence.production_summary.inspected_wafers == 300
    assert calls[0] is None
    assert calls[1] is not None
    assert "Saved analysis context" in first_messages[-1].content
    assert "2026-01-15T13:00:00Z/2026-01-15T17:00:00Z" in first_messages[-1].content


def test_sync_runner_persists_production_evidence_snapshot_on_assistant_message(
    database_session,
) -> None:
    conversation = create_conversation(database_session, title="Production")

    def complete(_messages):
        raise AssertionError("production question should use tools")

    def complete_with_tools(messages, tools, *, tool_call=None):
        if tool_call is None:
            return CompletionResult(
                content=None,
                tool_calls=(
                    ToolCall(
                        call_id="call-001",
                        name="get_production_summary",
                        arguments={
                            "equipment_id": "AOI-WAFER-01",
                            "start": "2026-01-15T15:00:00Z",
                            "end": "2026-01-15T18:00:00Z",
                        },
                    ),
                ),
            )
        return CompletionResult(content="The synthetic Yield Rate is 85.67%.")

    run_sync_exchange(
        database_session,
        conversation_id=conversation.id,
        content="What is the production yield for AOI-WAFER-01?",
        complete=complete,
        complete_with_tools=complete_with_tools,
    )

    assistant_message = list_messages(database_session, conversation.id)[-1]
    assert assistant_message.evidence_snapshot is not None
    assert assistant_message.evidence_snapshot["kind"] == "production_summary"
    assert (
        assistant_message.evidence_snapshot["production_summary"]["inspected_wafers"]
        == 300
    )


def test_sync_runner_executes_equipment_status_tool_with_context(
    database_session,
) -> None:
    conversation = create_conversation(database_session, title="Status")
    update_workspace_context(
        database_session,
        conversation.id,
        update=WorkspaceContextUpdate(
            device="AOI-WAFER-01", time_range="Last 4 hours"
        ),
    )
    calls = []

    def complete(messages):
        raise AssertionError("equipment-status question should use tools")

    def complete_with_tools(messages, tools, *, tool_call=None):
        calls.append((tools, tool_call))
        if tool_call is None:
            return CompletionResult(
                content=None,
                tool_calls=(
                    ToolCall(
                        call_id="call-status",
                        name="get_equipment_status",
                        arguments={},
                    ),
                ),
            )
        assert tool_call.name == "get_equipment_status"
        assert '"status":"running"' in tool_call.content
        return CompletionResult(content="The recorded equipment status is running.")

    exchange = run_sync_exchange(
        database_session,
        conversation_id=conversation.id,
        content="Is AOI-WAFER-01 down?",
        complete=complete,
        complete_with_tools=complete_with_tools,
    )

    assert exchange.assistant_message.content == (
        "The recorded equipment status is running."
    )
    assert exchange.evidence is not None
    assert exchange.evidence.equipment_status is not None
    assert exchange.evidence.equipment_status.status == "running"
    assert calls[0][1] is None
    assert calls[1][1] is not None


def test_sync_runner_executes_defect_distribution_before_production_summary(
    database_session,
) -> None:
    conversation = create_conversation(database_session, title="Defects")
    update_workspace_context(
        database_session,
        conversation.id,
        update=WorkspaceContextUpdate(
            device="AOI-WAFER-01",
            lot="LOT-DEMO-001",
            time_range="Last 4 hours",
        ),
    )
    selected_tools = []

    def complete(messages):
        raise AssertionError("defect distribution should use its selected tool")

    def complete_with_tools(messages, tools, *, tool_call=None):
        selected_tools.append(tools[0].name)
        if tool_call is None:
            return CompletionResult(
                content=None,
                tool_calls=(
                    ToolCall(
                        call_id="call-defects",
                        name="get_defect_distribution",
                        arguments={},
                    ),
                ),
            )
        assert '"classified_defect_count":30' in tool_call.content
        return CompletionResult(content="Edge-chip is the top recorded defect.")

    exchange = run_sync_exchange(
        database_session,
        conversation_id=conversation.id,
        content="Show the defect distribution.",
        complete=complete,
        complete_with_tools=complete_with_tools,
    )

    assert selected_tools == ["get_defect_distribution", "get_defect_distribution"]
    assert exchange.evidence is not None
    assert exchange.evidence.defect_distribution is not None
    assert exchange.evidence.defect_distribution.items[0].category == "edge-chip"
    assert exchange.assistant_message.content == (
        "Edge-chip is the top recorded defect."
    )


def test_sync_runner_retrieves_document_sources_for_procedural_question(
    database_session,
) -> None:
    conversation = create_conversation(database_session, title="Alarm procedure")
    selected_tools = []

    def complete(messages):
        raise AssertionError("procedural question should use document retrieval")

    def complete_with_tools(messages, tools, *, tool_call=None):
        selected_tools.append(tools[0].name)
        assert tool_call is not None
        assert '"section":"OPTICAL-SIGNAL-LOW"' in tool_call.content
        return CompletionResult(content="Check the fictional optical lens cover.")

    exchange = run_sync_exchange(
        database_session,
        conversation_id=conversation.id,
        content="What should an operator check when OPTICAL-SIGNAL-LOW occurs?",
        complete=complete,
        complete_with_tools=complete_with_tools,
    )

    assert selected_tools == ["search_documents"]
    assert exchange.evidence is not None
    assert exchange.evidence.document_search is not None
    assert exchange.evidence.document_search.sources[0].section == (
        "OPTICAL-SIGNAL-LOW"
    )


def test_sync_runner_uses_the_injected_document_corpus_service(
    database_session,
    tmp_path,
) -> None:
    service = DocumentCorpusService(
        store=LocalDocumentStore(storage_root=tmp_path / "uploads")
    )
    service.upload_document(
        filename="Local Upload Procedure.md",
        content=(
            b"# Local Upload Procedure\n\n"
            b"## Marker\n\n"
            b"Inspect the local-upload-marker before restarting.\n"
        ),
    )
    conversation = create_conversation(database_session, title="Local upload")

    def complete(messages):
        raise AssertionError("document retrieval should use the selected tool")

    def complete_with_tools(messages, tools, *, tool_call=None):
        assert tool_call is not None
        assert '"source":"local_upload"' in tool_call.content
        return CompletionResult(content="Use the local upload procedure.")

    exchange = run_sync_exchange(
        database_session,
        conversation_id=conversation.id,
        content="What is the local-upload-marker procedure?",
        complete=complete,
        complete_with_tools=complete_with_tools,
        document_corpus_service=service,
    )

    assert exchange.evidence is not None
    assert exchange.evidence.document_search is not None
    assert exchange.evidence.document_search.sources[0].source == "local_upload"
