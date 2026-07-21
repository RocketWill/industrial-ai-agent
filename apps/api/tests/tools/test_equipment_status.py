from datetime import UTC, datetime
from pathlib import Path

import pytest

from industrial_agent.tools.equipment_status import (
    EquipmentStatusRequest,
    EquipmentStatusToolError,
    get_equipment_status,
)

DATASET = (
    Path(__file__).resolve().parents[4]
    / "data/synthetic/aoi-wafer-inspection-v1.json"
)


def test_get_equipment_status_returns_recorded_warning_evidence() -> None:
    result = get_equipment_status(
        EquipmentStatusRequest(
            equipment_id="AOI-WAFER-01",
            at=datetime(2026, 1, 15, 15, 30, tzinfo=UTC),
        ),
        dataset_path=DATASET,
    )

    assert result.equipment_id == "AOI-WAFER-01"
    assert result.observed_at == datetime(2026, 1, 15, 15, 30, tzinfo=UTC)
    assert result.status == "warning"
    assert result.effective_start == datetime(2026, 1, 15, 15, tzinfo=UTC)
    assert result.effective_end == datetime(2026, 1, 15, 16, tzinfo=UTC)
    assert result.source_event_id == "state-002"
    assert result.reason_code == "SYNTHETIC-RECORDED-WARNING"
    assert result.limitations == ()


def test_get_equipment_status_returns_unknown_without_inference() -> None:
    result = get_equipment_status(
        EquipmentStatusRequest(
            equipment_id="AOI-WAFER-01",
            at=datetime(2026, 1, 15, 19, tzinfo=UTC),
        ),
        dataset_path=DATASET,
    )

    assert result.status == "unknown"
    assert result.source_event_id is None
    assert result.reason_code is None
    assert result.limitations == ("no_recorded_equipment_state",)


def test_get_equipment_status_rejects_unknown_equipment() -> None:
    with pytest.raises(EquipmentStatusToolError, match="Unknown Equipment"):
        get_equipment_status(
            EquipmentStatusRequest(
                equipment_id="AOI-WAFER-99",
                at=datetime(2026, 1, 15, 17, tzinfo=UTC),
            ),
            dataset_path=DATASET,
        )
