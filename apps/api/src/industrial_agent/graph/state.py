from dataclasses import dataclass
from typing import Any, Literal, TypedDict
from uuid import UUID

from industrial_agent.graph.combined import CombinedExchangeEvidence
from industrial_agent.llm.types import ChatMessage, ToolCall
from industrial_agent.schemas.context import WorkspaceContextRead
from industrial_agent.schemas.message import SuggestedAction
from industrial_agent.tools.defect_distribution import DefectDistributionResult
from industrial_agent.tools.document_search import DocumentSearchResult
from industrial_agent.tools.equipment_status import EquipmentStatusResult
from industrial_agent.tools.production import ProductionSummaryResult

ExecutionEventKind = Literal[
    "node_started",
    "node_completed",
    "user_message",
    "token",
    "assistant_message",
    "tool_call_started",
    "tool_result",
    "combined_tool_result",
    "combined_evidence_completed",
    "routing_started",
    "routing_retry",
    "routing_decided",
    "clarification_required",
    "routing_fallback_used",
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
    "INVALID_INPUT": "The manufacturing query is invalid.",
    "UNKNOWN_EQUIPMENT": "The requested Equipment is not available.",
    "UNKNOWN_PRODUCTION_LOT": "The requested Production Lot is not available.",
    "NO_DATA": "No Inspection Records match the requested query.",
    "TOOL_UNAVAILABLE": "Manufacturing data is temporarily unavailable.",
    "UNSUPPORTED_TOOL_CALL_PATTERN": (
        "This manufacturing request pattern is not supported."
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
    equipment_status: EquipmentStatusResult | None = None
    defect_distribution: DefectDistributionResult | None = None
    document_search: DocumentSearchResult | None = None
    tool_error: ToolError | None = None

    def __post_init__(self) -> None:
        populated = sum(
            item is not None
            for item in (
                self.production_summary,
                self.equipment_status,
                self.defect_distribution,
                self.document_search,
                self.tool_error,
            )
        )
        if populated > 1:
            raise ValueError("Evidence State can contain only one result or error")



@dataclass(frozen=True, slots=True)
class ExecutionEvent:
    kind: ExecutionEventKind
    payload: dict[str, Any]


class GraphState(TypedDict):
    conversation_id: UUID
    messages: list[ChatMessage]
    workspace_context: WorkspaceContextRead
    assistant_content: str
    suggested_actions: tuple[SuggestedAction, ...]
    execution_events: list[ExecutionEvent]
    evidence: EvidenceState | None
    combined_evidence: CombinedExchangeEvidence | None
    tool_call: ToolCall | None
