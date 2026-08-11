import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from industrial_agent.evaluation.fixtures import (
    load_evaluation_suite,
    load_formal_evaluation_suite,
)
from industrial_agent.evaluation.models import (
    AdapterAction,
    EvaluationDimension,
    ScenarioCategory,
)

SCENARIO = {
    "id": "en-general-greeting",
    "description": "Routes an explicit greeting.",
    "language": "en",
    "category": "general_response",
    "input": {"message": "Hello, what can you do?"},
    "adapter_script": {"actions": []},
    "expected": {"route": "general"},
    "dimensions": ["route_accuracy"],
    "safety_critical": False,
}


def test_formal_suite_uses_the_approved_closed_vocabularies() -> None:
    assert {item.value for item in ScenarioCategory} == {
        "production_summary",
        "equipment_status",
        "defect_distribution",
        "document_retrieval",
        "general_response",
        "combined_evidence",
        "missing_context",
        "unsupported_request",
        "empty_evidence",
        "safe_domain_error",
        "classifier_retry",
        "classifier_fallback",
        "citation_validation",
        "unsupported_claim_rejection",
    }
    assert {item.value for item in EvaluationDimension} == {
        "route_accuracy",
        "tool_selection_accuracy",
        "argument_resolution_accuracy",
        "evidence_parity",
        "retrieval_top_1",
        "retrieval_top_3",
        "citation_correctness",
        "safe_failure_correctness",
        "unsupported_claim_rejection",
        "retry_fallback_correctness",
    }
    assert {item.value for item in AdapterAction} == {
        "return_route",
        "transient_classifier_failure",
        "exhaust_classifier_retry",
        "return_grounded_answer",
        "return_invalid_numeric_claim",
        "return_invalid_citation",
        "return_general_answer",
        "fail_manufacturing",
        "fail_documents",
        "return_empty_documents",
    }


def test_load_evaluation_suite_returns_one_strict_typed_scenario(
    tmp_path: Path,
) -> None:
    fixture = tmp_path / "suite.json"
    fixture.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "suite_id": "formal-v1",
                "scenarios": [SCENARIO],
            }
        ),
        encoding="utf-8",
    )

    suite = load_evaluation_suite(fixture)

    assert suite.schema_version == "1"
    assert suite.suite_id == "formal-v1"
    assert suite.scenarios[0].id == "en-general-greeting"
    assert suite.scenarios[0].input.message == "Hello, what can you do?"
    assert suite.scenarios[0].dimensions == ("route_accuracy",)


def test_load_evaluation_suite_rejects_duplicate_scenario_ids(
    tmp_path: Path,
) -> None:
    fixture = tmp_path / "suite.json"
    fixture.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "suite_id": "formal-v1",
                "scenarios": [SCENARIO, SCENARIO],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="scenario IDs must be unique"):
        load_evaluation_suite(fixture)


def test_load_evaluation_suite_rejects_a_scenario_without_dimensions(
    tmp_path: Path,
) -> None:
    fixture = tmp_path / "suite.json"
    fixture.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "suite_id": "formal-v1",
                "scenarios": [{**SCENARIO, "dimensions": []}],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        load_evaluation_suite(fixture)


def test_load_evaluation_suite_preserves_retrieval_expectations(
    tmp_path: Path,
) -> None:
    fixture = tmp_path / "suite.json"
    retrieval = {
        "id": "alarm-optical",
        "description": "Targets the alarm recovery checks.",
        "language": "en",
        "category": "document_retrieval",
        "input": {"message": "optical lens cover illumination connector"},
        "adapter_script": {"actions": []},
        "expected": {
            "route": "document_search",
            "retrieval_kind": "single_document",
            "document_ids": ["aoi-alarm-guide"],
            "source_id": (
                "aoi-alarm-guide:optical-signal-low-recovery-boundary:001"
            ),
        },
        "dimensions": [
            "route_accuracy",
            "retrieval_top_1",
            "retrieval_top_3",
        ],
        "safety_critical": False,
    }
    fixture.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "suite_id": "formal-v1",
                "scenarios": [retrieval],
            }
        ),
        encoding="utf-8",
    )

    scenario = load_evaluation_suite(fixture).scenarios[0]

    assert scenario.category == "document_retrieval"
    assert scenario.expected.retrieval_kind == "single_document"
    assert scenario.expected.document_ids == ("aoi-alarm-guide",)
    assert scenario.expected.source_id.endswith(":001")


def test_load_evaluation_suite_rejects_retrieval_expectations_on_general_case(
    tmp_path: Path,
) -> None:
    fixture = tmp_path / "suite.json"
    invalid = {
        **SCENARIO,
        "expected": {
            "route": "general",
            "retrieval_kind": "single_document",
            "document_ids": ["aoi-alarm-guide"],
        },
    }
    fixture.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "suite_id": "formal-v1",
                "scenarios": [invalid],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValidationError,
        match="retrieval expectations require a document retrieval category",
    ):
        load_evaluation_suite(fixture)


def test_formal_suite_preserves_existing_retrieval_scenario_distribution() -> None:
    suite = load_formal_evaluation_suite()
    retrieval = [
        scenario
        for scenario in suite.scenarios
        if scenario.category == "document_retrieval"
    ]

    assert len(retrieval) == 12
    assert sum(
        scenario.expected.retrieval_kind == "single_document"
        for scenario in retrieval
    ) == 9
    assert sum(
        scenario.expected.retrieval_kind == "confusable"
        for scenario in retrieval
    ) == 2
    assert sum(
        scenario.expected.retrieval_kind == "unrelated"
        for scenario in retrieval
    ) == 1
    assert {scenario.id for scenario in retrieval} >= {
        "alarm-optical",
        "confusable-shared-time",
        "unrelated",
    }


def test_formal_suite_has_the_approved_matrix_size_and_coverage() -> None:
    suite = load_formal_evaluation_suite()

    assert len(suite.scenarios) == 45
    assert {scenario.language for scenario in suite.scenarios} == {"en", "zh-TW"}
    assert {scenario.category for scenario in suite.scenarios} == set(
        ScenarioCategory
    )
    covered_dimensions = {
        dimension
        for scenario in suite.scenarios
        for dimension in scenario.dimensions
    }
    assert covered_dimensions == set(EvaluationDimension)


def test_load_evaluation_suite_preserves_context_and_tool_expectations(
    tmp_path: Path,
) -> None:
    fixture = tmp_path / "suite.json"
    production = {
        "id": "en-production-summary",
        "description": "Resolves saved synthetic production context.",
        "language": "en",
        "category": "production_summary",
        "input": {
            "message": "Show the production summary.",
            "saved_context": {
                "equipment_id": "AOI-WAFER-01",
                "lot_id": "LOT-DEMO-001",
                "time_preset": "last_4_hours",
            },
        },
        "adapter_script": {"actions": ["return_grounded_answer"]},
        "expected": {
            "route": "production_summary",
            "tool": "get_production_summary",
            "arguments": {
                "equipment_id": "AOI-WAFER-01",
                "lot_id": "LOT-DEMO-001",
            },
        },
        "dimensions": [
            "route_accuracy",
            "tool_selection_accuracy",
            "argument_resolution_accuracy",
            "evidence_parity",
        ],
        "safety_critical": False,
    }
    fixture.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "suite_id": "formal-v1",
                "scenarios": [production],
            }
        ),
        encoding="utf-8",
    )

    scenario = load_evaluation_suite(fixture).scenarios[0]

    assert scenario.input.saved_context.equipment_id == "AOI-WAFER-01"
    assert scenario.input.saved_context.time_preset == "last_4_hours"
    assert scenario.expected.tool == "get_production_summary"
    assert scenario.expected.arguments["lot_id"] == "LOT-DEMO-001"


def test_load_evaluation_suite_rejects_tool_that_conflicts_with_category(
    tmp_path: Path,
) -> None:
    fixture = tmp_path / "suite.json"
    invalid = {
        **SCENARIO,
        "category": "production_summary",
        "expected": {
            "route": "production_summary",
            "tool": "search_documents",
        },
    }
    fixture.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "suite_id": "formal-v1",
                "scenarios": [invalid],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="tool does not match scenario category"):
        load_evaluation_suite(fixture)


def test_load_evaluation_suite_rejects_contradictory_adapter_actions(
    tmp_path: Path,
) -> None:
    fixture = tmp_path / "suite.json"
    invalid = {
        **SCENARIO,
        "category": "classifier_fallback",
        "adapter_script": {
            "actions": ["exhaust_classifier_retry", "return_route"]
        },
    }
    fixture.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "suite_id": "formal-v1",
                "scenarios": [invalid],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="adapter actions are contradictory"):
        load_evaluation_suite(fixture)
