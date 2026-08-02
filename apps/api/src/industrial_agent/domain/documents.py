"""Deterministic document parsing and local vector retrieval."""

import re
from dataclasses import dataclass
from hashlib import sha256
from math import sqrt

EMBEDDING_DIMENSIONS = 256
TOKEN_PATTERN = re.compile(r"[^\W_]+(?:-[^\W_]+)*", re.UNICODE)


@dataclass(frozen=True)
class DocumentChunk:
    """One stable, repository-local citation unit."""

    source_id: str
    document_id: str
    title: str
    section: str
    relative_path: str
    content: str
    ordinal: int


@dataclass(frozen=True)
class SearchMatch:
    """A document chunk paired with its deterministic cosine score."""

    chunk: DocumentChunk
    score: float


def parse_markdown_document(
    *, document_id: str, relative_path: str, markdown: str
) -> tuple[DocumentChunk, ...]:
    """Parse an H1 document into stable heading-aware chunks."""
    lines = markdown.splitlines()
    title = next(
        (line[2:].strip() for line in lines if line.startswith("# ")),
        None,
    )
    if not title:
        raise ValueError("Markdown document requires an H1 title")
    sections: list[tuple[str, list[str]]] = [("Overview", [])]
    for line in lines:
        if line.startswith("# "):
            continue
        if line.startswith("## ") or line.startswith("### "):
            section = line.lstrip("#").strip()
            sections.append((section, []))
            continue
        if line.strip():
            sections[-1][1].append(line.strip())
    chunks: list[DocumentChunk] = []
    for section, content_lines in sections:
        content = "\n".join(content_lines).strip()
        if not content:
            continue
        ordinal = len(chunks) + 1
        chunks.append(
            DocumentChunk(
                source_id=f"{document_id}:{ordinal:03d}",
                document_id=document_id,
                title=title,
                section=section,
                relative_path=relative_path,
                content=content,
                ordinal=ordinal,
            )
        )
    return tuple(chunks)


def embed_text(text: str) -> tuple[float, ...]:
    """Return a normalized deterministic feature-hashing vector."""
    vector = [0.0] * EMBEDDING_DIMENSIONS
    for token in TOKEN_PATTERN.findall(text.lower()):
        digest = sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:2], "big") % EMBEDDING_DIMENSIONS
        sign = 1.0 if digest[2] % 2 == 0 else -1.0
        vector[index] += sign
    norm = sqrt(sum(value * value for value in vector))
    if norm == 0:
        return tuple(vector)
    return tuple(value / norm for value in vector)


@dataclass(frozen=True)
class VectorIndex:
    """Small immutable in-memory cosine index."""

    entries: tuple[tuple[DocumentChunk, tuple[float, ...]], ...]

    def search(self, query: str, *, limit: int) -> tuple[SearchMatch, ...]:
        """Rank indexed chunks by cosine score and stable source ID."""
        query_vector = embed_text(query)
        matches = tuple(
            SearchMatch(
                chunk=chunk,
                score=max(
                    0.0,
                    sum(
                        query_value * chunk_value
                        for query_value, chunk_value in zip(
                            query_vector, vector, strict=True
                        )
                    ),
                ),
            )
            for chunk, vector in self.entries
        )
        return tuple(
            sorted(matches, key=lambda item: (-item.score, item.chunk.source_id))[
                :limit
            ]
        )


def build_vector_index(chunks: tuple[DocumentChunk, ...]) -> VectorIndex:
    """Build an immutable index for already validated chunks."""
    return VectorIndex(
        entries=tuple((chunk, embed_text(chunk.content)) for chunk in chunks)
    )
