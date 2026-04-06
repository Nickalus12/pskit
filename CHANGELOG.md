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
