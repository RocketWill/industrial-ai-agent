import json
from datetime import UTC, datetime

import pytest

from industrial_agent.mcp.server import call_tool, list_tools
from industrial_agent.tools.defect_distribution import (
    DefectDistributionRequest,
    get_defect_distribution,
)

REQUEST_ARGUMENTS = {
    "equipment_id": "AOI-WAFER-01",
    "lot_id": "LOT-DEMO-001",
    "start": "2026-01-15T13:00:00Z",
    "end": "2026-01-15T17:00:00Z",
}


@pytest.mark.anyio
async def test_server_discovers_defect_distribution_contract() -> None:
    tools = {tool.name: tool for tool in await list_tools()}

    tool = tools["get_defect_distribution"]
    assert tool.inputSchema["additionalProperties"] is False
    assert tool.outputSchema is not None


@pytest.mark.anyio
async def test_mcp_defect_distribution_matches_native_result() -> None:
    result = await call_tool("get_defect_distribution", REQUEST_ARGUMENTS)
    native = get_defect_distribution(
        DefectDistributionRequest(
            equipment_id="AOI-WAFER-01",
            lot_id="LOT-DEMO-001",
            start=datetime(2026, 1, 15, 13, tzinfo=UTC),
            end=datetime(2026, 1, 15, 17, tzinfo=UTC),
        )
    )

    assert result.isError is False
    assert result.structuredContent == native.model_dump(mode="json")
    assert json.loads(result.content[0].text) == result.structuredContent


@pytest.mark.anyio
async def test_mcp_defect_distribution_preserves_empty_evidence() -> None:
    result = await call_tool(
        "get_defect_distribution",
        {
            **REQUEST_ARGUMENTS,
            "start": "2026-01-10T13:00:00Z",
            "end": "2026-01-10T17:00:00Z",
        },
    )

    assert result.isError is False
    assert result.structuredContent is not None
    assert result.structuredContent["items"] == []
    assert result.structuredContent["limitations"]


@pytest.mark.anyio
async def test_mcp_defect_distribution_rejects_invalid_input() -> None:
    result = await call_tool(
        "get_defect_distribution",
        {**REQUEST_ARGUMENTS, "extra": "not-supported"},
    )

    assert result.isError is True
    assert result.content[0].text == "Invalid defect distribution request"


@pytest.mark.anyio
async def test_mcp_defect_distribution_keeps_safe_domain_errors() -> None:
    result = await call_tool(
        "get_defect_distribution",
        {**REQUEST_ARGUMENTS, "lot_id": "UNKNOWN"},
    )

    assert result.isError is True
    assert result.content[0].text == "Unknown Production Lot: UNKNOWN"


@pytest.mark.anyio
async def test_mcp_defect_distribution_sanitizes_unexpected_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_unexpectedly(request: DefectDistributionRequest) -> None:
        raise RuntimeError("private /tmp/defect-dataset")

    monkeypatch.setattr(
        "industrial_agent.mcp.server.get_defect_distribution",
        fail_unexpectedly,
    )

    result = await call_tool("get_defect_distribution", REQUEST_ARGUMENTS)

    assert result.isError is True
    assert result.content[0].text == "Defect distribution unavailable"
    assert "/tmp/defect-dataset" not in result.content[0].text
