from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from industrial_agent.domain.routing import EvidenceKind
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
    evidence_snapshot: "EvidenceSnapshotRead | None" = None

    @field_validator("suggested_actions", mode="before")
    @classmethod
    def normalize_missing_actions(cls, value: object) -> object:
        return () if value is None else value

    @model_validator(mode="after")
    def validate_role_actions(self) -> Self:
        if self.role == "user" and self.suggested_actions:
            raise ValueError("user messages cannot contain suggested actions")
        if self.role == "user" and self.evidence_snapshot is not None:
            raise ValueError("user messages cannot contain evidence snapshots")
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
    combined_evidence: "CombinedEvidenceRead | None" = None


class CombinedEvidencePathRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    status: Literal["succeeded", "empty", "failed", "not_run"]
    result: (
        ProductionSummaryResult
        | EquipmentStatusResult
        | DefectDistributionResult
        | DocumentSearchResult
        | None
    ) = None
    error_code: str | None = None


class CombinedEvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    manufacturing_kind: EvidenceKind
    manufacturing: CombinedEvidencePathRead
    documents: CombinedEvidencePathRead
    document_query: str
    answer_status: Literal["succeeded", "fallback"]

    @model_validator(mode="after")
    def validate_path_result_types(self) -> Self:
        expected_type = {
            EvidenceKind.PRODUCTION: ProductionSummaryResult,
            EvidenceKind.EQUIPMENT_STATUS: EquipmentStatusResult,
            EvidenceKind.DEFECT_DISTRIBUTION: DefectDistributionResult,
        }[self.manufacturing_kind]
        if self.manufacturing.result is not None and not isinstance(
            self.manufacturing.result, expected_type
        ):
            raise ValueError("manufacturing result does not match its evidence kind")
        if self.documents.result is not None and not isinstance(
            self.documents.result, DocumentSearchResult
        ):
            raise ValueError("document path requires a document search result")
        return self


class _AvailableEvidenceSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    status: Literal["available"]
    schema_version: Literal[1]


class ProductionSummarySnapshotRead(_AvailableEvidenceSnapshotRead):
    kind: Literal["production_summary"]
    production_summary: ProductionSummaryResult


class EquipmentStatusSnapshotRead(_AvailableEvidenceSnapshotRead):
    kind: Literal["equipment_status"]
    equipment_status: EquipmentStatusResult


class DefectDistributionSnapshotRead(_AvailableEvidenceSnapshotRead):
    kind: Literal["defect_distribution"]
    defect_distribution: DefectDistributionResult


class DocumentSearchSnapshotRead(_AvailableEvidenceSnapshotRead):
    kind: Literal["document_search"]
    document_search: DocumentSearchResult


class CombinedSnapshotRead(_AvailableEvidenceSnapshotRead, CombinedEvidenceRead):
    kind: Literal["combined"]


class UnavailableEvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    status: Literal["unavailable"]
    code: Literal["unsupported_snapshot_version", "invalid_snapshot"]


AvailableEvidenceSnapshotRead = Annotated[
    ProductionSummarySnapshotRead
    | EquipmentStatusSnapshotRead
    | DefectDistributionSnapshotRead
    | DocumentSearchSnapshotRead
    | CombinedSnapshotRead,
    Field(discriminator="kind"),
]

EvidenceSnapshotRead = Annotated[
    AvailableEvidenceSnapshotRead | UnavailableEvidenceRead,
    Field(discriminator="status"),
]


MessageRead.model_rebuild()
