from dataclasses import dataclass
from typing import Any, Literal, TypedDict
from uuid import UUID

from industrial_agent.llm.types import ChatMessage
from industrial_agent.schemas.context import WorkspaceContextRead

ExecutionEventKind = Literal[
    "node_started",
    "node_completed",
    "user_message",
    "token",
    "assistant_message",
    "error",
]


@dataclass(frozen=True, slots=True)
class ExecutionEvent:
    kind: ExecutionEventKind
    payload: dict[str, Any]


class GraphState(TypedDict):
    conversation_id: UUID
    messages: list[ChatMessage]
    workspace_context: WorkspaceContextRead
    assistant_content: str
    execution_events: list[ExecutionEvent]
