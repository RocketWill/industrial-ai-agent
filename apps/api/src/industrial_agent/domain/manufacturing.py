"""Manufacturing records and deterministic production analysis."""

from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

EquipmentStatus = Literal[
    "running", "idle", "warning", "down", "maintenance", "unknown"
]
RECORDED_EQUIPMENT_STATUSES = frozenset(
    {"running", "idle", "warning", "down", "maintenance"}
)


@dataclass(frozen=True)
class Equipment:
    """A fictional machine that processes or inspects production units."""

    equipment_id: str


@dataclass(frozen=True)
class EquipmentStateInterval:
    """An explicitly recorded synthetic equipment state over a UTC interval."""

    event_id: str
    equipment_id: str
    status: EquipmentStatus
    started_at: datetime
    ended_at: datetime
    reason_code: str | None = None

    def __post_init__(self) -> None:
        if self.status not in RECORDED_EQUIPMENT_STATUSES:
            raise ValueError("Equipment State Interval status must be recorded")
        if self.started_at.tzinfo is not UTC or self.ended_at.tzinfo is not UTC:
            raise ValueError("Equipment State Interval boundaries must use UTC")
        if self.started_at >= self.ended_at:
            raise ValueError("Equipment State Interval start must be before end")

    def contains(self, timestamp: datetime) -> bool:
        """Return whether the timestamp is inside this half-open interval."""
        return self.started_at <= timestamp < self.ended_at


@dataclass(frozen=True)
class EquipmentStatusObservation:
    """Deterministic equipment status evidence for one requested timestamp."""

    equipment_id: str
    observed_at: datetime
    status: EquipmentStatus
    source_interval: EquipmentStateInterval | None
    limitations: tuple[str, ...]


def get_equipment_status_at(
    *,
    intervals: tuple[EquipmentStateInterval, ...],
    equipment_id: str,
    observed_at: datetime,
) -> EquipmentStatusObservation:
    """Return an explicitly recorded status or an unknown evidence result."""
    matching = tuple(
        interval
        for interval in intervals
        if interval.equipment_id == equipment_id and interval.contains(observed_at)
    )
    if len(matching) > 1:
        raise ValueError("overlapping Equipment State Intervals")
    source = matching[0] if matching else None
    return EquipmentStatusObservation(
        equipment_id=equipment_id,
        observed_at=observed_at,
        status=source.status if source else "unknown",
        source_interval=source,
        limitations=() if source else ("no_recorded_equipment_state",),
    )


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


@dataclass(frozen=True)
class DefectDistributionItem:
    """One ranked category in a deterministic defect distribution."""

    category: str
    count: int
    share: float | None
    rank: int


@dataclass(frozen=True)
class DefectDistribution:
    """Recorded defect-category distribution for one Equipment and Time Range."""

    equipment_id: str
    time_range: TimeRange
    failed_wafers: int
    classified_defect_count: int
    unclassified_failed_wafers: int
    items: tuple[DefectDistributionItem, ...]
    limitations: tuple[str, ...]


def summarize_defect_distribution(
    *,
    records: tuple[InspectionRecord, ...],
    equipment_id: str,
    time_range: TimeRange,
) -> DefectDistribution:
    """Aggregate recorded categories without inferring missing classifications."""
    matching_records = tuple(
        record
        for record in records
        if record.equipment_id == equipment_id
        and time_range.contains(record.observed_at)
    )
    failed_wafers = sum(record.failed_wafers for record in matching_records)
    totals: Counter[str] = Counter()
    for record in matching_records:
        for defect in record.defect_counts:
            totals[defect.category] += defect.count
    classified = sum(totals.values())
    unclassified = failed_wafers - classified
    if unclassified < 0:
        raise ValueError("classified defects cannot exceed failed wafers")
    ordered = sorted(totals.items(), key=lambda item: (-item[1], item[0]))
    items = tuple(
        DefectDistributionItem(
            category=category,
            count=count,
            share=count / classified if classified else None,
            rank=index,
        )
        for index, (category, count) in enumerate(ordered, start=1)
    )
    limitations: list[str] = []
    if not matching_records:
        limitations.append("no_inspection_records")
    elif classified == 0:
        limitations.append("no_classified_defects")
    if unclassified > 0:
        limitations.append("incomplete_defect_classification")
    return DefectDistribution(
        equipment_id=equipment_id,
        time_range=time_range,
        failed_wafers=failed_wafers,
        classified_defect_count=classified,
        unclassified_failed_wafers=unclassified,
        items=items,
        limitations=tuple(limitations),
    )


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
