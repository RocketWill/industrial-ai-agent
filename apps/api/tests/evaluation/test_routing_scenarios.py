from industrial_agent.evaluation.models import EvaluationScenario
from industrial_agent.evaluation.runner import run_scenario
from industrial_agent.services.routing import UNSUPPORTED_MESSAGE


def test_run_scenario_records_deterministic_general_route() -> None:
    scenario = EvaluationScenario.model_validate(
        {
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
    )

    result = run_scenario(scenario)

    assert result.passed is True
    assert result.assertions[0].dimension == "route_accuracy"
    assert result.assertions[0].observed == "general"
    assert result.trace.route == "general"
    assert result.trace.decision_source == "deterministic_gate"
    assert result.trace.safe_action == "answer_general"
    assert result.trace.retry_count == 0
    assert result.trace.fallback_used is False
    assert result.stages[0].name == "route"
    assert result.stages[0].elapsed_ms >= 0


def test_run_scenario_checks_application_owned_unsupported_outcome() -> None:
    scenario = EvaluationScenario.model_validate(
        {
            "id": "en-unsupported-live-private",
            "description": "Rejects private live production access.",
            "language": "en",
            "category": "unsupported_request",
            "input": {"message": "Use our private live production records."},
            "adapter_script": {"actions": []},
            "expected": {
                "route": "unsupported",
                "decision_source": "deterministic_gate",
                "safe_action": "report_unsupported",
                "response_text": UNSUPPORTED_MESSAGE,
            },
            "dimensions": ["route_accuracy", "safe_failure_correctness"],
            "safety_critical": True,
        }
    )

    result = run_scenario(scenario)

    assert result.passed is True
    assert [assertion.dimension.value for assertion in result.assertions] == [
        "route_accuracy",
        "safe_failure_correctness",
    ]
    assert result.trace.response_text == UNSUPPORTED_MESSAGE


def test_run_scenario_records_classifier_retry_before_success() -> None:
    scenario = EvaluationScenario.model_validate(
        {
            "id": "en-classifier-retry",
            "description": "Retries one transient classifier failure.",
            "language": "en",
            "category": "classifier_retry",
            "input": {
                "message": "Please investigate the run.",
                "saved_context": {
                    "equipment_id": "AOI-WAFER-01",
                    "time_preset": "today",
                },
            },
            "adapter_script": {
                "actions": ["transient_classifier_failure", "return_route"],
                "candidate": {
                    "intent": "production_summary",
                    "requested_evidence": {"production": True},
                    "reason_code": "production_request",
                },
            },
            "expected": {
                "route": "production_summary",
                "decision_source": "classifier",
                "retry_count": 1,
                "fallback_used": False,
            },
            "dimensions": ["route_accuracy", "retry_fallback_correctness"],
            "safety_critical": False,
        }
    )

    result = run_scenario(scenario)

    assert result.passed is True
    assert result.trace.retry_count == 1
    assert result.trace.decision_source == "classifier"


def test_run_scenario_records_conservative_classifier_fallback() -> None:
    scenario = EvaluationScenario.model_validate(
        {
            "id": "en-classifier-fallback",
            "description": "Falls back after the bounded classifier attempts.",
            "language": "en",
            "category": "classifier_fallback",
            "input": {"message": "Please investigate the situation."},
            "adapter_script": {"actions": ["exhaust_classifier_retry"]},
            "expected": {
                "route": "general",
                "decision_source": "fallback",
                "retry_count": 1,
                "fallback_used": True,
            },
            "dimensions": ["route_accuracy", "retry_fallback_correctness"],
            "safety_critical": True,
        }
    )

    result = run_scenario(scenario)

    assert result.passed is True
    assert result.trace.fallback_used is True
    assert result.trace.retry_count == 1


def test_run_scenario_executes_production_tool_and_records_evidence() -> None:
    scenario = EvaluationScenario.model_validate(
        {
            "id": "en-production-evidence",
            "description": "Executes one explicit synthetic production query.",
            "language": "en",
            "category": "production_summary",
            "input": {
                "message": "Show the production summary for AOI-WAFER-01 today."
            },
            "adapter_script": {
                "actions": ["return_grounded_answer"],
                "tool_call": {
                    "name": "get_production_summary",
                    "arguments": {
                        "equipment_id": "AOI-WAFER-01",
                        "lot_id": "LOT-DEMO-001",
                        "start": "2026-01-15T15:00:00Z",
                        "end": "2026-01-15T18:00:00Z",
                    },
                },
            },
            "expected": {
                "route": "production_summary",
                "tool": "get_production_summary",
                "arguments": {
                    "equipment_id": "AOI-WAFER-01",
                    "lot_id": "LOT-DEMO-001",
                    "start": "2026-01-15T15:00:00Z",
                    "end": "2026-01-15T18:00:00Z",
                },
                "evidence": {
                    "inspected_wafers": 300,
                    "passed_wafers": 257,
                    "failed_wafers": 43,
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
    )

    result = run_scenario(scenario)

    assert result.passed is True
    assert result.trace.tool == "get_production_summary"
    assert result.trace.arguments["start"] == "2026-01-15T15:00:00Z"
    assert result.trace.evidence_kind == "production"
    assert result.trace.evidence_sufficient is True


def test_run_scenario_rejects_unsupported_numeric_claim() -> None:
    scenario = EvaluationScenario.model_validate(
        {
            "id": "en-unsupported-production-number",
            "description": "Rejects a number absent from production evidence.",
            "language": "en",
            "category": "unsupported_claim_rejection",
            "input": {
                "message": "Show the production summary for AOI-WAFER-01 today."
            },
            "adapter_script": {
                "actions": ["return_invalid_numeric_claim"],
                "tool_call": {
                    "name": "get_production_summary",
                    "arguments": {
                        "equipment_id": "AOI-WAFER-01",
                        "lot_id": "LOT-DEMO-001",
                        "start": "2026-01-15T15:00:00Z",
                        "end": "2026-01-15T18:00:00Z",
                    },
                },
                "answer": "The run inspected 999 wafers.",
            },
            "expected": {
                "route": "production_summary",
                "answer_accepted": False,
            },
            "dimensions": ["route_accuracy", "unsupported_claim_rejection"],
            "safety_critical": True,
        }
    )

    result = run_scenario(scenario)

    assert result.passed is True
    assert result.trace.answer_validation == "rejected"
