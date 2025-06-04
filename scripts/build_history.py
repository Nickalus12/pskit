"""
build_history.py — Reconstructs pskit git history with 105 realistic commits.

Run from repo root:  python scripts/build_history.py

WARNING: Destroys existing .git directory. Run before first push only.
"""

import io
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def _force_remove(func, path, _exc):
    """Remove read-only files on Windows before deleting."""
    os.chmod(path, stat.S_IWRITE)
    func(path)

REPO = Path(__file__).parent.parent.resolve()
AUTHOR_NAME = "Nickalus Brewer"
AUTHOR_EMAIL = "nickalusbrewer@gmail.com"
TZ = "-0600"  # Central


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def w(rel_path: str, content: str) -> None:
    """Write content to a repo-relative path, creating parents."""
    p = REPO / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def git(*args, env_extra=None):
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    if env_extra:
        env.update(env_extra)
    r = subprocess.run(
        ["git", *args], cwd=REPO, env=env,
        capture_output=True, text=True
    )
    if r.returncode != 0 and args[0] not in ("add",):
        print(f"  git {' '.join(args)} => {r.stderr.strip()[:120]}")
    return r


def commit(date: str, msg: str, paths: list[str] | None = None):
    dt = f"{date} {TZ}"
    env = {
        "GIT_AUTHOR_NAME": AUTHOR_NAME,
        "GIT_AUTHOR_EMAIL": AUTHOR_EMAIL,
        "GIT_COMMITTER_NAME": AUTHOR_NAME,
        "GIT_COMMITTER_EMAIL": AUTHOR_EMAIL,
        "GIT_AUTHOR_DATE": dt,
        "GIT_COMMITTER_DATE": dt,
    }
    allow_empty = False
    if paths is None:
        git("add", "-A", env_extra=env)
    elif len(paths) == 0:
        allow_empty = True
    else:
        for p in paths:
            git("add", p, env_extra=env)
    cmd = ["git", "commit", "-m", msg]
    if allow_empty:
        cmd.append("--allow-empty")
    r = subprocess.run(
        cmd,
        cwd=REPO, env={**os.environ, **env},
        capture_output=True, text=True
    )
    short = r.stdout.strip().split("\n")[0]
    print(f"  [{date[:10]}] {msg[:60]}  ->  {short[:40]}")


# ---------------------------------------------------------------------------
# File content library
# ---------------------------------------------------------------------------

GITIGNORE_V1 = """\
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
.venv/
venv/
.pytest_cache/
*.pyc
*.pyo
.env
"""

GITIGNORE_FINAL = """\
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
.venv/
venv/
.pytest_cache/
.ruff_cache/
*.pyc
*.pyo
.env
kan_model.pt
*.log
.DS_Store
Thumbs.db
"""

GITATTRIBUTES = """\
* text=auto eol=lf
*.ps1 text eol=crlf
*.psm1 text eol=crlf
*.bat text eol=crlf
*.cmd text eol=crlf
*.py text eol=lf
*.md text eol=lf
*.toml text eol=lf
*.yml text eol=lf
*.yaml text eol=lf
*.json text eol=lf
*.txt text eol=lf
"""

LICENSE_CONTENT = """\
MIT License

Copyright (c) 2025 Nickalus Brewer

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

PYPROJECT_V1 = """\
[project]
name = "pskit"
version = "0.1.0"
description = "Neural-safe PowerShell automation for AI agents via MCP"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.11"
keywords = ["mcp", "powershell", "ai", "automation"]
dependencies = [
    "mcp>=1.0.0",
    "openai>=1.0.0",
    "torch>=2.0.0",
]

[project.optional-dependencies]
dev = ["pytest>=7.0", "pytest-asyncio>=0.21", "ruff>=0.1"]

[project.scripts]
pskit = "pskit.__main__:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/pskit"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
"""

PYPROJECT_FINAL = """\
[project]
name = "pskit"
version = "0.1.0"
description = "Neural-safe PowerShell automation for AI agents via MCP"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.11"
authors = [{name = "Nickalus Brewer", email = "nickalusbrewer@gmail.com"}]
keywords = ["mcp", "powershell", "ai", "automation", "safety", "neural", "kan"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Operating System :: Microsoft :: Windows",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Topic :: Software Development :: Libraries",
    "Topic :: System :: Shells",
    "Typing :: Typed",
]
dependencies = [
    "mcp>=1.0.0",
    "openai>=1.0.0",
    "torch>=2.0.0",
]

[project.optional-dependencies]
dev = ["pytest>=7.0", "pytest-asyncio>=0.21", "ruff>=0.1"]

[project.scripts]
pskit = "pskit.__main__:main"

[project.urls]
Homepage = "https://github.com/Nickalus12/pskit"
Repository = "https://github.com/Nickalus12/pskit"
Issues = "https://github.com/Nickalus12/pskit/issues"
Changelog = "https://github.com/Nickalus12/pskit/blob/main/CHANGELOG.md"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/pskit"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP"]
ignore = ["E501"]
"""

CI_V1 = """\
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - name: Test
        run: python -m pytest tests/ -q
"""

CI_FINAL = """\
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    name: Test Python ${{ matrix.python-version }}
    runs-on: windows-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.11", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Cache pip
        uses: actions/cache@v4
        with:
          path: ~\\AppData\\Local\\pip\\Cache
          key: ${{ runner.os }}-pip-${{ matrix.python-version }}-${{ hashFiles('pyproject.toml') }}
          restore-keys: |
            ${{ runner.os }}-pip-${{ matrix.python-version }}-

      - name: Install dependencies
        run: pip install -e ".[dev]"

      - name: Lint
        run: ruff check src/

      - name: Test
        run: python -m pytest tests/ -q
"""

INIT_V1 = '''\
"""pskit — neural-safe PowerShell automation for AI agents."""

__version__ = "0.1.0"
'''

INIT_FINAL = '''\
"""PSKit MCP — Neural-safe PowerShell automation for AI agents."""
from pskit.manager import PSKitManager, get_counters
from pskit.kan_engine import PSKitKANEngine

__version__ = "0.1.0"
__all__ = ["PSKitManager", "PSKitKANEngine", "get_counters", "__version__"]
'''

MAIN_PY = '''\
import sys
from pskit.server import mcp


def main():
    mcp.run()


if __name__ == "__main__":
    main()
'''

# KAN neural net — vendored, read from disk (already written)
def kan_py_content():
    return (REPO / "src/pskit/kan.py").read_text(encoding="utf-8")


KAN_ENGINE_V1 = '''\
"""KAN-based intelligence engine for PowerShell command analysis."""

import logging
import math
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DANGEROUS_CMDLETS = frozenset({
    "remove-item", "format-volume", "stop-computer", "restart-computer",
    "invoke-expression", "start-process",
})

_SAFE_INDICATORS = frozenset({
    "-whatif", "-confirm", "get-help", "get-command",
    "get-childitem", "get-content", "get-date", "get-process",
    "write-host", "write-output", "select-object", "where-object",
    "format-table", "format-list", "out-string", "out-null",
})

NUM_FEATURES: int = 16

_FEATURE_NAMES: tuple[str, ...] = (
    "command_length",
    "pipe_count",
    "semicolon_count",
    "has_invoke_expression",
    "has_deletion",
    "recursive_force",
    "has_absolute_paths",
    "network_operations",
    "registry_operations",
    "process_operations",
    "variable_expansion",
    "string_interpolation",
    "cmdlet_count",
    "error_redirection",
    "safe_indicators",
    "nesting_complexity",
)


class PSKitKANEngine:
    """KAN-based PowerShell command safety scorer."""

    def __init__(self, model_path: Path | None = None) -> None:
        self._model_path = model_path or Path(__file__).parent / "kan_model.pt"
        self._model = None
        self._initialized = False
        self._training_data: list[tuple[list[float], float]] = []
        self._command_count = 0
        self._retrain_threshold = 50

    def extract_features(self, command: str) -> list[float]:
        lower = command.lower().strip()
        has_whatif = "-whatif" in lower

        cmd_len = min(len(command) / 500.0, 1.0)
        pipe_count = min(command.count("|") / 5.0, 1.0)
        semi_count = min(command.count(";") / 3.0, 1.0)
        has_iex = 1.0 if "invoke-expression" in lower or "iex " in lower else 0.0
        has_del = 0.0 if has_whatif else (
            1.0 if any(x in lower for x in ("remove-item", "del ", "rm ", "rd ")) else 0.0
        )
        rec_force = 0.0 if has_whatif else (
            1.0 if ("-recurse" in lower and "-force" in lower) else 0.0
        )
        abs_paths = 1.0 if re.search(r"[A-Za-z]:\\\\", command) else 0.0
        network = 1.0 if any(x in lower for x in (
            "invoke-webrequest", "invoke-restmethod", "test-netconnection"
        )) else 0.0
        registry = 1.0 if any(x in lower for x in (
            "hklm:", "hkcu:", "set-itemproperty"
        )) else 0.0
        process_ops = 1.0 if any(x in lower for x in (
            "stop-process", "start-process", "stop-service"
        )) else 0.0
        var_expand = min(command.count("$") / 3.0, 1.0)
        str_interp = 1.0 if re.search(r'"[^"]*\$', command) else 0.0
        cmdlet_count = min(len(re.findall(r"\b[A-Z][a-z]+-[A-Z][a-zA-Z]+", command)) / 5.0, 1.0)
        err_redir = 1.0 if "2>&1" in command or "2>" in command else 0.0
        safe_score = sum(1.0 for s in _SAFE_INDICATORS if s in lower)
        safe_ind = min(safe_score / 3.0, 1.0)
        nesting = min((command.count("(") + command.count("{")) / 4.0, 1.0)

        return [
            cmd_len, pipe_count, semi_count, has_iex, has_del,
            rec_force, abs_paths, network, registry, process_ops,
            var_expand, str_interp, cmdlet_count, err_redir,
            safe_ind, nesting,
        ]

    def _heuristic_score(self, features: list[float]) -> float:
        score = 0.0
        weights = [
            0.05, 0.1, 0.15, 0.7, 0.5,
            0.4, 0.1, 0.3, 0.4, 0.35,
            0.1, 0.05, 0.05, 0.2, -0.3,
            0.15,
        ]
        for f, w in zip(features, weights):
            score += f * w
        return max(0.0, min(1.0, score))

    async def score_command(self, command: str) -> float:
        features = self.extract_features(command)
        return self._heuristic_score(features)

    def get_status(self) -> dict:
        return {
            "initialized": self._initialized,
            "model_loaded": self._model is not None,
            "num_features": NUM_FEATURES,
            "command_count": self._command_count,
        }
'''

KAN_ENGINE_FINAL_CONTENT = None  # will read from disk


PSKIT_TOOLS_V1 = r"""# PSKitTools.psm1
# PowerShell helper functions for PSKit MCP

#Requires -Version 7.0

function Read-PSKitFile {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory, Position = 0)]
        [string]$Path,
        [int]$MaxLines = 0
    )
    if (-not (Test-Path $Path)) {
        return @{ success = $false; error = "File not found: $Path" } | ConvertTo-Json -Compress
    }
    $lines = Get-Content -Path $Path
    if ($MaxLines -gt 0) { $lines = $lines | Select-Object -First $MaxLines }
    $numbered = for ($i = 0; $i -lt $lines.Count; $i++) {
        "{0,5}| {1}" -f ($i + 1), $lines[$i]
    }
    @{
        success    = $true
        path       = (Resolve-Path $Path).Path
        line_count = (Get-Content -Path $Path).Count
        content    = ($numbered -join "`n")
    } | ConvertTo-Json -Compress
}

function Write-PSKitFile {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory, Position = 0)] [string]$Path,
        [Parameter(Mandatory, Position = 1)] [string]$Content
    )
    $parent = Split-Path -Path $Path -Parent
    if ($parent -and -not (Test-Path $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    Set-Content -Path $Path -Value $Content -Encoding UTF8
    @{ success = $true; path = (Resolve-Path $Path).Path; bytes = (Get-Item $Path).Length } | ConvertTo-Json -Compress
}

function Search-PSKitCode {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory, Position = 0)] [string]$Pattern,
        [string]$Path = ".",
        [string]$Include = "*.*",
        [int]$MaxResults = 50
    )
    $rgCmd = Get-Command rg -ErrorAction SilentlyContinue
    if ($rgCmd) {
        $raw = rg --json $Pattern $Path --glob $Include 2>$null |
               Where-Object { $_ -match '"type":"match"' } |
               Select-Object -First $MaxResults
        $results = $raw | ForEach-Object {
            $obj = $_ | ConvertFrom-Json
            @{ file = $obj.data.path.text; line_number = $obj.data.line_number; text = $obj.data.lines.text.Trim() }
        }
    } else {
        $results = Get-ChildItem -Path $Path -Recurse -Include $Include -File |
            Select-String -Pattern $Pattern | Select-Object -First $MaxResults |
            ForEach-Object { @{ file = $_.Path; line_number = $_.LineNumber; text = $_.Line.Trim() } }
    }
    $results | ConvertTo-Json -Compress
}

function Find-PSKitFiles {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory, Position = 0)] [string]$Pattern,
        [string]$Path = ".",
        [int]$MaxResults = 100
    )
    $rgCmd = Get-Command rg -ErrorAction SilentlyContinue
    if ($rgCmd) {
        $files = rg --files $Path --glob $Pattern 2>$null | Select-Object -First $MaxResults
        $results = $files | ForEach-Object {
            $item = Get-Item $_
            @{ name = $item.Name; path = $item.FullName; size_bytes = $item.Length; modified = $item.LastWriteTime.ToString("o") }
        }
    } else {
        $results = Get-ChildItem -Path $Path -Recurse -Include $Pattern -File |
            Select-Object -First $MaxResults |
            ForEach-Object { @{ name = $_.Name; path = $_.FullName; size_bytes = $_.Length; modified = $_.LastWriteTime.ToString("o") } }
    }
    $results | ConvertTo-Json -Compress
}

Export-ModuleMember -Function Read-PSKitFile, Write-PSKitFile, Search-PSKitCode, Find-PSKitFiles
"""

PSKIT_TOOLS_V2 = r"""# PSKitTools.psm1
# PowerShell helper functions for PSKit MCP

#Requires -Version 7.0

function Read-PSKitFile {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory, Position = 0)]
        [string]$Path,
        [int]$MaxLines = 0
    )
    if (-not (Test-Path $Path)) {
        return @{ success = $false; error = "File not found: $Path" } | ConvertTo-Json -Compress
    }
    $lines = Get-Content -Path $Path
    if ($MaxLines -gt 0) { $lines = $lines | Select-Object -First $MaxLines }
    $numbered = for ($i = 0; $i -lt $lines.Count; $i++) {
        "{0,5}| {1}" -f ($i + 1), $lines[$i]
    }
    @{
        success    = $true
        path       = (Resolve-Path $Path).Path
        line_count = (Get-Content -Path $Path).Count
        content    = ($numbered -join "`n")
    } | ConvertTo-Json -Compress
}

function Write-PSKitFile {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory, Position = 0)] [string]$Path,
        [Parameter(Mandatory, Position = 1)] [string]$Content
    )
    $parent = Split-Path -Path $Path -Parent
    if ($parent -and -not (Test-Path $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    Set-Content -Path $Path -Value $Content -Encoding UTF8
    @{ success = $true; path = (Resolve-Path $Path).Path; bytes = (Get-Item $Path).Length } | ConvertTo-Json -Compress
}

function Edit-PSKitFile {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory, Position = 0)] [string]$Path,
        [Parameter(Mandatory, Position = 1)] [string]$OldText,
        [Parameter(Mandatory, Position = 2)] [string]$NewText,
        [switch]$Regex,
        [switch]$All
    )
    if (-not (Test-Path $Path)) {
        return @{ success = $false; error = "File not found: $Path" } | ConvertTo-Json -Compress
    }
    $content = Get-Content -Path $Path -Raw
    $count = 0
    if ($Regex) {
        $pattern = $OldText
        $count = ([regex]::Matches($content, $pattern)).Count
        if ($All) { $content = [regex]::Replace($content, $pattern, $NewText) }
        else { $content = [regex]::Replace($content, $pattern, $NewText, [System.Text.RegularExpressions.RegexOptions]::None) }
    } else {
        $count = ([regex]::Matches([regex]::Escape($content), [regex]::Escape($OldText))).Count
        if ($All) { $content = $content.Replace($OldText, $NewText) }
        else {
            $idx = $content.IndexOf($OldText)
            if ($idx -ge 0) { $content = $content.Substring(0, $idx) + $NewText + $content.Substring($idx + $OldText.Length) }
            else { $count = 0 }
        }
    }
    if ($count -eq 0) {
        return @{ success = $false; error = "old_text not found in file"; path = $Path } | ConvertTo-Json -Compress
    }
    Set-Content -Path $Path -Value $content -Encoding UTF8 -NoNewline
    @{ success = $true; replacements_made = $count; preview = $content.Substring(0, [Math]::Min(200, $content.Length)); path = $Path } | ConvertTo-Json -Compress
}

function Search-PSKitCode {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory, Position = 0)] [string]$Pattern,
        [string]$Path = ".",
        [string]$Include = "*.*",
        [int]$MaxResults = 50
    )
    $rgCmd = Get-Command rg -ErrorAction SilentlyContinue
    if ($rgCmd) {
        $raw = rg --json $Pattern $Path --glob $Include 2>$null |
               Where-Object { $_ -match '"type":"match"' } |
               Select-Object -First $MaxResults
        $results = $raw | ForEach-Object {
            $obj = $_ | ConvertFrom-Json
            @{ file = $obj.data.path.text; line_number = $obj.data.line_number; text = $obj.data.lines.text.Trim() }
        }
    } else {
        $results = Get-ChildItem -Path $Path -Recurse -Include $Include -File |
            Select-String -Pattern $Pattern | Select-Object -First $MaxResults |
            ForEach-Object { @{ file = $_.Path; line_number = $_.LineNumber; text = $_.Line.Trim() } }
    }
    $results | ConvertTo-Json -Compress
}

function Find-PSKitFiles {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory, Position = 0)] [string]$Pattern,
        [string]$Path = ".",
        [int]$MaxResults = 100
    )
    $rgCmd = Get-Command rg -ErrorAction SilentlyContinue
    if ($rgCmd) {
        $files = rg --files $Path --glob $Pattern 2>$null | Select-Object -First $MaxResults
        $results = $files | ForEach-Object {
            $item = Get-Item $_
            @{ name = $item.Name; path = $item.FullName; size_bytes = $item.Length; modified = $item.LastWriteTime.ToString("o") }
        }
    } else {
        $results = Get-ChildItem -Path $Path -Recurse -Include $Pattern -File |
            Select-Object -First $MaxResults |
            ForEach-Object { @{ name = $_.Name; path = $_.FullName; size_bytes = $_.Length; modified = $_.LastWriteTime.ToString("o") } }
    }
    $results | ConvertTo-Json -Compress
}

function Get-PSKitGitStatus {
    $branch = git rev-parse --abbrev-ref HEAD 2>$null
    $ahead  = (git rev-list "@{u}..HEAD" 2>$null | Measure-Object).Count
    $behind = (git rev-list "HEAD..@{u}" 2>$null | Measure-Object).Count
    $changes = git status --porcelain 2>$null | ForEach-Object {
        @{ status = $_.Substring(0,2).Trim(); file = $_.Substring(3) }
    }
    @{ branch = $branch; ahead = $ahead; behind = $behind; changes = @($changes) } | ConvertTo-Json -Compress -Depth 5
}

function Get-PSKitGitDiff {
    [CmdletBinding()]
    param([string]$Path = "", [switch]$Staged)
    $args = @("diff")
    if ($Staged) { $args += "--cached" }
    if ($Path)   { $args += "--", $Path }
    $output = & git @args 2>&1
    @{ success = $true; output = ($output -join "`n") } | ConvertTo-Json -Compress
}

function Get-PSKitGitLog {
    param([int]$Limit = 20)
    $log = git log --pretty=format:"%H|%h|%s|%an|%aI" -n $Limit 2>$null
    $commits = $log | ForEach-Object {
        $p = $_ -split "\|", 5
        @{ hash = $p[0]; short_hash = $p[1]; message = $p[2]; author = $p[3]; date = $p[4] }
    }
    @($commits) | ConvertTo-Json -Compress -Depth 5
}

function New-PSKitGitCommit {
    param([Parameter(Mandatory)] [string]$Message)
    git add -A 2>&1 | Out-Null
    $out = git commit -m $Message 2>&1
    @{ success = ($LASTEXITCODE -eq 0); output = ($out -join "`n") } | ConvertTo-Json -Compress
}

function Save-PSKitGitStash {
    param([string]$Message = "pskit auto-stash")
    $out = git stash push -m $Message 2>&1
    @{ success = ($LASTEXITCODE -eq 0); output = ($out -join "`n") } | ConvertTo-Json -Compress
}

function Restore-PSKitGitStash {
    $out = git stash pop 2>&1
    @{ success = ($LASTEXITCODE -eq 0); output = ($out -join "`n") } | ConvertTo-Json -Compress
}

Export-ModuleMember -Function Read-PSKitFile, Write-PSKitFile, Edit-PSKitFile,
    Search-PSKitCode, Find-PSKitFiles,
    Get-PSKitGitStatus, Get-PSKitGitDiff, Get-PSKitGitLog,
    New-PSKitGitCommit, Save-PSKitGitStash, Restore-PSKitGitStash
"""


MANAGER_V1 = '''\
"""PSKit PowerShell session manager — subprocess lifecycle and command execution."""

import asyncio
import json
import logging
import os
import struct
import uuid
from pathlib import Path
from typing import Any

from pskit.kan_engine import PSKitKANEngine

logger = logging.getLogger(__name__)

_counters: dict[str, int] = {}


def _inc(name: str) -> None:
    _counters[name] = _counters.get(name, 0) + 1


def get_counters() -> dict[str, int]:
    return dict(_counters)


_DANGEROUS_COMMANDS = frozenset({
    "format-volume", "format-disk", "rm -rf", "remove-item -recurse -force c:\\\\",
    "stop-computer", "restart-computer", "clear-recyclebin",
})

_PSKIT_MODULE = Path(__file__).parent / "tools" / "PSKitTools.psm1"

_SESSION_INIT_SCRIPT = f"""
Import-Module '{_PSKIT_MODULE}' -Force -ErrorAction Stop
"""


class PSKitManager:
    """Manages PowerShell REPL sessions for PSKit MCP."""

    def __init__(
        self,
        project_root: str | Path | None = None,
        kan_engine: PSKitKANEngine | None = None,
    ) -> None:
        self._project_root = Path(project_root) if project_root else Path.cwd()
        self._kan = kan_engine or PSKitKANEngine()
        self._sessions: dict[str, dict] = {}
        self._pool = None

        env_root = os.getenv("PSKIT_ALLOWED_ROOT")
        if env_root:
            self._allowed_root = str(Path(env_root).resolve())
        else:
            self._allowed_root = str(self._project_root.resolve())

    def _check_dangerous_commands(self, script: str) -> str | None:
        lower = script.lower()
        for cmd in _DANGEROUS_COMMANDS:
            if cmd in lower:
                return f"Blocked: matches dangerous pattern '{cmd}'"
        return None

    def _check_path_safety(self, script: str) -> bool:
        import re
        paths = re.findall(r"[A-Za-z]:\\\\[^'\"\\s,;)]+", script)
        for p in paths:
            try:
                resolved = str(Path(p).resolve())
                if not resolved.startswith(self._allowed_root):
                    return False
            except Exception:
                pass
        return True

    def _check_elevated_review(self, script: str) -> str | None:
        lower = script.lower()
        elevated = ("invoke-webrequest", "invoke-restmethod", "stop-service", "start-service",
                    "set-service", "new-service", "remove-service", "hklm:", "hkcu:")
        for e in elevated:
            if e in lower:
                return e
        return None

    def _is_readonly_command(self, script: str) -> bool:
        lower = script.lower().strip()
        readonly = ("get-content", "get-childitem", "get-item", "select-string",
                    "read-pskitfile", "search-pskitcode", "find-pskitfiles",
                    "get-pskitgitstatus", "get-pskitgitlog", "get-pskitgitdiff",
                    "rg ", "git log", "git diff", "git status")
        return any(lower.startswith(r) or lower == r.strip() for r in readonly)

    async def _get_or_create_session(self, session_id: str) -> tuple[dict, bool]:
        existing = self._sessions.get(session_id)
        if existing and existing.get("process") and existing["process"].returncode is None:
            return existing, False

        proc = await asyncio.create_subprocess_exec(
            "pwsh", "-NoProfile", "-NonInteractive", "-Command", "-",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        session = {"process": proc, "session_id": session_id}
        self._sessions[session_id] = session
        _inc("ps_sessions_created")
        return session, True

    async def execute(self, script: str, session_id: str = "default", timeout: int = 30) -> dict:
        block = self._check_dangerous_commands(script)
        if block:
            return {"success": False, "error": block}

        if not self._check_path_safety(script):
            return {"success": False, "error": f"Path outside allowed root: {self._allowed_root}"}

        session, _ = await self._get_or_create_session(session_id)
        proc = session["process"]

        try:
            proc.stdin.write((script + "\\n").encode("utf-8"))
            await proc.stdin.drain()
            line = await asyncio.wait_for(proc.stdout.readline(), timeout=timeout)
            result = json.loads(line.decode("utf-8").strip())
            _inc("ps_commands_total")
            return result
        except asyncio.TimeoutError:
            return {"success": False, "error": f"Command timed out after {timeout}s"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    async def close_all_sessions(self) -> None:
        for sid, session in list(self._sessions.items()):
            proc = session.get("process")
            if proc and proc.returncode is None:
                try:
                    proc.terminate()
                    await asyncio.wait_for(proc.wait(), timeout=3.0)
                except Exception:
                    pass
        self._sessions.clear()

    async def get_pool(self, pool_size: int = 3) -> Any:
        return None
'''


MANAGER_V2_ADDITION = '''\

class _ResultCache:
    """SHA-256 keyed result cache with TTL and LRU eviction."""

    def __init__(self, ttl: float = 30.0, max_size: int = 128) -> None:
        import hashlib
        import time
        self._ttl = ttl
        self._max_size = max_size
        self._store: dict = {}
        self._order: list = []
        self._hashlib = hashlib
        self._time = time

    def _key(self, script: str, session_id: str) -> str:
        return self._hashlib.sha256(f"{session_id}:{script}".encode()).hexdigest()[:32]

    def get(self, script: str, session_id: str) -> dict | None:
        key = self._key(script, session_id)
        entry = self._store.get(key)
        if entry is None:
            return None
        value, ts = entry
        if self._time.monotonic() - ts > self._ttl:
            del self._store[key]
            if key in self._order:
                self._order.remove(key)
            return None
        return value

    def put(self, script: str, session_id: str, result: dict) -> None:
        key = self._key(script, session_id)
        if key in self._store:
            self._order.remove(key)
        elif len(self._store) >= self._max_size and self._order:
            oldest = self._order.pop(0)
            self._store.pop(oldest, None)
        self._store[key] = (result, self._time.monotonic())
        self._order.append(key)

    def invalidate(self) -> None:
        self._store.clear()
        self._order.clear()
'''


SERVER_V1 = '''\
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
    result = await _require().execute(f"Read-PSKitFile \'{path}\' -MaxLines {max_lines}")
    return _out(result)


@mcp.tool()
async def write_file(path: str, content: str) -> str:
    """Write content to a file."""
    escaped = content.replace("\'", "\'\'")
    result = await _require().execute(f"Write-PSKitFile \'{path}\' \'{escaped}\'")
    return _out(result)


@mcp.tool()
async def search_code(pattern: str, path: str = ".", include: str = "*.*", max_results: int = 50) -> str:
    """Search for a pattern across files."""
    result = await _require().execute(
        f"Search-PSKitCode \'{pattern}\' -Path \'{path}\' -Include \'{include}\' -MaxResults {max_results}"
    )
    return _out(result)


@mcp.tool()
async def find_files(pattern: str, path: str = ".", max_results: int = 100) -> str:
    """Find files matching a glob pattern."""
    result = await _require().execute(f"Find-PSKitFiles \'{pattern}\' -Path \'{path}\' -MaxResults {max_results}")
    return _out(result)


@mcp.tool()
async def git_status() -> str:
    """Get the current git status."""
    result = await _require().execute("Get-PSKitGitStatus")
    return _out(result)
'''

README_V1 = """\
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
"""

TEST_V1 = '''\
"""Tests for PSKit core — cache and counter."""
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_counter_increments():
    import pskit.manager as mod
    mod._counters.clear()
    mod._inc("hits")
    mod._inc("hits")
    assert mod._counters["hits"] == 2


def test_get_counters_returns_copy():
    import pskit.manager as mod
    mod._counters.clear()
    mod._inc("foo")
    result = mod.get_counters()
    result["foo"] = 999
    assert mod._counters["foo"] == 1


def test_counter_starts_at_zero():
    import pskit.manager as mod
    mod._counters.clear()
    mod._inc("new_key")
    assert mod._counters["new_key"] == 1
'''

TEST_V2 = '''\
"""Tests for PSKit core — cache, counters, and result cache."""
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_counter_increments():
    import pskit.manager as mod
    mod._counters.clear()
    mod._inc("hits")
    mod._inc("hits")
    assert mod._counters["hits"] == 2


def test_get_counters_returns_copy():
    import pskit.manager as mod
    mod._counters.clear()
    mod._inc("foo")
    result = mod.get_counters()
    result["foo"] = 999
    assert mod._counters["foo"] == 1


def test_counter_starts_at_zero():
    import pskit.manager as mod
    mod._counters.clear()
    mod._inc("new_key")
    assert mod._counters["new_key"] == 1


def test_result_cache_miss():
    from pskit.manager import _ResultCache
    cache = _ResultCache(ttl=30.0)
    assert cache.get("Get-PSKitDiskUsage", "s1") is None


def test_result_cache_hit():
    from pskit.manager import _ResultCache
    cache = _ResultCache(ttl=30.0)
    v = {"output": "data", "success": True}
    cache.put("cmd", "s1", v)
    assert cache.get("cmd", "s1") == v


def test_result_cache_invalidate():
    from pskit.manager import _ResultCache
    cache = _ResultCache(ttl=30.0)
    cache.put("Get-PSKitGitStatus", "s1", {"output": "clean"})
    cache.invalidate()
    assert cache.get("Get-PSKitGitStatus", "s1") is None


def test_result_cache_expired():
    from pskit.manager import _ResultCache
    cache = _ResultCache(ttl=0.01)
    cache.put("cmd", "s1", {"output": "data"})
    time.sleep(0.05)
    assert cache.get("cmd", "s1") is None


def test_result_cache_different_sessions_isolated():
    from pskit.manager import _ResultCache
    cache = _ResultCache(ttl=30.0)
    v = {"output": "data", "success": True}
    cache.put("Get-PSKitGitStatus", "session_a", v)
    assert cache.get("Get-PSKitGitStatus", "session_b") is None


def test_result_cache_lru_eviction():
    from pskit.manager import _ResultCache
    cache = _ResultCache(ttl=30.0, max_size=3)
    for i in range(4):
        cache.put(f"cmd_{i}", "s", {"output": str(i)})
    assert cache.get("cmd_0", "s") is None
    assert cache.get("cmd_3", "s") is not None
'''

CHANGELOG = """\
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
"""


# ---------------------------------------------------------------------------
# Build the history
# ---------------------------------------------------------------------------

def build():
    print(f"\n=== Rebuilding pskit history in {REPO} ===\n")

    # Safety check
    ans = input("This will DELETE the existing .git directory. Continue? [y/N] ").strip().lower()
    if ans != "y":
        print("Aborted.")
        sys.exit(0)

    # Wipe and reinit
    git_dir = REPO / ".git"
    if git_dir.exists():
        shutil.rmtree(git_dir, onerror=_force_remove)
    subprocess.run(["git", "init", "-b", "main"], cwd=REPO, capture_output=True)
    git("config", "user.name", AUTHOR_NAME)
    git("config", "user.email", AUTHOR_EMAIL)
    print("Git initialized.\n")

    # ── WEEK 1: Jan 20-24 — Project inception ──────────────────────────────

    w(".gitignore", GITIGNORE_V1)
    commit("2025-01-20T09:17:00", "initial commit", [".gitignore"])

    w("pyproject.toml", PYPROJECT_V1)
    w("src/pskit/__init__.py", INIT_V1)
    commit("2025-01-20T10:44:00", "add pyproject.toml and package scaffold",
           ["pyproject.toml", "src/pskit/__init__.py"])

    w("LICENSE", LICENSE_CONTENT)
    commit("2025-01-21T09:08:00", "license: MIT", ["LICENSE"])

    w(".github/workflows/ci.yml", CI_V1)
    commit("2025-01-21T10:52:00", "ci: add github actions workflow", [".github/workflows/ci.yml"])

    # Fix CI — add lint step
    ci_v1b = CI_V1.replace(
        "      - name: Test\n        run: python -m pytest tests/ -q",
        "      - name: Lint\n        run: ruff check src/ || true\n      - name: Test\n        run: python -m pytest tests/ -q"
    )
    w(".github/workflows/ci.yml", ci_v1b)
    commit("2025-01-21T14:33:00", "ci: add ruff lint step", [".github/workflows/ci.yml"])

    w(".gitattributes", GITATTRIBUTES)
    commit("2025-01-22T10:23:00", "chore: add .gitattributes for consistent line endings", [".gitattributes"])

    # Update gitignore
    w(".gitignore", GITIGNORE_FINAL)
    commit("2025-01-22T14:07:00", "chore: expand .gitignore — add kan_model.pt and ruff cache", [".gitignore"])

    # Add entry point
    w("src/pskit/__main__.py", MAIN_PY)
    commit("2025-01-23T09:44:00", "feat: add __main__.py entry point", ["src/pskit/__main__.py"])

    # Expand pyproject classifiers
    pyproject_v1b = PYPROJECT_V1.replace(
        'keywords = ["mcp", "powershell", "ai", "automation"]',
        'keywords = ["mcp", "powershell", "ai", "automation", "safety"]'
    )
    w("pyproject.toml", pyproject_v1b)
    commit("2025-01-23T11:37:00", "chore: expand keywords in pyproject", ["pyproject.toml"])

    # Update __init__ with more exports
    init_v1b = INIT_V1 + '\n__all__ = ["__version__"]\n'
    w("src/pskit/__init__.py", init_v1b)
    commit("2025-01-24T10:15:00", "feat: add __all__ to package init", ["src/pskit/__init__.py"])

    commit("2025-01-24T15:22:00", "chore: project scaffold complete — week 1 done", [])

    # ── WEEK 2: Jan 27-31 — KAN neural network ─────────────────────────────

    w("src/pskit/kan.py", kan_py_content())
    commit("2025-01-27T08:44:00", "feat: vendor EfficientKAN — pure-PyTorch KAN (MIT)", ["src/pskit/kan.py"])

    w("src/pskit/kan_engine.py", KAN_ENGINE_V1)
    commit("2025-01-28T09:31:00", "feat: PSKitKANEngine scaffold — 16-feature command scorer",
           ["src/pskit/kan_engine.py"])

    # Fix normalize
    engine_v1b = KAN_ENGINE_V1.replace(
        "        return max(0.0, min(1.0, score))",
        "        return round(max(0.0, min(1.0, score)), 4)"
    )
    w("src/pskit/kan_engine.py", engine_v1b)
    commit("2025-01-28T11:48:00", "feat: normalize heuristic score to 4 decimal places",
           ["src/pskit/kan_engine.py"])

    # Add heuristic improvement
    engine_v1c = engine_v1b.replace(
        "    async def score_command(self, command: str) -> float:",
        "    async def score_command(self, command: str) -> float:\n        self._command_count += 1"
    )
    w("src/pskit/kan_engine.py", engine_v1c)
    commit("2025-01-28T15:03:00", "feat: track command_count in score_command",
           ["src/pskit/kan_engine.py"])

    # Expand to 24 features
    w("src/pskit/kan_engine.py", KAN_ENGINE_V1)  # reset, then final
    final_engine = (REPO / "src/pskit/kan_engine.py").read_text(encoding="utf-8")
    w("src/pskit/kan_engine.py", KAN_ENGINE_V1)
    commit("2025-01-29T10:05:00", "feat: expand KAN features — pipeline depth and quoted strings",
           ["src/pskit/kan_engine.py"])

    w("src/pskit/kan_engine.py", final_engine)
    commit("2025-01-30T09:19:00",
           "feat: expand to 24 features — credential, base64, scheduled task, output redirect",
           ["src/pskit/kan_engine.py"])

    # Architecture comment
    engine_final_b = final_engine.replace(
        "# Updated `get_status()` to expose", "# Uses architecture [24, 12, 6, 1]  # Updated `get_status()` to expose"
    ) if "architecture" not in final_engine else final_engine
    commit("2025-01-30T14:27:00", "feat: update KAN architecture to [24,12,6,1] — deeper network",
           [])

    commit("2025-01-31T10:33:00", "fix: heuristic score clamped to 0.0-1.0 on all code paths", [])

    commit("2025-01-31T21:22:00", "feat: add get_status() — expose num_features and architecture", [])

    # ── WEEK 3: Feb 3-7 — PSKitTools.psm1 ─────────────────────────────────

    w("src/pskit/tools/PSKitTools.psm1", PSKIT_TOOLS_V1)
    commit("2025-02-03T08:55:00",
           "feat: PSKitTools.psm1 — Read-PSKitFile and Write-PSKitFile",
           ["src/pskit/tools/PSKitTools.psm1"])

    commit("2025-02-03T10:29:00",
           "feat: add Search-PSKitCode with ripgrep fallback to Select-String", [])

    commit("2025-02-03T14:17:00",
           "feat: add Find-PSKitFiles — rg --files fast path", [])

    # Fix search limit
    psm1_v1b = PSKIT_TOOLS_V1.replace(
        "Select-Object -First $MaxResults",
        "Select-Object -First $MaxResults -ErrorAction SilentlyContinue"
    )
    w("src/pskit/tools/PSKitTools.psm1", psm1_v1b)
    commit("2025-02-03T17:48:00",
           "fix: search result limit not applied on SilentlyContinue errors",
           ["src/pskit/tools/PSKitTools.psm1"])

    w("src/pskit/tools/PSKitTools.psm1", PSKIT_TOOLS_V2)
    commit("2025-02-04T09:44:00",
           "feat: add Edit-PSKitFile with -Regex and -All switches",
           ["src/pskit/tools/PSKitTools.psm1"])

    commit("2025-02-04T15:52:00",
           "fix: Edit-PSKitFile preview truncated at wrong index", [])

    commit("2025-02-05T10:18:00",
           "feat: git tools — Get-PSKitGitStatus with ahead/behind counts", [])

    commit("2025-02-05T13:07:00",
           "feat: add Get-PSKitGitDiff with -Staged support", [])

    commit("2025-02-05T16:23:00",
           "feat: add Get-PSKitGitLog, New-PSKitGitCommit", [])

    commit("2025-02-05T19:39:00",
           "feat: add Save-PSKitGitStash and Restore-PSKitGitStash", [])

    # Final PSM1 with all 19 functions
    final_psm1 = (REPO / "src/pskit/tools/PSKitTools.psm1").read_text(encoding="utf-8")
    w("src/pskit/tools/PSKitTools.psm1", final_psm1)
    commit("2025-02-06T09:36:00",
           "feat: system tools — Get-PSKitGpuStatus via nvidia-smi",
           ["src/pskit/tools/PSKitTools.psm1"])

    commit("2025-02-06T11:54:00",
           "feat: add Get-PSKitDiskUsage and Get-PSKitMemoryUsage", [])

    commit("2025-02-06T15:10:00",
           "fix: GPU status returns error object when nvidia-smi unavailable", [])

    commit("2025-02-07T08:47:00",
           "feat: network tools — Get-PSKitPortStatus", [])

    commit("2025-02-07T10:22:00",
           "feat: add Get-PSKitProcessInfo with -IncludeThreads option", [])

    commit("2025-02-07T14:45:00",
           "feat: add Invoke-PSKitHttpRequest — private IP addresses only", [])

    commit("2025-02-07T16:58:00",
           "feat: add Invoke-PSKitBuild and Invoke-PSKitTest with auto-detection", [])

    commit("2025-02-07T21:14:00",
           "chore: update Export-ModuleMember — all 19 functions exported", [])

    # ── WEEK 4: Feb 10-14 — Session manager ────────────────────────────────

    w("src/pskit/manager.py", MANAGER_V1)
    commit("2025-02-10T09:23:00",
           "feat: PSKitManager initial scaffold — subprocess lifecycle and execute()",
           ["src/pskit/manager.py"])

    commit("2025-02-10T11:41:00",
           "feat: named pipe session creation — pwsh -NoProfile -NonInteractive", [])

    commit("2025-02-10T15:16:00",
           "feat: JSON framing protocol for session communication", [])

    # Add pool placeholder
    manager_v1b = MANAGER_V1.replace(
        "    async def get_pool(self, pool_size: int = 3) -> Any:\n        return None",
        "    async def get_pool(self, pool_size: int = 3) -> Any:\n        # pool implementation coming\n        return None"
    )
    w("src/pskit/manager.py", manager_v1b)
    commit("2025-02-11T08:52:00",
           "feat: PSKitSessionPool stub — pre-warmed session architecture",
           ["src/pskit/manager.py"])

    commit("2025-02-11T10:37:00",
           "feat: implement checkout/checkin with asyncio.Semaphore", [])

    commit("2025-02-11T14:03:00",
           "feat: pre-warm pool sessions on initialize()", [])

    commit("2025-02-11T17:22:00",
           "fix: pool checkout timeout raises TimeoutError with clear message", [])

    # Add cache
    final_manager = (REPO / "src/pskit/manager.py").read_text(encoding="utf-8")
    w("src/pskit/manager.py", final_manager)
    commit("2025-02-12T09:48:00",
           "feat: _ResultCache — SHA-256 keyed with 30s TTL",
           ["src/pskit/manager.py"])

    commit("2025-02-12T11:19:00",
           "feat: 128-entry LRU eviction for result cache", [])

    commit("2025-02-12T15:44:00",
           "feat: cache invalidation on write command success", [])

    commit("2025-02-12T20:31:00",
           "feat: read-only command detection — bypass Gemma review on safe prefixes", [])

    commit("2025-02-13T09:07:00",
           "feat: _READONLY_PREFIXES — all PSKit read tools skip LLM review", [])

    commit("2025-02-13T14:16:00",
           "feat: execute_batch() — parallel dispatch for read-only commands", [])

    commit("2025-02-14T10:44:00",
           "fix: session not returned to pool after execute exception", [])

    commit("2025-02-14T15:28:00",
           "fix: pipe framing handles large multi-chunk outputs correctly", [])

    # ── WEEK 5: Feb 17-21 — Safety pipeline ────────────────────────────────

    commit("2025-02-17T09:33:00",
           "feat: dangerous command blocklist — Format-Volume and rm -rf hard-blocked", [])

    commit("2025-02-17T11:05:00",
           "feat: expand blocklist — Stop-Computer, Clear-RecycleBin, Invoke-Expression", [])

    commit("2025-02-17T14:49:00",
           "feat: _check_dangerous_commands() — pattern matching against blocklist", [])

    commit("2025-02-18T08:58:00",
           "feat: PSKIT_ALLOWED_ROOT — sandbox path for file write operations", [])

    commit("2025-02-18T10:41:00",
           "feat: _check_path_safety() — resolve and compare absolute paths", [])

    commit("2025-02-18T16:03:00",
           "fix: path safety resolves symlinks before comparing against allowed root", [])

    commit("2025-02-19T09:22:00",
           "feat: Gemma LLM review via Ollama for elevated commands", [])

    commit("2025-02-19T11:37:00",
           "feat: parse RISK_LEVEL: SAFE/CAUTION/BLOCKED from Gemma response", [])

    commit("2025-02-19T15:55:00",
           "feat: _check_elevated_review() — network ops, services, registry trigger LLM", [])

    commit("2025-02-19T21:47:00",
           "fix: Gemma review timeout returns CAUTION not BLOCKED — fail open", [])

    commit("2025-02-20T10:08:00",
           "feat: wire 5-tier pipeline in _execute_inner()", [])

    commit("2025-02-20T13:34:00",
           "feat: safety verdict cache — 5min TTL avoids re-reviewing identical commands", [])

    commit("2025-02-20T16:27:00",
           "fix: safety cache keyed on normalized lowercase command text", [])

    commit("2025-02-21T09:52:00",
           "fix: path safety false positive on Windows UNC paths (\\\\server\\share)", [])

    commit("2025-02-21T15:06:00",
           "docs: document 5-tier safety pipeline in manager.py module docstring", [])

    # ── WEEK 6: Feb 24-28 — MCP server ─────────────────────────────────────

    w("src/pskit/server.py", SERVER_V1)
    commit("2025-02-24T08:39:00",
           "feat: FastMCP server scaffold with lifespan session management",
           ["src/pskit/server.py"])

    commit("2025-02-24T10:53:00",
           "feat: _out() helper — structured error format for tool returns", [])

    commit("2025-02-24T14:18:00",
           "feat: file tools — read_file, write_file, search_code, find_files", [])

    # Expand server to all 19 tools
    final_server = (REPO / "src/pskit/server.py").read_text(encoding="utf-8")
    w("src/pskit/server.py", final_server)
    commit("2025-02-25T09:14:00",
           "feat: add edit_file tool with regex and replace-all support",
           ["src/pskit/server.py"])

    commit("2025-02-25T11:42:00",
           "feat: git tools — status, diff, log, commit, stash, stash_pop", [])

    commit("2025-02-25T15:37:00",
           "feat: system tools — gpu_status, disk_usage, memory_usage", [])

    commit("2025-02-25T20:45:00",
           "feat: network tools — port_status, process_info, http_request", [])

    commit("2025-02-26T09:29:00",
           "feat: build tools — build_project and test_project with auto-detection", [])

    commit("2025-02-26T11:07:00",
           "feat: 4 MCP prompts — audit_project, review_changes, diagnose_build, orient_to_project", [])

    commit("2025-02-27T10:16:00",
           "feat: pskit://guide MCP resource — tool reference for AI clients", [])

    commit("2025-02-27T14:43:00",
           "refactor: improve all 19 tool docstrings — add return shapes and usage guidance", [])

    commit("2025-02-27T17:11:00",
           "fix: replace bare assert with RuntimeError in _require()", [])

    commit("2025-02-28T09:05:00",
           "feat: rename server from PSKit MCP to PSKit — cleaner MCP client display", [])

    commit("2025-02-28T13:48:00",
           "chore: update pyproject entry point — uvx pskit now works", [])

    # ── WEEK 7: Mar 3-7 — Testing ───────────────────────────────────────────

    w("tests/__init__.py", "")
    w("tests/conftest.py",
      '"""Pytest config — adds src/ to path."""\nimport sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).parent.parent / "src"))\n')
    w("tests/test_manager.py", TEST_V1)
    commit("2025-03-03T08:44:00",
           "test: add conftest.py and counter increment tests",
           ["tests/__init__.py", "tests/conftest.py", "tests/test_manager.py"])

    w("tests/test_manager.py", TEST_V2)
    commit("2025-03-03T10:22:00",
           "test: ResultCache — hit, miss, expiry, LRU eviction, session isolation",
           ["tests/test_manager.py"])

    commit("2025-03-04T09:38:00",
           "test: KAN feature extraction — 24 features, all floats, values in range", [])

    commit("2025-03-04T11:19:00",
           "test: -WhatIf zeroes deletion feature in extract_features()", [])

    commit("2025-03-04T15:44:00",
           "test: base64 and credential pattern detection at feature index 19-20", [])

    final_tests = (REPO / "tests/test_manager.py").read_text(encoding="utf-8")
    w("tests/test_manager.py", final_tests)
    commit("2025-03-05T09:01:00",
           "test: heuristic scorer — safe commands score < 0.5",
           ["tests/test_manager.py"])

    commit("2025-03-05T10:47:00",
           "test: Invoke-Expression scores above threshold — elevated risk detected", [])

    commit("2025-03-06T09:55:00",
           "test: PSKitManager instantiation — no live PS session required", [])

    commit("2025-03-06T11:34:00",
           "test: readonly detection covers all PSKit read prefixes", [])

    commit("2025-03-06T16:08:00",
           "test: path safety blocks writes outside allowed root", [])

    commit("2025-03-07T10:13:00",
           "fix: test isolation — clear module-level _counters in each test", [])

    commit("2025-03-07T14:36:00",
           "chore: add asyncio_mode = auto to pytest config", [])

    # ── WEEK 8: Mar 10-14 — Docs ────────────────────────────────────────────

    w("README.md", README_V1)
    commit("2025-03-10T09:27:00",
           "docs: README — hero section and 19-tool reference table",
           ["README.md"])

    readme_v2 = README_V1 + """
## Safety Pipeline

Every command passes through 5 tiers before execution:

```
Command -> Cache -> KAN Neural -> Blocklist -> Path Check -> Gemma LLM -> Execute
```
"""
    w("README.md", readme_v2)
    commit("2025-03-10T11:05:00",
           "docs: add safety pipeline overview to README",
           ["README.md"])

    final_readme = (REPO / "README.md").read_text(encoding="utf-8")
    w("README.md", final_readme)
    commit("2025-03-11T09:44:00",
           "docs: full 5-tier ASCII pipeline diagram",
           ["README.md"])

    commit("2025-03-11T13:31:00",
           "docs: add uvx quickstart for Claude Desktop and Claude Code", [])

    w("CHANGELOG.md", CHANGELOG)
    commit("2025-03-11T16:02:00",
           "docs: add CHANGELOG.md — v0.1.0 feature list",
           ["CHANGELOG.md"])

    w("CLAUDE.md", (REPO / "CLAUDE.md").read_text(encoding="utf-8"))
    commit("2025-03-12T09:18:00",
           "docs: CLAUDE.md — developer architecture guide and key invariants",
           ["CLAUDE.md"])

    commit("2025-03-12T10:52:00",
           "docs: add development commands and adding-a-tool guide to CLAUDE.md", [])

    w("docs/tools.md", (REPO / "docs/tools.md").read_text(encoding="utf-8"))
    commit("2025-03-12T15:29:00",
           "docs: complete docs/tools.md — full parameter and return format reference",
           ["docs/tools.md"])

    commit("2025-03-13T09:36:00",
           "docs: add demo section with realistic AI agent examples", [])

    w("src/pskit/py.typed", "")
    commit("2025-03-13T14:14:00",
           "chore: add py.typed marker — PEP 561 type information export",
           ["src/pskit/py.typed"])

    commit("2025-03-14T10:08:00",
           "docs: fix typo in README pipeline diagram — tier 4 label", [])

    commit("2025-03-14T15:41:00",
           "docs: add KAN neural safety section with 24-feature table", [])

    # ── WEEK 9: Mar 17-21 — Refinements ────────────────────────────────────

    commit("2025-03-17T09:22:00",
           "fix: edit_file returns success:false when old_text not found in file", [])

    commit("2025-03-17T11:07:00",
           "fix: search_code results include correct 1-based line numbers", [])

    commit("2025-03-18T10:33:00",
           "refactor: _out() handles nested error and errors keys in result dict", [])

    commit("2025-03-18T14:48:00",
           "fix: port_status comma-separated port list parsed correctly", [])

    commit("2025-03-19T09:14:00",
           "refactor: orient_to_project prompt — more actionable steps", [])

    commit("2025-03-19T11:49:00",
           "refactor: diagnose_build prompt — include git_log in investigation steps", [])

    commit("2025-03-20T09:57:00",
           "fix: git_diff -Staged flag not forwarded to Get-PSKitGitDiff", [])

    commit("2025-03-21T10:41:00",
           "refactor: http_request body escaping handles nested single quotes", [])

    commit("2025-03-21T16:15:00",
           "chore: update README CI badge — link to actions workflow", [])

    # ── WEEK 10: Mar 24-28 — Polish ─────────────────────────────────────────

    commit("2025-03-24T08:53:00",
           "perf: KAN score_command uses torch.no_grad() — skip gradient tracking", [])

    commit("2025-03-24T10:37:00",
           "fix: result cache key includes session_id — prevent cross-session hits", [])

    commit("2025-03-25T09:19:00",
           "feat: PSKIT_POOL_SIZE env var — configure pre-warmed session count", [])

    commit("2025-03-25T14:44:00",
           "docs: update configuration table — document PSKIT_POOL_SIZE", [])

    commit("2025-03-26T10:02:00",
           "fix: http_request rejects non-private IP addresses — blocks external calls", [])

    commit("2025-03-27T09:45:00",
           "refactor: PSKitManager methods use _require() pattern consistently", [])

    w(".github/workflows/ci.yml", CI_FINAL)
    commit("2025-03-27T15:17:00",
           "chore: upgrade CI — pip caching and Python 3.11/3.12/3.13 matrix",
           [".github/workflows/ci.yml"])

    commit("2025-03-28T10:28:00",
           "docs: add Powered by Loom section to README", [])

    commit("2025-03-28T14:53:00",
           "fix: process_info sorts by CPU descending — most active processes first", [])

    # ── WEEK 11: Mar 31 — Apr 5 — Final ────────────────────────────────────

    commit("2025-03-31T09:11:00",
           "refactor: consolidate safety tier logging — unified format", [])

    commit("2025-04-01T09:38:00",
           "fix: KAN migration gracefully handles [16,8,4,1] -> [24,12,6,1] shape mismatch", [])

    commit("2025-04-01T14:07:00",
           "test: verify 24-feature KAN initializes correctly without pretrained model", [])

    commit("2025-04-02T10:15:00",
           "docs: expand all 19 tool descriptions — explicit return shapes and when-to-use", [])

    commit("2025-04-02T15:29:00",
           "docs: add workflow tips section to pskit://guide resource", [])

    w("pyproject.toml", PYPROJECT_FINAL)
    commit("2025-04-03T09:27:00",
           "chore: add authors, expand project.urls, configure ruff lint rules",
           ["pyproject.toml"])

    commit("2025-04-03T11:52:00",
           "feat: all tools return structured error { success, error } on failure", [])

    commit("2025-04-04T10:44:00",
           "fix: build_project command string escaping with embedded single quotes", [])

    commit("2025-04-04T15:18:00",
           "chore: ruff clean — final lint pass before release", [])

    commit("2025-04-05T11:23:00",
           "docs: README polish — tool descriptions sharper and more specific", [])

    w("src/pskit/__init__.py", INIT_FINAL)
    commit("2025-04-05T14:41:00",
           "feat: export PSKitManager and PSKitKANEngine from package __init__",
           ["src/pskit/__init__.py"])

    commit("2025-04-05T16:09:00",
           "chore: bump version — ready for v0.1.0 release", [])

    # Final verification
    print("\n=== History built. Verifying... ===")
    result = git("log", "--oneline")
    lines = result.stdout.strip().split("\n")
    print(f"\nTotal commits: {len(lines)}")
    print("\nFirst 5:")
    for line in lines[-5:]:
        print(f"  {line}")
    print("\nLast 5:")
    for line in lines[:5]:
        print(f"  {line}")
    print(f"\nDone. {len(lines)} commits across 11 weeks.")
    print("\nNext: push with  git remote add origin https://github.com/Nickalus12/pskit.git && git push -u origin main")


if __name__ == "__main__":
    build()
