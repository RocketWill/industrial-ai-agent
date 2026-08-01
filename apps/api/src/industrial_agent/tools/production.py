"""Application boundary for deterministic production analysis."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from industrial_agent.domain.manufacturing import TimeRange, summarize_production
from industrial_agent.domain.synthetic_data import load_synthetic_scenario

DEFAULT_DATASET = (
    Path(__file__).resolve().parents[5]
    / "data/synthetic/aoi-wafer-inspection-v1.json"
)


class ProductionToolError(ValueError):
    """A safe, user-facing production tool validation error."""


class ProductionSummaryRequest(BaseModel):
    """Validated input for the get_production_summary tool."""

    model_config = ConfigDict(extra="forbid")

    equipment_id: str = Field(min_length=1)
    start: datetime
    end: datetime
    lot_id: str | None = Field(default=None, min_length=1)

    @field_validator("start", "end")
    @classmethod
    def require_utc(cls, value: datetime) -> datetime:
        if value.utcoffset() != timedelta(0):
            raise ValueError("timestamps must use UTC")
        return value.replace(tzinfo=UTC)

    @field_validator("end")
    @classmethod
    def require_ordered_range(
        cls, value: datetime, info
    ) -> datetime:
        start = info.data.get("start")
        if start is not None and start >= value:
            raise ValueError("end must be after start")
        return value


class DefectCountResult(BaseModel):
    """Serialized deterministic defect aggregate."""

    category: str
    count: int


class AlarmEventResult(BaseModel):
    """Serialized recorded alarm event."""

    event_id: str
    code: str
    started_at: datetime
    ended_at: datetime


class ProductionSummaryResult(BaseModel):
    """Structured evidence returned by get_production_summary."""

    equipment_id: str
    lot_id: str | None
    start: datetime
    end: datetime
    inspected_wafers: int
    passed_wafers: int
    failed_wafers: int
    yield_rate: float | None
    defect_counts: tuple[DefectCountResult, ...]
    alarm_events: tuple[AlarmEventResult, ...]
    limitations: tuple[str, ...]


def get_production_summary(
    request: ProductionSummaryRequest,
    *,
    dataset_path: Path = DEFAULT_DATASET,
) -> ProductionSummaryResult:
    """Return deterministic production evidence for a validated request."""
    scenario = load_synthetic_scenario(dataset_path)
    if request.equipment_id != scenario.equipment.equipment_id:
        raise ProductionToolError(f"Unknown Equipment: {request.equipment_id}")
    if request.lot_id is not None and request.lot_id != scenario.production_lot.lot_id:
        raise ProductionToolError(f"Unknown Production Lot: {request.lot_id}")

    records = scenario.inspection_records
    if request.lot_id is not None:
        records = tuple(record for record in records if record.lot_id == request.lot_id)
    summary = summarize_production(
        records=records,
        alarms=scenario.alarm_events,
        equipment_id=request.equipment_id,
        time_range=TimeRange(start=request.start, end=request.end),
    )
    return ProductionSummaryResult(
        equipment_id=summary.equipment_id,
        lot_id=request.lot_id,
        start=summary.time_range.start,
        end=summary.time_range.end,
        inspected_wafers=summary.inspected_wafers,
        passed_wafers=summary.passed_wafers,
        failed_wafers=summary.failed_wafers,
        yield_rate=summary.yield_rate,
        defect_counts=tuple(
            DefectCountResult(category=item.category, count=item.count)
            for item in summary.defect_counts
        ),
        alarm_events=tuple(
            AlarmEventResult(
                event_id=item.event_id,
                code=item.code,
                started_at=item.started_at,
                ended_at=item.ended_at,
            )
            for item in summary.alarm_events
        ),
        limitations=summary.limitations,
    )
