# PSKit

> Neural-safe PowerShell automation for AI agents

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

PSKit is a [Model Context Protocol](https://modelcontextprotocol.io) server that gives AI agents
19 curated PowerShell tools backed by a neural safety pipeline.

## Install

```bash
pip install pskit
```

## Tools

| Category | Tool | Description |
|----------|------|-------------|
| **File** | `read_file` | Read file with line numbers |
| **File** | `write_file` | Write or create a file |
| **File** | `edit_file` | Find-and-replace in a file |
| **File** | `search_code` | Ripgrep-backed code search |
| **File** | `find_files` | Fast file glob discovery |
| **Git** | `git_status` | Working tree status |
| **Git** | `git_diff` | Staged and unstaged diff |
| **Git** | `git_log` | Recent commit history |
| **Git** | `git_commit` | Create a commit |
| **Git** | `git_stash` | Stash current changes |
| **Git** | `git_stash_pop` | Restore stashed changes |
| **System** | `gpu_status` | GPU utilization and VRAM |
| **System** | `disk_usage` | Disk space by drive |
| **System** | `memory_usage` | RAM and virtual memory |
| **Network** | `port_status` | TCP port listeners |
| **Network** | `process_info` | Top processes by CPU |
| **Network** | `http_request` | Localhost HTTP requests |
| **Build** | `build_project` | Run project build command |
| **Build** | `test_project` | Run project test suite |

## License

MIT © 2025 Nickalus Brewer

## Safety Pipeline

Every command passes through 5 tiers before execution:

```
Command -> Cache -> KAN Neural -> Blocklist -> Path Check -> Gemma LLM -> Execute
```
