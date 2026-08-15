"""Execute deterministic formal scenarios through application-owned seams."""

from time import perf_counter
from uuid import UUID

from industrial_agent.evaluation.adapters import DeterministicClassifierAdapter
from industrial_agent.evaluation.models import (
    EvaluationDimension,
    EvaluationScenario,
    EvaluationSuite,
    RetrievalKind,
    ScenarioCategory,
)
from industrial_agent.evaluation.results import (
    DimensionAssertion,
    EvaluationRun,
    ExecutionTrace,
    ScenarioResult,
    StageObservation,
    aggregate_results,
)
from industrial_agent.graph.combined import (
    CombinedToolUnavailable,
    execute_combined_evidence,
)
from industrial_agent.graph.state import EvidenceState, GraphState
from industrial_agent.graph.workflow import (
    execute_defect_distribution_tool,
    execute_document_search_tool,
    execute_equipment_status_tool,
    execute_production_tool,
    resolve_defect_distribution_request,
    resolve_equipment_status_request,
    resolve_production_request,
)
from industrial_agent.llm.types import ChatMessage, CompletionResult, ToolCall
from industrial_agent.schemas.context import WorkspaceContextRead
from industrial_agent.services.evidence import (
    validate_answer,
    validate_combined_answer,
    validate_evidence,
)
from industrial_agent.services.routing import route_exchange
from industrial_agent.services.routing_classifier import RoutingClassifier
from industrial_agent.tools.document_search import (
    DocumentSearchRequest,
    DocumentSearchResult,
    search_documents,
)


class _UnusedClassifierAdapter:
    def complete_with_tools(self, *args: object, **kwargs: object) -> None:
        raise AssertionError("deterministic route unexpectedly called classifier")


class EvaluationRunError(ValueError):
    """Report a safe, user-correctable suite invocation error."""


def run_suite(
    suite: EvaluationSuite, *, scenario_id: str | None = None
) -> EvaluationRun:
    """Run selected scenarios while isolating unexpected scenario failures."""
    scenarios = suite.scenarios
    if scenario_id is not None:
        scenarios = tuple(item for item in scenarios if item.id == scenario_id)
        if not scenarios:
            raise EvaluationRunError(f"Unknown scenario: {scenario_id}")
    results: list[ScenarioResult] = []
    suite_failures: list[str] = []
    for scenario in scenarios:
        try:
            results.append(run_scenario(scenario))
        except Exception as error:  # noqa: BLE001 - suite must isolate scenarios
            suite_failures.append(scenario.id)
            results.append(
                ScenarioResult(
                    scenario_id=scenario.id,
                    passed=False,
                    trace=ExecutionTrace(failure_class=type(error).__name__),
                    assertions=(
                        DimensionAssertion(
                            dimension=scenario.dimensions[0],
                            expected="completed",
                            observed="scenario_exception",
                            passed=False,
                            reason="scenario execution failed",
                        ),
                    ),
                    stages=(StageObservation(name="total", elapsed_ms=0),),
                    failure="Scenario execution failed.",
                )
            )
    frozen_results = tuple(results)
    return EvaluationRun(
        partial=scenario_id is not None,
        scenario_filter=scenario_id,
        results=frozen_results,
        summary=aggregate_results(frozen_results),
        suite_failures=tuple(suite_failures),
    )


def run_scenario(scenario: EvaluationScenario) -> ScenarioResult:
    """Run one validated deterministic scenario and record typed observations."""
    if scenario.category is ScenarioCategory.DOCUMENT_RETRIEVAL:
        return _run_retrieval_scenario(scenario)
    started = perf_counter()
    route_started = perf_counter()
    adapter = (
        DeterministicClassifierAdapter(scenario.adapter_script)
        if scenario.adapter_script.actions
        else _UnusedClassifierAdapter()
    )
    classifier = RoutingClassifier(adapter)  # type: ignore[arg-type]
    outcome = route_exchange(
        latest_question=scenario.input.message,
        classifier=classifier,
        current_context=scenario.input.current_context,
        saved_context=scenario.input.saved_context,
    )
    route_elapsed = (perf_counter() - route_started) * 1000
    observed = outcome.decision.intent.value
    expected = scenario.expected.route.value
    route_passed = observed == expected
    stages = [StageObservation(name="route", elapsed_ms=route_elapsed)]
    assertions: list[DimensionAssertion] = [
        DimensionAssertion(
            dimension=EvaluationDimension.ROUTE_ACCURACY,
            expected=expected,
            observed=observed,
            passed=route_passed,
            reason="route matched" if route_passed else "route did not match",
        )
    ]
    trace_values: dict[str, object] = {
        "route": outcome.decision.intent,
        "decision_source": outcome.decision.decision_source,
        "retry_count": outcome.decision.retry_count,
        "fallback_used": outcome.decision.fallback_state.value == "used",
        "safe_action": outcome.decision.safe_action,
        "response_text": outcome.response_text,
        "final_outcome": outcome.decision.safe_action.value,
    }
    if scenario.category is ScenarioCategory.COMBINED_EVIDENCE:
        return _run_combined_scenario(
            scenario,
            outcome=outcome,
            started=started,
            stages=stages,
            assertions=assertions,
            trace_values=trace_values,
        )
    if (
        EvaluationDimension.SAFE_FAILURE_CORRECTNESS in scenario.dimensions
        and (
            scenario.expected.safe_action is not None
            or scenario.expected.response_text is not None
        )
    ):
        expected_failure = {
            "safe_action": (
                scenario.expected.safe_action.value
                if scenario.expected.safe_action is not None
                else None
            ),
            "response_text": scenario.expected.response_text,
        }
        observed_failure = {
            "safe_action": outcome.decision.safe_action.value,
            "response_text": outcome.response_text,
        }
        failure_passed = observed_failure == expected_failure
        assertions.append(
            DimensionAssertion(
                dimension=EvaluationDimension.SAFE_FAILURE_CORRECTNESS,
                expected=expected_failure,
                observed=observed_failure,
                passed=failure_passed,
                reason=(
                    "safe outcome matched"
                    if failure_passed
                    else "safe outcome did not match"
                ),
            )
        )
    if scenario.adapter_script.tool_call is not None:
        tool_started = perf_counter()
        call_script = scenario.adapter_script.tool_call
        call = ToolCall(
            call_id=f"evaluation-{scenario.id}",
            name=call_script.name.value,
            arguments=dict(call_script.arguments),
        )
        state = _graph_state(scenario)
        completion = CompletionResult(content=None, tool_calls=(call,))
        resolver, executor, evidence_field, evidence_kind = {
            "get_production_summary": (
                resolve_production_request,
                execute_production_tool,
                "production_summary",
                "production",
            ),
            "get_equipment_status": (
                resolve_equipment_status_request,
                execute_equipment_status_tool,
                "equipment_status",
                "equipment_status",
            ),
            "get_defect_distribution": (
                resolve_defect_distribution_request,
                execute_defect_distribution_tool,
                "defect_distribution",
                "defect_distribution",
            ),
            "search_documents": (
                _resolve_document_request,
                execute_document_search_tool,
                "document_search",
                "documents",
            ),
        }[call.name]
        resolved_request, _ = resolver(state, call)
        resolved_arguments = (
            resolved_request.model_dump(mode="json")
            if resolved_request is not None
            else {}
        )
        tool_state = executor(state, completion)
        evidence = tool_state.get("evidence") or EvidenceState()
        tool_error = evidence.tool_error.code if evidence.tool_error else None
        evidence_result = getattr(evidence, evidence_field)
        evidence_payload = (
            evidence_result.model_dump(mode="json")
            if evidence_result is not None
            else {}
        )
        stages.append(
            StageObservation(
                name="tool_or_retrieval",
                elapsed_ms=(perf_counter() - tool_started) * 1000,
            )
        )
        validation_started = perf_counter()
        evidence_decision = validate_evidence(outcome.decision, evidence)
        stages.append(
            StageObservation(
                name="evidence_validation",
                elapsed_ms=(perf_counter() - validation_started) * 1000,
            )
        )
        trace_values.update(
            {
                "tool": call_script.name,
                "arguments": resolved_arguments,
                "evidence_kind": evidence_kind,
                "evidence_sufficient": evidence_decision.sufficient,
                "limitations": tuple(evidence_payload.get("limitations", ())),
                "failure_class": tool_error,
            }
        )
        if call.name == "search_documents" and evidence_result is not None:
            trace_values["citation_ids"] = tuple(
                source.source_id for source in evidence_result.sources
            )
        if (
            EvaluationDimension.SAFE_FAILURE_CORRECTNESS in scenario.dimensions
            and scenario.expected.evidence_sufficient is not None
        ):
            expected_safe_evidence = {
                "evidence_sufficient": scenario.expected.evidence_sufficient,
                "tool_error": scenario.expected.tool_error,
            }
            observed_safe_evidence = {
                "evidence_sufficient": evidence_decision.sufficient,
                "tool_error": tool_error,
            }
            _append_comparison(
                assertions,
                scenario,
                EvaluationDimension.SAFE_FAILURE_CORRECTNESS,
                expected_safe_evidence,
                observed_safe_evidence,
                "safe evidence outcome",
            )
        if scenario.adapter_script.answer is not None:
            answer_started = perf_counter()
            answer_decision = validate_answer(
                outcome.decision,
                evidence,
                scenario.adapter_script.answer,
            )
            answer_accepted = answer_decision.sufficient
            stages.append(
                StageObservation(
                    name="answer_validation",
                    elapsed_ms=(perf_counter() - answer_started) * 1000,
                )
            )
            trace_values["answer_validation"] = (
                "accepted" if answer_accepted else "rejected"
            )
            _append_comparison(
                assertions,
                scenario,
                EvaluationDimension.UNSUPPORTED_CLAIM_REJECTION,
                scenario.expected.answer_accepted,
                answer_accepted,
                "answer acceptance",
            )
            _append_comparison(
                assertions,
                scenario,
                EvaluationDimension.CITATION_CORRECTNESS,
                scenario.expected.answer_accepted,
                answer_accepted,
                "citation acceptance",
            )
        _append_comparison(
            assertions,
            scenario,
            EvaluationDimension.TOOL_SELECTION_ACCURACY,
            scenario.expected.tool.value if scenario.expected.tool else None,
            call.name,
            "tool selection",
        )
        _append_comparison(
            assertions,
            scenario,
            EvaluationDimension.ARGUMENT_RESOLUTION_ACCURACY,
            scenario.expected.arguments,
            resolved_arguments,
            "resolved arguments",
        )
        expected_evidence = scenario.expected.evidence
        observed_evidence = {
            key: evidence_payload.get(key) for key in expected_evidence
        }
        _append_comparison(
            assertions,
            scenario,
            EvaluationDimension.EVIDENCE_PARITY,
            expected_evidence,
            observed_evidence,
            "evidence",
        )
    if EvaluationDimension.RETRY_FALLBACK_CORRECTNESS in scenario.dimensions:
        expected_retry = {
            "decision_source": (
                scenario.expected.decision_source.value
                if scenario.expected.decision_source is not None
                else None
            ),
            "retry_count": scenario.expected.retry_count,
            "fallback_used": scenario.expected.fallback_used,
        }
        observed_retry = {
            "decision_source": outcome.decision.decision_source.value,
            "retry_count": outcome.decision.retry_count,
            "fallback_used": outcome.decision.fallback_state.value == "used",
        }
        retry_passed = observed_retry == expected_retry
        assertions.append(
            DimensionAssertion(
                dimension=EvaluationDimension.RETRY_FALLBACK_CORRECTNESS,
                expected=expected_retry,
                observed=observed_retry,
                passed=retry_passed,
                reason=(
                    "retry and fallback matched"
                    if retry_passed
                    else "retry or fallback did not match"
                ),
            )
        )
    scenario_passed = all(assertion.passed for assertion in assertions)
    return ScenarioResult(
        scenario_id=scenario.id,
        passed=scenario_passed,
        trace=ExecutionTrace.model_validate(trace_values),
        assertions=tuple(assertions),
        stages=tuple(
            [
                *stages,
                StageObservation(
                    name="total", elapsed_ms=(perf_counter() - started) * 1000
                ),
            ]
        ),
    )


def _graph_state(scenario: EvaluationScenario) -> GraphState:
    context = scenario.input.saved_context
    preset_labels = {
        "last_1_hour": "Last 1 hour",
        "last_4_hours": "Last 4 hours",
        "last_8_hours": "Last 8 hours",
        "last_24_hours": "Last 24 hours",
    }
    return {
        "conversation_id": UUID(int=0),
        "messages": [ChatMessage(role="user", content=scenario.input.message)],
        "workspace_context": WorkspaceContextRead(
            environment="synthetic",
            device=context.equipment_id,
            lot=context.lot_id,
            time_range=(
                preset_labels.get(context.time_preset.value)
                if context.time_preset is not None
                else None
            ),
            data_source="synthetic_demo",
        ),
        "assistant_content": "",
        "suggested_actions": (),
        "execution_events": [],
        "evidence": None,
        "combined_evidence": None,
        "tool_call": None,
    }


def _run_combined_scenario(
    scenario: EvaluationScenario,
    *,
    outcome,
    started: float,
    stages: list[StageObservation],
    assertions: list[DimensionAssertion],
    trace_values: dict[str, object],
) -> ScenarioResult:
    def fail_manufacturing(_request):
        raise CombinedToolUnavailable("scripted manufacturing failure")

    def fail_documents(_request, *, service=None):
        del service
        raise CombinedToolUnavailable("scripted document failure")

    def empty_documents(request, *, service=None):
        del service
        return DocumentSearchResult(
            query=request.query, sources=(), limitations=("no_relevant_sources",)
        )

    actions = set(scenario.adapter_script.actions)
    kwargs: dict[str, object] = {}
    if "fail_manufacturing" in actions:
        kwargs.update(
            production_tool=fail_manufacturing,
            equipment_status_tool=fail_manufacturing,
            defect_distribution_tool=fail_manufacturing,
        )
    if "fail_documents" in actions:
        kwargs["document_search_tool"] = fail_documents
    if "return_empty_documents" in actions:
        kwargs["document_search_tool"] = empty_documents
    execution_started = perf_counter()
    combined = execute_combined_evidence(
        decision=outcome.decision,
        original_query=scenario.input.message,
        **kwargs,  # type: ignore[arg-type]
    )
    stages.append(
        StageObservation(
            name="tool_or_retrieval",
            elapsed_ms=(perf_counter() - execution_started) * 1000,
        )
    )
    tool = {
        "production": "get_production_summary",
        "equipment_status": "get_equipment_status",
        "defect_distribution": "get_defect_distribution",
    }[combined.manufacturing_kind.value]
    observed_evidence = {
        "manufacturing_status": combined.manufacturing.status.value,
        "document_status": combined.documents.status.value,
        "query_contains": [
            term
            for term in scenario.expected.query_contains
            if term in combined.document_query
        ],
    }
    expected_evidence = {
        "manufacturing_status": scenario.expected.manufacturing_status,
        "document_status": scenario.expected.document_status,
        "query_contains": list(scenario.expected.query_contains),
    }
    _append_comparison(
        assertions,
        scenario,
        EvaluationDimension.TOOL_SELECTION_ACCURACY,
        scenario.expected.tool.value if scenario.expected.tool else None,
        tool,
        "combined manufacturing tool",
    )
    _append_comparison(
        assertions,
        scenario,
        EvaluationDimension.EVIDENCE_PARITY,
        expected_evidence,
        observed_evidence,
        "combined evidence",
    )
    _append_comparison(
        assertions,
        scenario,
        EvaluationDimension.SAFE_FAILURE_CORRECTNESS,
        {
            "manufacturing_status": scenario.expected.manufacturing_status,
            "document_status": scenario.expected.document_status,
        },
        {
            "manufacturing_status": combined.manufacturing.status.value,
            "document_status": combined.documents.status.value,
        },
        "combined safe outcome",
    )
    if scenario.adapter_script.answer is not None:
        accepted = bool(
            validate_combined_answer(combined, scenario.adapter_script.answer)
        )
        _append_comparison(
            assertions,
            scenario,
            EvaluationDimension.CITATION_CORRECTNESS,
            scenario.expected.answer_accepted,
            accepted,
            "combined citation",
        )
        _append_comparison(
            assertions,
            scenario,
            EvaluationDimension.UNSUPPORTED_CLAIM_REJECTION,
            scenario.expected.answer_accepted,
            accepted,
            "combined claim",
        )
        trace_values["answer_validation"] = (
            "accepted" if accepted else "rejected"
        )
    trace_values.update(
        tool=tool,
        evidence_kind="combined",
        evidence_sufficient=any(
            path.status.value in {"succeeded", "empty"}
            for path in (combined.manufacturing, combined.documents)
        ),
        limitations=(),
        final_outcome="combined_evidence_evaluated",
    )
    passed = all(assertion.passed for assertion in assertions)
    return ScenarioResult(
        scenario_id=scenario.id,
        passed=passed,
        trace=ExecutionTrace.model_validate(trace_values),
        assertions=tuple(assertions),
        stages=tuple(
            [
                *stages,
                StageObservation(
                    name="total", elapsed_ms=(perf_counter() - started) * 1000
                ),
            ]
        ),
    )


def _resolve_document_request(
    state: GraphState, call: ToolCall
) -> tuple[DocumentSearchRequest | None, None]:
    del state
    try:
        return DocumentSearchRequest.model_validate(call.arguments), None
    except ValueError:
        return None, None


def _run_retrieval_scenario(scenario: EvaluationScenario) -> ScenarioResult:
    started = perf_counter()
    retrieval_started = perf_counter()
    result = search_documents(
        DocumentSearchRequest(query=scenario.input.message, limit=3)
    )
    elapsed = (perf_counter() - retrieval_started) * 1000
    source_ids = tuple(source.source_id for source in result.sources)
    document_ids = tuple(source_id.split(":", 1)[0] for source_id in source_ids)
    assertions: list[DimensionAssertion] = []
    expected_documents = scenario.expected.document_ids
    kind = scenario.expected.retrieval_kind
    if EvaluationDimension.RETRIEVAL_TOP_1 in scenario.dimensions:
        expected = expected_documents[0]
        observed = document_ids[0] if document_ids else None
        _append_comparison(
            assertions,
            scenario,
            EvaluationDimension.RETRIEVAL_TOP_1,
            expected,
            observed,
            "top-one document",
        )
    if EvaluationDimension.RETRIEVAL_TOP_3 in scenario.dimensions:
        if kind is RetrievalKind.SINGLE_DOCUMENT:
            expected: object = True
            observed: object = bool(
                expected_documents and expected_documents[0] in document_ids
            )
        elif kind is RetrievalKind.CONFUSABLE:
            expected = True
            observed = bool(document_ids) and set(document_ids) <= set(
                expected_documents
            )
        else:
            expected = True
            observed = not document_ids
        _append_comparison(
            assertions,
            scenario,
            EvaluationDimension.RETRIEVAL_TOP_3,
            expected,
            observed,
            "top-three retrieval boundary",
        )
    passed = all(assertion.passed for assertion in assertions)
    return ScenarioResult(
        scenario_id=scenario.id,
        passed=passed,
        trace=ExecutionTrace(
            route="document_search",
            tool="search_documents",
            arguments={"query": scenario.input.message, "limit": 3},
            evidence_kind="documents",
            evidence_sufficient=bool(source_ids),
            citation_ids=source_ids,
            final_outcome="retrieval_evaluated",
        ),
        assertions=tuple(assertions),
        stages=(
            StageObservation(name="tool_or_retrieval", elapsed_ms=elapsed),
            StageObservation(
                name="total", elapsed_ms=(perf_counter() - started) * 1000
            ),
        ),
    )


def _append_comparison(
    assertions: list[DimensionAssertion],
    scenario: EvaluationScenario,
    dimension: EvaluationDimension,
    expected: object,
    observed: object,
    label: str,
) -> None:
    if dimension not in scenario.dimensions:
        return
    passed = expected == observed
    assertions.append(
        DimensionAssertion(
            dimension=dimension,
            expected=expected,  # type: ignore[arg-type]
            observed=observed,  # type: ignore[arg-type]
            passed=passed,
            reason=f"{label} matched" if passed else f"{label} did not match",
        )
    )
