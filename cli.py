from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any, Dict, List, Optional

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.pretty import pprint

from mcp_telegram.tools import enumerate_available_tools, tool_args, tool_runner, test_image_content

logging.basicConfig(
    level=logging.DEBUG,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)],
)
logger = logging.getLogger(__name__)

app = typer.Typer()


@app.command(name="list-tools")
def list_tools() -> None:
    console = Console()
    tools = list(enumerate_available_tools())
    pprint(tools)


@app.command(name="call-tool")
def call_tool_command(
    name: str,
    arguments: Optional[str] = None,
) -> None:
    console = Console()
    tools = dict(enumerate_available_tools())
    tool = tools.get(name)

    if not tool:
        available_tools = ", ".join(tools.keys())
        console.print(f"Tool {name} not found. Available tools: {available_tools}")
        sys.exit(1)

    if arguments:
        try:
            arguments_dict = json.loads(arguments)
        except json.JSONDecodeError as e:
            console.print(f"Error parsing arguments: {e}")
            sys.exit(1)
    else:
        arguments_dict = {}

    try:
        args = tool_args(tool, **arguments_dict)
        result = asyncio.run(tool_runner(args))
        pprint(result)
    except Exception as e:
        logger.exception("Error calling tool: %s", e)
        sys.exit(1)


@app.command(name="test-image")
def test_image() -> None:
    """Test the ImageContent creation to verify it works correctly"""
    try:
        asyncio.run(test_image_content())
        print("Test successful!")
    except Exception as e:
        logger.exception("Test failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    app()
