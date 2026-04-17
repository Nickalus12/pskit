"""PSKit MCP server — 38 tools with annotations, structured output, and progress reporting."""

import json as _json
import re as _re
import time as _time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession
from mcp.types import ToolAnnotations

from pskit.manager import PSKitManager, get_counters

_manager: PSKitManager | None = None
_start_time: float = _time.monotonic()


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[None]:
    global _manager, _start_time
    _start_time = _time.monotonic()
    _manager = PSKitManager()
    await _manager.get_pool()
    yield
    if _manager:
        await _manager.close_all_sessions()


mcp = FastMCP("PSKit", lifespan=lifespan)


def _require() -> PSKitManager:
    if _manager is None:
        raise RuntimeError("PSKit server not initialized — start via MCP lifespan")
    return _manager


# Strip ANSI/VT100 mode-control sequences — pwsh on Linux emits these to
# stdout when the line discipline isn't a TTY, prefixing every JSON payload.
_ANSI_RE = _re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|[PX^_][^\x1b]*\x1b\\|\][^\x07]*(?:\x07|\x1b\\)|[@-Z\\-_])")


def _parse(result: dict) -> dict:
    """Extract and parse the PS function's JSON output.

    The manager returns: {success, output: "<JSON string>", errors, session_id, ...}
    The PS function's actual data is inside the `output` field as a JSON string.
    This function parses that string and returns the clean data dict.
    """
    if result.get("success") is False:
        err = result.get("error") or result.get("errors") or "Command failed"
        raise RuntimeError(err)
    output = result.get("output", "")
    if isinstance(output, str) and output.strip():
        cleaned = _ANSI_RE.sub("", output).strip()
        try:
            parsed = _json.loads(cleaned)
            if isinstance(parsed, (dict, list)):
                return parsed
        except (_json.JSONDecodeError, ValueError):
            pass
    return result


def _text(result: dict) -> str:
    """Return raw text from the PS function output — for diffs, file content, etc.

    Same extraction as _parse but returns the string directly (or parsed output field).
    """
    if result.get("success") is False:
        err = result.get("error") or result.get("errors") or "Command failed"
        raise RuntimeError(err)
    output = result.get("output", "")
    if isinstance(output, str) and output.strip():
        cleaned = _ANSI_RE.sub("", output).strip()
        # Try parsing JSON to get a nested "output" or "diff" field
        try:
            parsed = _json.loads(cleaned)
            if isinstance(parsed, dict):
                # Return nested output/diff if present, otherwise the JSON string
                return parsed.get("output") or parsed.get("diff") or output
        except (_json.JSONDecodeError, ValueError):
            pass
        return output
    return _json.dumps(result)


# ---------------------------------------------------------------------------
# Structured output types (auto-generates outputSchema for clients)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# File Tools
# ---------------------------------------------------------------------------

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, title="Read File"))
async def read_file(path: str, max_lines: int = 0) -> dict[str, Any]:
    """Read a file with 1-based line numbers — call this before edit_file.

    Returns content with numbered lines: "    1| import os\\n    2| ..."

    Args:
        path: File path (absolute or relative).
        max_lines: Read only the first N lines. 0 = entire file.
    """
    result = await _require().execute(f"Read-PSKitFile '{path}' -MaxLines {max_lines}")
    return _parse(result)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, title="Read File Range"))
async def read_file_range(path: str, start_line: int, end_line: int) -> dict[str, Any]:
    """Read a specific line range from a file — efficient for large files.

    Args:
        path: File path.
        start_line: First line (1-based, inclusive).
        end_line: Last line (1-based, inclusive).
    """
    result = await _require().execute(
        f"Read-PSKitFileRange '{path}' -StartLine {start_line} -EndLine {end_line}"
    )
    return _parse(result)


@mcp.tool(annotations=ToolAnnotations(idempotentHint=True, title="Write File"))
async def write_file(path: str, content: str) -> dict[str, Any]:
    """Write content to a file, creating parent directories as needed.

    Args:
        path: Destination file path.
        content: Full file content (overwrites existing).
    """
    escaped = content.replace("'", "''")
    result = await _require().execute(f"Write-PSKitFile '{path}' '{escaped}'")
    return _parse(result)


@mcp.tool(annotations=ToolAnnotations(title="Edit File"))
async def edit_file(path: str, old_text: str, new_text: str,
                    regex: bool = False, replace_all: bool = False) -> dict[str, Any]:
    """Replace old_text with new_text in a file — surgical find-and-replace.

    If replacements_made is 0, old_text was not found — re-read the file first.

    Args:
        path: File to edit.
        old_text: Exact text to find including indentation.
        new_text: Replacement text.
        regex: Treat old_text as a .NET regex.
        replace_all: Replace every occurrence. Default: first only.
    """
    old_e = old_text.replace("'", "''")
    new_e = new_text.replace("'", "''")
    flags = (" -Regex" if regex else "") + (" -All" if replace_all else "")
    result = await _require().execute(f"Edit-PSKitFile '{path}' '{old_e}' '{new_e}'{flags}")
    return _parse(result)


@mcp.tool(annotations=ToolAnnotations(title="Move File"))
async def move_file(source: str, destination: str) -> dict[str, Any]:
    """Move or rename a file or directory. Creates parent directories as needed."""
    result = await _require().execute(f"Move-PSKitFile '{source}' '{destination}'")
    return _parse(result)


@mcp.tool(annotations=ToolAnnotations(destructiveHint=True, title="Delete File"))
async def delete_file(path: str, recurse: bool = False) -> dict[str, Any]:
    """Delete a file or directory. Not reversible.

    Args:
        path: Path to delete.
        recurse: Set True to delete a non-empty directory recursively.
    """
    flags = " -Recurse" if recurse else ""
    result = await _require().execute(f"Remove-PSKitFile '{path}'{flags}")
    return _parse(result)


@mcp.tool(annotations=ToolAnnotations(idempotentHint=True, title="Create Directory"))
async def create_directory(path: str) -> dict[str, Any]:
    """Create a directory and any missing parents."""
    result = await _require().execute(f"New-PSKitDirectory '{path}'")
    return _parse(result)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, title="List Directory"))
async def list_directory(path: str = ".", recurse: bool = False) -> dict[str, Any]:
    """List directory contents with name, type, size, and modified time.

    Args:
        path: Directory to list. Default: current directory.
        recurse: List recursively (capped at 200 items).
    """
    flags = " -Recurse" if recurse else ""
    result = await _require().execute(f"Get-PSKitDirectoryListing '{path}'{flags}")
    return _parse(result)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, title="Diff Files"))
async def diff_files(path1: str, path2: str) -> str:
    """Show a unified diff between two files.

    Returns the raw unified diff string.
    """
    result = await _require().execute(f"Compare-PSKitFiles '{path1}' '{path2}'")
    parsed = _parse(result)
    return parsed.get("diff", "")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, title="Search Code"))
async def search_code(pattern: str, path: str = ".", include: str = "*.*",
                      max_results: int = 50, context: int = 0) -> dict[str, Any]:
    """Search for a pattern across files — ripgrep-powered, regex supported.

    Args:
        pattern: Search pattern (regex supported).
        path: Root directory.
        include: File glob e.g. "*.py", "*.{ts,tsx}".
        max_results: Cap. Default 50.
        context: Lines of context around each match.
    """
    result = await _require().execute(
        f"Search-PSKitCode '{pattern}' -Path '{path}' -Include '{include}' "
        f"-MaxResults {max_results} -Context {context}"
    )
    return _parse(result)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, title="Find Files"))
async def find_files(pattern: str, path: str = ".", max_results: int = 100) -> dict[str, Any]:
    """Find files by glob pattern — ripgrep-fast when available.

    Args:
        pattern: Glob e.g. "*.py", "test_*.py".
        path: Root directory.
        max_results: File count cap.
    """
    result = await _require().execute(
        f"Find-PSKitFiles '{pattern}' -Path '{path}' -MaxResults {max_results}"
    )
    return _parse(result)


@mcp.tool(annotations=ToolAnnotations(title="Run Command"))
async def run_command(script: str, ctx: Context[ServerSession, None]) -> dict[str, Any]:
    """Run an arbitrary PowerShell script through the 5-tier safety pipeline.

    Reports progress while the command executes.

    Args:
        script: Any valid PowerShell script or command string.
    """
    await ctx.info(f"Executing: {script[:80]}")
    await ctx.report_progress(progress=0.0, total=1.0, message="Submitting to safety pipeline")
    result = await _require().execute(f"Invoke-PSKitCommand '{script.replace(chr(39), chr(39)*2)}'")
    await ctx.report_progress(progress=1.0, total=1.0, message="Complete")
    return _parse(result)


# ---------------------------------------------------------------------------
# Environment Tools
# ---------------------------------------------------------------------------

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, title="Get Environment Variables"))
async def get_env_vars(filter: str = "") -> dict[str, Any]:
    """List environment variables, filtered by name substring.

    Args:
        filter: Only return vars whose name contains this string.
    """
    result = await _require().execute(
        f"Get-PSKitEnvVars -Filter '{filter}'" if filter else "Get-PSKitEnvVars"
    )
    return _parse(result)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, title="Which"))
async def which(name: str) -> dict[str, Any]:
    """Check if a binary is on PATH — returns location and version.

    Args:
        name: Binary name e.g. "python", "node", "rg", "ollama".
    """
    result = await _require().execute(f"Get-PSKitWhich '{name}'")
    return _parse(result)


@mcp.tool(annotations=ToolAnnotations(title="Install Package"))
async def install_package(name: str, manager: str = "", version: str = "") -> dict[str, Any]:
    """Install a package using the detected or specified package manager.

    Args:
        name: Package name e.g. "requests", "lodash".
        manager: "pip", "npm", "cargo", or "winget". Auto-detected if empty.
        version: Specific version e.g. "2.28.0". Empty = latest.
    """
    flags = ""
    if manager:
        flags += f" -Manager '{manager}'"
    if version:
        flags += f" -Version '{version}'"
    result = await _require().execute(f"Install-PSKitPackage '{name}'{flags}")
    return _parse(result)


# ---------------------------------------------------------------------------
# Git Tools
# ---------------------------------------------------------------------------

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, title="Git Status"))
async def git_status() -> dict[str, Any]:
    """Get the current git working tree status.

    Returns branch name, ahead/behind count, and all changed files with status codes.
    Status codes: M=modified, A=added, D=deleted, R=renamed, ??=untracked.
    """
    result = await _require().execute("Get-PSKitGitStatus")
    return _parse(result)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, title="Git Diff"))
async def git_diff(path: str = "", staged: bool = False) -> str:
    """Show git diff as unified diff string.

    Args:
        path: Scope to a specific file. Empty = everything.
        staged: True to show staged (indexed) changes.
    """
    flags = " -Staged" if staged else ""
    cmd = f"Get-PSKitGitDiff -Path '{path}'{flags}" if path else f"Get-PSKitGitDiff{flags}"
    result = await _require().execute(cmd)
    parsed = _parse(result)
    return parsed.get("output", "")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, title="Git Log"))
async def git_log(limit: int = 20, path: str = "", since: str = "",
                  until: str = "", author: str = "") -> dict[str, Any]:
    """Show git commit history as structured data — newest first.

    Args:
        limit: Number of commits. Default 20.
        path: Filter to commits that touched this file.
        since: Date or relative e.g. "2025-01-01" or "2 weeks ago".
        until: Upper bound date.
        author: Filter by author name substring.
    """
    flags = f" -Limit {limit}"
    if path:
        flags += f" -Path '{path}'"
    if since:
        flags += f" -Since '{since}'"
    if until:
        flags += f" -Until '{until}'"
    if author:
        flags += f" -Author '{author}'"
    result = await _require().execute(f"Get-PSKitGitLog{flags}")
    return _parse(result)


@mcp.tool(annotations=ToolAnnotations(destructiveHint=True, idempotentHint=False, title="Git Commit"))
async def git_commit(message: str) -> dict[str, Any]:
    """Stage all changes and create a commit.

    Args:
        message: Commit message. Use conventional commits: feat/fix/chore/docs/refactor.
    """
    escaped = message.replace("'", "''")
    result = await _require().execute(f"New-PSKitGitCommit '{escaped}'")
    return _parse(result)


@mcp.tool(annotations=ToolAnnotations(title="Git Branch"))
async def git_branch(name: str, switch: bool = True) -> dict[str, Any]:
    """Create a new git branch.

    Args:
        name: Branch name e.g. "feat/new-tool".
        switch: Switch to the new branch immediately (default True).
    """
    flags = " -Switch" if switch else ""
    result = await _require().execute(f"New-PSKitGitBranch '{name}'{flags}")
    return _parse(result)


@mcp.tool(annotations=ToolAnnotations(title="Git Checkout"))
async def git_checkout(ref: str) -> dict[str, Any]:
    """Switch to an existing branch or ref.

    Args:
        ref: Branch name, tag, or commit hash.
    """
    result = await _require().execute(f"Switch-PSKitGitBranch '{ref}'")
    return _parse(result)


@mcp.tool(annotations=ToolAnnotations(destructiveHint=True, title="Git Push"))
async def git_push(remote: str = "origin", branch: str = "") -> dict[str, Any]:
    """Push the current branch to a remote.

    Args:
        remote: Remote name. Default "origin".
        branch: Branch to push. Default: current branch.
    """
    flags = f" -Remote '{remote}'"
    if branch:
        flags += f" -Branch '{branch}'"
    result = await _require().execute(f"Push-PSKitGit{flags}")
    return _parse(result)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, title="Git Blame"))
async def git_blame(path: str, start_line: int = 0, end_line: int = 0) -> list[dict[str, Any]]:
    """Show who last changed each line of a file.

    Args:
        path: File to blame.
        start_line: First line (1-based). 0 = blame entire file.
        end_line: Last line. Required if start_line is set.
    """
    flags = ""
    if start_line and end_line:
        flags = f" -StartLine {start_line} -EndLine {end_line}"
    result = await _require().execute(f"Get-PSKitGitBlame '{path}'{flags}")
    parsed = _parse(result)
    return parsed if isinstance(parsed, list) else parsed.get("output", [])


@mcp.tool(annotations=ToolAnnotations(title="Git Stash"))
async def git_stash(message: str = "pskit auto-stash") -> dict[str, Any]:
    """Save current working tree changes to the git stash."""
    escaped = message.replace("'", "''")
    result = await _require().execute(f"Save-PSKitGitStash '{escaped}'")
    return _parse(result)


@mcp.tool(annotations=ToolAnnotations(title="Git Stash Pop"))
async def git_stash_pop() -> dict[str, Any]:
    """Restore the most recently stashed changes."""
    result = await _require().execute("Restore-PSKitGitStash")
    return _parse(result)


# ---------------------------------------------------------------------------
# System Tools
# ---------------------------------------------------------------------------

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, title="GPU Status"))
async def gpu_status() -> dict[str, Any]:
    """Get NVIDIA GPU status: name, VRAM usage, utilization %, temperature.

    Returns an error object if nvidia-smi is unavailable.
    """
    result = await _require().execute("Get-PSKitGpuStatus")
    return _parse(result)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, title="Disk Usage"))
async def disk_usage(path: str = ".") -> dict[str, Any]:
    """Get disk space for the drive containing a path.

    Args:
        path: Any path on the drive to inspect. Default: current directory.
    """
    result = await _require().execute(f"Get-PSKitDiskUsage '{path}'")
    return _parse(result)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, title="Memory Usage"))
async def memory_usage() -> dict[str, Any]:
    """Get system RAM usage: total, free, and used in GB."""
    result = await _require().execute("Get-PSKitMemoryUsage")
    return _parse(result)


# ---------------------------------------------------------------------------
# Network & Process Tools
# ---------------------------------------------------------------------------

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, title="Port Status"))
async def port_status(ports: str = "") -> list[dict[str, Any]]:
    """Check which TCP ports are listening and which processes own them.

    Args:
        ports: Comma-separated port numbers e.g. "8080,5432,11434".
               Empty = default dev set (8080, 11434, 5432, 3000, 8000, etc.).
    """
    if ports:
        port_list = ",".join(p.strip() for p in ports.split(","))
        cmd = f"Get-PSKitPortStatus -Ports @({port_list})"
    else:
        cmd = "Get-PSKitPortStatus"
    result = await _require().execute(cmd)
    parsed = _parse(result)
    if isinstance(parsed, list):
        return parsed
    # Cross-platform Get-PSKitPortStatus returns { success, ports, platform }
    return parsed.get("ports", parsed.get("output", []))


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, title="Process Info"))
async def process_info(name: str = "", pid: int = -1, include_threads: bool = False) -> list[dict[str, Any]]:
    """Get information about running processes. Default: top 20 by CPU.

    Args:
        name: Filter by process name (partial match) e.g. "python", "ollama".
        pid: Filter by exact PID.
        include_threads: Include per-thread detail.
    """
    flags = " -IncludeThreads" if include_threads else ""
    if pid > 0:
        cmd = f"Get-PSKitProcessInfo -Id {pid}{flags}"
    elif name:
        cmd = f"Get-PSKitProcessInfo -Name '{name}'{flags}"
    else:
        cmd = f"Get-PSKitProcessInfo{flags}"
    result = await _require().execute(cmd)
    parsed = _parse(result)
    return parsed if isinstance(parsed, list) else parsed.get("output", [])


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True, title="HTTP Request"))
async def http_request(uri: str, method: str = "GET", body: str = "", timeout_sec: int = 30) -> dict[str, Any]:
    """Make an HTTP request to localhost or private network addresses only.

    Returns status_code, body, headers, elapsed_ms.

    Args:
        uri: Target URI — restricted to localhost and RFC-1918 private IPs.
        method: GET, POST, PUT, PATCH, DELETE.
        body: Request body for POST/PUT/PATCH.
        timeout_sec: Timeout in seconds.
    """
    escaped_body = body.replace("'", "''")
    cmd = f"Invoke-PSKitHttpRequest '{uri}' -Method '{method}' -Body '{escaped_body}' -TimeoutSec {timeout_sec}"
    result = await _require().execute(cmd)
    return _parse(result)


# ---------------------------------------------------------------------------
# Build & Test Tools
# ---------------------------------------------------------------------------

@mcp.tool(annotations=ToolAnnotations(title="Build Project"))
async def build_project(command: str = "", ctx: Context[ServerSession, None] = None) -> dict[str, Any]:
    """Run the project build — auto-detects build system with progress reporting.

    Returns structured result: success, exit_code, stdout, stderr, duration_ms.
    Auto-detection: npm build → cargo build → make → python -m build.

    Args:
        command: Override command e.g. "npm run build:prod".
    """
    if ctx:
        await ctx.info("Starting build...")
        await ctx.report_progress(progress=0.0, total=1.0, message="Running build")
    if command:
        escaped = command.replace("'", "''")
        cmd = f"Invoke-PSKitBuild -Command '{escaped}'"
    else:
        cmd = "Invoke-PSKitBuild"
    result = await _require().execute(cmd)
    parsed = _parse(result)
    if ctx:
        status = "Build succeeded" if parsed.get("success") else "Build failed"
        await ctx.report_progress(progress=1.0, total=1.0, message=status)
    return parsed


@mcp.tool(annotations=ToolAnnotations(title="Test Project"))
async def test_project(filter_expr: str = "", command: str = "",
                       ctx: Context[ServerSession, None] = None) -> dict[str, Any]:
    """Run the project test suite with progress reporting.

    Returns structured result: success, passed, failed, skipped, exit_code, stdout, stderr, duration_ms.
    Auto-detection: pytest → npm test → cargo test.

    Args:
        filter_expr: Test filter e.g. pytest -k expression "test_auth or test_login".
        command: Full override e.g. "pytest tests/unit/ -v".
    """
    if ctx:
        await ctx.info("Starting test suite...")
        await ctx.report_progress(progress=0.0, total=1.0, message="Running tests")
    if command:
        escaped = command.replace("'", "''")
        cmd = f"Invoke-PSKitTest -Command '{escaped}'"
    elif filter_expr:
        escaped = filter_expr.replace("'", "''")
        cmd = f"Invoke-PSKitTest -Filter '{escaped}'"
    else:
        cmd = "Invoke-PSKitTest"
    result = await _require().execute(cmd)
    parsed = _parse(result)
    if ctx:
        p = parsed.get("passed", 0)
        f = parsed.get("failed", 0)
        await ctx.report_progress(progress=1.0, total=1.0,
                                   message=f"{p} passed, {f} failed")
    return parsed


# ---------------------------------------------------------------------------
# MCP Prompts
# ---------------------------------------------------------------------------

@mcp.prompt()
def audit_project() -> str:
    """Full project audit: structure, git health, build, tests, and system state."""
    return """Use pskit tools to audit this project completely:

1. git_status() — branch and uncommitted changes
2. git_log(limit=10) — understand recent work
3. find_files("README*") then read_file() — what is this project?
4. find_files("*.toml") or find_files("package.json") — identify tech stack
5. find_files("*.py", max_results=40) or equivalent — map source structure
6. build_project() — does it build cleanly?
7. test_project() — do all tests pass?
8. disk_usage() and memory_usage() — system health
9. port_status() — what services are running?

Summarize: purpose, tech stack, current state, health indicators, and top 3 actionable recommendations."""


@mcp.prompt()
def review_changes() -> str:
    """Thorough review of all uncommitted changes before committing."""
    return """Review all current changes before committing:

1. git_status() — what changed and on which branch
2. git_diff() — all unstaged changes
3. git_diff(staged=True) — all staged changes
4. read_file() each modified file for full context
5. Assess: correctness, security implications, missing tests, style

Conclude with either:
- A commit message suggestion (conventional commits: feat/fix/refactor/docs/chore)
- Specific concerns that must be addressed before committing"""


@mcp.prompt()
def diagnose_build(error: str = "") -> str:
    """Diagnose a failing build or broken test suite."""
    intro = f"Error reported:\n{error}\n\n" if error else ""
    return f"""{intro}Diagnose why the build or tests are failing:

1. build_project() — capture exact error output
2. test_project() — which specific tests fail
3. search_code() for the error string — locate the source
4. read_file() the relevant files — get full context
5. git_log(limit=5) — did a recent commit introduce this?
6. git_diff() — what changed since the last working state?

Propose a specific fix with the exact code change (file, old_text, new_text)."""


@mcp.prompt()
def orient_to_project() -> str:
    """Orient yourself to an unfamiliar project before starting work."""
    return """Get oriented before starting any work:

1. find_files("README*") then read_file() the README completely
2. git_status() and git_log(limit=15) — current state and recent history
3. which("python") and which("node") — identify the runtime environment
4. find_files("*.toml") or find_files("package.json") — stack and deps
5. find_files("*.py", max_results=30) or equivalent — map source structure
6. port_status() — what services are currently running

Summarize: what this is, tech stack, current git state, and what you need to work effectively."""


@mcp.prompt()
def refactor_file(path: str = "") -> str:
    """Refactor a specific file for clarity and maintainability."""
    target = f"Target file: {path}\n\n" if path else ""
    return f"""{target}Refactor this file without changing external behavior:

1. read_file("{path or 'TARGET_FILE'}") — read the entire file
2. Identify issues: duplicated logic, long functions, unclear names, missing types
3. git_stash() — save current state before making changes
4. Make targeted edits using edit_file() — one concern at a time
5. test_project() — verify no regressions
6. git_diff() — review all changes before committing

Constraints: preserve all public interfaces, do not change behavior, keep tests green."""


@mcp.prompt()
def write_tests_for(path: str = "") -> str:
    """Generate a comprehensive test suite for a specific module."""
    target = f"Target: {path}\n\n" if path else ""
    return f"""{target}Write tests for this module:

1. read_file("{path or 'TARGET_MODULE'}") — understand the public API
2. find_files("test_*.py") — read existing tests for conventions
3. Identify: happy paths, edge cases, error conditions, boundary values
4. write_file() the new test file following existing conventions
5. test_project() — run and fix until all new tests pass"""


@mcp.prompt()
def explain_codebase() -> str:
    """Produce a high-level architectural explanation of this codebase."""
    return """Build a high-level understanding of this codebase:

1. find_files("README*") and read_file() — start with the overview
2. list_directory(".") — top-level structure
3. find_files("*.toml") or find_files("package.json") — tech stack and entry points
4. find_files("*.py", max_results=50) or equivalent — enumerate all source files
5. For each top-level module: read_file() the main file
6. git_log(limit=20) — recent development trajectory

Produce a structured explanation: purpose, architecture, key modules, data flow, dependencies, how to run."""


# ---------------------------------------------------------------------------
# MCP Resources
# ---------------------------------------------------------------------------

@mcp.resource("pskit://guide")
def usage_guide() -> str:
    """PSKit quick-reference: all 38 tool signatures, return shapes, and usage tips."""
    return """# PSKit Tool Reference (38 tools)

## File Tools
- read_file(path, max_lines=0) -> { content, line_count, path } [readOnly]
- read_file_range(path, start_line, end_line) -> { content, start_line, end_line, line_count } [readOnly]
- write_file(path, content) -> { success, path, bytes } [idempotent]
- edit_file(path, old_text, new_text, regex=False, replace_all=False) -> { success, replacements_made, preview }
- move_file(source, destination) -> { success, source, destination }
- delete_file(path, recurse=False) -> { success, path } [DESTRUCTIVE]
- create_directory(path) -> { success, path } [idempotent]
- list_directory(path=".", recurse=False) -> { items: [{name, path, type, size_bytes, modified}], count } [readOnly]
- diff_files(path1, path2) -> unified diff string [readOnly]
- search_code(pattern, path=".", include="*.*", max_results=50, context=0) -> { matches: [{file, line, text}], count } [readOnly]
- find_files(pattern, path=".", max_results=100) -> { files: [{name, path, size_bytes, modified}], count } [readOnly]
- run_command(script) -> { success, exit_code, output, stderr, duration_ms } [progress]

## Environment Tools
- get_env_vars(filter="") -> { vars: {NAME: value}, count } [readOnly]
- which(name) -> { found, name, path, version } [readOnly]
- install_package(name, manager="", version="") -> { success, manager, package, output }

## Git Tools
- git_status() -> { branch, ahead_behind, changes: [{status, file}] } [readOnly]
- git_diff(path="", staged=False) -> unified diff string [readOnly]
- git_log(limit=20, path="", since="", until="", author="") -> { commits: [{hash, short, message, author, date}] } [readOnly]
- git_commit(message) -> { success, output } [DESTRUCTIVE]
- git_branch(name, switch=True) -> { success, branch, output }
- git_checkout(ref) -> { success, ref, output }
- git_push(remote="origin", branch="") -> { success, remote, branch, output } [DESTRUCTIVE]
- git_blame(path, start_line=0, end_line=0) -> [{line, hash, author, date, content}] [readOnly]
- git_stash(message="pskit auto-stash") -> { success, output }
- git_stash_pop() -> { success, output }

## System Tools
- gpu_status() -> { gpu, memory_total, memory_used, memory_free, utilization, temperature } [readOnly]
- disk_usage(path=".") -> { drive, used_gb, free_gb, total_gb } [readOnly]
- memory_usage() -> { total_gb, free_gb, used_gb } [readOnly]

## Network & Process Tools
- port_status(ports="") -> [{port, listening, pid, process_name}] [readOnly]
- process_info(name="", pid=-1, include_threads=False) -> [{name, id, cpu_s, memory_mb, start_time}] [readOnly]
- http_request(uri, method="GET", body="", timeout_sec=30) -> { status_code, body, headers, elapsed_ms } [localhost/private only]

## Build & Test Tools
- build_project(command="") -> { success, command_used, exit_code, stdout, stderr, duration_ms } [progress]
- test_project(filter_expr="", command="") -> { success, command_used, exit_code, passed, failed, skipped, stdout, stderr, duration_ms } [progress]

## Workflow Rules
1. Always read_file before edit_file — verify old_text exists exactly
2. Use search_code to locate code before reading whole files
3. git_stash before risky edits, git_stash_pop to restore if needed
4. build_project() -> test_project() -> git_commit() — always in that order
5. port_status("11434") to verify Ollama before http_request to Ollama
6. If edit_file replacements_made=0, re-read the file first

## Tool Annotations
- [readOnly] — does not modify state, safe to call freely
- [DESTRUCTIVE] — makes irreversible changes, confirm before calling
- [idempotent] — safe to retry, same result each time
- [progress] — reports incremental progress during execution
"""


@mcp.resource("pskit://status")
def server_status() -> str:
    """Live PSKit server status — sessions, cache, counters, uptime."""
    uptime = round(_time.monotonic() - _start_time, 1)
    counters = get_counters()
    pool_info: dict[str, Any] = {}
    if _manager and _manager._pool:
        pool = _manager._pool
        pool_info = {
            "initialized": getattr(pool, "initialized", False),
            "pool_size": getattr(pool, "_pool_size", 0),
        }
    cache_info: dict[str, Any] = {}
    if _manager:
        cache = getattr(_manager, "_result_cache", None)
        if cache:
            cache_info = {
                "entries": len(getattr(cache, "_store", {})),
                "max_size": getattr(cache, "_max_size", 0),
                "ttl_seconds": getattr(cache, "_ttl", 0),
            }
    return _json.dumps({
        "uptime_seconds": uptime,
        "active_sessions": len(_manager._sessions) if _manager else 0,
        "pool": pool_info,
        "cache": cache_info,
        "counters": counters,
    }, indent=2)
