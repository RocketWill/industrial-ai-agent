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
    assert result.sources[0].source_id == "aoi-alarm-guide:002"
    assert result.sources[0].relative_path == (
        "data/synthetic/documents/aoi-wafer-inspector-alarm-guide.md"
    )
    assert "optical lens cover" in result.sources[0].excerpt
    assert 0 < result.sources[0].score <= 1
    assert result.limitations == ()
