"""Strict contracts for the versioned deterministic evaluation suite."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from industrial_agent.domain.routing import (
    DecisionSource,
    ExtractedContext,
    RouteCandidate,
    RouteIntent,
    SafeAction,
)


class EvaluationModel(BaseModel):
    """Frozen evaluation contract that rejects undeclared fixture fields."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class ScenarioCategory(StrEnum):
    """Closed first-slice category vocabulary."""

    PRODUCTION_SUMMARY = "production_summary"
    EQUIPMENT_STATUS = "equipment_status"
    DEFECT_DISTRIBUTION = "defect_distribution"
    GENERAL_RESPONSE = "general_response"
    DOCUMENT_RETRIEVAL = "document_retrieval"
    COMBINED_EVIDENCE = "combined_evidence"
    MISSING_CONTEXT = "missing_context"
    UNSUPPORTED_REQUEST = "unsupported_request"
    EMPTY_EVIDENCE = "empty_evidence"
    SAFE_DOMAIN_ERROR = "safe_domain_error"
    CLASSIFIER_RETRY = "classifier_retry"
    CLASSIFIER_FALLBACK = "classifier_fallback"
    CITATION_VALIDATION = "citation_validation"
    UNSUPPORTED_CLAIM_REJECTION = "unsupported_claim_rejection"


class EvaluationDimension(StrEnum):
    """Closed dimensions supported by the first fixture slice."""

    ROUTE_ACCURACY = "route_accuracy"
    TOOL_SELECTION_ACCURACY = "tool_selection_accuracy"
    ARGUMENT_RESOLUTION_ACCURACY = "argument_resolution_accuracy"
    EVIDENCE_PARITY = "evidence_parity"
    RETRIEVAL_TOP_1 = "retrieval_top_1"
    RETRIEVAL_TOP_3 = "retrieval_top_3"
    CITATION_CORRECTNESS = "citation_correctness"
    SAFE_FAILURE_CORRECTNESS = "safe_failure_correctness"
    UNSUPPORTED_CLAIM_REJECTION = "unsupported_claim_rejection"
    RETRY_FALLBACK_CORRECTNESS = "retry_fallback_correctness"


class AdapterAction(StrEnum):
    """Closed deterministic behavior available to fixture scripts."""

    RETURN_ROUTE = "return_route"
    TRANSIENT_CLASSIFIER_FAILURE = "transient_classifier_failure"
    EXHAUST_CLASSIFIER_RETRY = "exhaust_classifier_retry"
    RETURN_GROUNDED_ANSWER = "return_grounded_answer"
    RETURN_INVALID_NUMERIC_CLAIM = "return_invalid_numeric_claim"
    RETURN_INVALID_CITATION = "return_invalid_citation"
    RETURN_GENERAL_ANSWER = "return_general_answer"
    FAIL_MANUFACTURING = "fail_manufacturing"
    FAIL_DOCUMENTS = "fail_documents"
    RETURN_EMPTY_DOCUMENTS = "return_empty_documents"


class ExpectedTool(StrEnum):
    """Application-owned tools that formal scenarios may select."""

    PRODUCTION_SUMMARY = "get_production_summary"
    EQUIPMENT_STATUS = "get_equipment_status"
    DEFECT_DISTRIBUTION = "get_defect_distribution"
    DOCUMENT_SEARCH = "search_documents"


class RetrievalKind(StrEnum):
    """Existing retrieval scenario families preserved by the formal suite."""

    SINGLE_DOCUMENT = "single_document"
    CONFUSABLE = "confusable"
    UNRELATED = "unrelated"


class ScenarioInput(EvaluationModel):
    """User input for one formal evaluation scenario."""

    message: str = Field(min_length=1)
    current_context: ExtractedContext = ExtractedContext()
    saved_context: ExtractedContext = ExtractedContext()


class ScriptedToolCall(EvaluationModel):
    """Deterministic tool input kept separate from expected observations."""

    name: ExpectedTool
    arguments: dict[str, JsonValue] = Field(default_factory=dict)


class AdapterScript(EvaluationModel):
    """Closed deterministic actions consumed by evaluation adapters."""

    actions: tuple[AdapterAction, ...] = ()
    candidate: RouteCandidate | None = None
    tool_call: ScriptedToolCall | None = None
    answer: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def reject_contradictory_actions(self) -> "AdapterScript":
        actions = set(self.actions)
        if {
            AdapterAction.EXHAUST_CLASSIFIER_RETRY,
            AdapterAction.RETURN_ROUTE,
        } <= actions:
            raise ValueError("adapter actions are contradictory")
        if AdapterAction.RETURN_ROUTE in actions and self.candidate is None:
            raise ValueError("return_route requires a classifier candidate")
        return self


class ScenarioExpectation(EvaluationModel):
    """Typed expected route for the first evaluation tracer."""

    route: RouteIntent
    decision_source: DecisionSource | None = None
    retry_count: int | None = Field(default=None, ge=0, le=1)
    fallback_used: bool | None = None
    safe_action: SafeAction | None = None
    response_text: str | None = None
    tool: ExpectedTool | None = None
    arguments: dict[str, JsonValue] = Field(default_factory=dict)
    evidence: dict[str, JsonValue] = Field(default_factory=dict)
    evidence_sufficient: bool | None = None
    tool_error: str | None = None
    answer_accepted: bool | None = None
    retrieval_kind: RetrievalKind | None = None
    document_ids: tuple[str, ...] = ()
    source_id: str | None = None
    manufacturing_status: Literal["succeeded", "empty", "failed"] | None = None
    document_status: Literal["succeeded", "empty", "failed"] | None = None
    query_contains: tuple[str, ...] = ()


class EvaluationScenario(EvaluationModel):
    """One versioned formal evaluation scenario."""

    id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str = Field(min_length=1)
    language: Literal["en", "zh-TW"]
    category: ScenarioCategory
    input: ScenarioInput
    adapter_script: AdapterScript
    expected: ScenarioExpectation
    dimensions: tuple[EvaluationDimension, ...] = Field(min_length=1)
    safety_critical: bool

    @model_validator(mode="after")
    def match_expectations_to_category(self) -> "EvaluationScenario":
        has_retrieval_expectation = any(
            (
                self.expected.retrieval_kind is not None,
                bool(self.expected.document_ids),
                self.expected.source_id is not None,
            )
        )
        if (
            has_retrieval_expectation
            and self.category is not ScenarioCategory.DOCUMENT_RETRIEVAL
        ):
            raise ValueError(
                "retrieval expectations require a document retrieval category"
            )
        expected_tool = {
            ScenarioCategory.PRODUCTION_SUMMARY: ExpectedTool.PRODUCTION_SUMMARY,
            ScenarioCategory.EQUIPMENT_STATUS: ExpectedTool.EQUIPMENT_STATUS,
            ScenarioCategory.DEFECT_DISTRIBUTION: ExpectedTool.DEFECT_DISTRIBUTION,
            ScenarioCategory.DOCUMENT_RETRIEVAL: ExpectedTool.DOCUMENT_SEARCH,
        }.get(self.category)
        if (
            expected_tool is not None
            and self.expected.tool is not None
            and self.expected.tool is not expected_tool
        ):
            raise ValueError("tool does not match scenario category")
        return self


class EvaluationSuite(EvaluationModel):
    """Top-level versioned deterministic evaluation fixture."""

    schema_version: Literal["1"]
    suite_id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    scenarios: tuple[EvaluationScenario, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def require_unique_scenario_ids(self) -> "EvaluationSuite":
        ids = tuple(scenario.id for scenario in self.scenarios)
        if len(ids) != len(set(ids)):
            raise ValueError("scenario IDs must be unique")
        return self
