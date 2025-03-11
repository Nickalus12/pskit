# Changelog

All notable changes to PSKit are documented here.

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
