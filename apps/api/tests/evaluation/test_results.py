import pytest
from pydantic import ValidationError

from industrial_agent.evaluation.models import EvaluationDimension
from industrial_agent.evaluation.results import (
    DimensionAssertion,
    ScenarioResult,
    StageObservation,
    aggregate_results,
)


def test_aggregate_results_reports_dimensions_without_a_composite_score() -> None:
    result = ScenarioResult(
        scenario_id="en-general-greeting",
        passed=False,
        assertions=(
            DimensionAssertion(
                dimension=EvaluationDimension.ROUTE_ACCURACY,
                expected="general",
                observed="general",
                passed=True,
                reason="route matched",
            ),
            DimensionAssertion(
                dimension=EvaluationDimension.CITATION_CORRECTNESS,
                expected="valid source",
                observed="missing source",
                passed=False,
                reason="citation was missing",
            ),
        ),
        stages=(StageObservation(name="route", elapsed_ms=1.25),),
    )

    summary = aggregate_results((result,))

    assert summary.overall_passed is False
    assert summary.dimensions[0].dimension == "route_accuracy"
    assert summary.dimensions[0].passed == 1
    assert summary.dimensions[1].dimension == "citation_correctness"
    assert summary.dimensions[1].failed == 1
    assert "score" not in summary.model_dump()


def test_scenario_result_rejects_pass_state_that_hides_failed_assertion() -> None:
    with pytest.raises(ValidationError, match="passed must match assertions"):
        ScenarioResult(
            scenario_id="unsafe-result",
            passed=True,
            assertions=(
                DimensionAssertion(
                    dimension=EvaluationDimension.SAFE_FAILURE_CORRECTNESS,
                    expected="unsupported",
                    observed="general",
                    passed=False,
                    reason="unsafe route",
                ),
            ),
            stages=(),
        )


def test_retrieval_top_one_preserves_the_approved_eight_of_nine_threshold() -> None:
    results = tuple(
        ScenarioResult(
            scenario_id=f"retrieval-{index}",
            passed=index != 8,
            assertions=(
                DimensionAssertion(
                    dimension=EvaluationDimension.RETRIEVAL_TOP_1,
                    expected="expected document first",
                    observed=(
                        "expected document first" if index != 8 else "ranked second"
                    ),
                    passed=index != 8,
                    reason="retrieval rank checked",
                ),
            ),
            stages=(),
        )
        for index in range(9)
    )

    summary = aggregate_results(results)

    assert summary.dimensions[0].passed == 8
    assert summary.dimensions[0].failed == 1
    assert summary.dimensions[0].threshold_passed is True
    assert summary.overall_passed is True
