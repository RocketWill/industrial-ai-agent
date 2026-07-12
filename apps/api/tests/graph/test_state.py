from uuid import uuid4

import pytest

from industrial_agent.graph.errors import GraphExecutionError
from industrial_agent.graph.state import ExecutionEvent, GraphState
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
    )

    assert state["assistant_content"] == ""
    assert state["execution_events"] == []
    assert state["messages"][0].content == "Check history"


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
