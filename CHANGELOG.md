## [0.3.1] - 2026-04-17

### Fixed

- **Performance**: On Linux and macOS, skip the Windows-only named-pipe session path entirely. Previously every PowerShell session waited 15 s for a `PIPE_READY` marker that could never arrive, then fell back to stdin/stdout mode. Pool pre-warm dropped from ~45 s to ~2 s; per-call overhead dropped from >15 s to <1 s on POSIX. Windows behaviour unchanged.

## [0.3.0] — 2026-04-17

### Added

- **Cross-platform support**: PSKit now runs on Linux and macOS in addition to Windows
- 5 cross-platform integration tests exercising `memory_usage`, `disk_usage`, `port_status`, `process_info`, `run_command` via real pwsh
- CI matrix expanded to Windows / Ubuntu / macOS × Python 3.11 / 3.12 / 3.13 (9 jobs)
- 24 POSIX-flavoured destructive patterns added to the dangerous-command blocklist (filesystem wipes, fork bombs, pipe-to-shell installers, etc.)
- 12 POSIX read-only command prefixes recognised for tier-1 cache fast path

### Changed

- `Get-PSKitMemoryUsage` branches on `$IsLinux` / `$IsMacOS` / Windows, reading `/proc/meminfo`, `sysctl` + `vm_stat`, or `Win32_OperatingSystem`
- `Get-PSKitDiskUsage` uses `df -Pk` on POSIX, `Get-PSDrive` on Windows
- `Get-PSKitPortStatus` uses `ss -tlnp` on Linux, `lsof` on macOS, `Get-NetTCPConnection` on Windows
- `Get-PSKitProcessInfo` guards `.Responding` / `.Threads` access so it degrades cleanly on non-Windows
- `Install-PSKitPackage` dispatches to `apt` / `dnf` / `pacman` on Linux, `brew` on macOS, `winget` on Windows
- All platform-aware tools now return a `platform` field (`"windows"`, `"linux"`, or `"macos"`)
- README: dropped "on Windows" claim, added Platform Support matrix and per-OS client configuration examples
- `docs/tools.md`: updated tool count, added cross-platform behaviour blocks for each affected tool
- `pyproject.toml`: classifiers now include `Operating System :: POSIX :: Linux` and `Operating System :: MacOS`; description updated

### Fixed

- Cleared ruff lint bitrot in `__main__.py` and `manager.py` (23 pre-existing findings) so CI lint step passes on modern ruff
- `release.yml`: macOS runner installs PowerShell via formula (`brew install powershell`) — the cask path was renamed upstream

# Changelog

All notable changes to PSKit are documented here.

## [0.2.0] — 2026-04-06

### Added

- **19 new MCP tools** (38 total): `read_file_range`, `move_file`, `delete_file`, `create_directory`, `list_directory`, `diff_files`, `run_command`, `get_env_vars`, `which`, `install_package`, `git_branch`, `git_checkout`, `git_push`, `git_blame`
- **Structured build/test returns**: `build_project` and `test_project` now return `{exit_code, stdout, stderr, passed, failed, skipped, duration_ms}`
- **`search_code` context lines**: `-Context N` shows N lines around each match
- **`git_log` filters**: `path`, `since`, `until`, `author` parameters
- **`pskit.config`**: layered config from `pskit.config.toml` and environment variables
- **`pskit.audit`**: append-only `.pskit/audit.jsonl` command audit log with KAN scores and verdicts
- **CLI subcommands**: `pskit doctor`, `pskit audit`, `pskit version`
- **3 new MCP prompts**: `refactor_file`, `write_tests_for`, `explain_codebase` (6 total)
- **`pskit://status` resource**: live server uptime, session count, cache stats, counters
- **PyPI publishing**: renamed package to `pskit-mcp`, added Trusted Publisher CI release workflow

### Changed

- Package name: `pskit` → `pskit-mcp` on PyPI (install: `pip install pskit-mcp`)
- Both `pskit` and `pskit-mcp` CLI entry points registered
- Version bump to 0.2.0

## [0.1.0] — 2025-04-06

### Added

- 19 PowerShell tools across 5 categories: File, Git, System, Network, Build
- 5-tier neural safety pipeline
  - Tier 1: SHA-256 result cache (30s TTL, 128 entries)
  - Tier 2: KAN neural scorer (24 features, sub-millisecond)
  - Tier 3: Dangerous command blocklist
  - Tier 4: Path safety enforcement via PSKIT_ALLOWED_ROOT
  - Tier 5: Gemma LLM review via Ollama (elevated commands, fail-open)
- Named-pipe session pool — 3 pre-warmed sessions, ~5ms round-trip
- FastMCP server with lifespan session management
- 4 MCP prompts: audit_project, review_changes, diagnose_build, orient_to_project
- pskit://guide MCP resource — tool reference for AI agents
- uvx pskit — one-command install and run
- Full type annotations and py.typed marker (PEP 561)
