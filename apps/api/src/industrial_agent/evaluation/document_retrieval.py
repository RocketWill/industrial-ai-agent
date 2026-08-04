"""Evaluate document retrieval against a machine-readable scenario fixture."""

from dataclasses import dataclass

from industrial_agent.evaluation.fixtures import load_formal_evaluation_suite
from industrial_agent.tools.document_search import (
    DocumentSearchRequest,
    search_documents,
)


@dataclass(frozen=True)
class ScenarioEvaluation:
    """Stable retrieval evidence for one evaluation scenario."""

    scenario_id: str
    source_ids: tuple[str, ...]
    scores: tuple[float, ...]
    expected_rank: int | None


@dataclass(frozen=True)
class RetrievalEvaluation:
    """Per-scenario evidence and aggregate single-document results."""

    scenarios: tuple[ScenarioEvaluation, ...]
    single_document_count: int
    top_one_hits: int
    top_three_hits: int
    unrelated_rejections: int


def evaluate_retrieval_fixture() -> RetrievalEvaluation:
    """Run stable fixture queries through the public retrieval boundary."""
    scenarios = (
        scenario
        for scenario in load_formal_evaluation_suite().scenarios
        if scenario.category == "document_retrieval"
    )
    single_document_count = 0
    top_one_hits = 0
    top_three_hits = 0
    unrelated_rejections = 0
    scenario_results: list[ScenarioEvaluation] = []

    for scenario in scenarios:
        result = search_documents(
            DocumentSearchRequest(query=scenario.input.message, limit=3)
        )
        document_ids = [source.source_id.split(":", 1)[0] for source in result.sources]
        expected_source_id = scenario.expected.source_id
        source_ids = tuple(source.source_id for source in result.sources)
        expected_rank = (
            source_ids.index(expected_source_id) + 1
            if expected_source_id in source_ids
            else None
        )
        scenario_results.append(
            ScenarioEvaluation(
                scenario_id=scenario.id,
                source_ids=source_ids,
                scores=tuple(source.score for source in result.sources),
                expected_rank=expected_rank,
            )
        )
        if scenario.expected.retrieval_kind == "single_document":
            single_document_count += 1
            expected = scenario.expected.document_ids[0]
            top_one_hits += bool(document_ids and document_ids[0] == expected)
            top_three_hits += expected in document_ids
        elif scenario.expected.retrieval_kind == "unrelated":
            unrelated_rejections += not result.sources

    return RetrievalEvaluation(
        scenarios=tuple(scenario_results),
        single_document_count=single_document_count,
        top_one_hits=top_one_hits,
        top_three_hits=top_three_hits,
        unrelated_rejections=unrelated_rejections,
    )
