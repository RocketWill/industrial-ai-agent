from industrial_agent.graph.runner import run_sync_exchange
from industrial_agent.graph.state import EvidenceState
from industrial_agent.graph.workflow import execute_production_tool, load_context
from industrial_agent.llm.types import ChatMessage, CompletionResult, ToolCall
from industrial_agent.schemas.context import WorkspaceContextUpdate
from industrial_agent.services.conversation import (
    create_conversation,
    update_workspace_context,
)
from industrial_agent.services.message import list_messages


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
