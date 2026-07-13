from uuid import uuid4

import pytest

from industrial_agent.graph.errors import GraphExecutionError
from industrial_agent.graph.state import (
    EvidenceState,
    ExecutionEvent,
    GraphState,
    ToolError,
)
from industrial_agent.llm.types import ChatMessage
from industrial_agent.schemas.context import WorkspaceContextRead


def test_graph_state_keeps_typed_conversation_inputs() -> None:
    state = GraphState(
        conversation_id=uuid4(),
        messages=[ChatMessage(role="user", content="Check history")],
        workspace_context=WorkspaceContextRead(
            environment="synthetic",
            device=None,
            lot=None,
            time_range=None,
            data_source="synthetic_demo",
        ),
        assistant_content="",
        execution_events=[],
        evidence=None,
    )

    assert state["assistant_content"] == ""
    assert state["execution_events"] == []
    assert state["messages"][0].content == "Check history"


def test_evidence_state_contains_a_safe_tool_error() -> None:
    evidence = EvidenceState(
        tool_error=ToolError(
            code="UNKNOWN_EQUIPMENT",
        )
    )

    assert evidence.production_summary is None
    assert evidence.tool_error is not None
    assert evidence.tool_error.code == "UNKNOWN_EQUIPMENT"
    assert "path" not in evidence.tool_error.message


def test_execution_event_has_serializable_payload() -> None:
    event = ExecutionEvent(kind="node_started", payload={"node": "load_context"})

    assert event.kind == "node_started"
    assert event.payload == {"node": "load_context"}


def test_graph_execution_error_exposes_safe_code_without_provider_details() -> None:
    error = GraphExecutionError(code="assistant_unavailable")

    assert error.code == "assistant_unavailable"
    assert str(error) == "assistant_unavailable"


def test_graph_execution_error_rejects_provider_details() -> None:
    with pytest.raises(ValueError, match="safe"):
        GraphExecutionError(code="provider timeout: secret-token")
