"""PSKit MCP server — file and git tools."""

import json as _json
from contextlib import asynccontextmanager
from typing import AsyncIterator

from mcp.server.fastmcp import FastMCP

from pskit.manager import PSKitManager

_manager: PSKitManager | None = None


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[None]:
    global _manager
    _manager = PSKitManager()
    yield
    if _manager:
        await _manager.close_all_sessions()


mcp = FastMCP("PSKit", lifespan=lifespan)


def _out(result: dict) -> str:
    if result.get("success") is False:
        return _json.dumps({"success": False, "error": result.get("error", "Unknown error")})
    return result.get("output") or result.get("error") or _json.dumps(result)


def _require() -> PSKitManager:
    if _manager is None:
        raise RuntimeError("PSKit server not initialized")
    return _manager


@mcp.tool()
async def read_file(path: str, max_lines: int = 0) -> str:
    """Read a file with line numbers."""
    result = await _require().execute(f"Read-PSKitFile '{path}' -MaxLines {max_lines}")
    return _out(result)


@mcp.tool()
async def write_file(path: str, content: str) -> str:
    """Write content to a file."""
    escaped = content.replace("'", "''")
    result = await _require().execute(f"Write-PSKitFile '{path}' '{escaped}'")
    return _out(result)


@mcp.tool()
async def search_code(pattern: str, path: str = ".", include: str = "*.*", max_results: int = 50) -> str:
    """Search for a pattern across files."""
    result = await _require().execute(
        f"Search-PSKitCode '{pattern}' -Path '{path}' -Include '{include}' -MaxResults {max_results}"
    )
    return _out(result)


@mcp.tool()
async def find_files(pattern: str, path: str = ".", max_results: int = 100) -> str:
    """Find files matching a glob pattern."""
    result = await _require().execute(f"Find-PSKitFiles '{pattern}' -Path '{path}' -MaxResults {max_results}")
    return _out(result)


@mcp.tool()
async def git_status() -> str:
    """Get the current git status."""
    result = await _require().execute("Get-PSKitGitStatus")
    return _out(result)
