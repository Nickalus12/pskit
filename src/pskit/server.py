"""PSKit MCP server — 38 PowerShell tools + prompts + resources via Model Context Protocol."""

import json as _json
import time as _time
from contextlib import asynccontextmanager
from typing import Annotated, AsyncIterator

from mcp.server.fastmcp import FastMCP

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


def _out(result: dict) -> str:
    """Return tool output. Structured error on failure so Claude knows what went wrong."""
    if result.get("success") is False:
        err = result.get("error") or result.get("errors") or "Unknown error"
        return _json.dumps({"success": False, "error": err})
    return result.get("output") or result.get("error") or _json.dumps(result)


def _require() -> PSKitManager:
    if _manager is None:
        raise RuntimeError("PSKit server not initialized — start via MCP lifespan")
    return _manager


# ---------------------------------------------------------------------------
# File Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def read_file(path: str, max_lines: int = 0) -> str:
    """Read a file with 1-based line numbers — essential before any edit.

    Returns JSON: { content (numbered lines), line_count, path }.
    Line format: "    1| import os\\n    2| ..."

    Args:
        path: File path (absolute or relative).
        max_lines: Read only the first N lines. 0 = entire file.

    Always call this before edit_file to verify old_text exists exactly.
    Use max_lines=50 for a quick peek at large files.
    """
    result = await _require().execute(f"Read-PSKitFile '{path}' -MaxLines {max_lines}")
    return _out(result)


@mcp.tool()
async def read_file_range(path: str, start_line: int, end_line: int) -> str:
    """Read a specific line range from a file — efficient for large files.

    Returns JSON: { content (numbered lines), start_line, end_line, line_count, path }.

    Args:
        path: File path.
        start_line: First line to return (1-based, inclusive).
        end_line: Last line to return (1-based, inclusive).

    Use when you know which section of a large file you need — avoids pulling
    thousands of lines when you only need lines 800-850.
    """
    result = await _require().execute(
        f"Read-PSKitFileRange '{path}' -StartLine {start_line} -EndLine {end_line}"
    )
    return _out(result)


@mcp.tool()
async def write_file(path: str, content: str) -> str:
    """Write content to a file, creating parent directories as needed.

    Returns JSON: { success, path (resolved absolute), bytes }.

    Args:
        path: Destination file path.
        content: Full file content (overwrites existing).

    For surgical changes to existing files, prefer edit_file instead.
    """
    escaped = content.replace("'", "''")
    result = await _require().execute(f"Write-PSKitFile '{path}' '{escaped}'")
    return _out(result)


@mcp.tool()
async def edit_file(path: str, old_text: str, new_text: str, regex: bool = False, replace_all: bool = False) -> str:
    """Replace old_text with new_text in a file — surgical, line-precise.

    Returns JSON: { success, replacements_made, preview, path }.

    Args:
        path: File to edit.
        old_text: Exact text to find (including indentation). Must exist.
        new_text: Replacement text.
        regex: Treat old_text as a .NET regex pattern.
        replace_all: Replace every occurrence. Default: first only.

    If replacements_made is 0, the text was not found — re-read the file.
    Always call read_file first to verify old_text appears exactly as you will pass it.
    """
    old_e = old_text.replace("'", "''")
    new_e = new_text.replace("'", "''")
    flags = (" -Regex" if regex else "") + (" -All" if replace_all else "")
    result = await _require().execute(f"Edit-PSKitFile '{path}' '{old_e}' '{new_e}'{flags}")
    return _out(result)


@mcp.tool()
async def move_file(source: str, destination: str) -> str:
    """Move or rename a file or directory.

    Returns JSON: { success, source, destination }.

    Args:
        source: Current path of the file or directory.
        destination: Target path. Parent directories are created if needed.
    """
    result = await _require().execute(f"Move-PSKitFile '{source}' '{destination}'")
    return _out(result)


@mcp.tool()
async def delete_file(path: str, recurse: bool = False) -> str:
    """Delete a file or directory.

    Returns JSON: { success, path }.

    Args:
        path: Path to delete.
        recurse: Set True to delete a non-empty directory recursively.

    Use with care — deletion goes through the safety pipeline but is not reversible.
    """
    flags = " -Recurse" if recurse else ""
    result = await _require().execute(f"Remove-PSKitFile '{path}'{flags}")
    return _out(result)


@mcp.tool()
async def create_directory(path: str) -> str:
    """Create a directory (and any missing parents).

    Returns JSON: { success, path }.
    """
    result = await _require().execute(f"New-PSKitDirectory '{path}'")
    return _out(result)


@mcp.tool()
async def list_directory(path: str = ".", recurse: bool = False) -> str:
    """List directory contents with metadata.

    Returns JSON: { items: [{ name, path, type, size_bytes, modified }], count, path }.

    Args:
        path: Directory to list. Defaults to current directory.
        recurse: Set True to list recursively (capped at 200 items).
    """
    flags = " -Recurse" if recurse else ""
    result = await _require().execute(f"Get-PSKitDirectoryListing '{path}'{flags}")
    return _out(result)


@mcp.tool()
async def diff_files(path1: str, path2: str) -> str:
    """Show a unified diff between two files.

    Returns JSON: { diff (unified diff string), identical (bool), path1, path2 }.

    Useful for comparing generated output against expected, or tracking
    how a file changed between two versions.
    """
    result = await _require().execute(f"Compare-PSKitFiles '{path1}' '{path2}'")
    return _out(result)


@mcp.tool()
async def search_code(pattern: str, path: str = ".", include: str = "*.*", max_results: int = 50, context: int = 0) -> str:
    """Search for a pattern across files — ripgrep-powered, regex supported.

    Returns JSON: { matches: [{ file, line, text }], count, pattern, engine }.

    Args:
        pattern: Search pattern (regex supported).
        path: Root directory. Default: current directory.
        include: File glob filter e.g. "*.py", "*.{ts,tsx}". Default: all files.
        max_results: Cap results. Default 50.
        context: Lines of context around each match (like rg -C). Default 0.

    Use to locate definitions, usages, TODOs, or error strings before reading files.
    """
    result = await _require().execute(
        f"Search-PSKitCode '{pattern}' -Path '{path}' -Include '{include}' "
        f"-MaxResults {max_results} -Context {context}"
    )
    return _out(result)


@mcp.tool()
async def find_files(pattern: str, path: str = ".", max_results: int = 100) -> str:
    """Find files by glob pattern — ripgrep-fast when available.

    Returns JSON: { files: [{ name, path, size_bytes, modified }], count, pattern, engine }.

    Args:
        pattern: Glob e.g. "*.py", "test_*.py", "**/*.config.js".
        path: Root directory.
        max_results: File count cap.

    Use to map project structure or locate config/test files before reading them.
    """
    result = await _require().execute(
        f"Find-PSKitFiles '{pattern}' -Path '{path}' -MaxResults {max_results}"
    )
    return _out(result)


@mcp.tool()
async def run_command(script: str) -> str:
    """Run an arbitrary PowerShell script — fully gated by the 5-tier safety pipeline.

    Returns JSON: { success, exit_code, output, stderr, duration_ms }.

    Args:
        script: Any valid PowerShell script or command string.

    Use when the specific pre-built tools don't cover what you need.
    The command still passes through KAN neural scoring, blocklist, path safety,
    and optionally Gemma LLM review — it is not a bypass.
    """
    result = await _require().execute(f"Invoke-PSKitCommand '{script.replace(chr(39), chr(39)*2)}'")
    return _out(result)


# ---------------------------------------------------------------------------
# Environment Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_env_vars(filter: str = "") -> str:
    """List environment variables, optionally filtered by name substring.

    Returns JSON: { vars: { NAME: value }, count }.

    Args:
        filter: Only return variables whose name contains this string.
                Leave empty to list all (may be large).

    Useful for checking PATH, VIRTUAL_ENV, API keys presence (not values), etc.
    """
    result = await _require().execute(
        f"Get-PSKitEnvVars -Filter '{filter}'" if filter else "Get-PSKitEnvVars"
    )
    return _out(result)


@mcp.tool()
async def which(name: str) -> str:
    """Check if a binary is on PATH and get its location and version.

    Returns JSON: { found (bool), name, path, version }.

    Args:
        name: Binary name e.g. "python", "node", "rg", "ollama".

    Use to verify dependencies before running commands that require them.
    """
    result = await _require().execute(f"Get-PSKitWhich '{name}'")
    return _out(result)


@mcp.tool()
async def install_package(name: str, manager: str = "", version: str = "") -> str:
    """Install a package using the detected or specified package manager.

    Returns JSON: { success, manager, package, command, output }.

    Args:
        name: Package name e.g. "requests", "lodash", "serde".
        manager: "pip", "npm", "cargo", or "winget". Auto-detected if empty.
        version: Specific version string e.g. "2.28.0". Empty = latest.
    """
    flags = ""
    if manager:
        flags += f" -Manager '{manager}'"
    if version:
        flags += f" -Version '{version}'"
    result = await _require().execute(f"Install-PSKitPackage '{name}'{flags}")
    return _out(result)


# ---------------------------------------------------------------------------
# Git Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def git_status() -> str:
    """Get the current git working tree status.

    Returns JSON: { branch, ahead_behind, changes: [{ status, file }] }.
    Status codes: M=modified, A=added, D=deleted, R=renamed, ??=untracked.

    Call at the start of every session and before committing.
    """
    result = await _require().execute("Get-PSKitGitStatus")
    return _out(result)


@mcp.tool()
async def git_diff(path: str = "", staged: bool = False) -> str:
    """Show git diff as unified diff string.

    Args:
        path: Scope to a specific file. Empty = everything.
        staged: True to show staged changes. Default: unstaged.
    """
    flags = " -Staged" if staged else ""
    cmd = f"Get-PSKitGitDiff -Path '{path}'{flags}" if path else f"Get-PSKitGitDiff{flags}"
    result = await _require().execute(cmd)
    return _out(result)


@mcp.tool()
async def git_log(limit: int = 20, path: str = "", since: str = "", until: str = "", author: str = "") -> str:
    """Show git commit history as structured data.

    Returns JSON: { commits: [{ hash, short, message, author, date }], count }.

    Args:
        limit: Number of commits. Default 20.
        path: Filter to commits that touched this file.
        since: ISO date or relative e.g. "2025-01-01" or "2 weeks ago".
        until: Upper bound date.
        author: Filter by author name substring.
    """
    flags = f" -Limit {limit}"
    if path:   flags += f" -Path '{path}'"
    if since:  flags += f" -Since '{since}'"
    if until:  flags += f" -Until '{until}'"
    if author: flags += f" -Author '{author}'"
    result = await _require().execute(f"Get-PSKitGitLog{flags}")
    return _out(result)


@mcp.tool()
async def git_commit(message: str) -> str:
    """Stage all changes and create a commit.

    Returns JSON: { success, output }.

    Args:
        message: Commit message. Use conventional commits: "feat/fix/chore: description".

    Run test_project first to confirm nothing is broken.
    """
    escaped = message.replace("'", "''")
    result = await _require().execute(f"New-PSKitGitCommit '{escaped}'")
    return _out(result)


@mcp.tool()
async def git_branch(name: str, switch: bool = True) -> str:
    """Create a new git branch.

    Returns JSON: { success, branch, output }.

    Args:
        name: Branch name e.g. "feat/new-tool" or "fix/port-status".
        switch: Switch to the new branch after creating (default True).
    """
    flags = " -Switch" if switch else ""
    result = await _require().execute(f"New-PSKitGitBranch '{name}'{flags}")
    return _out(result)


@mcp.tool()
async def git_checkout(ref: str) -> str:
    """Switch to an existing branch or ref.

    Returns JSON: { success, ref, output }.

    Args:
        ref: Branch name, tag, or commit hash to check out.
    """
    result = await _require().execute(f"Switch-PSKitGitBranch '{ref}'")
    return _out(result)


@mcp.tool()
async def git_push(remote: str = "origin", branch: str = "") -> str:
    """Push the current branch to a remote.

    Returns JSON: { success, remote, branch, output }.

    Args:
        remote: Remote name. Default "origin".
        branch: Branch to push. Default: current branch.
    """
    flags = f" -Remote '{remote}'"
    if branch:
        flags += f" -Branch '{branch}'"
    result = await _require().execute(f"Push-PSKitGit{flags}")
    return _out(result)


@mcp.tool()
async def git_blame(path: str, start_line: int = 0, end_line: int = 0) -> str:
    """Show who last changed each line of a file.

    Returns JSON array: [{ line, hash, author, date, content }].

    Args:
        path: File to blame.
        start_line: First line (1-based). 0 = blame entire file.
        end_line: Last line (1-based). Must be set if start_line is set.

    Use to understand when a bug was introduced and by which commit.
    """
    flags = ""
    if start_line and end_line:
        flags = f" -StartLine {start_line} -EndLine {end_line}"
    result = await _require().execute(f"Get-PSKitGitBlame '{path}'{flags}")
    return _out(result)


@mcp.tool()
async def git_stash(message: str = "pskit auto-stash") -> str:
    """Save current working tree changes to the stash.

    Returns JSON: { success, output }.
    """
    escaped = message.replace("'", "''")
    result = await _require().execute(f"Save-PSKitGitStash '{escaped}'")
    return _out(result)


@mcp.tool()
async def git_stash_pop() -> str:
    """Restore the most recently stashed changes.

    Returns JSON: { success, output }.
    """
    result = await _require().execute("Restore-PSKitGitStash")
    return _out(result)


# ---------------------------------------------------------------------------
# System Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def gpu_status() -> str:
    """Get NVIDIA GPU status via nvidia-smi.

    Returns JSON: { gpu, memory_total, memory_used, memory_free, utilization, temperature }.
    Returns { error } if nvidia-smi is unavailable.
    """
    result = await _require().execute("Get-PSKitGpuStatus")
    return _out(result)


@mcp.tool()
async def disk_usage(path: str = ".") -> str:
    """Get disk space for the drive containing a path.

    Returns JSON: { drive, used_gb, free_gb, total_gb }.
    """
    result = await _require().execute(f"Get-PSKitDiskUsage '{path}'")
    return _out(result)


@mcp.tool()
async def memory_usage() -> str:
    """Get system RAM usage.

    Returns JSON: { total_gb, free_gb, used_gb }.
    """
    result = await _require().execute("Get-PSKitMemoryUsage")
    return _out(result)


# ---------------------------------------------------------------------------
# Network & Process Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def port_status(ports: str = "") -> str:
    """Check which TCP ports are listening and which processes own them.

    Returns JSON array: [{ port, listening, pid, process_name }].

    Args:
        ports: Comma-separated port numbers e.g. "8080,5432,11434".
               Empty = default dev set (8080, 11434, 5432, 3000, 8000, etc.).

    Use to verify a service is running before http_request calls.
    """
    if ports:
        port_list = ",".join(p.strip() for p in ports.split(","))
        cmd = f"Get-PSKitPortStatus -Ports @({port_list})"
    else:
        cmd = "Get-PSKitPortStatus"
    result = await _require().execute(cmd)
    return _out(result)


@mcp.tool()
async def process_info(name: str = "", pid: int = -1, include_threads: bool = False) -> str:
    """Get information about running processes.

    Returns JSON array: [{ name, id, cpu_s, memory_mb, start_time, responding }].
    Default: top 20 by CPU usage.

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
    return _out(result)


@mcp.tool()
async def http_request(uri: str, method: str = "GET", body: str = "", timeout_sec: int = 30) -> str:
    """Make an HTTP request to localhost or private network.

    Returns JSON: { status_code, body, headers, elapsed_ms }.

    Args:
        uri: Target URI — restricted to localhost and RFC-1918 IPs.
        method: GET, POST, PUT, PATCH, DELETE.
        body: Request body for POST/PUT/PATCH.
        timeout_sec: Timeout in seconds.

    Use port_status first to confirm the service is listening.
    Example: http_request("http://localhost:11434/api/tags")
    """
    escaped_body = body.replace("'", "''")
    cmd = f"Invoke-PSKitHttpRequest '{uri}' -Method '{method}' -Body '{escaped_body}' -TimeoutSec {timeout_sec}"
    result = await _require().execute(cmd)
    return _out(result)


@mcp.tool()
async def get_env_var(filter: str = "") -> str:
    """List environment variables filtered by name substring.

    Returns JSON: { vars: { NAME: value }, count }.

    Args:
        filter: Name contains filter. Empty = list all.
    """
    result = await _require().execute(
        f"Get-PSKitEnvVars -Filter '{filter}'" if filter else "Get-PSKitEnvVars"
    )
    return _out(result)


# ---------------------------------------------------------------------------
# Build & Test Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def build_project(command: str = "") -> str:
    """Run the project build — auto-detects build system.

    Returns JSON: { success, command_used, exit_code, stdout, stderr, duration_ms }.

    Auto-detection: npm build → cargo build → make → python -m build.

    Args:
        command: Override command e.g. "npm run build:prod".
    """
    if command:
        escaped = command.replace("'", "''")
        cmd = f"Invoke-PSKitBuild -Command '{escaped}'"
    else:
        cmd = "Invoke-PSKitBuild"
    result = await _require().execute(cmd)
    return _out(result)


@mcp.tool()
async def test_project(filter_expr: str = "", command: str = "") -> str:
    """Run the project test suite — auto-detects test framework.

    Returns JSON: { success, command_used, exit_code, passed, failed, skipped, stdout, stderr, duration_ms }.

    Auto-detection: pytest → npm test → cargo test.

    Args:
        filter_expr: Test filter e.g. pytest -k expression "test_auth or test_login".
        command: Full override e.g. "pytest tests/unit/ -v --tb=short".
    """
    if command:
        escaped = command.replace("'", "''")
        cmd = f"Invoke-PSKitTest -Command '{escaped}'"
    elif filter_expr:
        escaped = filter_expr.replace("'", "''")
        cmd = f"Invoke-PSKitTest -Filter '{escaped}'"
    else:
        cmd = "Invoke-PSKitTest"
    result = await _require().execute(cmd)
    return _out(result)


# ---------------------------------------------------------------------------
# MCP Prompts — pre-built agent workflows
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

Summarize: what this is, tech stack, current git state, and what you need to know to work effectively."""


@mcp.prompt()
def refactor_file(path: str = "") -> str:
    """Refactor a specific file for clarity, performance, and maintainability."""
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
2. search_code("import", path="{path or '.'}") — find existing test patterns
3. find_files("test_*.py") — read existing tests for conventions
4. Identify: happy paths, edge cases, error conditions, boundary values
5. write_file() the new test file following existing conventions
6. test_project() — run and fix until all new tests pass

Output a test file that covers at minimum: one test per public function/method,
one edge case per function, and one error/exception path per function."""


@mcp.prompt()
def explain_codebase() -> str:
    """Produce a high-level architectural explanation of this codebase."""
    return """Build a high-level understanding of this codebase:

1. find_files("README*") and read_file() — start with the overview
2. list_directory(".") — top-level structure
3. find_files("*.toml") or find_files("package.json") — identify tech stack and entry points
4. find_files("*.py", max_results=50) or equivalent — enumerate all source files
5. For each top-level module/directory: read_file() the main file
6. search_code("def ", include="*.py") or equivalent — key functions/classes
7. git_log(limit=20) — recent development trajectory

Produce a structured explanation covering: purpose, architecture, key modules,
data flow, external dependencies, and how to run it."""


# ---------------------------------------------------------------------------
# MCP Resources
# ---------------------------------------------------------------------------


@mcp.resource("pskit://guide")
def usage_guide() -> str:
    """PSKit quick-reference: all tool signatures, return shapes, and usage tips."""
    return """# PSKit Tool Reference (38 tools)

## File Tools
- read_file(path, max_lines=0) -> { content, line_count, path }
- read_file_range(path, start_line, end_line) -> { content, start_line, end_line, line_count }
- write_file(path, content) -> { success, path, bytes }
- edit_file(path, old_text, new_text, regex=False, replace_all=False) -> { success, replacements_made, preview }
- move_file(source, destination) -> { success, source, destination }
- delete_file(path, recurse=False) -> { success, path }
- create_directory(path) -> { success, path }
- list_directory(path=".", recurse=False) -> { items: [{ name, path, type, size_bytes, modified }], count }
- diff_files(path1, path2) -> { diff, identical, path1, path2 }
- search_code(pattern, path=".", include="*.*", max_results=50, context=0) -> { matches: [{file, line, text}], count }
- find_files(pattern, path=".", max_results=100) -> { files: [{name, path, size_bytes, modified}], count }
- run_command(script) -> { success, exit_code, output, stderr, duration_ms }

## Environment Tools
- get_env_vars(filter="") -> { vars: {NAME: value}, count }
- which(name) -> { found, name, path, version }
- install_package(name, manager="", version="") -> { success, manager, package, output }

## Git Tools
- git_status() -> { branch, ahead_behind, changes: [{status, file}] }
- git_diff(path="", staged=False) -> unified diff string
- git_log(limit=20, path="", since="", until="", author="") -> { commits: [{hash, short, message, author, date}] }
- git_commit(message) -> { success, output }
- git_branch(name, switch=True) -> { success, branch, output }
- git_checkout(ref) -> { success, ref, output }
- git_push(remote="origin", branch="") -> { success, remote, branch, output }
- git_blame(path, start_line=0, end_line=0) -> [{line, hash, author, date, content}]
- git_stash(message="pskit auto-stash") -> { success, output }
- git_stash_pop() -> { success, output }

## System Tools
- gpu_status() -> { gpu, memory_total, memory_used, memory_free, utilization, temperature }
- disk_usage(path=".") -> { drive, used_gb, free_gb, total_gb }
- memory_usage() -> { total_gb, free_gb, used_gb }

## Network & Process Tools
- port_status(ports="") -> [{port, listening, pid, process_name}]
- process_info(name="", pid=-1, include_threads=False) -> [{name, id, cpu_s, memory_mb, start_time}]
- http_request(uri, method="GET", body="", timeout_sec=30) -> { status_code, body, headers, elapsed_ms }
  RESTRICTION: localhost and private IPs only

## Build & Test Tools
- build_project(command="") -> { success, command_used, exit_code, stdout, stderr, duration_ms }
- test_project(filter_expr="", command="") -> { success, command_used, exit_code, passed, failed, skipped, stdout, stderr, duration_ms }

## Workflow
1. Always read_file before edit_file — verify old_text exists exactly
2. Use search_code to locate code before reading whole files
3. git_stash before risky edits, git_stash_pop to restore if needed
4. port_status("11434") to verify Ollama before http_request to Ollama
5. build_project() -> test_project() -> git_commit() — always in that order
6. If edit_file replacements_made=0, re-read the file and check spacing/indentation

## Errors
All tools return { "success": false, "error": "..." } on failure.
Read the error, adjust approach, do not retry unchanged.
"""


@mcp.resource("pskit://status")
def server_status() -> str:
    """Live PSKit server status — sessions, cache, counters, uptime."""
    import json
    uptime = round(_time.monotonic() - _start_time, 1)
    counters = get_counters()
    pool_info = {}
    if _manager and _manager._pool:
        pool = _manager._pool
        pool_info = {
            "initialized": getattr(pool, "initialized", False),
            "pool_size": getattr(pool, "_pool_size", 0),
        }
    cache_info = {}
    if _manager:
        cache = getattr(_manager, "_result_cache", None)
        if cache:
            cache_info = {
                "entries": len(getattr(cache, "_store", {})),
                "max_size": getattr(cache, "_max_size", 0),
                "ttl_seconds": getattr(cache, "_ttl", 0),
            }
    return json.dumps({
        "uptime_seconds": uptime,
        "active_sessions": len(_manager._sessions) if _manager else 0,
        "pool": pool_info,
        "cache": cache_info,
        "counters": counters,
    }, indent=2)
