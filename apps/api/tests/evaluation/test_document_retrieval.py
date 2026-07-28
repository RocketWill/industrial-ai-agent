import json
from pathlib import Path

from industrial_agent.evaluation.document_retrieval import (
    evaluate_retrieval_fixture,
)
from industrial_agent.tools.document_search import (
    DocumentSearchRequest,
    search_documents,
)

FIXTURE_PATH = Path(__file__).parents[1] / "fixtures/document_retrieval_scenarios.json"


def test_retrieval_fixture_has_the_approved_scenario_shape() -> None:
    scenarios = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    assert len(scenarios) == 12
    assert sum(item["kind"] == "single_document" for item in scenarios) == 9
    assert sum(item["kind"] == "confusable" for item in scenarios) == 2
    assert sum(item["kind"] == "unrelated" for item in scenarios) == 1


def test_single_document_retrieval_meets_the_approved_thresholds() -> None:
    evaluation = evaluate_retrieval_fixture(FIXTURE_PATH)

    assert evaluation.single_document_count == 9
    assert evaluation.top_three_hits == 9
    assert evaluation.top_one_hits >= 8
    assert evaluation.unrelated_rejections == 1


def test_confusable_scenarios_return_only_expected_document_families() -> None:
    scenarios = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    for scenario in scenarios:
        if scenario["kind"] != "confusable":
            continue
        result = search_documents(
            DocumentSearchRequest(query=scenario["query"], limit=3)
        )
        returned = {source.source_id.split(":", 1)[0] for source in result.sources}
        assert returned
        assert returned <= set(scenario["expected_document_ids"])


def test_retrieval_evaluation_is_repeatable() -> None:
    assert evaluate_retrieval_fixture(FIXTURE_PATH) == evaluate_retrieval_fixture(
        FIXTURE_PATH
    )
