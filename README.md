# PSKit

> Neural-safe PowerShell automation for AI agents

[![CI](https://github.com/Nickalus12/pskit/actions/workflows/ci.yml/badge.svg)](https://github.com/Nickalus12/pskit/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/pskit-mcp.svg)](https://pypi.org/project/pskit-mcp/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

PSKit is a [Model Context Protocol](https://modelcontextprotocol.io) server that gives AI agents **38 PowerShell tools** backed by a **5-tier neural safety pipeline**. Every command passes through a KAN (Kolmogorov-Arnold Network) neural scorer before execution — catching dangerous patterns in under 1 millisecond.

Works with **Claude Desktop**, **Claude Code**, **Cursor**, **Windsurf**, and any MCP-compatible client on Windows.

---

## Install

### Recommended — no virtual environment needed

```bash
uvx pskit-mcp
```

### With pip

```bash
pip install pskit-mcp
```

### With HTTP transport (for shared/remote use)

```bash
pip install "pskit-mcp[http]"
pskit serve --http --port 8000
```

---

## Quick Start

### Claude Desktop

Add to `%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "pskit": {
      "command": "uvx",
      "args": ["pskit-mcp"],
      "env": {
        "PSKIT_ALLOWED_ROOT": "C:\\Your\\Projects"
      }
    }
  }
}
```

### Claude Code

```bash
claude mcp add pskit -- uvx pskit-mcp
```

### Verify it works

```bash
pskit doctor
```

```
PSKit Doctor
+---------------------------+------+------------------------------------------+
| PowerShell (pwsh)         |  OK  | PowerShell 7.5.0                         |
| git                       |  OK  | git version 2.47.1                       |
| ripgrep (rg)              |  OK  | ripgrep 14.1.0 -- fast search active     |
| nvidia-smi                | WARN | not found -- gpu_status returns error    |
| Ollama                    |  OK  | running at localhost:11434               |
| Allowed root              |  OK  | C:\Projects\myapp                       |
| KAN model                 | WARN | no trained weights -- heuristic active  |
+---------------------------+------+------------------------------------------+
```

---

## What AI Agents Can Do

Once connected, an agent can autonomously work across your entire project:

```python
# Map the project structure
find_files("*.py", max_results=50)
list_directory("src/")

# Read, search, and edit files precisely
read_file("src/auth.py")
search_code("TODO", include="*.py", context=3)
edit_file("src/auth.py",
    old_text="def login(user):",
    new_text="def login(user: str) -> bool:")

# Full git workflow
git_status()               # branch, changes, ahead/behind
git_diff(staged=True)
git_commit("feat: add type hints to auth module")
git_push()

# Run builds and tests with structured results
result = build_project()
# { success: true, exit_code: 0, stdout: "...", duration_ms: 4821 }

result = test_project(filter_expr="test_auth")
# { success: true, passed: 12, failed: 0, skipped: 2, duration_ms: 1203 }

# System and network inspection
disk_usage()               # { drive: "C", free_gb: 142.3, total_gb: 476.9 }
port_status("8080,11434,5432")          # which services are listening
http_request("http://localhost:8000/health")  # localhost only

# Check and install dependencies
which("rg")                # { found: true, version: "14.1.0" }
install_package("requests", manager="pip")
```

---

## Safety Pipeline

Every command passes through 5 tiers before execution:

```
 Command Input
      |
      v
+---------------------------------------------+
|  Tier 1 . Result Cache                      |
|  SHA-256 keyed . 30s TTL . 128 LRU entries  |
|  Read-only hits served instantly            |
+--------------------+------------------------+
                     | miss
                     v
+---------------------------------------------+
|  Tier 2 . KAN Neural Scorer                 |
|  24 features . Kolmogorov-Arnold Network    |
|  Sub-millisecond risk classification        |
+--------------------+------------------------+
                     |
                     v
+---------------------------------------------+
|  Tier 3 . Dangerous Command Blocklist       |
|  Hard-blocks: Format-Volume, rm -rf,        |
|  mass deletion, privilege escalation        |
+--------------------+------------------------+
                     |
                     v
+---------------------------------------------+
|  Tier 4 . Path Safety Check                 |
|  Enforces PSKIT_ALLOWED_ROOT boundary       |
|  Blocks writes outside project root         |
+--------------------+------------------------+
                     | elevated only
                     v
+---------------------------------------------+
|  Tier 5 . Gemma LLM Review (optional)       |
|  Ollama-backed . Fail-open if offline       |
|  Deep semantic analysis of intent           |
+--------------------+------------------------+
                     |
                     v
                Execute
```

---

## KAN Neural Safety

PSKit uses a **Kolmogorov-Arnold Network** to score every command across **24 structural features** before execution:

| Feature Group | What It Detects |
|---|---|
| Structure | command length, pipe depth, semicolons, nesting |
| Dangerous patterns | `Invoke-Expression`, deletion flags, `--force --recurse` |
| Network | outbound requests, drive mappings, mail |
| Credentials | `Get-Credential`, SecureString, `-Password` parameters |
| Obfuscation | base64 encoding, variable expansion, string interpolation |
| Persistence | registry writes, scheduled task creation, service installs |
| Output | redirection, file output, compression |

Unlike rule-based filters, KAN learns **non-linear risk combinations**. Scores 0.0 (safe) to 1.0 (dangerous) in **under 1ms**, acting as an always-on pre-filter before the optional Ollama LLM review.

---

## Built-In Agent Workflows

PSKit ships 6 ready-to-use MCP prompts accessible from Claude's prompt library:

| Prompt | What It Does |
|---|---|
| **Audit Project** | Full sweep: git state, structure, build, tests, system health |
| **Review Changes** | Pre-commit diff review with commit message suggestion |
| **Diagnose Build** | Systematic failure investigation with specific code fix |
| **Orient to Project** | First-session orientation before starting any work |
| **Refactor File** | Targeted single-file cleanup with stash safety net |
| **Write Tests For** | Generate tests following existing project conventions |

Plus a `pskit://guide` resource Claude can read anytime for the complete tool reference, and a `pskit://status` resource for live server health.

---

## Tools (38 total)

| Category | Tools |
|---|---|
| **File** | `read_file`, `read_file_range`, `write_file`, `edit_file`, `move_file`, `delete_file`, `create_directory`, `list_directory`, `diff_files` |
| **Search** | `search_code` (ripgrep + context lines), `find_files` |
| **Shell** | `run_command` (safety-gated arbitrary PS with progress) |
| **Environment** | `get_env_vars`, `which`, `install_package` |
| **Git** | `git_status`, `git_diff`, `git_log`, `git_commit`, `git_branch`, `git_checkout`, `git_push`, `git_blame`, `git_stash`, `git_stash_pop` |
| **System** | `gpu_status`, `disk_usage`, `memory_usage` |
| **Network** | `port_status`, `process_info`, `http_request` (private IPs only) |
| **Build** | `build_project`, `test_project` (structured results with pass/fail counts) |

All 38 tools return **typed structured output** with auto-generated JSON schemas. Annotated with `readOnly`, `destructive`, and `idempotent` hints so clients auto-approve safe operations and warn on destructive ones.

---

## CLI

```bash
pskit serve           # Start MCP server on stdio (default)
pskit serve --http    # Start on streamable HTTP (port 8000)
pskit doctor          # System health check
pskit audit           # View recent command audit log with KAN scores
pskit version         # Print version
```

---

## Configuration

| Variable | Default | Description |
|---|---|---|
| `PSKIT_ALLOWED_ROOT` | Current directory | File writes sandboxed to this path |
| `PSKIT_POOL_SIZE` | `3` | Pre-warmed PowerShell session count |
| `PSKIT_SAFETY_MODEL` | `gemma4:e2b` | Ollama model for Tier 5 review |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama endpoint |

Or use `pskit.config.toml` in your project root:

```toml
[pskit]
allowed_root = "."
pool_size = 5
safety_model = "gemma3:4b"
```

---

## Audit Log

Every command is logged to `.pskit/audit.jsonl` with KAN score, safety verdict, and duration:

```bash
pskit audit
```

```
PSKit Audit (last 50)
+---------------------+----------+-------+------+-------------------------------------+
| Time                | Verdict  |  KAN  |  ms  | Command                             |
+---------------------+----------+-------+------+-------------------------------------+
| 2026-04-06 15:42:11 | safe     | 0.023 |   18 | Get-PSKitGitStatus                  |
| 2026-04-06 15:42:14 | safe     | 0.031 |  247 | Read-PSKitFile 'src/auth.py'        |
| 2026-04-06 15:42:19 | caution  | 0.441 |  892 | Invoke-PSKitHttpRequest 'localhost' |
+---------------------+----------+-------+------+-------------------------------------+

  Total: 47  Blocked: 0  Avg KAN: 0.089  Avg ms: 124
```

---

## Requirements

- **Python 3.11+**
- **PowerShell 7.0+** — `pwsh` on PATH ([download](https://github.com/PowerShell/PowerShell/releases))
- **PyTorch 2.0+** — for the KAN neural scorer
- **ripgrep** *(optional)* — faster file search when `rg` is on PATH
- **Ollama** *(optional)* — enables Tier 5 Gemma LLM safety review

---

## Powered by Loom

PSKit was extracted from [Loom](https://github.com/Nickalus12/loom), a multi-agent orchestration platform. Loom uses PSKit as its PowerShell execution layer.

---

## Contributing

```bash
git clone https://github.com/Nickalus12/pskit
pip install -e ".[dev]"
python -m pytest tests/ -q    # 38 tests, no live PS session required
ruff check src/               # lint
```

See [CLAUDE.md](CLAUDE.md) for architecture docs and the guide to adding new tools.

---

## License

MIT (c) 2025-2026 Nickalus Brewer
