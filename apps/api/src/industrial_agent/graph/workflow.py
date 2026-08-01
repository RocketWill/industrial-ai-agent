from collections.abc import Callable, Sequence
from uuid import UUID

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from industrial_agent.graph.errors import GraphExecutionError
from industrial_agent.graph.state import ExecutionEvent, GraphState
from industrial_agent.llm.types import ChatMessage
from industrial_agent.services import conversation as conversation_service
from industrial_agent.services import message as message_service

Complete = Callable[[Sequence[ChatMessage]], str]


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
