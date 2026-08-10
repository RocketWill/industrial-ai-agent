"""Typed scenario traces and per-dimension evaluation aggregation."""

from enum import StrEnum

from pydantic import Field, JsonValue, model_validator

from industrial_agent.domain.routing import DecisionSource, RouteIntent, SafeAction
from industrial_agent.evaluation.models import (
    EvaluationDimension,
    EvaluationModel,
    ExpectedTool,
)


class StageName(StrEnum):
    """Stable workflow stages observable without changing production state."""

    ROUTE = "route"
    ARGUMENT_RESOLUTION = "argument_resolution"
    TOOL_OR_RETRIEVAL = "tool_or_retrieval"
    EVIDENCE_VALIDATION = "evidence_validation"
    ANSWER_VALIDATION = "answer_validation"
    TOTAL = "total"


class StageObservation(EvaluationModel):
    """One non-negative local elapsed-time observation."""

    name: StageName
    elapsed_ms: float = Field(ge=0)


class DimensionAssertion(EvaluationModel):
    """One independently diagnosable scenario assertion."""

    dimension: EvaluationDimension
    expected: JsonValue
    observed: JsonValue
    passed: bool
    reason: str = Field(min_length=1)


class ExecutionTrace(EvaluationModel):
    """Evaluation-owned trace assembled from stable application seams."""

    route: RouteIntent | None = None
    decision_source: DecisionSource | None = None
    retry_count: int = Field(default=0, ge=0)
    fallback_used: bool = False
    safe_action: SafeAction | None = None
    response_text: str | None = None
    tool: ExpectedTool | None = None
    arguments: dict[str, JsonValue] = Field(default_factory=dict)
    evidence_kind: str | None = None
    evidence_sufficient: bool | None = None
    limitations: tuple[str, ...] = ()
    citation_ids: tuple[str, ...] = ()
    answer_validation: str | None = None
    final_outcome: str | None = None
    failure_class: str | None = None


class ScenarioResult(EvaluationModel):
    """Immutable formal result for one scenario."""

    scenario_id: str
    passed: bool
    trace: ExecutionTrace = ExecutionTrace()
    assertions: tuple[DimensionAssertion, ...] = Field(min_length=1)
    stages: tuple[StageObservation, ...]
    failure: str | None = None

    @model_validator(mode="after")
    def match_pass_state_to_assertions(self) -> "ScenarioResult":
        if self.passed != all(assertion.passed for assertion in self.assertions):
            raise ValueError("passed must match assertions")
        return self


class DimensionSummary(EvaluationModel):
    """Aggregate counts for one applicable evaluation dimension."""

    dimension: EvaluationDimension
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    total: int = Field(ge=0)
    threshold_passed: bool


class EvaluationSummary(EvaluationModel):
    """Separate dimension outcomes without a weighted composite score."""

    overall_passed: bool
    dimensions: tuple[DimensionSummary, ...]


class EvaluationRun(EvaluationModel):
    """One complete or filtered suite execution before serialization."""

    partial: bool
    scenario_filter: str | None = None
    results: tuple[ScenarioResult, ...]
    summary: EvaluationSummary
    suite_failures: tuple[str, ...] = ()


def aggregate_results(results: tuple[ScenarioResult, ...]) -> EvaluationSummary:
    """Aggregate applicable assertions in stable dimension vocabulary order."""
    dimensions: list[DimensionSummary] = []
    for dimension in EvaluationDimension:
        assertions = tuple(
            assertion
            for result in results
            for assertion in result.assertions
            if assertion.dimension is dimension
        )
        if not assertions:
            continue
        passed = sum(assertion.passed for assertion in assertions)
        failed = len(assertions) - passed
        threshold_passed = (
            passed * 9 >= len(assertions) * 8
            if dimension is EvaluationDimension.RETRIEVAL_TOP_1
            else failed == 0
        )
        dimensions.append(
            DimensionSummary(
                dimension=dimension,
                passed=passed,
                failed=failed,
                total=len(assertions),
                threshold_passed=threshold_passed,
            )
        )
    return EvaluationSummary(
        overall_passed=bool(dimensions)
        and all(item.threshold_passed for item in dimensions),
        dimensions=tuple(dimensions),
    )
