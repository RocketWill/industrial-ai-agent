"""Load independently created synthetic manufacturing scenarios."""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from industrial_agent.domain.manufacturing import (
    AlarmEvent,
    DefectCount,
    Equipment,
    InspectionRecord,
    ProductionLot,
)


@dataclass(frozen=True)
class SyntheticScenario:
    """Validated records and limitations loaded from a synthetic dataset."""

    equipment: Equipment
    production_lot: ProductionLot
    inspection_records: tuple[InspectionRecord, ...]
    alarm_events: tuple[AlarmEvent, ...]
    causal_claim: str | None


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_synthetic_scenario(path: Path) -> SyntheticScenario:
    """Load a JSON scenario through the public manufacturing domain types."""
    payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    equipment = Equipment(equipment_id=payload["equipment"]["equipment_id"])
    production_lot = ProductionLot(
        lot_id=payload["production_lot"]["lot_id"],
        unit=payload["production_lot"]["unit"],
    )
    records = tuple(
        InspectionRecord(
            record_id=item["record_id"],
            equipment_id=equipment.equipment_id,
            lot_id=production_lot.lot_id,
            observed_at=_timestamp(item["observed_at"]),
            inspected_wafers=item["inspected_wafers"],
            passed_wafers=item["passed_wafers"],
            failed_wafers=item["failed_wafers"],
            defect_counts=tuple(
                DefectCount(category=defect["category"], count=defect["count"])
                for defect in item["defect_counts"]
            ),
        )
        for item in payload["inspection_records"]
    )
    alarms = tuple(
        AlarmEvent(
            event_id=item["event_id"],
            equipment_id=equipment.equipment_id,
            code=item["code"],
            started_at=_timestamp(item["started_at"]),
            ended_at=_timestamp(item["ended_at"]),
        )
        for item in payload["alarm_events"]
    )
    return SyntheticScenario(
        equipment=equipment,
        production_lot=production_lot,
        inspection_records=records,
        alarm_events=alarms,
        causal_claim=payload["causal_claim"],
    )
