import json
import os
from pathlib import Path

import pytest

from industrial_agent.domain.documents import (
    MAX_UPLOAD_BYTES,
    DocumentValidationError,
    normalize_uploaded_document_id,
)
from industrial_agent.services import documents as document_service
from industrial_agent.services.documents import (
    BuiltInDocumentError,
    DocumentConflictError,
    DocumentNotFoundError,
    DocumentStoreError,
    DocumentStoreStatus,
    DocumentStoreUnavailableError,
    LocalDocumentStore,
)

VALID_MARKDOWN = """# Optical Signal Guide

## Recovery

Record the fictional alarm before restarting the inspection sequence.
"""


def test_normalize_uploaded_document_id_creates_ascii_kebab_id() -> None:
    assert normalize_uploaded_document_id("Optical Signal Guide 2.md") == (
        "uploaded-optical-signal-guide-2"
    )


def test_local_store_upload_returns_ready_metadata_and_persists_markdown(
    tmp_path: Path,
) -> None:
    storage_root = tmp_path / "uploads"
    store = LocalDocumentStore(storage_root=storage_root)

    document = store.upload_document(
        filename="Optical Signal Guide.md",
        content=VALID_MARKDOWN.encode("utf-8"),
    )

    assert document.metadata.document_id == "uploaded-optical-signal-guide"
    assert document.metadata.title == "Optical Signal Guide"
    assert document.metadata.document_type == "uploaded_document"
    assert document.metadata.source == "local_upload"
    assert document.metadata.filename == "Optical Signal Guide.md"
    assert document.metadata.relative_path == (
        "uploads/uploaded-optical-signal-guide.md"
    )
    assert document.metadata.size_bytes == len(VALID_MARKDOWN.encode("utf-8"))
    assert document.metadata.status == "ready"
    assert document.metadata.deletable is True
    assert document.metadata.synthetic_demo is False
    assert document.markdown == VALID_MARKDOWN
    assert document.chunks[0].source_id == (
        "uploaded-optical-signal-guide:recovery:001"
    )
    assert (storage_root / "uploaded-optical-signal-guide.md").read_text(
        encoding="utf-8"
    ) == VALID_MARKDOWN
    assert (storage_root / "manifest.json").exists()


@pytest.mark.parametrize(
    ("filename", "content"),
    [
        ("guide.txt", VALID_MARKDOWN.encode("utf-8")),
        ("guide.md", b""),
        ("guide.md", b"# Guide\n\xff"),
        ("guide.md", b"Preamble\n\n# Guide\n\n## Recovery\n\nEvidence."),
        (
            "guide.md",
            b"# Guide\n\n## Recovery\n\nEvidence.\n\n# Second\n",
        ),
        ("guide.md", b"# Guide\n\nOverview only."),
        ("guide.md", b"# Guide\n\n## Empty\n"),
        ("guide.md", b"# Guide\n\n### No parent\n\nEvidence."),
    ],
)
def test_local_store_rejects_invalid_upload_without_publishing(
    tmp_path: Path,
    filename: str,
    content: bytes,
) -> None:
    storage_root = tmp_path / "uploads"
    store = LocalDocumentStore(storage_root=storage_root)

    with pytest.raises(DocumentValidationError):
        store.upload_document(filename=filename, content=content)

    assert tuple(storage_root.iterdir()) == ()
    assert store.list_documents()[-1].source == "built_in"


def test_local_store_accepts_exactly_one_mib(
    tmp_path: Path,
) -> None:
    prefix = b"# Boundary Guide\n\n## Recovery\n\n"
    content = prefix + b"a" * (MAX_UPLOAD_BYTES - len(prefix))
    store = LocalDocumentStore(storage_root=tmp_path / "uploads")

    document = store.upload_document(filename="boundary.md", content=content)

    assert document.metadata.size_bytes == MAX_UPLOAD_BYTES


def test_local_store_rejects_one_byte_over_one_mib(
    tmp_path: Path,
) -> None:
    prefix = b"# Boundary Guide\n\n## Recovery\n\n"
    content = prefix + b"a" * (MAX_UPLOAD_BYTES - len(prefix) + 1)
    store = LocalDocumentStore(storage_root=tmp_path / "uploads")

    with pytest.raises(DocumentValidationError, match="1 MiB"):
        store.upload_document(filename="boundary.md", content=content)


def test_local_store_rejects_filename_without_an_identifier(
    tmp_path: Path,
) -> None:
    store = LocalDocumentStore(storage_root=tmp_path / "uploads")

    with pytest.raises(DocumentValidationError, match="identifiable name"):
        store.upload_document(filename="文件.md", content=VALID_MARKDOWN.encode())


def test_local_store_rejects_duplicate_normalized_id_and_keeps_manifest(
    tmp_path: Path,
) -> None:
    storage_root = tmp_path / "uploads"
    store = LocalDocumentStore(storage_root=storage_root)
    store.upload_document(
        filename="Guide One.md",
        content=VALID_MARKDOWN.encode("utf-8"),
    )
    prior_manifest = (storage_root / "manifest.json").read_bytes()
    prior_files = {path.name for path in storage_root.iterdir()}

    with pytest.raises(DocumentConflictError, match="identity"):
        store.upload_document(
            filename="guide-one.md",
            content=VALID_MARKDOWN.encode("utf-8"),
        )

    assert (storage_root / "manifest.json").read_bytes() == prior_manifest
    assert {path.name for path in storage_root.iterdir()} == prior_files


def test_local_store_rejects_another_filename_with_the_same_normalized_id(
    tmp_path: Path,
) -> None:
    store = LocalDocumentStore(storage_root=tmp_path / "uploads")
    store.upload_document(
        filename="Unique Name.md",
        content=VALID_MARKDOWN.encode("utf-8"),
    )

    with pytest.raises(DocumentConflictError, match="identity"):
        store.upload_document(
            filename="unique_name.md",
            content=VALID_MARKDOWN.encode("utf-8"),
        )


def test_local_store_rejects_filename_collision_with_built_in_document(
    tmp_path: Path,
) -> None:
    store = LocalDocumentStore(storage_root=tmp_path / "uploads")

    with pytest.raises(DocumentConflictError, match="filename"):
        store.upload_document(
            filename="AOI-WAFER-INSPECTOR-ALARM-GUIDE.MD",
            content=VALID_MARKDOWN.encode("utf-8"),
        )


def test_local_store_recovers_upload_after_restart(
    tmp_path: Path,
) -> None:
    storage_root = tmp_path / "uploads"
    first_store = LocalDocumentStore(storage_root=storage_root)
    created = first_store.upload_document(
        filename="Restart Guide.md",
        content=VALID_MARKDOWN.encode("utf-8"),
    )
    manifest = (storage_root / "manifest.json").read_text(encoding="utf-8")

    restarted_store = LocalDocumentStore(storage_root=storage_root)
    recovered = restarted_store.get_document(created.metadata.document_id)

    assert recovered == created
    assert restarted_store.list_documents()[-1] == created.metadata
    assert str(tmp_path) not in manifest
    assert restarted_store.status == DocumentStoreStatus(available=True)


def test_invalid_local_state_keeps_built_ins_and_reports_safe_unavailability(
    tmp_path: Path,
) -> None:
    storage_root = tmp_path / "uploads"
    storage_root.mkdir()
    (storage_root / "manifest.json").write_text("not-json", encoding="utf-8")

    store = LocalDocumentStore(storage_root=storage_root)

    assert store.status == DocumentStoreStatus(
        available=False,
        message="Local uploaded-document storage is unavailable",
    )
    assert all(document.source == "built_in" for document in store.list_documents())
    assert str(tmp_path) not in (store.status.message or "")
    with pytest.raises(
        DocumentStoreUnavailableError,
        match="storage is unavailable",
    ):
        store.upload_document(
            filename="new.md",
            content=VALID_MARKDOWN.encode("utf-8"),
        )


def test_restart_does_not_silently_discard_invalid_uploaded_markdown(
    tmp_path: Path,
) -> None:
    storage_root = tmp_path / "uploads"
    store = LocalDocumentStore(storage_root=storage_root)
    created = store.upload_document(
        filename="Corrupted.md",
        content=VALID_MARKDOWN.encode("utf-8"),
    )
    content_path = storage_root / f"{created.metadata.document_id}.md"
    content_path.write_bytes(b"not valid Markdown")

    restarted_store = LocalDocumentStore(storage_root=storage_root)

    assert restarted_store.status.available is False
    assert restarted_store.get_document(created.metadata.document_id) is None
    assert content_path.exists()


def test_local_store_deletes_uploaded_document_and_updates_manifest(
    tmp_path: Path,
) -> None:
    storage_root = tmp_path / "uploads"
    store = LocalDocumentStore(storage_root=storage_root)
    created = store.upload_document(
        filename="Delete Guide.md",
        content=VALID_MARKDOWN.encode("utf-8"),
    )

    store.delete_document(created.metadata.document_id)

    assert store.get_document(created.metadata.document_id) is None
    assert all(
        metadata.document_id != created.metadata.document_id
        for metadata in store.list_documents()
    )
    assert not (storage_root / f"{created.metadata.document_id}.md").exists()
    assert json.loads((storage_root / "manifest.json").read_text()) == {
        "documents": [],
        "version": 1,
    }


def test_local_store_rejects_built_in_delete_without_mutation(
    tmp_path: Path,
) -> None:
    storage_root = tmp_path / "uploads"
    store = LocalDocumentStore(storage_root=storage_root)
    before = store.list_documents()

    with pytest.raises(BuiltInDocumentError, match="cannot be deleted"):
        store.delete_document(before[0].document_id)

    assert store.list_documents() == before
    assert tuple(storage_root.iterdir()) == ()


def test_local_store_rejects_unknown_delete_without_mutation(
    tmp_path: Path,
) -> None:
    storage_root = tmp_path / "uploads"
    store = LocalDocumentStore(storage_root=storage_root)
    before = store.list_documents()

    with pytest.raises(DocumentNotFoundError, match="not found"):
        store.delete_document("uploaded-missing-document")

    assert store.list_documents() == before
    assert tuple(storage_root.iterdir()) == ()


def test_upload_manifest_publication_failure_rolls_back_disk_and_memory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage_root = tmp_path / "uploads"
    store = LocalDocumentStore(storage_root=storage_root)
    existing = store.upload_document(
        filename="Existing Guide.md",
        content=VALID_MARKDOWN.encode("utf-8"),
    )
    before_metadata = store.list_documents()
    before_disk = {
        path.name: path.read_bytes() for path in storage_root.iterdir()
    }
    manifest_path = storage_root / "manifest.json"
    original_replace = os.replace

    def fail_manifest_replace(
        source: str | os.PathLike[str],
        destination: str | os.PathLike[str],
    ) -> None:
        if Path(destination) == manifest_path:
            raise OSError("manifest publication failed")
        original_replace(source, destination)

    monkeypatch.setattr(document_service.os, "replace", fail_manifest_replace)

    with pytest.raises(DocumentStoreError, match="could not be saved"):
        store.upload_document(
            filename="New Guide.md",
            content=VALID_MARKDOWN.encode("utf-8"),
        )

    assert store.list_documents() == before_metadata
    assert store.get_document(existing.metadata.document_id) == existing
    assert {
        path.name: path.read_bytes() for path in storage_root.iterdir()
    } == before_disk
    assert not (storage_root / "uploaded-new-guide.md").exists()


def test_delete_manifest_publication_failure_rolls_back_disk_and_memory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage_root = tmp_path / "uploads"
    store = LocalDocumentStore(storage_root=storage_root)
    existing = store.upload_document(
        filename="Delete Failure Guide.md",
        content=VALID_MARKDOWN.encode("utf-8"),
    )
    before_metadata = store.list_documents()
    before_disk = {
        path.name: path.read_bytes() for path in storage_root.iterdir()
    }
    manifest_path = storage_root / "manifest.json"
    original_replace = os.replace

    def fail_manifest_replace(
        source: str | os.PathLike[str],
        destination: str | os.PathLike[str],
    ) -> None:
        if Path(destination) == manifest_path:
            raise OSError("manifest publication failed")
        original_replace(source, destination)

    monkeypatch.setattr(document_service.os, "replace", fail_manifest_replace)

    with pytest.raises(DocumentStoreError, match="could not be deleted"):
        store.delete_document(existing.metadata.document_id)

    assert store.list_documents() == before_metadata
    assert store.get_document(existing.metadata.document_id) == existing
    assert {
        path.name: path.read_bytes() for path in storage_root.iterdir()
    } == before_disk


def test_delete_final_backup_cleanup_failure_rolls_back_disk_and_memory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage_root = tmp_path / "uploads"
    store = LocalDocumentStore(storage_root=storage_root)
    existing = store.upload_document(
        filename="Backup Failure Guide.md",
        content=VALID_MARKDOWN.encode("utf-8"),
    )
    before_metadata = store.list_documents()
    before_disk = {
        path.name: path.read_bytes() for path in storage_root.iterdir()
    }
    target_prefix = f".{existing.metadata.document_id}.md."
    original_unlink = Path.unlink
    original_replace = os.replace
    cleanup_failure_armed = False

    def arm_after_backup_move(
        source: str | os.PathLike[str],
        destination: str | os.PathLike[str],
    ) -> None:
        nonlocal cleanup_failure_armed
        if Path(source) == storage_root / f"{existing.metadata.document_id}.md":
            cleanup_failure_armed = True
        original_replace(source, destination)

    def fail_backup_unlink(path: Path, *args: object, **kwargs: object) -> None:
        if (
            cleanup_failure_armed
            and path.parent == storage_root
            and path.name.startswith(target_prefix)
        ):
            raise OSError("backup cleanup failed")
        original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(document_service.os, "replace", arm_after_backup_move)
    monkeypatch.setattr(Path, "unlink", fail_backup_unlink)

    with pytest.raises(DocumentStoreError, match="could not be deleted"):
        store.delete_document(existing.metadata.document_id)

    assert store.list_documents() == before_metadata
    assert store.get_document(existing.metadata.document_id) == existing
    assert {
        path.name: path.read_bytes() for path in storage_root.iterdir()
    } == before_disk
