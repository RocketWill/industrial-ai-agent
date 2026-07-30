"""Typed boundary for deterministic local document retrieval."""

from pydantic import BaseModel, ConfigDict, Field

from industrial_agent.domain.documents import (
    TOKEN_PATTERN,
    DocumentSource,
    VectorIndex,
)
from industrial_agent.services.documents import (
    DocumentCorpusService,
    get_document_corpus_service,
)

MINIMUM_SCORE = 0.05
LEXICAL_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "check",
        "do",
        "for",
        "from",
        "how",
        "i",
        "in",
        "is",
        "it",
        "of",
        "on",
        "operator",
        "or",
        "occurs",
        "should",
        "the",
        "to",
        "what",
        "when",
        "with",
    }
)


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
    source: DocumentSource


class DocumentSearchResult(BaseModel):
    """Current-exchange document retrieval evidence."""

    query: str
    sources: tuple[RetrievedSourceResult, ...]
    limitations: tuple[str, ...]


def search_documents(
    request: DocumentSearchRequest,
    *,
    index: VectorIndex | None = None,
    service: DocumentCorpusService | None = None,
) -> DocumentSearchResult:
    """Search one immutable active corpus with lexical and cosine gates."""
    snapshot = None
    if index is not None:
        active_index = index
    else:
        active_service = service or get_document_corpus_service()
        snapshot = active_service.get_snapshot()
        active_index = snapshot.index
    query_terms = _meaningful_terms(request.query)
    matches = tuple(
        match
        for match in active_index.search(request.query, limit=len(active_index.entries))
        if query_terms & _meaningful_terms(
            f"{match.chunk.title} {match.chunk.section} {match.chunk.content}"
        )
        and match.score >= MINIMUM_SCORE
    )[: request.limit]
    sources = tuple(
        RetrievedSourceResult(
            source_id=match.chunk.source_id,
            title=match.chunk.title,
            section=match.chunk.section,
            relative_path=match.chunk.relative_path,
            excerpt=match.chunk.content,
            score=match.score,
            source=(
                snapshot.source_for(match.chunk.document_id)
                if snapshot is not None
                else "built_in"
            ),
        )
        for match in matches
    )
    return DocumentSearchResult(
        query=request.query,
        sources=sources,
        limitations=() if sources else ("no_relevant_sources",),
    )


def _meaningful_terms(text: str) -> frozenset[str]:
    """Return normalized lexical terms after removing a fixed stopword set."""
    return frozenset(
        token
        for token in TOKEN_PATTERN.findall(text.lower())
        if token not in LEXICAL_STOPWORDS
    )
