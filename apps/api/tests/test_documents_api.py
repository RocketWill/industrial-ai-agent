from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from industrial_agent.main import create_app
from industrial_agent.services.documents import (
    DocumentCorpusService,
    DocumentStoreError,
    LocalDocumentStore,
)

VALID_MARKDOWN = """# Optical Signal Upload

## Recovery

Inspect the fictional signal window before restarting the sequence.
Record the local-upload-marker before closing the guide.
"""


@pytest.fixture
def document_client(tmp_path: Path) -> Generator[TestClient, None, None]:
    service = DocumentCorpusService(
        store=LocalDocumentStore(storage_root=tmp_path / "uploads")
    )
    with TestClient(create_app(document_corpus_service=service)) as client:
        yield client


def test_lists_ordered_document_metadata(document_client: TestClient) -> None:
    response = document_client.get("/documents")

    assert response.status_code == 200
    payload = response.json()
    assert [item["document_id"] for item in payload] == [
        "aoi-alarm-guide",
        "aoi-operator-sop",
        "aoi-preventive-maintenance-guide",
    ]
    assert set(payload[0]) == {
        "document_id",
        "title",
        "document_type",
        "source",
        "filename",
        "relative_path",
        "size_bytes",
        "status",
        "deletable",
        "synthetic_demo",
    }
    assert all(item["source"] == "built_in" for item in payload)
    assert all(item["status"] == "ready" for item in payload)
    assert all(item["deletable"] is False for item in payload)
    assert all(item["synthetic_demo"] is True for item in payload)


def test_upload_returns_metadata_and_full_read(document_client: TestClient) -> None:
    response = document_client.post(
        "/documents",
        files={
            "file": (
                "Optical Signal Upload.md",
                VALID_MARKDOWN.encode("utf-8"),
                "text/markdown",
            )
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload == {
        "document_id": "uploaded-optical-signal-upload",
        "title": "Optical Signal Upload",
        "document_type": "uploaded_document",
        "source": "local_upload",
        "filename": "Optical Signal Upload.md",
        "relative_path": "uploads/uploaded-optical-signal-upload.md",
        "size_bytes": len(VALID_MARKDOWN.encode("utf-8")),
        "status": "ready",
        "deletable": True,
        "synthetic_demo": False,
    }

    read_response = document_client.get(
        "/documents/uploaded-optical-signal-upload"
    )

    assert read_response.status_code == 200
    read_payload = read_response.json()
    assert read_payload["document_id"] == payload["document_id"]
    assert read_payload["source"] == "local_upload"
    assert read_payload["synthetic_demo"] is False
    assert read_payload["markdown"] == VALID_MARKDOWN
    listed_ids = [
        item["document_id"] for item in document_client.get("/documents").json()
    ]
    assert listed_ids[-1] == "uploaded-optical-signal-upload"


def test_delete_uploaded_document_returns_204_and_removes_read_access(
    document_client: TestClient,
) -> None:
    upload_response = document_client.post(
        "/documents",
        files={"file": ("Delete Guide.md", VALID_MARKDOWN, "text/markdown")},
    )
    assert upload_response.status_code == 201
    document_id = upload_response.json()["document_id"]

    delete_response = document_client.delete(f"/documents/{document_id}")

    assert delete_response.status_code == 204
    assert delete_response.content == b""
    assert document_client.get(f"/documents/{document_id}").status_code == 404
    assert all(
        item["document_id"] != document_id
        for item in document_client.get("/documents").json()
    )


@pytest.mark.parametrize("document_id", [
    "aoi-alarm-guide",
    "aoi-operator-sop",
    "aoi-preventive-maintenance-guide",
])
def test_delete_rejects_built_in_documents(
    document_client: TestClient,
    document_id: str,
) -> None:
    response = document_client.delete(f"/documents/{document_id}")

    assert response.status_code == 403
    assert response.json() == {"detail": "Built-in documents cannot be deleted"}


def test_delete_unknown_document_returns_not_found(
    document_client: TestClient,
) -> None:
    response = document_client.delete("/documents/uploaded-missing-document")

    assert response.status_code == 404
    assert response.json() == {"detail": "Document not found"}


def test_duplicate_upload_returns_conflict_without_replacing_document(
    document_client: TestClient,
) -> None:
    first = document_client.post(
        "/documents",
        files={"file": ("Duplicate Guide.md", VALID_MARKDOWN, "text/markdown")},
    )
    assert first.status_code == 201

    replacement_markdown = VALID_MARKDOWN.replace(
        "local-upload-marker", "replacement-marker"
    )
    second = document_client.post(
        "/documents",
        files={
            "file": (
                "duplicate-guide.MD",
                replacement_markdown,
                "text/markdown",
            )
        },
    )

    assert second.status_code == 409
    assert document_client.get(
        "/documents/uploaded-duplicate-guide"
    ).json()["markdown"] == VALID_MARKDOWN


@pytest.mark.parametrize(
    ("filename", "content_type"),
    [("notes.txt", "text/plain"), ("notes.md", "image/png")],
)
def test_upload_rejects_unsupported_filename_or_media(
    document_client: TestClient,
    filename: str,
    content_type: str,
) -> None:
    response = document_client.post(
        "/documents",
        files={"file": (filename, VALID_MARKDOWN, content_type)},
    )

    assert response.status_code == 415
    assert response.json()["detail"] in {
        "Only Markdown (.md) files are supported",
        "The upload media type is not supported",
    }


@pytest.mark.parametrize(
    "content",
    [
        b"",
        b"\xff\xfe\xfd",
        b"## Missing title\n\nContent\n",
        b"# First\n\n# Second\n\n## Recovery\n\nContent\n",
        b"# No section\n\nOnly overview content\n",
    ],
)
def test_upload_rejects_invalid_markdown(
    document_client: TestClient,
    content: bytes,
) -> None:
    response = document_client.post(
        "/documents",
        files={"file": ("invalid.md", content, "text/markdown")},
    )

    assert response.status_code == 422
    assert "private" not in response.text.casefold()


def _markdown_of_size(size_bytes: int) -> bytes:
    prefix = "# Sized Upload\n\n## Content\n\n"
    prefix_bytes = prefix.encode("utf-8")
    assert len(prefix_bytes) <= size_bytes
    return prefix_bytes + (b"x" * (size_bytes - len(prefix_bytes)))


def test_upload_accepts_exactly_one_mib(document_client: TestClient) -> None:
    content = _markdown_of_size(1024 * 1024)

    response = document_client.post(
        "/documents",
        files={"file": ("one-mib.md", content, "text/markdown")},
    )

    assert response.status_code == 201
    assert response.json()["size_bytes"] == 1024 * 1024


def test_upload_rejects_one_byte_over_limit(document_client: TestClient) -> None:
    content = _markdown_of_size(1024 * 1024 + 1)

    response = document_client.post(
        "/documents",
        files={"file": ("over-limit.md", content, "text/markdown")},
    )

    assert response.status_code == 413
    assert response.json() == {
        "detail": "The Markdown document exceeds the 1 MiB limit"
    }


def test_upload_requires_one_multipart_file_field(
    document_client: TestClient,
) -> None:
    missing = document_client.post("/documents")
    extra = document_client.post(
        "/documents",
        files=[
            ("file", ("valid.md", VALID_MARKDOWN, "text/markdown")),
            ("extra", (None, "unexpected")),
        ],
    )
    duplicate = document_client.post(
        "/documents",
        files=[
            ("file", ("first.md", VALID_MARKDOWN, "text/markdown")),
            ("file", ("second.md", VALID_MARKDOWN, "text/markdown")),
        ],
    )

    assert missing.status_code == 422
    assert extra.status_code == 422
    assert duplicate.status_code == 422


def test_uploaded_document_survives_application_restart(tmp_path: Path) -> None:
    storage_root = tmp_path / "uploads"
    first_service = DocumentCorpusService(
        store=LocalDocumentStore(storage_root=storage_root)
    )
    with TestClient(create_app(document_corpus_service=first_service)) as client:
        upload_response = client.post(
            "/documents",
            files={
                "file": (
                    "Restart Guide.md",
                    VALID_MARKDOWN,
                    "text/markdown",
                )
            },
        )
    assert upload_response.status_code == 201

    restarted_service = DocumentCorpusService(
        store=LocalDocumentStore(storage_root=storage_root)
    )
    with TestClient(create_app(document_corpus_service=restarted_service)) as client:
        list_response = client.get("/documents")
        read_response = client.get("/documents/uploaded-restart-guide")

    assert list_response.status_code == 200
    assert list_response.json()[-1]["document_id"] == "uploaded-restart-guide"
    assert read_response.status_code == 200
    assert read_response.json()["markdown"] == VALID_MARKDOWN


def test_list_reports_unavailable_local_storage_without_exposing_path(
    tmp_path: Path,
) -> None:
    storage_root = tmp_path / "uploads"
    storage_root.mkdir()
    (storage_root / "manifest.json").write_text("not-json", encoding="utf-8")
    service = DocumentCorpusService(
        store=LocalDocumentStore(storage_root=storage_root)
    )

    with TestClient(create_app(document_corpus_service=service)) as client:
        list_response = client.get("/documents")
        built_in_response = client.get("/documents/aoi-alarm-guide")

    assert list_response.status_code == 503
    unavailable_payload = list_response.json()
    assert unavailable_payload["detail"] == (
        "Local uploaded-document storage is unavailable"
    )
    assert len(unavailable_payload["documents"]) == 3
    assert all(
        document["source"] == "built_in"
        for document in unavailable_payload["documents"]
    )
    assert str(storage_root) not in list_response.text
    assert built_in_response.status_code == 200


def test_upload_storage_failure_returns_safe_503(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    absolute_path = tmp_path / "private" / "manifest.json"
    service = DocumentCorpusService(
        store=LocalDocumentStore(storage_root=tmp_path / "uploads")
    )

    def fail_upload(*, filename: str, content: bytes):
        raise DocumentStoreError(f"cannot save {absolute_path}")

    monkeypatch.setattr(service, "upload_document", fail_upload)
    with TestClient(create_app(document_corpus_service=service)) as client:
        response = client.post(
            "/documents",
            files={"file": ("safe.md", VALID_MARKDOWN, "text/markdown")},
        )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Document storage is temporarily unavailable"
    }
    assert str(absolute_path) not in response.text


def test_delete_storage_failure_returns_safe_503(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    absolute_path = tmp_path / "private" / "manifest.json"
    service = DocumentCorpusService(
        store=LocalDocumentStore(storage_root=tmp_path / "uploads")
    )
    created = service.upload_document(
        filename="Delete Failure.md",
        content=VALID_MARKDOWN.encode("utf-8"),
    )

    def fail_delete(_document_id: str):
        raise DocumentStoreError(f"cannot delete {absolute_path}")

    monkeypatch.setattr(service, "delete_document", fail_delete)
    with TestClient(create_app(document_corpus_service=service)) as client:
        response = client.delete(
            f"/documents/{created.metadata.document_id}"
        )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Document storage is temporarily unavailable"
    }
    assert str(absolute_path) not in response.text


def test_reads_a_registry_owned_document(document_client: TestClient) -> None:
    response = document_client.get("/documents/aoi-alarm-guide")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {
        "document_id",
        "title",
        "document_type",
        "source",
        "filename",
        "relative_path",
        "size_bytes",
        "status",
        "deletable",
        "markdown",
        "synthetic_demo",
    }
    assert payload["document_id"] == "aoi-alarm-guide"
    assert payload["title"] == "AOI Wafer Inspector Alarm Guide"
    assert payload["document_type"] == "alarm_guide"
    assert payload["relative_path"] == (
        "data/synthetic/documents/aoi-wafer-inspector-alarm-guide.md"
    )
    assert payload["source"] == "built_in"
    assert payload["filename"] == "aoi-wafer-inspector-alarm-guide.md"
    assert payload["status"] == "ready"
    assert payload["deletable"] is False
    assert payload["synthetic_demo"] is True
    assert payload["markdown"].startswith(
        "# AOI Wafer Inspector Alarm Guide\n"
    )


@pytest.mark.parametrize(
    ("document_id", "title", "document_type", "relative_path", "heading"),
    [
        (
            "aoi-operator-sop",
            "AOI Operator Inspection SOP",
            "operator_sop",
            "data/synthetic/documents/aoi-operator-inspection-sop.md",
            "# AOI Operator Inspection SOP\n",
        ),
        (
            "aoi-preventive-maintenance-guide",
            "AOI Preventive Maintenance Guide",
            "maintenance_guide",
            "data/synthetic/documents/aoi-preventive-maintenance-guide.md",
            "# AOI Preventive Maintenance Guide\n",
        ),
    ],
)
def test_reads_each_other_registry_owned_document(
    document_client: TestClient,
    document_id: str,
    title: str,
    document_type: str,
    relative_path: str,
    heading: str,
) -> None:
    response = document_client.get(f"/documents/{document_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["document_id"] == document_id
    assert payload["title"] == title
    assert payload["document_type"] == document_type
    assert payload["source"] == "built_in"
    assert payload["relative_path"] == relative_path
    assert payload["synthetic_demo"] is True
    assert payload["markdown"].startswith(heading)


def test_unknown_document_id_returns_not_found(document_client: TestClient) -> None:
    response = document_client.get("/documents/not-in-registry")

    assert response.status_code == 404
    assert response.json() == {"detail": "Document not found"}


def test_document_domain_failure_returns_safe_service_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    absolute_path = tmp_path / "private-document.md"
    service = DocumentCorpusService(
        store=LocalDocumentStore(storage_root=tmp_path / "uploads")
    )

    def fail_to_read(_document_id: str):
        raise DocumentStoreError(f"cannot read {absolute_path}")

    monkeypatch.setattr(service, "get_document", fail_to_read)
    with TestClient(create_app(document_corpus_service=service)) as client:
        response = client.get("/documents/aoi-alarm-guide")

    assert response.status_code == 503
    assert response.json() == {"detail": "Document corpus unavailable"}
    assert str(absolute_path) not in response.text
