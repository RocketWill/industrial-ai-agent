from datetime import UTC, datetime
from pathlib import Path

import pytest

from industrial_agent.domain.manufacturing import (
    AlarmEvent,
    DefectCount,
    InspectionRecord,
    TimeRange,
    summarize_production,
)
from industrial_agent.domain.synthetic_data import load_synthetic_scenario

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]


def test_time_range_uses_a_utc_half_open_interval() -> None:
    time_range = TimeRange(
        start=datetime(2026, 1, 15, 8, tzinfo=UTC),
        end=datetime(2026, 1, 15, 9, tzinfo=UTC),
    )

    assert time_range.contains(datetime(2026, 1, 15, 8, tzinfo=UTC))
    assert not time_range.contains(datetime(2026, 1, 15, 9, tzinfo=UTC))


def test_inspection_record_rejects_inconsistent_counts() -> None:
    with pytest.raises(ValueError, match="passed and failed"):
        InspectionRecord(
            record_id="inspection-001",
            equipment_id="AOI-WAFER-01",
            lot_id="LOT-DEMO-001",
            observed_at=datetime(2026, 1, 15, 8, tzinfo=UTC),
            inspected_wafers=10,
            passed_wafers=8,
            failed_wafers=1,
        )


def test_inspection_record_rejects_defect_counts_above_failures() -> None:
    with pytest.raises(ValueError, match="cannot exceed failed"):
        InspectionRecord(
            record_id="inspection-001",
            equipment_id="AOI-WAFER-01",
            lot_id="LOT-DEMO-001",
            observed_at=datetime(2026, 1, 15, 8, tzinfo=UTC),
            inspected_wafers=10,
            passed_wafers=9,
            failed_wafers=1,
            defect_counts=(DefectCount(category="edge-chip", count=2),),
        )


def test_production_summary_aggregates_only_matching_observations() -> None:
    records = (
        InspectionRecord(
            record_id="inspection-001",
            equipment_id="AOI-WAFER-01",
            lot_id="LOT-DEMO-001",
            observed_at=datetime(2026, 1, 15, 15, tzinfo=UTC),
            inspected_wafers=100,
            passed_wafers=90,
            failed_wafers=10,
            defect_counts=(
                DefectCount(category="edge-chip", count=7),
                DefectCount(category="scratch", count=3),
            ),
        ),
        InspectionRecord(
            record_id="inspection-at-end",
            equipment_id="AOI-WAFER-01",
            lot_id="LOT-DEMO-001",
            observed_at=datetime(2026, 1, 15, 16, tzinfo=UTC),
            inspected_wafers=100,
            passed_wafers=100,
            failed_wafers=0,
        ),
        InspectionRecord(
            record_id="other-equipment",
            equipment_id="AOI-WAFER-02",
            lot_id="LOT-DEMO-001",
            observed_at=datetime(2026, 1, 15, 15, 30, tzinfo=UTC),
            inspected_wafers=100,
            passed_wafers=100,
            failed_wafers=0,
        ),
    )
    alarms = (
        AlarmEvent(
            event_id="alarm-001",
            equipment_id="AOI-WAFER-01",
            code="OPTICAL-SIGNAL-LOW",
            started_at=datetime(2026, 1, 15, 14, 55, tzinfo=UTC),
            ended_at=datetime(2026, 1, 15, 15, 5, tzinfo=UTC),
        ),
    )

    summary = summarize_production(
        records=records,
        alarms=alarms,
        equipment_id="AOI-WAFER-01",
        time_range=TimeRange(
            start=datetime(2026, 1, 15, 15, tzinfo=UTC),
            end=datetime(2026, 1, 15, 16, tzinfo=UTC),
        ),
    )

    assert summary.inspected_wafers == 100
    assert summary.passed_wafers == 90
    assert summary.failed_wafers == 10
    assert summary.yield_rate == 0.9
    assert summary.defect_counts == (
        DefectCount(category="edge-chip", count=7),
        DefectCount(category="scratch", count=3),
    )
    assert summary.alarm_events == alarms
    assert summary.limitations == ()


def test_synthetic_aoi_scenario_preserves_observations_without_claiming_cause() -> None:
    scenario = load_synthetic_scenario(
        REPOSITORY_ROOT / "data/synthetic/aoi-wafer-inspection-v1.json"
    )

    assert scenario.equipment.equipment_id == "AOI-WAFER-01"
    assert scenario.production_lot.lot_id == "LOT-DEMO-001"
    assert scenario.production_lot.unit == "wafer"
    assert scenario.inspection_records[0].observed_at == datetime(
        2026, 1, 15, 8, tzinfo=UTC
    )
    assert scenario.inspection_records[-1].observed_at == datetime(
        2026, 1, 15, 17, tzinfo=UTC
    )
    assert scenario.alarm_events[0].code == "OPTICAL-SIGNAL-LOW"
    assert scenario.causal_claim is None


def test_empty_production_summary_keeps_overlapping_alarm_as_recorded_fact() -> None:
    alarm = AlarmEvent(
        event_id="alarm-001",
        equipment_id="AOI-WAFER-01",
        code="OPTICAL-SIGNAL-LOW",
        started_at=datetime(2026, 1, 15, 15, tzinfo=UTC),
        ended_at=datetime(2026, 1, 15, 16, tzinfo=UTC),
    )

    summary = summarize_production(
        records=(),
        alarms=(alarm,),
        equipment_id="AOI-WAFER-01",
        time_range=TimeRange(
            start=datetime(2026, 1, 15, 15, tzinfo=UTC),
            end=datetime(2026, 1, 15, 16, tzinfo=UTC),
        ),
    )

    assert summary.inspected_wafers == 0
    assert summary.yield_rate is None
    assert summary.defect_counts == ()
    assert summary.alarm_events == (alarm,)
    assert summary.limitations == ("no_inspection_records",)
