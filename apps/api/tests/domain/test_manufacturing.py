import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from industrial_agent.domain.manufacturing import (
    AlarmEvent,
    DefectCount,
    EquipmentStateInterval,
    InspectionRecord,
    TimeRange,
    get_equipment_status_at,
    summarize_defect_distribution,
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


def test_equipment_status_lookup_uses_recorded_half_open_intervals() -> None:
    interval = EquipmentStateInterval(
        event_id="state-001",
        equipment_id="AOI-WAFER-01",
        status="running",
        started_at=datetime(2026, 1, 15, 8, tzinfo=UTC),
        ended_at=datetime(2026, 1, 15, 9, tzinfo=UTC),
        reason_code="SCHEDULED-RUN",
    )

    recorded = get_equipment_status_at(
        intervals=(interval,),
        equipment_id="AOI-WAFER-01",
        observed_at=datetime(2026, 1, 15, 8, tzinfo=UTC),
    )
    unknown = get_equipment_status_at(
        intervals=(interval,),
        equipment_id="AOI-WAFER-01",
        observed_at=datetime(2026, 1, 15, 9, tzinfo=UTC),
    )

    assert recorded.status == "running"
    assert recorded.source_interval == interval
    assert recorded.limitations == ()
    assert unknown.status == "unknown"
    assert unknown.source_interval is None
    assert unknown.limitations == ("no_recorded_equipment_state",)


def test_equipment_status_lookup_rejects_overlapping_recorded_states() -> None:
    intervals = tuple(
        EquipmentStateInterval(
            event_id=f"state-{index}",
            equipment_id="AOI-WAFER-01",
            status=status,
            started_at=start,
            ended_at=end,
        )
        for index, status, start, end in (
            (
                1,
                "running",
                datetime(2026, 1, 15, 8, tzinfo=UTC),
                datetime(2026, 1, 15, 10, tzinfo=UTC),
            ),
            (
                2,
                "warning",
                datetime(2026, 1, 15, 9, tzinfo=UTC),
                datetime(2026, 1, 15, 11, tzinfo=UTC),
            ),
        )
    )

    with pytest.raises(ValueError, match="overlapping Equipment State Intervals"):
        get_equipment_status_at(
            intervals=intervals,
            equipment_id="AOI-WAFER-01",
            observed_at=datetime(2026, 1, 15, 9, 30, tzinfo=UTC),
        )


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


def test_defect_distribution_reports_classified_shares_and_rank() -> None:
    scenario = load_synthetic_scenario(
        REPOSITORY_ROOT / "data/synthetic/aoi-wafer-inspection-v1.json"
    )

    distribution = summarize_defect_distribution(
        records=scenario.inspection_records,
        equipment_id="AOI-WAFER-01",
        time_range=TimeRange(
            start=datetime(2026, 1, 15, 13, tzinfo=UTC),
            end=datetime(2026, 1, 15, 17, tzinfo=UTC),
        ),
    )

    assert distribution.failed_wafers == 30
    assert distribution.classified_defect_count == 30
    assert distribution.unclassified_failed_wafers == 0
    assert distribution.items[0].category == "edge-chip"
    assert distribution.items[0].count == 19
    assert distribution.items[0].share == pytest.approx(19 / 30)
    assert distribution.items[0].rank == 1
    assert distribution.items[1].category == "scratch"
    assert distribution.items[1].count == 11
    assert distribution.items[1].share == pytest.approx(11 / 30)
    assert distribution.items[1].rank == 2
    assert distribution.limitations == ()


def test_defect_distribution_reports_incomplete_classification() -> None:
    record = InspectionRecord(
        record_id="inspection-001",
        equipment_id="AOI-WAFER-01",
        lot_id="LOT-DEMO-001",
        observed_at=datetime(2026, 1, 15, 15, tzinfo=UTC),
        inspected_wafers=10,
        passed_wafers=6,
        failed_wafers=4,
        defect_counts=(DefectCount(category="scratch", count=3),),
    )

    distribution = summarize_defect_distribution(
        records=(record,),
        equipment_id="AOI-WAFER-01",
        time_range=TimeRange(
            start=datetime(2026, 1, 15, 14, tzinfo=UTC),
            end=datetime(2026, 1, 15, 16, tzinfo=UTC),
        ),
    )

    assert distribution.unclassified_failed_wafers == 1
    assert distribution.limitations == ("incomplete_defect_classification",)


def test_defect_distribution_reports_empty_time_range() -> None:
    distribution = summarize_defect_distribution(
        records=(),
        equipment_id="AOI-WAFER-01",
        time_range=TimeRange(
            start=datetime(2026, 1, 15, 14, tzinfo=UTC),
            end=datetime(2026, 1, 15, 16, tzinfo=UTC),
        ),
    )

    assert distribution.items == ()
    assert distribution.failed_wafers == 0
    assert distribution.limitations == ("no_inspection_records",)


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
    assert scenario.equipment_state_intervals[1].status == "warning"
    assert scenario.equipment_state_intervals[1].started_at == datetime(
        2026, 1, 15, 15, tzinfo=UTC
    )
    assert scenario.causal_claim is None


def test_synthetic_loader_rejects_overlapping_equipment_states(tmp_path) -> None:
    source = REPOSITORY_ROOT / "data/synthetic/aoi-wafer-inspection-v1.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["equipment_state_intervals"].append(
        {
            "event_id": "state-overlap",
            "status": "maintenance",
            "started_at": "2026-01-15T14:30:00Z",
            "ended_at": "2026-01-15T15:30:00Z",
            "reason_code": "SYNTHETIC-MAINTENANCE",
        }
    )
    candidate = tmp_path / "overlapping.json"
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="overlapping Equipment State Intervals"):
        load_synthetic_scenario(candidate)


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
