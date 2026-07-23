from datetime import UTC, datetime
from pathlib import Path

import pytest

from industrial_agent.tools.defect_distribution import (
    DefectDistributionRequest,
    get_defect_distribution,
)

DATASET = (
    Path(__file__).resolve().parents[4]
    / "data/synthetic/aoi-wafer-inspection-v1.json"
)


def test_get_defect_distribution_returns_ranked_aoi_evidence() -> None:
    result = get_defect_distribution(
        DefectDistributionRequest(
            equipment_id="AOI-WAFER-01",
            lot_id="LOT-DEMO-001",
            start=datetime(2026, 1, 15, 13, tzinfo=UTC),
            end=datetime(2026, 1, 15, 17, tzinfo=UTC),
        ),
        dataset_path=DATASET,
    )

    assert result.failed_wafers == 30
    assert result.classified_defect_count == 30
    assert result.unclassified_failed_wafers == 0
    assert result.items[0].category == "edge-chip"
    assert result.items[0].count == 19
    assert result.items[0].share == pytest.approx(19 / 30)
    assert result.items[0].rank == 1
    assert result.items[1].category == "scratch"
    assert result.items[1].count == 11
    assert result.items[1].share == pytest.approx(11 / 30)
    assert result.items[1].rank == 2
    assert result.limitations == ()
