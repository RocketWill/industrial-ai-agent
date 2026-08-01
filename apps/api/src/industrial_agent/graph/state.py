from dataclasses import dataclass
from typing import Any, Literal, TypedDict
from uuid import UUID

from industrial_agent.llm.types import ChatMessage, ToolCall
from industrial_agent.schemas.context import WorkspaceContextRead
from industrial_agent.tools.production import ProductionSummaryResult

ExecutionEventKind = Literal[
    "node_started",
    "node_completed",
    "user_message",
    "token",
    "assistant_message",
    "tool_call_started",
    "tool_result",
    "error",
]
ToolErrorCode = Literal[
    "INVALID_INPUT",
    "UNKNOWN_EQUIPMENT",
    "UNKNOWN_PRODUCTION_LOT",
    "NO_DATA",
    "TOOL_UNAVAILABLE",
    "UNSUPPORTED_TOOL_CALL_PATTERN",
]

_TOOL_ERROR_MESSAGES: dict[ToolErrorCode, str] = {
    "INVALID_INPUT": "The production query is invalid.",
    "UNKNOWN_EQUIPMENT": "The requested Equipment is not available.",
    "UNKNOWN_PRODUCTION_LOT": "The requested Production Lot is not available.",
    "NO_DATA": "No Inspection Records match the requested query.",
    "TOOL_UNAVAILABLE": "Production data is temporarily unavailable.",
    "UNSUPPORTED_TOOL_CALL_PATTERN": (
        "This production request pattern is not supported."
    ),
}


@dataclass(frozen=True, slots=True)
class ToolError:
    """A safe, typed production-tool failure."""

    code: ToolErrorCode

    @property
    def message(self) -> str:
        return _TOOL_ERROR_MESSAGES[self.code]


@dataclass(frozen=True, slots=True)
class EvidenceState:
    """One production result or error for the current graph run."""

    production_summary: ProductionSummaryResult | None = None
    tool_error: ToolError | None = None

    def __post_init__(self) -> None:
        if self.production_summary is not None and self.tool_error is not None:
            raise ValueError("Evidence State cannot contain both result and error")



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
    evidence: EvidenceState | None
    tool_call: ToolCall | None
