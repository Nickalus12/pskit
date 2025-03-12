# PSKit — Developer Context

PSKit is a standalone Python MCP server exposing 19 PowerShell tools with a 5-tier neural safety pipeline. Used by [Loom](https://github.com/Nickalus12/loom) as its PowerShell execution layer.

## Architecture

| File | Purpose |
|------|---------|
| `src/pskit/server.py` | FastMCP server — 19 tools, 4 prompts, 1 resource |
| `src/pskit/manager.py` | PSKitManager — session pool, 5-tier safety pipeline, result cache |
| `src/pskit/kan_engine.py` | PSKitKANEngine — 24-feature KAN neural command scorer |
| `src/pskit/kan.py` | Vendored EfficientKAN (MIT) — pure PyTorch KAN implementation |
| `src/pskit/tools/PSKitTools.psm1` | 19 PowerShell functions loaded into every session |
| `tests/test_manager.py` | 32 unit tests (no live PS session required) |

## Key Invariants

- All PS execution flows through `PSKitManager.execute(script)` — never bypass
- Safety pipeline lives in `_execute_inner()` — 5 tiers run in order, never skip
- Result cache invalidates on every write command success (conservative but correct)
- Session pool: 3 named-pipe connections to `pwsh`, checkout/checkin pattern
- KAN scorer: `PSKitKANEngine.score_command(cmd)` → float 0.0 (safe) – 1.0 (dangerous)

## Development Commands

```bash
python -m pytest tests/ -q          # run all 32 unit tests
ruff check src/                      # lint
python -m pskit                      # start MCP server on stdio
```

## Adding a New Tool

1. Add PS function to `src/pskit/tools/PSKitTools.psm1`
2. Add function name to `Export-ModuleMember` at the bottom of the psm1
3. Add `@mcp.tool()` in `server.py` calling `_require().execute("New-PSKitFunction ...")`
4. Write tests in `tests/test_manager.py` (mock the PS session — don't need real pwsh)

## Adding a New Prompt

```python
@mcp.prompt()
def my_workflow() -> str:
    """One-line description shown in Claude's prompt library."""
    return "Step-by-step instructions telling Claude how to use pskit tools..."
```

## Safety Pipeline (do not modify without understanding all 5 tiers)

1. `_ResultCache` — SHA-256 keyed, 30s TTL, 128 LRU entries
2. `PSKitKANEngine.score_command()` — 24-feature neural scorer, <1ms
3. `_check_dangerous_commands()` — hard-block list, no override
4. `_check_path_safety()` — enforces `PSKIT_ALLOWED_ROOT`
5. `_local_engine.review_powershell_command()` — Gemma via Ollama, elevated only, fail-open

## Environment Variables

| Variable | Default | Effect |
|---|---|---|
| `PSKIT_ALLOWED_ROOT` | `cwd` | Sandbox root for file writes |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Tier 5 LLM endpoint |
| `PSKIT_SAFETY_MODEL` | `gemma4:e2b` | Tier 5 Ollama model |
| `PSKIT_POOL_SIZE` | `3` | Pre-warmed session count |
