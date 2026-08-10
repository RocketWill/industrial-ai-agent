from industrial_agent.evaluation.fixtures import load_formal_evaluation_suite
from industrial_agent.evaluation.models import EvaluationScenario
from industrial_agent.evaluation.results import aggregate_results
from industrial_agent.evaluation.runner import run_scenario


def test_formal_retrieval_scenarios_preserve_approved_thresholds() -> None:
    scenarios = tuple(
        scenario
        for scenario in load_formal_evaluation_suite().scenarios
        if scenario.category == "document_retrieval"
    )

    results = tuple(run_scenario(scenario) for scenario in scenarios)
    summary = aggregate_results(results)
    dimensions = {item.dimension.value: item for item in summary.dimensions}

    assert len(results) == 12
    assert dimensions["retrieval_top_1"].passed >= 8
    assert dimensions["retrieval_top_1"].total == 9
    assert dimensions["retrieval_top_1"].threshold_passed is True
    assert dimensions["retrieval_top_3"].threshold_passed is True
    assert summary.overall_passed is True
    assert all(
        result.trace.citation_ids or result.scenario_id == "unrelated"
        for result in results
    )


def test_document_answer_requires_a_returned_source_citation() -> None:
    base = {
        "description": "Checks citation grounding against retrieved sources.",
        "language": "en",
        "category": "citation_validation",
        "input": {"message": "Find the manual for optical signal alarms."},
        "expected": {
            "route": "document_search",
            "tool": "search_documents",
        },
        "dimensions": ["route_accuracy", "citation_correctness"],
        "safety_critical": True,
    }
    valid = EvaluationScenario.model_validate(
        {
            **base,
            "id": "en-valid-document-citation",
            "adapter_script": {
                "actions": ["return_grounded_answer"],
                "tool_call": {
                        "name": "search_documents",
                        "arguments": {
                            "query": "Find the manual for optical signal alarms.",
                            "limit": 3,
                        },
                },
                    "answer": (
                        "Follow the recorded checks "
                        "[aoi-alarm-guide:optical-signal-low:001]."
                ),
            },
            "expected": {**base["expected"], "answer_accepted": True},
        }
    )
    invalid = EvaluationScenario.model_validate(
        {
            **base,
            "id": "en-missing-document-citation",
            "adapter_script": {
                "actions": ["return_invalid_citation"],
                "tool_call": {
                        "name": "search_documents",
                        "arguments": {
                            "query": "Find the manual for optical signal alarms.",
                            "limit": 3,
                        },
                },
                "answer": "Follow the recorded checks.",
            },
            "expected": {**base["expected"], "answer_accepted": False},
        }
    )

    valid_result = run_scenario(valid)
    invalid_result = run_scenario(invalid)

    assert valid_result.passed is True
    assert valid_result.trace.answer_validation == "accepted"
    assert invalid_result.passed is True
    assert invalid_result.trace.answer_validation == "rejected"
