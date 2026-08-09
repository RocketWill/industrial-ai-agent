from industrial_agent.domain.documents import DocumentChunk, build_vector_index
from industrial_agent.tools.document_search import (
    DocumentSearchRequest,
    search_documents,
)


def test_document_search_returns_citable_optical_alarm_section() -> None:
    result = search_documents(
        DocumentSearchRequest(
            query="What should an operator check when OPTICAL-SIGNAL-LOW occurs?",
            limit=3,
        )
    )

    assert result.sources
    assert result.sources[0].section == "OPTICAL-SIGNAL-LOW"
    assert result.sources[0].source_id == (
        "aoi-alarm-guide:optical-signal-low:001"
    )
    assert result.sources[0].relative_path == (
        "data/synthetic/documents/aoi-wafer-inspector-alarm-guide.md"
    )
    assert result.sources[0].source == "built_in"
    assert "optical lens cover" in result.sources[0].excerpt
    assert 0 < result.sources[0].score <= 1
    assert result.limitations == ()


def test_document_search_retrieves_each_registered_document() -> None:
    cases = (
        ("scratch category handling record", "aoi-alarm-guide"),
        ("required inspected passed failed wafer counts", "aoi-operator-sop"),
        (
            "maintenance carrier-path observation task",
            "aoi-preventive-maintenance-guide",
        ),
    )

    for query, expected_document_id in cases:
        result = search_documents(DocumentSearchRequest(query=query, limit=3))
        assert result.sources[0].source_id.startswith(expected_document_id + ":")


def test_document_search_rejects_unrelated_lexical_noise() -> None:
    result = search_documents(
        DocumentSearchRequest(query="restaurant weather violin", limit=3)
    )

    assert result.sources == ()
    assert result.limitations == ("no_relevant_sources",)


def test_document_search_requires_a_meaningful_shared_term() -> None:
    result = search_documents(
        DocumentSearchRequest(query="what should the operator do", limit=3)
    )

    assert result.sources == ()
    assert result.limitations == ("no_relevant_sources",)


def test_document_search_rejects_positive_hash_collision_without_overlap() -> None:
    chunk = DocumentChunk(
        source_id="collision:test:001",
        document_id="collision",
        title="Collision",
        section="Test",
        relative_path="data/synthetic/documents/collision.md",
        content="token40",
        ordinal=1,
    )

    result = search_documents(
        DocumentSearchRequest(query="token45", limit=3),
        index=build_vector_index((chunk,)),
    )

    assert result.sources == ()
    assert result.limitations == ("no_relevant_sources",)
