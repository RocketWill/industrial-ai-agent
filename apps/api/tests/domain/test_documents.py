import math
from pathlib import Path

import pytest

from industrial_agent.domain.documents import (
    DEFAULT_DOCUMENT_REGISTRY,
    CorpusConstructionError,
    DocumentChunk,
    DocumentCorpus,
    DocumentRegistryEntry,
    build_document_corpus,
    build_vector_index,
    embed_text,
    parse_markdown_document,
)


def test_default_document_registry_has_exact_membership_and_order() -> None:
    assert DEFAULT_DOCUMENT_REGISTRY == (
        DocumentRegistryEntry(
            document_id="aoi-alarm-guide",
            relative_path=(
                "data/synthetic/documents/aoi-wafer-inspector-alarm-guide.md"
            ),
            document_type="alarm_guide",
        ),
        DocumentRegistryEntry(
            document_id="aoi-operator-sop",
            relative_path="data/synthetic/documents/aoi-operator-inspection-sop.md",
            document_type="operator_sop",
        ),
        DocumentRegistryEntry(
            document_id="aoi-preventive-maintenance-guide",
            relative_path=(
                "data/synthetic/documents/aoi-preventive-maintenance-guide.md"
            ),
            document_type="maintenance_guide",
        ),
    )


def test_corpus_builder_preserves_registry_metadata_and_document_order() -> None:
    corpus = build_document_corpus()

    assert isinstance(corpus, DocumentCorpus)
    assert corpus.registry == DEFAULT_DOCUMENT_REGISTRY
    assert [entry.document_id for entry in corpus.registry] == [
        "aoi-alarm-guide",
        "aoi-operator-sop",
        "aoi-preventive-maintenance-guide",
    ]
    assert [chunk.document_id for chunk in corpus.chunks] == sorted(
        [chunk.document_id for chunk in corpus.chunks],
        key=lambda document_id: [
            entry.document_id for entry in corpus.registry
        ].index(document_id),
    )
    assert all(
        Path(entry.relative_path).is_relative_to("data/synthetic/documents")
        for entry in corpus.registry
    )
    assert any(
        chunk.source_id == "aoi-alarm-guide:optical-signal-low:001"
        for chunk in corpus.chunks
    )


def test_corpus_builder_rejects_a_path_outside_repository_root(tmp_path: Path) -> None:
    registry = (
        DocumentRegistryEntry(
            document_id="escape",
            relative_path="../outside.md",
            document_type="operator_sop",
        ),
    )

    with pytest.raises(CorpusConstructionError, match="outside repository"):
        build_document_corpus(repository_root=tmp_path, registry=registry)


@pytest.mark.parametrize(
    ("relative_path", "write_document"),
    [
        ("missing.md", False),
        ("invalid.md", True),
    ],
)
def test_corpus_builder_fails_atomically_for_missing_or_invalid_document(
    tmp_path: Path,
    relative_path: str,
    write_document: bool,
) -> None:
    valid_path = tmp_path / "valid.md"
    valid_path.write_text(
        "# Valid Synthetic Demo\n\n## Procedure\n\nRecord the demo event.\n",
        encoding="utf-8",
    )
    if write_document:
        (tmp_path / relative_path).write_text(
            "Content appears before a title.\n",
            encoding="utf-8",
        )

    registry = (
        DocumentRegistryEntry(
            document_id="valid",
            relative_path="valid.md",
            document_type="operator_sop",
        ),
        DocumentRegistryEntry(
            document_id="invalid-entry",
            relative_path=relative_path,
            document_type="maintenance_guide",
        ),
    )

    with pytest.raises(CorpusConstructionError):
        build_document_corpus(repository_root=tmp_path, registry=registry)


def test_markdown_parser_uses_full_heading_paths_and_section_local_citations() -> None:
    markdown = """# AOI Guide

Overview evidence.

## Recovery

Recovery evidence.

### Reset boundary

Reset evidence.
"""

    chunks = parse_markdown_document(
        document_id="aoi-guide",
        relative_path="data/synthetic/documents/aoi-guide.md",
        markdown=markdown,
    )

    assert [
        (chunk.source_id, chunk.section, chunk.content) for chunk in chunks
    ] == [
        ("aoi-guide:overview:001", "Overview", "Overview evidence."),
        ("aoi-guide:recovery:001", "Recovery", "Recovery evidence."),
        (
            "aoi-guide:recovery-reset-boundary:001",
            "Recovery / Reset boundary",
            "Reset evidence.",
        ),
    ]


def test_chunk_policy_keeps_paragraph_and_list_item_blocks_intact() -> None:
    paragraph = " ".join(f"paragraph-{index}" for index in range(70))
    list_item = "- " + " ".join(f"item-{index}" for index in range(70))
    markdown = f"""# AOI Guide

## Procedure

{paragraph}

{list_item}
"""

    chunks = parse_markdown_document(
        document_id="aoi-guide",
        relative_path="data/synthetic/documents/aoi-guide.md",
        markdown=markdown,
    )

    assert [chunk.content for chunk in chunks] == [paragraph, list_item]


def test_chunk_policy_keeps_wrapped_markdown_lines_in_one_paragraph() -> None:
    markdown = """# AOI Guide

## Procedure

This paragraph wraps across
two Markdown source lines.
"""

    chunks = parse_markdown_document(
        document_id="aoi-guide",
        relative_path="data/synthetic/documents/aoi-guide.md",
        markdown=markdown,
    )

    assert chunks[0].content == (
        "This paragraph wraps across two Markdown source lines."
    )


def test_chunk_policy_repeats_a_complete_trailing_block_for_overlap() -> None:
    first_block = " ".join(f"first-{index}" for index in range(100))
    overlap_block = " ".join(f"overlap-{index}" for index in range(15))
    next_block = " ".join(f"next-{index}" for index in range(100))
    markdown = f"""# AOI Guide

## Procedure

{first_block}

{overlap_block}

{next_block}
"""

    chunks = parse_markdown_document(
        document_id="aoi-guide",
        relative_path="data/synthetic/documents/aoi-guide.md",
        markdown=markdown,
    )

    assert len(chunks) == 2
    assert chunks[0].content == f"{first_block}\n\n{overlap_block}"
    assert chunks[1].content == f"{overlap_block}\n\n{next_block}"


def test_chunk_policy_enforces_soft_and_hard_word_limits() -> None:
    at_hard_limit = " ".join(f"hard-{index}" for index in range(160))
    at_limit = parse_markdown_document(
        document_id="aoi-guide",
        relative_path="data/synthetic/documents/aoi-guide.md",
        markdown=f"# AOI Guide\n\n## Procedure\n\n{at_hard_limit}\n",
    )

    assert len(at_limit) == 1
    assert at_limit[0].content == at_hard_limit

    oversized = " ".join(f"oversized-{index}" for index in range(161))
    with pytest.raises(
        CorpusConstructionError,
        match="aoi-guide.*Procedure.*161.*160",
    ):
        parse_markdown_document(
            document_id="aoi-guide",
            relative_path="data/synthetic/documents/aoi-guide.md",
            markdown=f"# AOI Guide\n\n## Procedure\n\n{oversized}\n",
        )


def test_chunk_policy_does_not_partially_overlap_a_block_over_twenty_words() -> None:
    first_block = " ".join(f"first-{index}" for index in range(95))
    trailing_block = " ".join(f"trailing-{index}" for index in range(25))
    next_block = " ".join(f"next-{index}" for index in range(100))
    markdown = f"""# AOI Guide

## Procedure

{first_block}

{trailing_block}

{next_block}
"""

    chunks = parse_markdown_document(
        document_id="aoi-guide",
        relative_path="data/synthetic/documents/aoi-guide.md",
        markdown=markdown,
    )

    assert chunks[0].content == f"{first_block}\n\n{trailing_block}"
    assert chunks[1].content == next_block


def test_chunks_do_not_cross_sections_and_chunk_indexes_are_section_local() -> None:
    alpha_first = " ".join(f"alpha-first-{index}" for index in range(80))
    alpha_second = " ".join(f"alpha-second-{index}" for index in range(80))
    beta = " ".join(f"beta-{index}" for index in range(80))
    markdown = f"""# AOI Guide

## Alpha

{alpha_first}

{alpha_second}

## Beta

{beta}
"""

    chunks = parse_markdown_document(
        document_id="aoi-guide",
        relative_path="data/synthetic/documents/aoi-guide.md",
        markdown=markdown,
    )

    assert [(chunk.source_id, chunk.section) for chunk in chunks] == [
        ("aoi-guide:alpha:001", "Alpha"),
        ("aoi-guide:alpha:002", "Alpha"),
        ("aoi-guide:beta:001", "Beta"),
    ]
    assert chunks[0].content == alpha_first
    assert chunks[1].content == alpha_second
    assert chunks[2].content == beta


def test_markdown_parser_rejects_duplicate_normalized_section_slugs() -> None:
    markdown = """# AOI Guide

## Optical Signal

First evidence.

## optical-signal

Second evidence.
"""

    with pytest.raises(
        CorpusConstructionError,
        match="duplicate section slug 'optical-signal'",
    ):
        parse_markdown_document(
            document_id="aoi-guide",
            relative_path="data/synthetic/documents/aoi-guide.md",
            markdown=markdown,
        )


def test_markdown_parser_rejects_an_empty_normalized_section_slug() -> None:
    markdown = """# AOI Guide

## !!!

Evidence with no ASCII heading slug.
"""

    with pytest.raises(
        CorpusConstructionError,
        match="empty normalized slug",
    ):
        parse_markdown_document(
            document_id="aoi-guide",
            relative_path="data/synthetic/documents/aoi-guide.md",
            markdown=markdown,
        )


def test_section_local_citation_ids_survive_unrelated_section_insertion() -> None:
    base = """# AOI Guide

## Stable section

Stable evidence.
"""
    with_unrelated_section = """# AOI Guide

## Unrelated section

Unrelated evidence.

## Stable section

Stable evidence.
"""

    base_chunks = parse_markdown_document(
        document_id="aoi-guide",
        relative_path="data/synthetic/documents/aoi-guide.md",
        markdown=base,
    )
    inserted_chunks = parse_markdown_document(
        document_id="aoi-guide",
        relative_path="data/synthetic/documents/aoi-guide.md",
        markdown=with_unrelated_section,
    )

    stable_base = next(
        chunk for chunk in base_chunks if chunk.section == "Stable section"
    )
    stable_inserted = next(
        chunk
        for chunk in inserted_chunks
        if chunk.section == "Stable section"
    )
    assert stable_inserted.source_id == stable_base.source_id
    assert stable_inserted.content == stable_base.content


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
        "aoi-guide:overview:001",
        "aoi-guide:optical-signal-alarm:001",
        "aoi-guide:recovery:001",
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


def test_vector_index_embeds_title_and_full_section_path_but_keeps_excerpt() -> None:
    chunk = DocumentChunk(
        source_id="guide:recovery-reset-boundary:001",
        document_id="guide",
        title="AOI Guide",
        section="Recovery / Reset boundary",
        relative_path="data/synthetic/documents/aoi.md",
        content="Reset the fictional control once.",
        ordinal=1,
    )

    index = build_vector_index((chunk,))

    assert chunk.content == "Reset the fictional control once."
    assert index.entries[0][1] == embed_text(
        "AOI Guide\nRecovery / Reset boundary\nReset the fictional control once."
    )
