"""Manufacturing records and deterministic production analysis."""

from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True)
class Equipment:
    """A fictional machine that processes or inspects production units."""

    equipment_id: str


@dataclass(frozen=True)
class ProductionLot:
    """A named group of wafers tracked through a synthetic scenario."""

    lot_id: str
    unit: str


@dataclass(frozen=True)
class DefectCount:
    """The failed-wafer count assigned to one fictional defect category."""

    category: str
    count: int

    def __post_init__(self) -> None:
        if not self.category:
            raise ValueError("Defect Count category cannot be empty")
        if self.count < 0:
            raise ValueError("Defect Count cannot be negative")


@dataclass(frozen=True)
class InspectionRecord:
    """Counts observed for one Equipment and Production Lot at a UTC time."""

    record_id: str
    equipment_id: str
    lot_id: str
    observed_at: datetime
    inspected_wafers: int
    passed_wafers: int
    failed_wafers: int
    defect_counts: tuple[DefectCount, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        counts = (self.inspected_wafers, self.passed_wafers, self.failed_wafers)
        if any(count < 0 for count in counts):
            raise ValueError("Inspection Record counts cannot be negative")
        if self.passed_wafers + self.failed_wafers != self.inspected_wafers:
            raise ValueError("passed and failed wafers must equal inspected wafers")
        if sum(defect.count for defect in self.defect_counts) > self.failed_wafers:
            raise ValueError("Defect Counts cannot exceed failed wafers")
        if self.observed_at.tzinfo is not UTC:
            raise ValueError("Inspection Record timestamp must use UTC")


@dataclass(frozen=True)
class AlarmEvent:
    """A fictional equipment event recorded independently from inspections."""

    event_id: str
    equipment_id: str
    code: str
    started_at: datetime
    ended_at: datetime

    def __post_init__(self) -> None:
        if self.started_at.tzinfo is not UTC or self.ended_at.tzinfo is not UTC:
            raise ValueError("Alarm Event boundaries must use UTC")
        if self.started_at >= self.ended_at:
            raise ValueError("Alarm Event start must be before end")


@dataclass(frozen=True)
class TimeRange:
    """A UTC interval that includes its start and excludes its end."""

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.start.tzinfo is not UTC or self.end.tzinfo is not UTC:
            raise ValueError("Time Range boundaries must use UTC")
        if self.start >= self.end:
            raise ValueError("Time Range start must be before end")

    def contains(self, timestamp: datetime) -> bool:
        """Return whether a UTC timestamp falls within this Time Range."""
        return self.start <= timestamp < self.end


@dataclass(frozen=True)
class ProductionSummary:
    """A deterministic aggregation for one Equipment and Time Range."""

    equipment_id: str
    time_range: TimeRange
    inspected_wafers: int
    passed_wafers: int
    failed_wafers: int
    yield_rate: float | None
    defect_counts: tuple[DefectCount, ...]
    alarm_events: tuple[AlarmEvent, ...]
    limitations: tuple[str, ...]


def summarize_production(
    *,
    records: tuple[InspectionRecord, ...],
    alarms: tuple[AlarmEvent, ...],
    equipment_id: str,
    time_range: TimeRange,
) -> ProductionSummary:
    """Aggregate recorded facts without interpreting correlation or cause."""
    matching_records = tuple(
        record
        for record in records
        if record.equipment_id == equipment_id
        and time_range.contains(record.observed_at)
    )
    inspected = sum(record.inspected_wafers for record in matching_records)
    passed = sum(record.passed_wafers for record in matching_records)
    failed = sum(record.failed_wafers for record in matching_records)

    defect_totals: Counter[str] = Counter()
    for record in matching_records:
        for defect in record.defect_counts:
            defect_totals[defect.category] += defect.count
    defect_counts = tuple(
        DefectCount(category=category, count=count)
        for category, count in sorted(
            defect_totals.items(), key=lambda item: (-item[1], item[0])
        )
    )
    matching_alarms = tuple(
        alarm
        for alarm in alarms
        if alarm.equipment_id == equipment_id
        and alarm.started_at < time_range.end
        and alarm.ended_at > time_range.start
    )

    return ProductionSummary(
        equipment_id=equipment_id,
        time_range=time_range,
        inspected_wafers=inspected,
        passed_wafers=passed,
        failed_wafers=failed,
        yield_rate=passed / inspected if inspected else None,
        defect_counts=defect_counts,
        alarm_events=matching_alarms,
        limitations=() if matching_records else ("no_inspection_records",),
    )
