# PSKit MCP — Tool Reference

This document is the complete developer reference for all 33 PSKit MCP tools. All tools run cross-platform on Windows, Linux, and macOS via PowerShell 7. Each entry covers parameters, return format, and a working example.

All tools return a JSON string. On success, the top-level `success` field is `true`. On failure it is `false` and an `error` field describes the problem. Path parameters accept native paths for the current OS: `C:\Projects\app` on Windows, `/home/you/app` on Linux, `/Users/you/app` on macOS.

---

## File Operations

### `read_file`

Read a file from disk, returned with 1-based line numbers.

**Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `path` | `str` | yes | — | Absolute or relative path to the file |
| `max_lines` | `int` | no | `0` | Maximum lines to return; `0` means all lines |

**Return schema**

```json
{
  "success": true,
  "path": "C:\\Projects\\myapp\\src\\main.py",
  "line_count": 142,
  "content": "    1| import os\n    2| import sys\n    ..."
}
```

**Error response**

```json
{ "success": false, "error": "File not found: C:\\Projects\\missing.py" }
```

**Example**

```
read_file(path="src/main.py", max_lines=50)
```

---

### `write_file`

Write content to a file. Parent directories are created automatically.

**Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `path` | `str` | yes | — | Destination file path |
| `content` | `str` | yes | — | Full file content to write (UTF-8) |

**Return schema**

```json
{
  "success": true,
  "path": "C:\\Projects\\myapp\\src\\config.py",
  "bytes": 1024
}
```

**Example**

```
write_file(path="src/config.py", content="DEBUG = False\nPORT = 8080\n")
```

---

### `edit_file`

Replace a substring or regex pattern inside an existing file.

**Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `path` | `str` | yes | — | Path to the file to edit |
| `old_text` | `str` | yes | — | Text to search for |
| `new_text` | `str` | yes | — | Replacement text |
| `regex` | `bool` | no | `false` | Treat `old_text` as a .NET regex pattern |
| `replace_all` | `bool` | no | `false` | Replace every occurrence; default replaces only the first |

**Return schema**

```json
{
  "success": true,
  "path": "C:\\Projects\\myapp\\src\\config.py",
  "replacements_made": 1,
  "preview": "DEBUG = True\nPORT = 8080\n"
}
```

**Error response**

```json
{ "success": false, "error": "OldText not found in file", "path": "src/config.py" }
```

**Example — literal replace**

```
edit_file(path="src/config.py", old_text="DEBUG = False", new_text="DEBUG = True")
```

**Example — regex replace all**

```
edit_file(
    path="src/app.py",
    old_text=r"print\((.+?)\)",
    new_text=r"logger.debug(\1)",
    regex=True,
    replace_all=True
)
```

---

### `search_code`

Search for a pattern across files using ripgrep when available, falling back to `Select-String`.

**Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `pattern` | `str` | yes | — | Search pattern (literal or ripgrep regex) |
| `path` | `str` | no | `"."` | Root directory to search under |
| `include` | `str` | no | `"*.*"` | Glob to restrict file types, e.g. `"*.py"` |
| `max_results` | `int` | no | `50` | Maximum number of matches to return |

**Return schema**

```json
{
  "success": true,
  "pattern": "def execute",
  "count": 3,
  "engine": "rg",
  "matches": [
    { "file": "src/manager.py", "line": 412, "text": "async def execute(" },
    { "file": "src/pool.py",    "line": 87,  "text": "def execute_pooled(" }
  ]
}
```

**Example**

```
search_code(pattern="TODO", path="src", include="*.py", max_results=20)
```

---

### `find_files`

Find files matching a glob pattern under a directory tree.

**Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `pattern` | `str` | yes | — | Glob pattern, e.g. `"*.toml"` or `"**/*.test.ts"` |
| `path` | `str` | no | `"."` | Root directory to search |
| `max_results` | `int` | no | `100` | Maximum number of files to return |

**Return schema**

```json
{
  "success": true,
  "pattern": "*.py",
  "count": 12,
  "engine": "rg",
  "files": [
    {
      "name": "manager.py",
      "path": "C:\\Projects\\pskit\\src\\pskit\\manager.py",
      "size": 24576,
      "modified": "2025-04-06T09:00:00.000Z"
    }
  ]
}
```

**Example**

```
find_files(pattern="*.py", path="src", max_results=50)
```

---

## Git Operations

### `git_status`

Get the current git status of the working directory.

**Parameters**

None.

**Return schema**

```json
{
  "success": true,
  "branch": "main",
  "changes": [
    { "status": "M",  "file": "src/manager.py" },
    { "status": "??", "file": "tests/new_test.py" }
  ],
  "ahead_behind": "0\t0"
}
```

**Example**

```
git_status()
```

---

### `git_diff`

Show the git diff for the working tree or a specific file.

**Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `path` | `str` | no | `""` | Restrict diff to this file path |
| `staged` | `bool` | no | `false` | Show staged (index) diff instead of working tree |

**Return schema**

```json
{
  "success": true,
  "diff": "diff --git a/src/manager.py b/src/manager.py\n--- a/src/manager.py\n+++ ..."
}
```

**Example — unstaged diff for one file**

```
git_diff(path="src/manager.py")
```

**Example — all staged changes**

```
git_diff(staged=True)
```

---

### `git_log`

Show recent git commit history.

**Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `limit` | `int` | no | `20` | Number of commits to return |

**Return schema**

```json
{
  "success": true,
  "count": 3,
  "commits": [
    {
      "hash":    "a1b2c3d4e5f6...",
      "short":   "a1b2c3d",
      "message": "feat: add KAN neural scorer",
      "author":  "Nickalus Brewer",
      "date":    "2025-04-06 09:00:00 -0500"
    }
  ]
}
```

**Example**

```
git_log(limit=10)
```

---

### `git_commit`

Stage all changes and create a git commit.

**Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `message` | `str` | yes | — | Commit message |

**Return schema**

```json
{
  "success": true,
  "output": "[main a1b2c3d] feat: add neural safety pipeline\n 3 files changed, 142 insertions(+)"
}
```

**Example**

```
git_commit(message="fix: correct path safety check for UNC paths")
```

---

### `git_stash`

Save current working tree changes to the git stash.

**Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `message` | `str` | no | `"PSKit auto-stash"` | Stash description |

**Return schema**

```json
{
  "success": true,
  "output": "Saved working directory and index state On main: PSKit auto-stash"
}
```

**Example**

```
git_stash(message="WIP: refactoring session pool")
```

---

### `git_stash_pop`

Restore the most recently stashed changes.

**Parameters**

None.

**Return schema**

```json
{
  "success": true,
  "output": "On branch main\nChanges not staged for commit: ..."
}
```

**Example**

```
git_stash_pop()
```

---

## System Information

### `gpu_status`

Get NVIDIA GPU status via `nvidia-smi`.

**Parameters**

None.

**Return schema — GPU present**

```json
{
  "success": true,
  "gpu": "NVIDIA GeForce RTX 4090",
  "memory_total": "24576 MiB",
  "memory_used": "4096 MiB",
  "memory_free": "20480 MiB",
  "utilization": "12 %",
  "temperature": "54"
}
```

**Return schema — no GPU**

```json
{ "success": false, "error": "nvidia-smi not available" }
```

**Example**

```
gpu_status()
```

---

### `disk_usage`

Get disk space statistics for the drive containing the given path.

**Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `path` | `str` | no | `"."` | Any path on the target drive |

**Return schema**

```json
{
  "success": true,
  "drive": "C",
  "used_gb": 312.45,
  "free_gb": 187.55,
  "total_gb": 500.0
}
```

**Example**

```
disk_usage(path="C:\\")
```

**Cross-platform behaviour**

Returns an additional `platform` field and, on POSIX, a `mount` field (filesystem mount point).
Uses `df -Pk` on Linux and macOS; `Get-PSDrive` on Windows. The `drive` field is a drive letter
on Windows and the filesystem identifier (e.g. `overlay`, `/dev/nvme0n1p2`) on POSIX.


---

### `memory_usage`

Get system RAM statistics.

**Parameters**

None.

**Return schema**

```json
{
  "success": true,
  "total_gb": 64.0,
  "free_gb": 41.23,
  "used_gb": 22.77
}
```

**Example**

```
memory_usage()
```

**Cross-platform behaviour**

Returns an additional `platform` field (`"windows"` / `"linux"` / `"macos"`).
Uses `/proc/meminfo` on Linux (MemAvailable when present, else MemFree+Buffers+Cached),
`sysctl hw.memsize` + `vm_stat` on macOS, and `Win32_OperatingSystem` (CIM) on Windows.


---

## Network and Process

### `port_status`

Check which TCP ports are listening and which processes own them.

**Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `ports` | `str` | no | `""` | Comma-separated port numbers; empty uses the default set |

Default set: `8080, 8443, 11434, 7474, 7687, 5432, 3000, 3001, 8000, 9000`

**Return schema**

```json
{
  "success": true,
  "ports": [
    { "port": 11434, "listening": true,  "pid": 4892, "process_name": "ollama" },
    { "port": 5432,  "listening": false, "pid": null, "process_name": null }
  ]
}
```

**Example — default ports**

```
port_status()
```

**Example — specific ports**

```
port_status(ports="3000,4000,8080")
```

**Cross-platform behaviour**

Returns an additional `platform` field. Uses `ss -tlnp` on Linux (falls back to `/proc/net/tcp`
without process names when `ss` is missing), `lsof -nP -iTCP -sTCP:LISTEN` on macOS, and
`Get-NetTCPConnection` on Windows.


---

### `process_info`

Get information about running processes.

**Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `name` | `str` | no | `""` | Filter by process name |
| `pid` | `int` | no | `-1` | Filter by PID; takes precedence over `name` |
| `include_threads` | `bool` | no | `false` | Include per-thread state in the response |

When both `name` and `pid` are omitted, returns the top 20 processes by CPU time.

**Return schema**

```json
{
  "success": true,
  "count": 2,
  "processes": [
    {
      "name": "pwsh",
      "id": 4892,
      "cpu_s": 1.23,
      "memory_mb": 87.4,
      "start_time": "2025-04-06T08:00:00.0000000+00:00",
      "responding": true,
      "thread_count": 12
    }
  ]
}
```

**Example — by name**

```
process_info(name="python")
```

**Example — by PID with threads**

```
process_info(pid=4892, include_threads=True)
```

**Cross-platform behaviour**

On Linux and macOS the `.Responding` and per-thread `ThreadState` properties of
`System.Diagnostics.Process` are unavailable; those fields return `null` instead of raising.


---

### `http_request`

Make an HTTP request to a localhost or private network address.

Restricted to `127.x.x.x`, `::1`, `10.x.x.x`, `172.16-31.x.x`, and `192.168.x.x` for safety.

**Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `uri` | `str` | yes | — | Target URI (must be localhost or private IP) |
| `method` | `str` | no | `"GET"` | HTTP method: `GET`, `POST`, `PUT`, `DELETE`, etc. |
| `body` | `str` | no | `""` | Request body string |
| `timeout_sec` | `int` | no | `30` | Request timeout in seconds |

**Return schema**

```json
{
  "success": true,
  "status_code": 200,
  "body": "{\"models\": [{\"name\": \"gemma4:e2b\"}]}",
  "headers": "{\"Content-Type\": \"application/json\"}",
  "elapsed_ms": 12
}
```

**Error — external address blocked**

```json
{
  "success": false,
  "error": "Invoke-PSKitHttpRequest is restricted to localhost and private IPs. Uri: https://example.com"
}
```

**Example — query Ollama**

```
http_request(uri="http://localhost:11434/api/tags")
```

**Example — POST with body**

```
http_request(
    uri="http://localhost:8000/api/run",
    method="POST",
    body='{"command": "build"}'
)
```

---

## Build and Test

### `build_project`

Run the project's build command. Auto-detects the build system when no command is provided.

**Auto-detection order**

| File present | Command run |
|---|---|
| `package.json` | `npm run build` |
| `pyproject.toml` | `python -m build` |
| `Cargo.toml` | `cargo build` |
| `Makefile` | `make` |

**Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `command` | `str` | no | `""` | Override auto-detection with a custom command |

**Return schema**

```json
{
  "success": true,
  "command": "python -m build",
  "output": "* Creating virtualenv isolated environment...\n* Building sdist...\n..."
}
```

**Error — no build system**

```json
{ "success": false, "error": "No build system detected" }
```

**Example — auto-detect**

```
build_project()
```

**Example — custom command**

```
build_project(command="dotnet build --configuration Release")
```

---

### `test_project`

Run the project's test suite. Auto-detects the test framework when no command is provided.

**Auto-detection order**

| File present | Command run |
|---|---|
| `pyproject.toml` | `python -m pytest` |
| `package.json` | `npm test` |
| `Cargo.toml` | `cargo test` |

**Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `filter_expr` | `str` | no | `""` | Test filter expression (e.g. pytest `-k` value) |
| `command` | `str` | no | `""` | Override auto-detection with a custom command |

**Return schema**

```json
{
  "success": true,
  "command": "python -m pytest -k \"test_cache\"",
  "output": "collected 4 items\n\ntests/test_manager.py::test_result_cache_hit PASSED\n..."
}
```

**Example — run all tests**

```
test_project()
```

**Example — filter by name**

```
test_project(filter_expr="test_cache")
```

**Example — custom runner**

```
test_project(command="python -m pytest tests/ -v --tb=short")
```

---

## Return Value Conventions

All tools return a compact JSON string. The Python-side `_out()` helper in `server.py` extracts `output` first, then `error`, so callers always receive the most useful field as a plain string rather than raw JSON. To access structured fields, parse the string as JSON.

```python
import json

raw = await read_file(path="pyproject.toml")
data = json.loads(raw)
print(data["line_count"])
```

## Safety Considerations

- `write_file`, `edit_file`, `git_commit`, `build_project`, and `test_project` are write operations. They invalidate the read-only result cache on success.
- `http_request` is network-restricted to localhost and RFC-1918 ranges. External URIs are rejected before the request is sent.
- All tools pass through the 5-tier KAN neural safety pipeline. Commands classified as `blocked` by the KAN scorer or the dangerous-command blocklist are rejected before any PowerShell process is involved.
- The `PSKIT_ALLOWED_ROOT` environment variable enforces a filesystem boundary. Any write operation targeting an absolute path outside that boundary is rejected by Tier 4. This applies equally to Windows (`C:\...`), Linux (`/home/...`), and macOS (`/Users/...`) paths.
