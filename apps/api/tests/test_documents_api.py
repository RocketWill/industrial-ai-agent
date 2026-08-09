import pytest

from industrial_agent.api import documents as documents_api
from industrial_agent.domain.documents import CorpusConstructionError


def test_reads_a_registry_owned_document(conversation_client) -> None:
    response = conversation_client.get("/documents/aoi-alarm-guide")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {
        "document_id",
        "title",
        "document_type",
        "relative_path",
        "markdown",
        "synthetic_demo",
    }
    assert payload["document_id"] == "aoi-alarm-guide"
    assert payload["title"] == "AOI Wafer Inspector Alarm Guide"
    assert payload["document_type"] == "alarm_guide"
    assert payload["relative_path"] == (
        "data/synthetic/documents/aoi-wafer-inspector-alarm-guide.md"
    )
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
    conversation_client,
    document_id: str,
    title: str,
    document_type: str,
    relative_path: str,
    heading: str,
) -> None:
    response = conversation_client.get(f"/documents/{document_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["document_id"] == document_id
    assert payload["title"] == title
    assert payload["document_type"] == document_type
    assert payload["relative_path"] == relative_path
    assert payload["synthetic_demo"] is True
    assert payload["markdown"].startswith(heading)


def test_unknown_document_id_returns_not_found(conversation_client) -> None:
    response = conversation_client.get("/documents/not-in-registry")

    assert response.status_code == 404
    assert response.json() == {"detail": "Document not found"}


def test_document_domain_failure_returns_safe_service_unavailable(
    conversation_client,
    monkeypatch,
    tmp_path,
) -> None:
    absolute_path = tmp_path / "private-document.md"

    def fail_to_read(_document_id: str):
        raise CorpusConstructionError(f"cannot read {absolute_path}")

    monkeypatch.setattr(
        documents_api,
        "read_registry_document",
        fail_to_read,
    )

    response = conversation_client.get("/documents/aoi-alarm-guide")

    assert response.status_code == 503
    assert response.json() == {"detail": "Document corpus unavailable"}
    assert str(absolute_path) not in response.text
