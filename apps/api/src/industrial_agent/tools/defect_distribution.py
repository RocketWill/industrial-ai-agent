"""Application boundary for deterministic defect distribution analysis."""

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from industrial_agent.domain.manufacturing import (
    TimeRange,
    summarize_defect_distribution,
)
from industrial_agent.domain.synthetic_data import load_synthetic_scenario
from industrial_agent.tools.production import (
    DEFAULT_DATASET,
    ProductionSummaryRequest,
)


class DefectDistributionToolError(ValueError):
    """A safe, user-facing defect distribution validation error."""


class DefectDistributionRequest(ProductionSummaryRequest):
    """Validated input for the get_defect_distribution tool."""


class DefectDistributionItemResult(BaseModel):
    """Serialized ranked defect category."""

    category: str
    count: int
    share: float | None
    rank: int


class DefectDistributionResult(BaseModel):
    """Structured evidence returned by get_defect_distribution."""

    equipment_id: str
    lot_id: str | None
    start: datetime
    end: datetime
    failed_wafers: int
    classified_defect_count: int
    unclassified_failed_wafers: int
    items: tuple[DefectDistributionItemResult, ...]
    limitations: tuple[str, ...]


def get_defect_distribution(
    request: DefectDistributionRequest,
    *,
    dataset_path: Path = DEFAULT_DATASET,
) -> DefectDistributionResult:
    """Return deterministic defect distribution evidence for one query."""
    scenario = load_synthetic_scenario(dataset_path)
    if request.equipment_id != scenario.equipment.equipment_id:
        raise DefectDistributionToolError(
            f"Unknown Equipment: {request.equipment_id}"
        )
    if request.lot_id is not None and request.lot_id != scenario.production_lot.lot_id:
        raise DefectDistributionToolError(
            f"Unknown Production Lot: {request.lot_id}"
        )
    records = scenario.inspection_records
    if request.lot_id is not None:
        records = tuple(record for record in records if record.lot_id == request.lot_id)
    distribution = summarize_defect_distribution(
        records=records,
        equipment_id=request.equipment_id,
        time_range=TimeRange(start=request.start, end=request.end),
    )
    return DefectDistributionResult(
        equipment_id=distribution.equipment_id,
        lot_id=request.lot_id,
        start=distribution.time_range.start,
        end=distribution.time_range.end,
        failed_wafers=distribution.failed_wafers,
        classified_defect_count=distribution.classified_defect_count,
        unclassified_failed_wafers=distribution.unclassified_failed_wafers,
        items=tuple(
            DefectDistributionItemResult(
                category=item.category,
                count=item.count,
                share=item.share,
                rank=item.rank,
            )
            for item in distribution.items
        ),
        limitations=distribution.limitations,
    )
