"""Low-level stdio MCP server for deterministic manufacturing tools."""

import asyncio
import json
import logging
from collections.abc import Mapping
from typing import Any

import mcp.server.stdio
from mcp import types
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from pydantic import ValidationError

from industrial_agent.tools.defect_distribution import (
    DefectDistributionRequest,
    DefectDistributionResult,
    DefectDistributionToolError,
    get_defect_distribution,
)
from industrial_agent.tools.equipment_status import (
    EquipmentStatusRequest,
    EquipmentStatusResult,
    EquipmentStatusToolError,
    get_equipment_status,
)
from industrial_agent.tools.production import (
    ProductionSummaryRequest,
    ProductionSummaryResult,
    ProductionToolError,
    get_production_summary,
)

LOGGER = logging.getLogger(__name__)
SERVER_NAME = "industrial-ai-agent"
SERVER_VERSION = "0.1.0"
PRODUCTION_TOOL_NAME = "get_production_summary"
EQUIPMENT_STATUS_TOOL_NAME = "get_equipment_status"
DEFECT_DISTRIBUTION_TOOL_NAME = "get_defect_distribution"


async def list_tools() -> list[types.Tool]:
    """List the stable tools exposed through the local MCP boundary."""
    return [
        types.Tool(
            name=PRODUCTION_TOOL_NAME,
            description=(
                "Return deterministic production evidence for one synthetic "
                "equipment ID and explicit UTC time range."
            ),
            inputSchema=ProductionSummaryRequest.model_json_schema(
                mode="validation"
            ),
            outputSchema=ProductionSummaryResult.model_json_schema(
                mode="serialization"
            ),
        ),
        types.Tool(
            name=EQUIPMENT_STATUS_TOOL_NAME,
            description=(
                "Return recorded synthetic equipment status evidence at one "
                "explicit UTC timestamp."
            ),
            inputSchema=EquipmentStatusRequest.model_json_schema(
                mode="validation"
            ),
            outputSchema=EquipmentStatusResult.model_json_schema(
                mode="serialization"
            ),
        ),
        types.Tool(
            name=DEFECT_DISTRIBUTION_TOOL_NAME,
            description=(
                "Return deterministic ranked defect evidence for one "
                "synthetic equipment ID and explicit UTC time range."
            ),
            inputSchema=DefectDistributionRequest.model_json_schema(
                mode="validation"
            ),
            outputSchema=DefectDistributionResult.model_json_schema(
                mode="serialization"
            ),
        ),
    ]


def _error_result(message: str) -> types.CallToolResult:
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=message)],
        isError=True,
    )


async def call_tool(
    name: str,
    arguments: Mapping[str, Any],
) -> types.CallToolResult:
    """Validate and call one MCP tool without weakening domain boundaries."""
    if name == DEFECT_DISTRIBUTION_TOOL_NAME:
        return _call_defect_distribution(arguments)
    if name == EQUIPMENT_STATUS_TOOL_NAME:
        return _call_equipment_status(arguments)
    if name != PRODUCTION_TOOL_NAME:
        return _error_result("Unknown tool")
    try:
        request = ProductionSummaryRequest.model_validate(dict(arguments))
    except ValidationError:
        return _error_result("Invalid production summary request")

    try:
        result = get_production_summary(request)
    except ProductionToolError as error:
        return _error_result(str(error))
    except Exception:
        LOGGER.exception("Unexpected production summary MCP failure")
        return _error_result("Production summary unavailable")

    structured = result.model_dump(mode="json")
    return types.CallToolResult(
        content=[
            types.TextContent(
                type="text",
                text=json.dumps(structured, indent=2),
            )
        ],
        structuredContent=structured,
        isError=False,
    )


def _call_equipment_status(
    arguments: Mapping[str, Any],
) -> types.CallToolResult:
    try:
        request = EquipmentStatusRequest.model_validate(dict(arguments))
    except ValidationError:
        return _error_result("Invalid equipment status request")

    try:
        result = get_equipment_status(request)
    except EquipmentStatusToolError as error:
        return _error_result(str(error))
    except Exception:
        LOGGER.exception("Unexpected equipment status MCP failure")
        return _error_result("Equipment status unavailable")

    structured = result.model_dump(mode="json")
    return types.CallToolResult(
        content=[
            types.TextContent(
                type="text",
                text=json.dumps(structured, indent=2),
            )
        ],
        structuredContent=structured,
        isError=False,
    )


def _call_defect_distribution(
    arguments: Mapping[str, Any],
) -> types.CallToolResult:
    try:
        request = DefectDistributionRequest.model_validate(dict(arguments))
    except ValidationError:
        return _error_result("Invalid defect distribution request")

    try:
        result = get_defect_distribution(request)
    except DefectDistributionToolError as error:
        return _error_result(str(error))
    except Exception:
        LOGGER.exception("Unexpected defect distribution MCP failure")
        return _error_result("Defect distribution unavailable")

    structured = result.model_dump(mode="json")
    return types.CallToolResult(
        content=[
            types.TextContent(
                type="text",
                text=json.dumps(structured, indent=2),
            )
        ],
        structuredContent=structured,
        isError=False,
    )


def create_server() -> Server:
    """Create an import-safe MCP server without starting a transport."""
    server = Server(
        name=SERVER_NAME,
        version=SERVER_VERSION,
        instructions=(
            "Read deterministic evidence from the repository's synthetic "
            "manufacturing scenario."
        ),
    )

    server.list_tools()(list_tools)
    server.call_tool()(call_tool)

    return server


async def run_server() -> None:
    """Run the local server over MCP stdio."""
    server = create_server()
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name=SERVER_NAME,
                server_version=SERVER_VERSION,
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
                instructions=server.instructions,
            ),
        )


def main() -> None:
    """Run the async stdio server from the project script."""
    asyncio.run(run_server())


if __name__ == "__main__":
    main()
