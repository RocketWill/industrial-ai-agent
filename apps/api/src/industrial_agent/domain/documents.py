"""Deterministic document parsing and local vector retrieval."""

import re
import unicodedata
from dataclasses import dataclass
from hashlib import sha256
from math import sqrt
from pathlib import Path
from typing import Literal

EMBEDDING_DIMENSIONS = 256
TOKEN_PATTERN = re.compile(r"[^\W_]+(?:-[^\W_]+)*", re.UNICODE)
LIST_ITEM_PATTERN = re.compile(r"^\s*(?:[-+*]|\d+[.)])\s+")
SOFT_CHUNK_WORD_LIMIT = 120
HARD_CHUNK_WORD_LIMIT = 160
MAX_CHUNK_OVERLAP_WORDS = 20
REPOSITORY_ROOT = Path(__file__).resolve().parents[5]


class CorpusConstructionError(ValueError):
    """Raised when the configured synthetic document corpus is invalid."""


@dataclass(frozen=True)
class DocumentRegistryEntry:
    """Immutable metadata for one repository-owned corpus document."""

    document_id: str
    relative_path: str
    document_type: Literal["alarm_guide", "operator_sop", "maintenance_guide"]


DEFAULT_DOCUMENT_REGISTRY = (
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
class DocumentCorpus:
    """An immutable, fully constructed corpus and its source registry."""

    registry: tuple[DocumentRegistryEntry, ...]
    chunks: tuple[DocumentChunk, ...]


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
    sections: list[tuple[tuple[str, ...], list[str]]] = [((), [])]
    current_h2: str | None = None
    for line in lines:
        if line.startswith("# "):
            continue
        if line.startswith("## "):
            section = line.lstrip("#").strip()
            current_h2 = section
            sections.append(((section,), []))
            continue
        if line.startswith("### "):
            if current_h2 is None:
                raise CorpusConstructionError(
                    f"Document '{document_id}' contains an H3 without an H2 parent"
                )
            section = line.lstrip("#").strip()
            sections.append(((current_h2, section), []))
            continue
        sections[-1][1].append(line.rstrip())
    chunks: list[DocumentChunk] = []
    seen_section_slugs: set[str] = {"overview"}
    for section_path, content_lines in sections:
        section_slug = _normalize_section_slug(section_path)
        if section_path and section_slug in seen_section_slugs:
            raise CorpusConstructionError(
                f"Document '{document_id}' contains duplicate section slug "
                f"'{section_slug}'"
            )
        seen_section_slugs.add(section_slug)
        blocks = _parse_blocks(content_lines)
        if not blocks:
            continue
        section = " / ".join(section_path) if section_path else "Overview"
        section_chunks = _chunk_section(
            document_id=document_id,
            section=section,
            blocks=blocks,
        )
        for section_index, content in enumerate(section_chunks, start=1):
            chunks.append(
                DocumentChunk(
                    source_id=(
                        f"{document_id}:{section_slug}:{section_index:03d}"
                    ),
                    document_id=document_id,
                    title=title,
                    section=section,
                    relative_path=relative_path,
                    content=content,
                    ordinal=len(chunks) + 1,
                )
            )
    return tuple(chunks)


def _normalize_section_slug(section_path: tuple[str, ...]) -> str:
    """Return the reserved or normalized slug for one section path."""
    if not section_path:
        return "overview"
    ascii_path = unicodedata.normalize(
        "NFKD", " / ".join(section_path)
    ).encode("ascii", "ignore").decode("ascii")
    slug = "-".join(re.findall(r"[a-z0-9]+", ascii_path.lower()))
    if not slug:
        raise CorpusConstructionError("Section heading has an empty normalized slug")
    return slug


def _word_count(text: str) -> int:
    """Count words with the same tokenization used by local embeddings."""
    return len(TOKEN_PATTERN.findall(text))


def _parse_blocks(lines: list[str]) -> tuple[str, ...]:
    """Parse paragraphs and complete Markdown list items into blocks."""
    blocks: list[str] = []
    current_lines: list[str] = []
    current_is_list_item = False

    def flush() -> None:
        if current_lines:
            blocks.append(" ".join(line.strip() for line in current_lines))
            current_lines.clear()

    for line in lines:
        if not line.strip():
            flush()
            current_is_list_item = False
            continue
        if LIST_ITEM_PATTERN.match(line):
            flush()
            current_lines.append(line)
            current_is_list_item = True
            continue
        if current_is_list_item and line[:1].isspace():
            current_lines.append(line)
            continue
        if not current_is_list_item:
            current_lines.append(line)
            continue
        flush()
        current_lines.append(line)
        current_is_list_item = False
    flush()
    return tuple(blocks)


def _chunk_section(
    *, document_id: str, section: str, blocks: tuple[str, ...]
) -> tuple[str, ...]:
    """Pack complete blocks into one section's soft-limited chunks."""
    for block in blocks:
        block_words = _word_count(block)
        if block_words > HARD_CHUNK_WORD_LIMIT:
            raise CorpusConstructionError(
                f"Document '{document_id}' section '{section}' contains an "
                f"indivisible block of {block_words} words; maximum is "
                f"{HARD_CHUNK_WORD_LIMIT}"
            )
    chunks: list[str] = []
    previous_chunk_blocks: tuple[str, ...] = ()
    block_index = 0
    while block_index < len(blocks):
        next_block_words = _word_count(blocks[block_index])
        overlap_blocks = _select_overlap_blocks(
            previous_chunk_blocks=previous_chunk_blocks,
            next_block_words=next_block_words,
        )
        current_blocks = list(overlap_blocks)
        current_words = sum(_word_count(block) for block in current_blocks)
        new_words = 0
        while block_index < len(blocks):
            block = blocks[block_index]
            block_words = _word_count(block)
            if new_words and new_words + block_words > SOFT_CHUNK_WORD_LIMIT:
                break
            if not new_words and current_words + block_words > HARD_CHUNK_WORD_LIMIT:
                current_blocks = []
                current_words = 0
            current_blocks.append(block)
            current_words += block_words
            new_words += block_words
            block_index += 1
        chunks.append("\n\n".join(current_blocks))
        previous_chunk_blocks = tuple(current_blocks)
    return tuple(chunks)


def _select_overlap_blocks(
    *, previous_chunk_blocks: tuple[str, ...], next_block_words: int
) -> tuple[str, ...]:
    """Select a complete trailing-block suffix within overlap and hard limits."""
    overlap_blocks: list[str] = []
    overlap_words = 0
    for block in reversed(previous_chunk_blocks):
        block_words = _word_count(block)
        if overlap_words + block_words > MAX_CHUNK_OVERLAP_WORDS:
            break
        overlap_blocks.insert(0, block)
        overlap_words += block_words
    while overlap_blocks and overlap_words + next_block_words > HARD_CHUNK_WORD_LIMIT:
        overlap_words -= _word_count(overlap_blocks.pop(0))
    return tuple(overlap_blocks)


def _validate_markdown_document(
    *, document_id: str, markdown: str
) -> None:
    """Validate the document structure required by corpus construction."""
    lines = markdown.splitlines()
    h1_indexes = [index for index, line in enumerate(lines) if line.startswith("# ")]
    if len(h1_indexes) != 1:
        raise CorpusConstructionError(
            f"Document '{document_id}' must contain exactly one H1 title"
        )
    h1_index = h1_indexes[0]
    if not lines[h1_index][2:].strip():
        raise CorpusConstructionError(
            f"Document '{document_id}' must contain a non-empty H1 title"
        )
    if any(line.strip() for line in lines[:h1_index]):
        raise CorpusConstructionError(
            f"Document '{document_id}' contains content before its H1 title"
        )


def _resolve_document_path(
    *, repository_root: Path, entry: DocumentRegistryEntry
) -> Path:
    """Resolve one registry path while enforcing repository containment."""
    try:
        relative_path = Path(entry.relative_path)
    except (TypeError, ValueError) as error:
        raise CorpusConstructionError(
            f"Document '{entry.document_id}' has an invalid relative path"
        ) from error
    if relative_path.is_absolute():
        raise CorpusConstructionError(
            f"Document '{entry.document_id}' path is outside repository"
        )

    root = repository_root.resolve()
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise CorpusConstructionError(
            f"Document '{entry.document_id}' path is outside repository"
        ) from error
    return candidate


def build_document_corpus(
    repository_root: Path = REPOSITORY_ROOT,
    registry: tuple[DocumentRegistryEntry, ...] = DEFAULT_DOCUMENT_REGISTRY,
) -> DocumentCorpus:
    """Build a complete immutable corpus or raise without returning partial data."""
    entries = tuple(registry)
    seen_document_ids: set[str] = set()
    chunks: list[DocumentChunk] = []

    for entry in entries:
        if entry.document_id in seen_document_ids:
            raise CorpusConstructionError(
                f"Duplicate document ID '{entry.document_id}' in registry"
            )
        seen_document_ids.add(entry.document_id)

        document_path = _resolve_document_path(
            repository_root=repository_root,
            entry=entry,
        )
        if not document_path.exists():
            raise CorpusConstructionError(
                f"Document '{entry.document_id}' is missing"
            )
        if not document_path.is_file():
            raise CorpusConstructionError(
                f"Document '{entry.document_id}' is not a regular file"
            )
        try:
            markdown = document_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            raise CorpusConstructionError(
                f"Document '{entry.document_id}' is not valid UTF-8"
            ) from error
        except OSError as error:
            raise CorpusConstructionError(
                f"Document '{entry.document_id}' cannot be read"
            ) from error

        _validate_markdown_document(document_id=entry.document_id, markdown=markdown)
        parsed_chunks = parse_markdown_document(
            document_id=entry.document_id,
            relative_path=entry.relative_path,
            markdown=markdown,
        )
        if not parsed_chunks:
            raise CorpusConstructionError(
                f"Document '{entry.document_id}' produced no chunks"
            )
        chunks.extend(parsed_chunks)

    return DocumentCorpus(registry=entries, chunks=tuple(chunks))


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
        entries=tuple(
            (
                chunk,
                embed_text(
                    f"{chunk.title}\n{chunk.section}\n{chunk.content}"
                ),
            )
            for chunk in chunks
        )
    )
