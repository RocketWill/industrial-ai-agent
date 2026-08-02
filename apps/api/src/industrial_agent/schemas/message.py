from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from industrial_agent.models.message import MessageRole
from industrial_agent.tools.equipment_status import EquipmentStatusResult
from industrial_agent.tools.production import ProductionSummaryResult


class MessageCreate(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    content: str = Field(min_length=1, max_length=10_000)


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conversation_id: UUID
    role: MessageRole
    content: str
    created_at: datetime

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
    tool_error: ToolErrorRead | None = None


class MessageExchangeRead(BaseModel):
    user_message: MessageRead
    assistant_message: MessageRead
    evidence: EvidenceRead | None = None
