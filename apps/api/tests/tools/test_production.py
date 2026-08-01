from datetime import UTC, datetime
from pathlib import Path

import pytest

from industrial_agent.tools.production import (
    ProductionSummaryRequest,
    ProductionToolError,
    get_production_summary,
)

DATASET = (
    Path(__file__).resolve().parents[4]
    / "data/synthetic/aoi-wafer-inspection-v1.json"
)


def test_get_production_summary_returns_structured_aoi_evidence() -> None:
    result = get_production_summary(
        ProductionSummaryRequest(
            equipment_id="AOI-WAFER-01",
            lot_id="LOT-DEMO-001",
            start=datetime(2026, 1, 15, 15, tzinfo=UTC),
            end=datetime(2026, 1, 15, 18, tzinfo=UTC),
        ),
        dataset_path=DATASET,
    )

    assert result.equipment_id == "AOI-WAFER-01"
    assert result.lot_id == "LOT-DEMO-001"
    assert result.inspected_wafers == 300
    assert result.passed_wafers == 257
    assert result.failed_wafers == 43
    assert result.yield_rate == pytest.approx(257 / 300)
    assert result.defect_counts[0].category == "edge-chip"
    assert result.defect_counts[0].count == 34
    assert result.alarm_events[0].code == "OPTICAL-SIGNAL-LOW"
    assert result.limitations == ()


def test_get_production_summary_rejects_unknown_equipment() -> None:
    with pytest.raises(ProductionToolError, match="Unknown Equipment"):
        get_production_summary(
            ProductionSummaryRequest(
                equipment_id="AOI-WAFER-99",
                start=datetime(2026, 1, 15, 15, tzinfo=UTC),
                end=datetime(2026, 1, 15, 16, tzinfo=UTC),
            ),
            dataset_path=DATASET,
        )


def test_get_production_summary_without_lot_aggregates_the_equipment() -> None:
    result = get_production_summary(
        ProductionSummaryRequest(
            equipment_id="AOI-WAFER-01",
            start=datetime(2026, 1, 15, 8, tzinfo=UTC),
            end=datetime(2026, 1, 15, 18, tzinfo=UTC),
        ),
        dataset_path=DATASET,
    )

    assert result.lot_id is None
    assert result.inspected_wafers == 1000
    assert result.passed_wafers == 942
    assert result.failed_wafers == 58


def test_get_production_summary_rejects_unknown_lot() -> None:
    with pytest.raises(ProductionToolError, match="Unknown Production Lot"):
        get_production_summary(
            ProductionSummaryRequest(
                equipment_id="AOI-WAFER-01",
                lot_id="LOT-DEMO-999",
                start=datetime(2026, 1, 15, 15, tzinfo=UTC),
                end=datetime(2026, 1, 15, 16, tzinfo=UTC),
            ),
            dataset_path=DATASET,
        )


def test_get_production_summary_preserves_empty_domain_result() -> None:
    result = get_production_summary(
        ProductionSummaryRequest(
            equipment_id="AOI-WAFER-01",
            start=datetime(2026, 1, 15, 18, tzinfo=UTC),
            end=datetime(2026, 1, 15, 19, tzinfo=UTC),
        ),
        dataset_path=DATASET,
    )

    assert result.inspected_wafers == 0
    assert result.yield_rate is None
    assert result.limitations == ("no_inspection_records",)
