from industrial_agent.evaluation.document_retrieval import (
    evaluate_retrieval_fixture,
)
from industrial_agent.evaluation.fixtures import load_formal_evaluation_suite
from industrial_agent.tools.document_search import (
    DocumentSearchRequest,
    search_documents,
)


def test_retrieval_fixture_has_the_approved_scenario_shape() -> None:
    scenarios = [
        scenario
        for scenario in load_formal_evaluation_suite().scenarios
        if scenario.category == "document_retrieval"
    ]

    assert len(scenarios) == 12
    single_document_count = sum(
        item.expected.retrieval_kind == "single_document" for item in scenarios
    )
    assert single_document_count == 9
    assert sum(item.expected.retrieval_kind == "confusable" for item in scenarios) == 2
    assert sum(item.expected.retrieval_kind == "unrelated" for item in scenarios) == 1


def test_single_document_retrieval_meets_the_approved_thresholds() -> None:
    evaluation = evaluate_retrieval_fixture()

    assert evaluation.single_document_count == 9
    assert evaluation.top_three_hits == 9
    assert evaluation.top_one_hits >= 8
    assert evaluation.unrelated_rejections == 1


def test_confusable_scenarios_return_only_expected_document_families() -> None:
    scenarios = load_formal_evaluation_suite().scenarios

    for scenario in scenarios:
        if scenario.expected.retrieval_kind != "confusable":
            continue
        result = search_documents(
            DocumentSearchRequest(query=scenario.input.message, limit=3)
        )
        returned = {source.source_id.split(":", 1)[0] for source in result.sources}
        assert returned
        assert returned <= set(scenario.expected.document_ids)


def test_retrieval_evaluation_is_repeatable() -> None:
    assert evaluate_retrieval_fixture() == evaluate_retrieval_fixture()
