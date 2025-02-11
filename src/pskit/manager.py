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
    "format-volume", "format-disk", "rm -rf", "remove-item -recurse -force c:\\",
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
        paths = re.findall(r"[A-Za-z]:\\[^'"\s,;)]+", script)
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
            proc.stdin.write((script + "\n").encode("utf-8"))
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
        # pool implementation coming
        return None
