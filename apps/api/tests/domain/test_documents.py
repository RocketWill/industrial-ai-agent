import math

import pytest

from industrial_agent.domain.documents import (
    DocumentChunk,
    build_vector_index,
    embed_text,
    parse_markdown_document,
)


def test_markdown_parser_creates_stable_heading_aware_chunks() -> None:
    markdown = """# AOI Guide

Synthetic training document.

## Optical signal alarm

Check the lens cover for contamination.

## Recovery

Record the alarm code before restarting inspection.
"""

    first = parse_markdown_document(
        document_id="aoi-guide",
        relative_path="data/synthetic/documents/aoi-guide.md",
        markdown=markdown,
    )
    second = parse_markdown_document(
        document_id="aoi-guide",
        relative_path="data/synthetic/documents/aoi-guide.md",
        markdown=markdown,
    )

    assert [chunk.source_id for chunk in first] == [
        "aoi-guide:001",
        "aoi-guide:002",
        "aoi-guide:003",
    ]
    assert first == second
    assert first[1].title == "AOI Guide"
    assert first[1].section == "Optical signal alarm"
    assert "lens cover" in first[1].content


def test_hashed_embedding_is_normalized_and_deterministic() -> None:
    first = embed_text("optical signal low lens contamination")
    second = embed_text("optical signal low lens contamination")

    assert first == second
    assert math.sqrt(sum(value * value for value in first)) == pytest.approx(1.0)


def test_vector_index_ranks_relevant_alarm_section_first() -> None:
    chunks = (
        DocumentChunk(
            source_id="guide:001",
            document_id="guide",
            title="AOI Guide",
            section="OPTICAL-SIGNAL-LOW",
            relative_path="data/synthetic/documents/aoi.md",
            content="Check the optical lens cover and illumination connector.",
            ordinal=1,
        ),
        DocumentChunk(
            source_id="guide:002",
            document_id="guide",
            title="AOI Guide",
            section="Shutdown",
            relative_path="data/synthetic/documents/aoi.md",
            content="Use the normal application shutdown sequence.",
            ordinal=2,
        ),
    )

    results = build_vector_index(chunks).search(
        "What should an operator check for optical signal low?",
        limit=2,
    )

    assert results[0].chunk.source_id == "guide:001"
    assert 0 < results[0].score <= 1
    assert results[0].score > results[1].score
