from datetime import UTC, datetime
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from industrial_agent.models.message import MessageRole
from industrial_agent.tools.defect_distribution import DefectDistributionResult
from industrial_agent.tools.document_search import DocumentSearchResult
from industrial_agent.tools.equipment_status import EquipmentStatusResult
from industrial_agent.tools.production import ProductionSummaryResult


class MessageCreate(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    content: str = Field(min_length=1, max_length=10_000)


class SuggestedActionId(StrEnum):
    PRODUCTION_EVIDENCE_FIRST = "production_evidence_first"
    DOCUMENT_EVIDENCE_FIRST = "document_evidence_first"


_CANONICAL_ACTIONS = {
    SuggestedActionId.PRODUCTION_EVIDENCE_FIRST: (
        "Production evidence",
        "Show the production evidence first.",
    ),
    SuggestedActionId.DOCUMENT_EVIDENCE_FIRST: (
        "Document evidence",
        "Search the documents first.",
    ),
}


class SuggestedAction(BaseModel):
    """One immutable application-owned continuation for a clarification."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: SuggestedActionId
    label: str = Field(min_length=1)
    message: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_canonical_action(self) -> Self:
        if (self.label, self.message) != _CANONICAL_ACTIONS[self.id]:
            raise ValueError("suggested action does not match its canonical ID")
        return self


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conversation_id: UUID
    role: MessageRole
    content: str
    suggested_actions: tuple[SuggestedAction, ...] = ()
    created_at: datetime

    @field_validator("suggested_actions", mode="before")
    @classmethod
    def normalize_missing_actions(cls, value: object) -> object:
        return () if value is None else value

    @model_validator(mode="after")
    def validate_role_actions(self) -> Self:
        if self.role == "user" and self.suggested_actions:
            raise ValueError("user messages cannot contain suggested actions")
        return self

    @field_validator("created_at", mode="after")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class ToolErrorRead(BaseModel):
    code: str
    message: str


class EvidenceRead(BaseModel):
    production_summary: ProductionSummaryResult | None = None
    equipment_status: EquipmentStatusResult | None = None
    defect_distribution: DefectDistributionResult | None = None
    document_search: DocumentSearchResult | None = None
    tool_error: ToolErrorRead | None = None


class MessageExchangeRead(BaseModel):
    user_message: MessageRead
    assistant_message: MessageRead
    evidence: EvidenceRead | None = None
