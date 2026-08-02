"""Application boundary for deterministic synthetic equipment status."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from industrial_agent.domain.manufacturing import (
    EquipmentStatus,
    get_equipment_status_at,
)
from industrial_agent.domain.synthetic_data import load_synthetic_scenario
from industrial_agent.tools.production import DEFAULT_DATASET


class EquipmentStatusToolError(ValueError):
    """A safe, user-facing equipment status tool validation error."""


class EquipmentStatusRequest(BaseModel):
    """Validated input for the get_equipment_status tool."""

    model_config = ConfigDict(extra="forbid")

    equipment_id: str = Field(min_length=1)
    at: datetime

    @field_validator("at")
    @classmethod
    def require_utc(cls, value: datetime) -> datetime:
        if value.utcoffset() != timedelta(0):
            raise ValueError("timestamp must use UTC")
        return value.replace(tzinfo=UTC)


class EquipmentStatusResult(BaseModel):
    """Structured evidence returned by get_equipment_status."""

    equipment_id: str
    observed_at: datetime
    status: EquipmentStatus
    effective_start: datetime | None
    effective_end: datetime | None
    source_event_id: str | None
    reason_code: str | None
    limitations: tuple[str, ...]


def get_equipment_status(
    request: EquipmentStatusRequest,
    *,
    dataset_path: Path = DEFAULT_DATASET,
) -> EquipmentStatusResult:
    """Return recorded synthetic equipment status for one UTC timestamp."""
    scenario = load_synthetic_scenario(dataset_path)
    if request.equipment_id != scenario.equipment.equipment_id:
        raise EquipmentStatusToolError(f"Unknown Equipment: {request.equipment_id}")

    observation = get_equipment_status_at(
        intervals=scenario.equipment_state_intervals,
        equipment_id=request.equipment_id,
        observed_at=request.at,
    )
    source = observation.source_interval
    return EquipmentStatusResult(
        equipment_id=observation.equipment_id,
        observed_at=observation.observed_at,
        status=observation.status,
        effective_start=source.started_at if source else None,
        effective_end=source.ended_at if source else None,
        source_event_id=source.event_id if source else None,
        reason_code=source.reason_code if source else None,
        limitations=observation.limitations,
    )
