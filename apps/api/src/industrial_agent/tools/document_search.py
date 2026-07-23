"""Typed boundary for deterministic local document retrieval."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from industrial_agent.domain.documents import (
    build_vector_index,
    parse_markdown_document,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_DOCUMENT = (
    REPOSITORY_ROOT
    / "data/synthetic/documents/aoi-wafer-inspector-alarm-guide.md"
)
DEFAULT_RELATIVE_PATH = (
    "data/synthetic/documents/aoi-wafer-inspector-alarm-guide.md"
)
MINIMUM_SCORE = 0.05


class DocumentSearchRequest(BaseModel):
    """Validated query for the search_documents tool."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=3, ge=1, le=3)


class RetrievedSourceResult(BaseModel):
    """One citable source returned by local retrieval."""

    source_id: str
    title: str
    section: str
    relative_path: str
    excerpt: str
    score: float


class DocumentSearchResult(BaseModel):
    """Current-exchange document retrieval evidence."""

    query: str
    sources: tuple[RetrievedSourceResult, ...]
    limitations: tuple[str, ...]


def search_documents(
    request: DocumentSearchRequest,
    *,
    document_path: Path = DEFAULT_DOCUMENT,
) -> DocumentSearchResult:
    """Search the independently written fictional guide."""
    chunks = parse_markdown_document(
        document_id="aoi-alarm-guide",
        relative_path=DEFAULT_RELATIVE_PATH,
        markdown=document_path.read_text(encoding="utf-8"),
    )
    matches = tuple(
        match
        for match in build_vector_index(chunks).search(
            request.query, limit=request.limit
        )
        if match.score >= MINIMUM_SCORE
    )
    sources = tuple(
        RetrievedSourceResult(
            source_id=match.chunk.source_id,
            title=match.chunk.title,
            section=match.chunk.section,
            relative_path=match.chunk.relative_path,
            excerpt=match.chunk.content,
            score=match.score,
        )
        for match in matches
    )
    return DocumentSearchResult(
        query=request.query,
        sources=sources,
        limitations=() if sources else ("no_relevant_sources",),
    )
