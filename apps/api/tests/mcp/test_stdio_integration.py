from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryFile

import anyio
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

API_ROOT = Path(__file__).resolve().parents[2]
REQUEST_ARGUMENTS = {
    "equipment_id": "AOI-WAFER-01",
    "lot_id": "LOT-DEMO-001",
    "start": "2026-01-15T13:00:00Z",
    "end": "2026-01-15T17:00:00Z",
}


@pytest.mark.anyio
async def test_project_entrypoint_serves_production_summary_over_stdio() -> None:
    parameters = StdioServerParameters(
        command="uv",
        args=["run", "industrial-agent-mcp"],
        cwd=API_ROOT,
    )
    with TemporaryFile(mode="w+") as stderr:
        with anyio.fail_after(15):
            async with stdio_client(parameters, errlog=stderr) as (read, write):
                async with ClientSession(
                    read,
                    write,
                    read_timeout_seconds=timedelta(seconds=5),
                ) as session:
                    await session.initialize()
                    discovered = await session.list_tools()
                    result = await session.call_tool(
                        "get_production_summary",
                        arguments=REQUEST_ARGUMENTS,
                    )

        stderr.seek(0)
        stderr_output = stderr.read()

    assert [tool.name for tool in discovered.tools] == [
        "get_production_summary",
        "get_equipment_status",
        "get_defect_distribution",
    ]
    assert result.isError is False
    assert result.structuredContent is not None
    assert result.structuredContent["equipment_id"] == "AOI-WAFER-01"
    assert "Traceback" not in stderr_output
