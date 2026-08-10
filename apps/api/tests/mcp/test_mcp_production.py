import json
from datetime import UTC, datetime

import pytest

from industrial_agent.mcp.server import call_tool, list_tools
from industrial_agent.tools.production import (
    ProductionSummaryRequest,
    get_production_summary,
)

REQUEST_ARGUMENTS = {
    "equipment_id": "AOI-WAFER-01",
    "lot_id": "LOT-DEMO-001",
    "start": "2026-01-15T13:00:00Z",
    "end": "2026-01-15T17:00:00Z",
}


@pytest.mark.anyio
async def test_server_discovers_the_production_summary_contract() -> None:
    tools = await list_tools()
    production_tool = next(
        tool for tool in tools if tool.name == "get_production_summary"
    )

    assert production_tool.outputSchema is not None
    assert production_tool.inputSchema["additionalProperties"] is False


@pytest.mark.anyio
async def test_mcp_production_summary_matches_the_native_result() -> None:
    result = await call_tool(
        "get_production_summary",
        REQUEST_ARGUMENTS,
    )
    native = get_production_summary(
        ProductionSummaryRequest(
            equipment_id="AOI-WAFER-01",
            lot_id="LOT-DEMO-001",
            start=datetime(2026, 1, 15, 13, tzinfo=UTC),
            end=datetime(2026, 1, 15, 17, tzinfo=UTC),
        )
    )

    assert result.structuredContent == native.model_dump(mode="json")
    assert result.isError is False
    assert len(result.content) == 1
    assert json.loads(result.content[0].text) == result.structuredContent


@pytest.mark.anyio
async def test_mcp_production_summary_rejects_extra_input_fields() -> None:
    result = await call_tool(
        "get_production_summary",
        {**REQUEST_ARGUMENTS, "conversation_id": "not-supported"},
    )

    assert result.isError is True
    assert result.content[0].text == "Invalid production summary request"


@pytest.mark.anyio
async def test_mcp_production_summary_preserves_empty_evidence() -> None:
    result = await call_tool(
        "get_production_summary",
        {
            **REQUEST_ARGUMENTS,
            "start": "2026-01-10T13:00:00Z",
            "end": "2026-01-10T17:00:00Z",
        },
    )

    assert result.isError is False
    assert result.structuredContent is not None
    assert result.structuredContent["inspected_wafers"] == 0
    assert result.structuredContent["yield_rate"] is None
    assert result.structuredContent["limitations"]


@pytest.mark.anyio
async def test_mcp_production_summary_keeps_safe_domain_errors() -> None:
    result = await call_tool(
        "get_production_summary",
        {**REQUEST_ARGUMENTS, "equipment_id": "UNKNOWN"},
    )

    assert result.isError is True
    assert result.content[0].text == "Unknown Equipment: UNKNOWN"


@pytest.mark.anyio
async def test_mcp_production_summary_rejects_non_utc_ranges() -> None:
    result = await call_tool(
        "get_production_summary",
        {
            **REQUEST_ARGUMENTS,
            "start": "2026-01-15T13:00:00+08:00",
            "end": "2026-01-15T17:00:00+08:00",
        },
    )

    assert result.isError is True
    assert result.content[0].text == "Invalid production summary request"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "arguments",
    [
        {key: value for key, value in REQUEST_ARGUMENTS.items() if key != "start"},
        {
            **REQUEST_ARGUMENTS,
            "start": "2026-01-15T17:00:00Z",
            "end": "2026-01-15T13:00:00Z",
        },
    ],
)
async def test_mcp_production_summary_rejects_incomplete_or_reversed_ranges(
    arguments: dict[str, str],
) -> None:
    result = await call_tool("get_production_summary", arguments)

    assert result.isError is True
    assert result.content[0].text == "Invalid production summary request"


@pytest.mark.anyio
async def test_mcp_production_summary_sanitizes_unexpected_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_unexpectedly(request: ProductionSummaryRequest) -> None:
        raise RuntimeError("private /tmp/dataset-path")

    monkeypatch.setattr(
        "industrial_agent.mcp.server.get_production_summary",
        fail_unexpectedly,
    )

    result = await call_tool("get_production_summary", REQUEST_ARGUMENTS)

    assert result.isError is True
    assert result.content[0].text == "Production summary unavailable"
    assert "/tmp/dataset-path" not in result.content[0].text
