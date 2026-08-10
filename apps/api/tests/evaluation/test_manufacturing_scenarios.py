import pytest

from industrial_agent.evaluation.models import EvaluationScenario
from industrial_agent.evaluation.runner import run_scenario


@pytest.mark.parametrize(
    ("payload", "expected_kind"),
    [
        (
            {
                "id": "en-equipment-status-evidence",
                "description": "Reads one recorded warning state.",
                "language": "en",
                "category": "equipment_status",
                "input": {
                    "message": "What is the equipment status for AOI-WAFER-01 today?"
                },
                "adapter_script": {
                    "actions": ["return_grounded_answer"],
                    "tool_call": {
                        "name": "get_equipment_status",
                        "arguments": {
                            "equipment_id": "AOI-WAFER-01",
                            "at": "2026-01-15T15:30:00Z",
                        },
                    },
                },
                "expected": {
                    "route": "equipment_status",
                    "tool": "get_equipment_status",
                    "arguments": {
                        "equipment_id": "AOI-WAFER-01",
                        "at": "2026-01-15T15:30:00Z",
                    },
                    "evidence": {
                        "status": "warning",
                        "reason_code": "SYNTHETIC-RECORDED-WARNING",
                    },
                },
                "dimensions": [
                    "route_accuracy",
                    "tool_selection_accuracy",
                    "argument_resolution_accuracy",
                    "evidence_parity",
                ],
                "safety_critical": False,
            },
            "equipment_status",
        ),
        (
            {
                "id": "en-defect-distribution-evidence",
                "description": "Ranks recorded synthetic defect categories.",
                "language": "en",
                "category": "defect_distribution",
                "input": {
                    "message": "Show the defect distribution for AOI-WAFER-01 today."
                },
                "adapter_script": {
                    "actions": ["return_grounded_answer"],
                    "tool_call": {
                        "name": "get_defect_distribution",
                        "arguments": {
                            "equipment_id": "AOI-WAFER-01",
                            "lot_id": "LOT-DEMO-001",
                            "start": "2026-01-15T13:00:00Z",
                            "end": "2026-01-15T17:00:00Z",
                        },
                    },
                },
                "expected": {
                    "route": "defect_distribution",
                    "tool": "get_defect_distribution",
                    "arguments": {
                        "equipment_id": "AOI-WAFER-01",
                        "lot_id": "LOT-DEMO-001",
                        "start": "2026-01-15T13:00:00Z",
                        "end": "2026-01-15T17:00:00Z",
                    },
                    "evidence": {"failed_wafers": 30, "classified_defect_count": 30},
                },
                "dimensions": [
                    "route_accuracy",
                    "tool_selection_accuracy",
                    "argument_resolution_accuracy",
                    "evidence_parity",
                ],
                "safety_critical": False,
            },
            "defect_distribution",
        ),
    ],
)
def test_run_scenario_records_manufacturing_evidence(
    payload: dict[str, object], expected_kind: str
) -> None:
    result = run_scenario(EvaluationScenario.model_validate(payload))

    assert result.passed is True
    assert result.trace.evidence_kind == expected_kind
    assert result.trace.evidence_sufficient is True


@pytest.mark.parametrize(
    ("scenario_id", "arguments", "expected", "expected_error"),
    [
        (
            "en-empty-production-evidence",
            {
                "equipment_id": "AOI-WAFER-01",
                "start": "2026-01-15T18:00:00Z",
                "end": "2026-01-15T19:00:00Z",
            },
            {
                "evidence": {
                    "inspected_wafers": 0,
                    "yield_rate": None,
                    "limitations": ["no_inspection_records"],
                },
                "evidence_sufficient": False,
            },
            None,
        ),
        (
            "en-unknown-production-equipment",
            {
                "equipment_id": "AOI-WAFER-99",
                "start": "2026-01-15T15:00:00Z",
                "end": "2026-01-15T16:00:00Z",
            },
            {"evidence_sufficient": False, "tool_error": "UNKNOWN_EQUIPMENT"},
            "UNKNOWN_EQUIPMENT",
        ),
    ],
)
def test_run_scenario_preserves_empty_evidence_and_safe_tool_errors(
    scenario_id: str,
    arguments: dict[str, object],
    expected: dict[str, object],
    expected_error: str | None,
) -> None:
    scenario = EvaluationScenario.model_validate(
        {
            "id": scenario_id,
            "description": "Checks a safe production evidence boundary.",
            "language": "en",
            "category": (
                "empty_evidence" if expected_error is None else "safe_domain_error"
            ),
            "input": {
                "message": "Show the production summary for AOI-WAFER-01 today."
            },
            "adapter_script": {
                "actions": [],
                "tool_call": {
                    "name": "get_production_summary",
                    "arguments": arguments,
                },
            },
            "expected": {
                "route": "production_summary",
                "tool": "get_production_summary",
                "arguments": arguments,
                **expected,
            },
            "dimensions": [
                "route_accuracy",
                "evidence_parity",
                "safe_failure_correctness",
            ],
            "safety_critical": True,
        }
    )

    result = run_scenario(scenario)

    assert result.passed is True
    assert result.trace.evidence_sufficient is False
    assert result.trace.failure_class == expected_error
