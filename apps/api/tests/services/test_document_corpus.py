from __future__ import annotations

import threading
from pathlib import Path

import pytest

from industrial_agent.domain.documents import build_vector_index
from industrial_agent.main import create_app
from industrial_agent.services.documents import (
    DocumentCorpusService,
    DocumentStoreError,
    LocalDocumentStore,
)
from industrial_agent.tools.document_search import (
    DocumentSearchRequest,
    search_documents,
)

VALID_MARKDOWN = """# Optical Signal Upload

## Recovery

Inspect the fictional signal window before restarting the sequence.
Record the local-upload-marker before closing the guide.
"""


def make_service(tmp_path: Path) -> DocumentCorpusService:
    return DocumentCorpusService(
        store=LocalDocumentStore(storage_root=tmp_path / "uploads")
    )


def test_application_wires_the_supplied_corpus_service(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    application = create_app(document_corpus_service=service)

    assert application.state.document_corpus_service is service


def test_service_owns_one_immutable_active_index_snapshot(
    tmp_path: Path,
) -> None:
    service = make_service(tmp_path)
    previous_index = service.get_index()
    previous_document_ids = tuple(
        chunk.document_id for chunk, _ in previous_index.entries
    )

    service.upload_document(
        filename="Optical Signal Upload.md",
        content=VALID_MARKDOWN.encode("utf-8"),
    )

    assert service.get_index() is not previous_index
    assert tuple(
        chunk.document_id for chunk, _ in previous_index.entries
    ) == previous_document_ids
    assert all(
        document_id != "uploaded-optical-signal-upload"
        for document_id in previous_document_ids
    )
    assert service.get_document("uploaded-optical-signal-upload") is not None


def test_reader_continues_using_previous_snapshot_during_candidate_build(
    tmp_path: Path,
) -> None:
    started = threading.Event()
    release = threading.Event()
    calls = 0

    def blocking_index_builder(chunks):
        nonlocal calls
        calls += 1
        if calls == 2:
            started.set()
            assert release.wait(timeout=2)
        return build_vector_index(chunks)

    service = DocumentCorpusService(
        store=LocalDocumentStore(storage_root=tmp_path / "uploads"),
        index_builder=blocking_index_builder,
    )
    upload_error: list[BaseException] = []

    def upload() -> None:
        try:
            service.upload_document(
                filename="Concurrent Guide.md",
                content=VALID_MARKDOWN.encode("utf-8"),
            )
        except BaseException as error:  # pragma: no cover - assertion aid
            upload_error.append(error)

    worker = threading.Thread(target=upload)
    worker.start()
    assert started.wait(timeout=2)

    previous_result = search_documents(
        DocumentSearchRequest(query="local-upload-marker", limit=3),
        service=service,
    )

    release.set()
    worker.join(timeout=2)

    assert upload_error == []
    assert previous_result.sources == ()
    assert search_documents(
        DocumentSearchRequest(query="local-upload-marker", limit=3),
        service=service,
    ).sources[0].source == "local_upload"


def test_candidate_index_failure_keeps_active_snapshot_and_disk_unchanged(
    tmp_path: Path,
) -> None:
    calls = 0

    def fail_on_candidate(chunks):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("candidate index failed")
        return build_vector_index(chunks)

    storage_root = tmp_path / "uploads"
    service = DocumentCorpusService(
        store=LocalDocumentStore(storage_root=storage_root),
        index_builder=fail_on_candidate,
    )
    before_files = tuple(path.name for path in storage_root.iterdir())
    before_index = service.get_index()

    with pytest.raises(DocumentStoreError, match="could not be indexed"):
        service.upload_document(
            filename="Failed Candidate.md",
            content=VALID_MARKDOWN.encode("utf-8"),
        )

    assert service.get_index() is before_index
    assert service.get_document("uploaded-failed-candidate") is None
    assert tuple(path.name for path in storage_root.iterdir()) == before_files


def test_mutations_are_serialized_by_the_service_boundary(tmp_path: Path) -> None:
    first_started = threading.Event()
    release_first = threading.Event()
    second_attempted = threading.Event()
    second_builder_called = threading.Event()
    calls = 0

    def serial_index_builder(chunks):
        nonlocal calls
        calls += 1
        if calls == 2:
            first_started.set()
            assert release_first.wait(timeout=2)
        elif calls == 3:
            second_builder_called.set()
        return build_vector_index(chunks)

    service = DocumentCorpusService(
        store=LocalDocumentStore(storage_root=tmp_path / "uploads"),
        index_builder=serial_index_builder,
    )
    errors: list[BaseException] = []

    def upload(filename: str, attempted: threading.Event | None = None) -> None:
        if attempted is not None:
            attempted.set()
        try:
            service.upload_document(
                filename=filename,
                content=VALID_MARKDOWN.encode("utf-8"),
            )
        except BaseException as error:  # pragma: no cover - assertion aid
            errors.append(error)

    first = threading.Thread(target=upload, args=("First Guide.md",))
    second = threading.Thread(
        target=upload,
        args=("Second Guide.md", second_attempted),
    )
    first.start()
    assert first_started.wait(timeout=2)
    second.start()
    assert second_attempted.wait(timeout=2)
    assert not second_builder_called.is_set()

    release_first.set()
    first.join(timeout=2)
    second.join(timeout=2)

    assert errors == []
    assert {item.filename for item in service.list_documents() if item.deletable} == {
        "First Guide.md",
        "Second Guide.md",
    }


def test_upload_then_delete_changes_search_for_the_same_service(
    tmp_path: Path,
) -> None:
    service = make_service(tmp_path)

    created = service.upload_document(
        filename="Local Recovery Guide.md",
        content=VALID_MARKDOWN.encode("utf-8"),
    )
    query = DocumentSearchRequest(query="local-upload-marker", limit=3)

    uploaded_result = search_documents(query, service=service)
    assert uploaded_result.sources[0].source == "local_upload"
    assert uploaded_result.sources[0].source_id.startswith(
        "uploaded-local-recovery-guide:"
    )
    assert service.get_document(created.metadata.document_id) == created

    service.delete_document(created.metadata.document_id)

    assert search_documents(query, service=service).sources == ()
    assert service.get_document(created.metadata.document_id) is None
    assert all(
        item.document_id != created.metadata.document_id
        for item in service.list_documents()
    )


def test_invalid_local_state_keeps_built_ins_searchable_in_service(
    tmp_path: Path,
) -> None:
    storage_root = tmp_path / "uploads"
    storage_root.mkdir()
    (storage_root / "manifest.json").write_text("not-json", encoding="utf-8")
    service = DocumentCorpusService(
        store=LocalDocumentStore(storage_root=storage_root)
    )

    result = search_documents(
        DocumentSearchRequest(query="OPTICAL-SIGNAL-LOW optical lens cover"),
        service=service,
    )

    assert result.sources[0].source == "built_in"
    assert service.status.available is False
    assert all(item.source == "built_in" for item in service.list_documents())
