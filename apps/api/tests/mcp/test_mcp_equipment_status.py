import json
from datetime import UTC, datetime

import pytest

from industrial_agent.mcp.server import call_tool, list_tools
from industrial_agent.tools.equipment_status import (
    EquipmentStatusRequest,
    get_equipment_status,
)


@pytest.mark.anyio
async def test_server_discovers_equipment_status_contract() -> None:
    tools = {tool.name: tool for tool in await list_tools()}

    tool = tools["get_equipment_status"]
    assert tool.inputSchema["additionalProperties"] is False
    assert tool.outputSchema is not None


@pytest.mark.anyio
async def test_mcp_equipment_status_matches_native_result() -> None:
    arguments = {
        "equipment_id": "AOI-WAFER-01",
        "at": "2026-01-15T15:30:00Z",
    }

    result = await call_tool("get_equipment_status", arguments)
    native = get_equipment_status(
        EquipmentStatusRequest(
            equipment_id="AOI-WAFER-01",
            at=datetime(2026, 1, 15, 15, 30, tzinfo=UTC),
        )
    )

    assert result.isError is False
    assert result.structuredContent == native.model_dump(mode="json")
    assert json.loads(result.content[0].text) == result.structuredContent


@pytest.mark.anyio
async def test_mcp_equipment_status_preserves_unknown_evidence() -> None:
    result = await call_tool(
        "get_equipment_status",
        {"equipment_id": "AOI-WAFER-01", "at": "2026-01-15T19:00:00Z"},
    )

    assert result.isError is False
    assert result.structuredContent is not None
    assert result.structuredContent["status"] == "unknown"
    assert result.structuredContent["limitations"] == [
        "no_recorded_equipment_state"
    ]


@pytest.mark.anyio
async def test_mcp_equipment_status_rejects_invalid_input() -> None:
    result = await call_tool(
        "get_equipment_status",
        {
            "equipment_id": "AOI-WAFER-01",
            "at": "2026-01-15T15:30:00+08:00",
            "unsupported": True,
        },
    )

    assert result.isError is True
    assert result.content[0].text == "Invalid equipment status request"


@pytest.mark.anyio
async def test_mcp_equipment_status_keeps_safe_domain_errors() -> None:
    result = await call_tool(
        "get_equipment_status",
        {"equipment_id": "UNKNOWN", "at": "2026-01-15T15:30:00Z"},
    )

    assert result.isError is True
    assert result.content[0].text == "Unknown Equipment: UNKNOWN"


@pytest.mark.anyio
async def test_mcp_equipment_status_sanitizes_unexpected_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_unexpectedly(request: EquipmentStatusRequest) -> None:
        raise RuntimeError("private /tmp/status-dataset")

    monkeypatch.setattr(
        "industrial_agent.mcp.server.get_equipment_status",
        fail_unexpectedly,
    )

    result = await call_tool(
        "get_equipment_status",
        {"equipment_id": "AOI-WAFER-01", "at": "2026-01-15T15:30:00Z"},
    )

    assert result.isError is True
    assert result.content[0].text == "Equipment status unavailable"
    assert "/tmp/status-dataset" not in result.content[0].text
