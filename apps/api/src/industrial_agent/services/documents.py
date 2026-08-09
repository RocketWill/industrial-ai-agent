"""Persistent local Markdown storage for the document-management slices."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import RLock

from industrial_agent.domain import documents as document_domain
from industrial_agent.domain.documents import (
    DEFAULT_DOCUMENT_REGISTRY,
    REPOSITORY_ROOT,
    CorpusConstructionError,
    DocumentChunk,
    DocumentMetadata,
    DocumentRegistryEntry,
    DocumentSource,
    DocumentValidationError,
    StoredDocument,
    VectorIndex,
    build_document_corpus,
    normalize_uploaded_document_id,
    read_registry_document,
    validate_uploaded_markdown,
)

logger = logging.getLogger(__name__)

MANIFEST_FILENAME = "manifest.json"
MANIFEST_VERSION = 1
UPLOADS_RELATIVE_DIRECTORY = "uploads"
DEFAULT_UPLOAD_STORAGE_ROOT = REPOSITORY_ROOT / "apps" / "api" / "uploads"

_STORE_UNAVAILABLE_MESSAGE = "Local uploaded-document storage is unavailable"
_PERSISTENCE_FAILURE_MESSAGE = "The local document could not be saved"
_DELETE_FAILURE_MESSAGE = "The local document could not be deleted"


class DocumentStoreError(RuntimeError):
    """Base error for safe local document-store failures."""


class DocumentConflictError(DocumentStoreError):
    """Raised when an upload identity or original filename already exists."""


class DocumentNotFoundError(DocumentStoreError):
    """Raised when a requested local document does not exist."""


class BuiltInDocumentError(DocumentStoreError):
    """Raised when a caller attempts to delete a built-in document."""


class DocumentStoreUnavailableError(DocumentStoreError):
    """Raised when local storage cannot safely accept a mutation."""


class _InvalidLocalState(Exception):
    """Internal marker for local state that must not be silently discarded."""


@dataclass(frozen=True)
class DocumentStoreStatus:
    """Safe management status for the local upload area."""

    available: bool
    message: str | None = None


IndexBuilder = Callable[[tuple[DocumentChunk, ...]], VectorIndex]


@dataclass(frozen=True, slots=True)
class DocumentCorpusSnapshot:
    """Immutable runtime documents and index used by one retrieval exchange."""

    documents: tuple[StoredDocument, ...]
    index: VectorIndex

    def source_for(self, document_id: str) -> DocumentSource:
        """Return provenance for an indexed document in this snapshot."""
        for document in self.documents:
            if document.metadata.document_id == document_id:
                return document.metadata.source
        return "built_in"


class LocalDocumentStore:
    """Own built-in metadata and persistent local Markdown uploads.

    The store validates a complete candidate set before changing disk state.
    It does not own an active retrieval snapshot; that lifecycle belongs to a
    later corpus-service slice.
    """

    def __init__(
        self,
        storage_root: Path | str = DEFAULT_UPLOAD_STORAGE_ROOT,
        *,
        repository_root: Path = REPOSITORY_ROOT,
        registry: tuple[DocumentRegistryEntry, ...] = DEFAULT_DOCUMENT_REGISTRY,
    ) -> None:
        self._lock = RLock()
        self._storage_root = Path(storage_root)
        self._repository_root = repository_root
        self._registry = tuple(registry)
        self._built_in_documents = self._load_built_in_documents()
        self._local_documents: tuple[StoredDocument, ...] = ()
        self._available = True
        self._status_message: str | None = None
        self._load_local_state()

    @property
    def status(self) -> DocumentStoreStatus:
        """Return safe local-storage availability without exposing paths."""
        with self._lock:
            return DocumentStoreStatus(
                available=self._available,
                message=self._status_message,
            )

    def list_documents(self) -> tuple[DocumentMetadata, ...]:
        """Return built-ins followed by local uploads in stable order."""
        with self._lock:
            documents = self._built_in_documents
            if self._available:
                documents += self._local_documents
            return tuple(document.metadata for document in documents)

    def get_document(self, document_id: str) -> StoredDocument | None:
        """Return one current document, or ``None`` for an unknown ID."""
        with self._lock:
            for document in self._built_in_documents:
                if document.metadata.document_id == document_id:
                    return document
            if self._available:
                for document in self._local_documents:
                    if document.metadata.document_id == document_id:
                        return document
            return None

    def upload_document(
        self,
        *,
        filename: str,
        content: bytes,
        index_builder: IndexBuilder | None = None,
    ) -> StoredDocument:
        """Validate and atomically persist one uploaded Markdown document."""
        with self._lock:
            self._require_available()
            document = self._validate_upload(filename=filename, content=content)
            self._check_collisions(document.metadata)
            candidate_documents = self._local_documents + (document,)
            self._validate_candidate(
                candidate_documents,
                index_builder=index_builder,
            )
            manifest = self._manifest_bytes(candidate_documents)
            self._publish_upload(document, manifest)
            self._local_documents = candidate_documents
            return document

    def delete_document(
        self,
        document_id: str,
        *,
        index_builder: IndexBuilder | None = None,
    ) -> None:
        """Atomically remove one local upload after candidate validation."""
        with self._lock:
            if any(
                document.metadata.document_id == document_id
                for document in self._built_in_documents
            ):
                raise BuiltInDocumentError("Built-in documents cannot be deleted")
            self._require_available()
            remaining = tuple(
                document
                for document in self._local_documents
                if document.metadata.document_id != document_id
            )
            if len(remaining) == len(self._local_documents):
                raise DocumentNotFoundError("Document not found")
            self._validate_candidate(remaining, index_builder=index_builder)
            manifest = self._manifest_bytes(remaining)
            target = self._document_path(document_id)
            self._publish_delete(target=target, manifest=manifest)
            self._local_documents = remaining

    def _load_built_in_documents(self) -> tuple[StoredDocument, ...]:
        try:
            corpus = build_document_corpus(
                repository_root=self._repository_root,
                registry=self._registry,
            )
            document_domain.build_vector_index(corpus.chunks)
            documents: list[StoredDocument] = []
            for entry in self._registry:
                registry_document = read_registry_document(
                    entry.document_id,
                    repository_root=self._repository_root,
                    registry=self._registry,
                )
                if registry_document is None:
                    raise CorpusConstructionError(
                        f"Document '{entry.document_id}' is unavailable"
                    )
                chunks = tuple(
                    chunk
                    for chunk in corpus.chunks
                    if chunk.document_id == entry.document_id
                )
                metadata = DocumentMetadata(
                    document_id=entry.document_id,
                    title=registry_document.title,
                    document_type=entry.document_type,
                    source="built_in",
                    filename=Path(entry.relative_path).name,
                    relative_path=entry.relative_path,
                    size_bytes=len(registry_document.markdown.encode("utf-8")),
                    status="ready",
                    deletable=False,
                    synthetic_demo=True,
                )
                documents.append(
                    StoredDocument(
                        metadata=metadata,
                        markdown=registry_document.markdown,
                        chunks=chunks,
                    )
                )
            return tuple(documents)
        except (CorpusConstructionError, OSError, ValueError) as error:
            raise DocumentStoreError(
                "The built-in document corpus is unavailable"
            ) from error

    def _load_local_state(self) -> None:
        try:
            self._storage_root.mkdir(parents=True, exist_ok=True)
            if not self._storage_root.is_dir():
                raise _InvalidLocalState
            self._local_documents = self._read_manifest_state()
            self._validate_candidate(self._local_documents)
        except _InvalidLocalState:
            self._mark_unavailable()
        except (OSError, DocumentStoreError, ValueError):
            self._mark_unavailable()

    def _read_manifest_state(self) -> tuple[StoredDocument, ...]:
        manifest_path = self._manifest_path
        try:
            if not manifest_path.exists():
                entries = tuple(self._storage_root.iterdir())
                if entries:
                    raise _InvalidLocalState
                return ()
            if not manifest_path.is_file():
                raise _InvalidLocalState
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise _InvalidLocalState from error

        if not isinstance(payload, dict):
            raise _InvalidLocalState
        if payload.get("version") != MANIFEST_VERSION:
            raise _InvalidLocalState
        manifest_entries = payload.get("documents")
        if not isinstance(manifest_entries, list):
            raise _InvalidLocalState

        documents: list[StoredDocument] = []
        seen_ids: set[str] = set()
        seen_filenames: set[str] = set()
        for entry in manifest_entries:
            document = self._read_manifest_document(
                entry,
                seen_ids=seen_ids,
                seen_filenames=seen_filenames,
            )
            documents.append(document)

        expected_files = {MANIFEST_FILENAME}
        expected_files.update(
            f"{document.metadata.document_id}.md" for document in documents
        )
        try:
            actual_files = {path.name for path in self._storage_root.iterdir()}
        except OSError as error:
            raise _InvalidLocalState from error
        if actual_files != expected_files:
            raise _InvalidLocalState
        return tuple(documents)

    def _read_manifest_document(
        self,
        entry: object,
        *,
        seen_ids: set[str],
        seen_filenames: set[str],
    ) -> StoredDocument:
        if not isinstance(entry, dict):
            raise _InvalidLocalState
        document_id = entry.get("document_id")
        filename = entry.get("filename")
        title = entry.get("title")
        size_bytes = entry.get("size_bytes")
        if not isinstance(document_id, str):
            raise _InvalidLocalState
        if not isinstance(filename, str) or not isinstance(title, str):
            raise _InvalidLocalState
        if (
            not title.strip()
            or not isinstance(size_bytes, int)
            or isinstance(size_bytes, bool)
            or size_bytes <= 0
        ):
            raise _InvalidLocalState
        try:
            expected_id = normalize_uploaded_document_id(filename)
        except DocumentValidationError as error:
            raise _InvalidLocalState from error
        if document_id != expected_id:
            raise _InvalidLocalState
        if document_id.casefold() in seen_ids:
            raise _InvalidLocalState
        if filename.casefold() in seen_filenames:
            raise _InvalidLocalState
        seen_ids.add(document_id.casefold())
        seen_filenames.add(filename.casefold())

        try:
            content_path = self._document_path(document_id)
            if not content_path.is_file():
                raise _InvalidLocalState
            content = content_path.read_bytes()
            if len(content) != size_bytes:
                raise _InvalidLocalState
            markdown = content.decode("utf-8")
        except (OSError, UnicodeDecodeError) as error:
            raise _InvalidLocalState from error
        try:
            chunks = validate_uploaded_markdown(
                document_id=document_id,
                relative_path=self._relative_path(document_id),
                markdown=markdown,
            )
        except DocumentValidationError as error:
            raise _InvalidLocalState from error
        if chunks[0].title != title:
            raise _InvalidLocalState

        metadata = DocumentMetadata(
            document_id=document_id,
            title=title,
            document_type="uploaded_document",
            source="local_upload",
            filename=filename,
            relative_path=self._relative_path(document_id),
            size_bytes=size_bytes,
            status="ready",
            deletable=True,
            synthetic_demo=False,
        )
        return StoredDocument(
            metadata=metadata,
            markdown=markdown,
            chunks=chunks,
        )

    def _validate_upload(self, *, filename: str, content: bytes) -> StoredDocument:
        if not isinstance(content, bytes):
            raise DocumentValidationError("The upload content must be bytes")
        if len(content) == 0:
            raise DocumentValidationError("The Markdown document cannot be empty")
        if len(content) > document_domain.MAX_UPLOAD_BYTES:
            raise DocumentValidationError(
                "The Markdown document exceeds the 1 MiB limit"
            )
        document_id = normalize_uploaded_document_id(filename)
        try:
            markdown = content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise DocumentValidationError(
                "The Markdown document must be valid UTF-8"
            ) from error
        relative_path = self._relative_path(document_id)
        chunks = validate_uploaded_markdown(
            document_id=document_id,
            relative_path=relative_path,
            markdown=markdown,
        )
        metadata = DocumentMetadata(
            document_id=document_id,
            title=chunks[0].title,
            document_type="uploaded_document",
            source="local_upload",
            filename=filename,
            relative_path=relative_path,
            size_bytes=len(content),
            status="ready",
            deletable=True,
            synthetic_demo=False,
        )
        return StoredDocument(metadata=metadata, markdown=markdown, chunks=chunks)

    def _check_collisions(self, metadata: DocumentMetadata) -> None:
        documents = self._built_in_documents + self._local_documents
        if any(
            document.metadata.document_id.casefold() == metadata.document_id.casefold()
            for document in documents
        ):
            raise DocumentConflictError("A document with this identity already exists")
        if any(
            document.metadata.filename.casefold() == metadata.filename.casefold()
            for document in documents
        ):
            raise DocumentConflictError("A document with this filename already exists")

    def _validate_candidate(
        self,
        local_documents: tuple[StoredDocument, ...],
        *,
        index_builder: IndexBuilder | None = None,
    ) -> VectorIndex:
        chunks = tuple(
            chunk
            for document in self._built_in_documents + local_documents
            for chunk in document.chunks
        )
        try:
            builder = (
                document_domain.build_vector_index
                if index_builder is None
                else index_builder
            )
            index = builder(chunks)
            if not isinstance(index, VectorIndex):
                raise TypeError("The candidate index has an invalid type")
            return index
        except Exception as error:
            raise DocumentStoreError(
                "The candidate document corpus could not be indexed"
            ) from error

    def _manifest_bytes(self, documents: tuple[StoredDocument, ...]) -> bytes:
        payload = {
            "version": MANIFEST_VERSION,
            "documents": [
                {
                    "document_id": document.metadata.document_id,
                    "filename": document.metadata.filename,
                    "size_bytes": document.metadata.size_bytes,
                    "title": document.metadata.title,
                }
                for document in documents
            ],
        }
        return (
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")

    def _publish_upload(self, document: StoredDocument, manifest: bytes) -> None:
        content_path = self._document_path(document.metadata.document_id)
        if content_path.exists():
            raise DocumentConflictError("A document with this identity already exists")

        content_temp: Path | None = None
        manifest_temp: Path | None = None
        content_published = False
        try:
            content_temp = self._write_temp_file(
                document.markdown.encode("utf-8"),
                prefix=f".{content_path.name}.",
            )
            manifest_temp = self._write_temp_file(
                manifest,
                prefix=f".{MANIFEST_FILENAME}.",
            )
            os.replace(content_temp, content_path)
            content_published = True
            os.replace(manifest_temp, self._manifest_path)
        except (OSError, DocumentStoreError) as error:
            if content_published:
                try:
                    content_path.unlink(missing_ok=True)
                except OSError as rollback_error:
                    self._mark_unavailable()
                    raise DocumentStoreUnavailableError(
                        _STORE_UNAVAILABLE_MESSAGE
                    ) from rollback_error
            if isinstance(error, DocumentStoreError):
                raise
            raise DocumentStoreError(_PERSISTENCE_FAILURE_MESSAGE) from error
        finally:
            self._unlink_quietly(content_temp)
            self._unlink_quietly(manifest_temp)

    def _publish_delete(self, *, target: Path, manifest: bytes) -> None:
        if not target.exists():
            raise DocumentStoreError(_DELETE_FAILURE_MESSAGE)
        manifest_path = self._manifest_path
        try:
            old_manifest = manifest_path.read_bytes()
            old_manifest_exists = True
        except FileNotFoundError:
            old_manifest = b""
            old_manifest_exists = False
        except OSError as error:
            raise DocumentStoreError(_DELETE_FAILURE_MESSAGE) from error

        manifest_temp: Path | None = None
        backup_path: Path | None = None
        file_moved = False
        manifest_published = False
        try:
            manifest_temp = self._write_temp_file(
                manifest,
                prefix=f".{MANIFEST_FILENAME}.",
            )
            backup_path = self._reserve_temp_path(prefix=f".{target.name}.")
            os.replace(target, backup_path)
            file_moved = True
            os.replace(manifest_temp, manifest_path)
            manifest_published = True
            backup_path.unlink()
        except (OSError, DocumentStoreError) as error:
            try:
                if manifest_published:
                    self._restore_manifest(
                        old_manifest=old_manifest,
                        existed=old_manifest_exists,
                    )
                if file_moved and backup_path is not None:
                    os.replace(backup_path, target)
            except (OSError, DocumentStoreError) as rollback_error:
                self._mark_unavailable()
                raise DocumentStoreUnavailableError(
                    _STORE_UNAVAILABLE_MESSAGE
                ) from rollback_error
            if isinstance(error, DocumentStoreError):
                raise
            raise DocumentStoreError(_DELETE_FAILURE_MESSAGE) from error
        finally:
            self._unlink_quietly(manifest_temp)
            self._unlink_quietly(backup_path)

    def _restore_manifest(self, *, old_manifest: bytes, existed: bool) -> None:
        if existed:
            restore_temp = self._write_temp_file(
                old_manifest,
                prefix=f".{MANIFEST_FILENAME}.rollback.",
            )
            try:
                os.replace(restore_temp, self._manifest_path)
            finally:
                self._unlink_quietly(restore_temp)
        else:
            self._manifest_path.unlink(missing_ok=True)

    def _write_temp_file(self, content: bytes, *, prefix: str) -> Path:
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=self._storage_root,
                prefix=prefix,
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                temporary_file.write(content)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            return temporary_path
        except OSError as error:
            self._unlink_quietly(temporary_path)
            raise DocumentStoreError(_PERSISTENCE_FAILURE_MESSAGE) from error

    def _reserve_temp_path(self, *, prefix: str) -> Path:
        try:
            descriptor, path = tempfile.mkstemp(
                dir=self._storage_root,
                prefix=prefix,
                suffix=".tmp",
            )
            os.close(descriptor)
            temporary_path = Path(path)
            temporary_path.unlink()
            return temporary_path
        except OSError as error:
            raise DocumentStoreError(_DELETE_FAILURE_MESSAGE) from error

    def _require_available(self) -> None:
        if not self._available:
            raise DocumentStoreUnavailableError(_STORE_UNAVAILABLE_MESSAGE)

    def _mark_unavailable(self) -> None:
        self._available = False
        self._status_message = _STORE_UNAVAILABLE_MESSAGE
        logger.warning("Local document store is unavailable")

    def _document_path(self, document_id: str) -> Path:
        return self._storage_root / f"{document_id}.md"

    def _relative_path(self, document_id: str) -> str:
        return f"{UPLOADS_RELATIVE_DIRECTORY}/{document_id}.md"

    @property
    def _manifest_path(self) -> Path:
        return self._storage_root / MANIFEST_FILENAME

    @staticmethod
    def _unlink_quietly(path: Path | None) -> None:
        if path is None:
            return
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.warning("Could not clean a local document temporary file")


class DocumentCorpusService:
    """Own one active immutable corpus snapshot and serialized mutations."""

    def __init__(
        self,
        store: LocalDocumentStore | None = None,
        *,
        index_builder: IndexBuilder | None = None,
    ) -> None:
        self._store = store or LocalDocumentStore()
        self._index_builder = index_builder or document_domain.build_vector_index
        self._mutation_lock = RLock()
        documents = self._documents_from_store()
        self._active_snapshot = DocumentCorpusSnapshot(
            documents=documents,
            index=self._index_builder(self._chunks_for(documents)),
        )

    @property
    def status(self) -> DocumentStoreStatus:
        """Return the underlying local upload management status."""
        return self._store.status

    @property
    def active_snapshot(self) -> DocumentCorpusSnapshot:
        """Return the immutable snapshot currently used by readers."""
        return self._active_snapshot

    def get_snapshot(self) -> DocumentCorpusSnapshot:
        """Return the active snapshot for one consistent retrieval exchange."""
        return self._active_snapshot

    def get_index(self) -> VectorIndex:
        """Return the active immutable vector index."""
        return self._active_snapshot.index

    def list_documents(self) -> tuple[DocumentMetadata, ...]:
        """List metadata from the same snapshot used for retrieval."""
        return tuple(document.metadata for document in self._active_snapshot.documents)

    def get_document(self, document_id: str) -> StoredDocument | None:
        """Read one document from the active snapshot, if present."""
        for document in self._active_snapshot.documents:
            if document.metadata.document_id == document_id:
                return document
        return None

    def upload_document(self, *, filename: str, content: bytes) -> StoredDocument:
        """Publish one uploaded document after its candidate index is ready."""
        with self._mutation_lock:
            candidate_index: VectorIndex | None = None

            def build_candidate(chunks: tuple[DocumentChunk, ...]) -> VectorIndex:
                nonlocal candidate_index
                candidate_index = self._index_builder(chunks)
                return candidate_index

            document = self._store.upload_document(
                filename=filename,
                content=content,
                index_builder=build_candidate,
            )
            if candidate_index is None:
                raise DocumentStoreError(
                    "The candidate document corpus could not be indexed"
                )
            documents = self._active_snapshot.documents + (document,)
            self._active_snapshot = DocumentCorpusSnapshot(
                documents=documents,
                index=candidate_index,
            )
            return document

    def delete_document(self, document_id: str) -> None:
        """Remove one local document after its candidate index is ready."""
        with self._mutation_lock:
            candidate_index: VectorIndex | None = None

            def build_candidate(chunks: tuple[DocumentChunk, ...]) -> VectorIndex:
                nonlocal candidate_index
                candidate_index = self._index_builder(chunks)
                return candidate_index

            self._store.delete_document(
                document_id,
                index_builder=build_candidate,
            )
            if candidate_index is None:
                raise DocumentStoreError(
                    "The candidate document corpus could not be indexed"
                )
            documents = tuple(
                document
                for document in self._active_snapshot.documents
                if document.metadata.document_id != document_id
            )
            self._active_snapshot = DocumentCorpusSnapshot(
                documents=documents,
                index=candidate_index,
            )

    def _documents_from_store(self) -> tuple[StoredDocument, ...]:
        documents: list[StoredDocument] = []
        for metadata in self._store.list_documents():
            document = self._store.get_document(metadata.document_id)
            if document is None:
                raise DocumentStoreError("The active document corpus is unavailable")
            documents.append(document)
        return tuple(documents)

    @staticmethod
    def _chunks_for(
        documents: tuple[StoredDocument, ...],
    ) -> tuple[DocumentChunk, ...]:
        return tuple(chunk for document in documents for chunk in document.chunks)


_default_service_lock = RLock()
_default_service: DocumentCorpusService | None = None


def get_document_corpus_service() -> DocumentCorpusService:
    """Return the process-wide service used by default application callers."""
    global _default_service
    if _default_service is None:
        with _default_service_lock:
            if _default_service is None:
                _default_service = DocumentCorpusService()
    return _default_service
