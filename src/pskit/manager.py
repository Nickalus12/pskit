import asyncio
import hashlib
import json
import logging
import os
import re
import struct
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pskit.kan_engine import PSKitKANEngine

# Lightweight built-in counters — no external telemetry dependency
_counters: dict[str, int] = {}

def _inc(name: str) -> None:
    _counters[name] = _counters.get(name, 0) + 1

def get_counters() -> dict[str, int]:
    return dict(_counters)

# Safety verdict cache — avoids repeating Gemma review for identical commands
_SAFETY_CACHE_TTL = 300  # seconds
_SAFETY_CACHE_MAX = 256

# Commands that are provably read-only: skip Gemma review, KAN + blocklist still run
_READONLY_PREFIXES: frozenset[str] = frozenset({
    "get-content",
    "get-childitem",
    "get-item",
    "select-string",
    "read-pskitfile",
    "search-pskitcode",
    "find-pskitfiles",
    "get-pskitgitlog",
    "get-pskitgitstatus",
    "get-pskitgitdiff",
    "get-pskitdiskusage",
    "get-pskitmemoryusage",
    "get-pskitgpustatus",
    "rg ",
    "git log",
    "git diff",
    "git status",
    "git show",
    "git branch",
})

logger = logging.getLogger(__name__)

_DANGEROUS_COMMANDS: frozenset[str] = frozenset({
    # Hard-blocked: destructive system commands that should never run
    "Remove-Item -Recurse -Force /",
    "Format-Volume",
    "Stop-Computer",
    "Restart-Computer",
    "Clear-RecycleBin",
    "rm -rf",
    "del /s /q C:\\",
})

_ELEVATED_REVIEW_COMMANDS: frozenset[str] = frozenset({
    # These commands are legitimate but risky — force Gemma LLM review
    # even when KAN scores them as safe. If Gemma (or Ollama) is unavailable,
    # the fail-closed handler in _execute_inner blocks them.
    # Network operations
    "invoke-webrequest",
    "invoke-restmethod",
    "send-mailmessage",
    "start-bitstransfer",
    # Process / service manipulation
    "stop-service",
    "set-service",
    "new-service",
    "start-process",
    # Firewall / network config
    "new-netfirewallrule",
    "remove-netfirewallrule",
    "disable-netadapter",
    # Execution bypass
    "invoke-expression",
    "set-executionpolicy",
    # Registry modification
    "set-itemproperty",
    "new-itemproperty",
    "remove-itemproperty",
})

_PWSH_CANDIDATES: tuple[str, ...] = ("pwsh-preview", "pwsh", "powershell")

_MODULE_PATH = str(Path(__file__).parent / "PSKitTools.psm1").replace("\\", "/")

_SESSION_INIT_TEMPLATE = """\
$ErrorActionPreference = 'Continue'
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
# Note: ConstrainedLanguage mode cannot be set programmatically from FullLanguage.
# Security is enforced via: (1) local Gemma safety review, (2) path allowlist,
# (3) dangerous command blocklist, and (4) project-root working directory.
Set-Location '__LOOM_PROJECT_ROOT__'
try {
    Import-Module '__LOOM_MODULE_PATH__' -Force -ErrorAction Stop
} catch {
    Write-Warning "Loom module failed to load: $($_.Exception.Message). Loom cmdlets will be unavailable."
}
"""

_EXEC_WRAPPER_TEMPLATE = """\
$__loom_marker = '__LOOM_MARKER__'
Write-Host $__loom_marker
try {
    __LOOM_SCRIPT__
} catch {
    Write-Error $_.Exception.Message
}
Write-Host "LOOM_EXIT:$($?):$LASTEXITCODE"
Write-Host $__loom_marker
"""

# Named-pipe server embedded in the PS session.
# Replaces the stdin/stdout marker protocol after session startup.
# Communication: 4-byte LE uint32 length prefix + UTF-8 JSON body (both directions).
_PIPE_SERVER_TEMPLATE = r"""
$ErrorActionPreference = 'Continue'
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Set-Location '__LOOM_PROJECT_ROOT__'
try {
    Import-Module '__LOOM_MODULE_PATH__' -Force -ErrorAction Stop
} catch {
    Write-Warning "Loom module failed to load: $($_.Exception.Message)"
}

$__loomPipeName = '__LOOM_PIPE_NAME__'
$__loomPipe = [System.IO.Pipes.NamedPipeServerStream]::new(
    $__loomPipeName,
    [System.IO.Pipes.PipeDirection]::InOut,
    1,
    [System.IO.Pipes.PipeTransmissionMode]::Byte,
    [System.IO.Pipes.PipeOptions]::None,
    65536, 65536
)

# Signal Python that the pipe is ready to accept connections
Write-Host "PIPE_READY:$__loomPipeName"
[Console]::Out.Flush()

# Redirect host streams to null — prevents stdout buffer deadlock
# after Python stops reading stdout (all data flows through the pipe)
[Console]::SetOut([System.IO.TextWriter]::Null)
[Console]::SetError([System.IO.TextWriter]::Null)

$__loomPipe.WaitForConnection()
$__loomReader = [System.IO.BinaryReader]::new($__loomPipe, [System.Text.Encoding]::UTF8, $true)
$__loomWriter = [System.IO.BinaryWriter]::new($__loomPipe, [System.Text.Encoding]::UTF8, $true)

function __LoomExec($__script) {
    $__outLines = [System.Collections.Generic.List[string]]::new()
    $__errLines = [System.Collections.Generic.List[string]]::new()
    $__t = [System.Diagnostics.Stopwatch]::GetTimestamp()
    try {
        $__sb = [scriptblock]::Create($__script)
        $__raw = & $__sb 2>&1
        foreach ($__item in $__raw) {
            if ($__item -is [System.Management.Automation.ErrorRecord]) {
                $__errLines.Add($__item.Exception.Message)
            } else {
                $__outLines.Add($__item.ToString())
            }
        }
    } catch {
        $__errLines.Add($_.Exception.Message)
    }
    $__ms = [int](([System.Diagnostics.Stopwatch]::GetTimestamp() - $__t) * 1000 / [System.Diagnostics.Stopwatch]::Frequency)
    return @{
        output     = [string]::Join("`n", $__outLines).TrimEnd()
        errors     = [string]::Join("`n", $__errLines).TrimEnd()
        success    = ($__errLines.Count -eq 0)
        duration_ms = $__ms
    }
}

while ($__loomPipe.IsConnected) {
    try {
        $__msgLen = $__loomReader.ReadInt32()
        if ($__msgLen -le 0 -or $__msgLen -gt 67108864) { break }  # sanity: 64MB max
        $__msgBytes = $__loomReader.ReadBytes($__msgLen)
        $__msg = [System.Text.Encoding]::UTF8.GetString($__msgBytes) | ConvertFrom-Json

        $__resp = switch ($__msg.type) {
            'exec' {
                $__r = __LoomExec $__msg.script
                @{ id = $__msg.id; type = 'result'
                   output = $__r.output; errors = $__r.errors
                   success = $__r.success; duration_ms = $__r.duration_ms
                } | ConvertTo-Json -Compress -Depth 2
            }
            'batch' {
                $__results = @($__msg.scripts | ForEach-Object { __LoomExec $_ })
                @{ id = $__msg.id; type = 'batch_result'; results = $__results
                } | ConvertTo-Json -Compress -Depth 4
            }
            'exit' { break }
            default {
                @{ id = $__msg.id; type = 'error'
                   error = "Unknown type: $($__msg.type)"
                } | ConvertTo-Json -Compress
            }
        }
        if (-not $__resp) { break }

        $__respBytes = [System.Text.Encoding]::UTF8.GetBytes($__resp)
        $__loomWriter.Write([int]$__respBytes.Length)
        $__loomWriter.Write($__respBytes, 0, $__respBytes.Length)
        $__loomWriter.Flush()
    } catch [System.IO.EndOfStreamException] { break
    } catch { break }
}

try { $__loomPipe.Disconnect() } catch {}
$__loomPipe.Dispose()
"""


# ---------------------------------------------------------------------------
# Named-pipe async protocol (Windows ProactorEventLoop)
# ---------------------------------------------------------------------------

class _PipeProtocol(asyncio.Protocol):
    """Length-prefixed JSON framing over a Windows named pipe."""

    def __init__(self) -> None:
        self._buf = bytearray()
        self._transport: asyncio.BaseTransport | None = None
        self._queue: asyncio.Queue[dict] = asyncio.Queue()
        self.closed = False

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self._transport = transport

    def data_received(self, data: bytes) -> None:
        self._buf.extend(data)
        while len(self._buf) >= 4:
            (length,) = struct.unpack_from("<I", self._buf, 0)
            if len(self._buf) < 4 + length:
                break
            payload = bytes(self._buf[4 : 4 + length])
            del self._buf[: 4 + length]
            try:
                self._queue.put_nowait(json.loads(payload))
            except json.JSONDecodeError:
                pass

    def connection_lost(self, exc: Exception | None) -> None:
        self.closed = True

    def send(self, msg: dict) -> None:
        if self._transport and not self.closed:
            payload = json.dumps(msg).encode("utf-8")
            frame = struct.pack("<I", len(payload)) + payload
            self._transport.write(frame)

    async def recv(self, timeout: float = 120.0) -> dict:
        return await asyncio.wait_for(self._queue.get(), timeout=timeout)

    def close(self) -> None:
        if self._transport:
            self._transport.close()


class _NamedPipeClient:
    """Async client for the embedded PS named-pipe server."""

    def __init__(self, pipe_name: str) -> None:
        self._pipe_name = pipe_name
        self._proto: _PipeProtocol | None = None

    @property
    def connected(self) -> bool:
        return self._proto is not None and not self._proto.closed

    async def connect(self, timeout: float = 10.0) -> None:
        pipe_path = f"\\\\.\\pipe\\{self._pipe_name}"
        loop = asyncio.get_running_loop()
        deadline = time.monotonic() + timeout
        last_exc: Exception = OSError("pipe not ready")
        while time.monotonic() < deadline:
            try:
                proto = _PipeProtocol()
                await loop.create_pipe_connection(lambda: proto, pipe_path)
                # Yield one tick so connection_made() fires before we use the transport.
                # create_pipe_connection resolves the future but schedules connection_made()
                # as a callback — _transport is None until we yield to the event loop.
                await asyncio.sleep(0)
                self._proto = proto
                return
            except (FileNotFoundError, OSError) as exc:
                last_exc = exc
                await asyncio.sleep(0.05)
        raise TimeoutError(
            f"Cannot connect to pipe {pipe_path} within {timeout}s: {last_exc}"
        )

    async def execute(self, script: str, timeout: float = 120.0) -> dict:
        msg_id = uuid.uuid4().hex[:12]
        assert self._proto is not None
        self._proto.send({"id": msg_id, "type": "exec", "script": script})
        return await self._proto.recv(timeout=timeout)

    async def execute_batch(
        self, scripts: list[str], timeout: float = 120.0
    ) -> list[dict]:
        msg_id = uuid.uuid4().hex[:12]
        assert self._proto is not None
        self._proto.send({"id": msg_id, "type": "batch", "scripts": scripts})
        resp = await self._proto.recv(timeout=timeout)
        return resp.get("results", [])

    def close(self) -> None:
        if self._proto:
            try:
                self._proto.send({"id": "bye", "type": "exit"})
            except Exception:
                pass
            self._proto.close()


class _ResultCache:
    """LRU cache for read-only command results. TTL=30s, max=128 entries."""

    def __init__(self, ttl: float = 30.0, max_size: int = 128) -> None:
        self._ttl = ttl
        self._max_size = max_size
        self._data: dict[str, tuple[dict, float]] = {}
        self._order: list[str] = []

    def _key(self, script: str, session_id: str) -> str:
        return hashlib.sha256(f"{session_id}:{script}".encode()).hexdigest()[:32]

    def get(self, script: str, session_id: str) -> dict | None:
        key = self._key(script, session_id)
        entry = self._data.get(key)
        if entry is None:
            return None
        result, expire = entry
        if time.monotonic() > expire:
            self._data.pop(key, None)
            if key in self._order:
                self._order.remove(key)
            return None
        self._order.remove(key)
        self._order.append(key)
        return result

    def put(self, script: str, session_id: str, result: dict) -> None:
        key = self._key(script, session_id)
        if key in self._data and key in self._order:
            self._order.remove(key)
        elif len(self._data) >= self._max_size and self._order:
            lru_key = self._order.pop(0)
            self._data.pop(lru_key, None)
        self._data[key] = (result, time.monotonic() + self._ttl)
        self._order.append(key)

    def invalidate(self) -> None:
        self._data.clear()
        self._order.clear()


class PSKitSessionPool:
    """Pre-warmed pool of named-pipe PS sessions for fast parallel execution."""

    def __init__(self, pool_size: int = 3) -> None:
        self._pool_size = pool_size
        self._available: asyncio.Queue = asyncio.Queue()
        self._all_sessions: list[str] = []
        self.initialized: bool = False

    async def initialize(self, manager: "PSKitManager") -> None:
        for i in range(self._pool_size):
            session_id = f"__pool_{i}__"
            await manager._get_or_create_session(session_id)
            await self._available.put(session_id)
            self._all_sessions.append(session_id)
        self.initialized = True
        logger.info("PowerShell session pool initialized: %d sessions", self._pool_size)

    async def checkout(self, timeout: float = 5.0) -> str:
        return await asyncio.wait_for(self._available.get(), timeout=timeout)

    def checkin(self, session_id: str) -> None:
        self._available.put_nowait(session_id)

    async def execute_pooled(
        self, script: str, manager: "PSKitManager", **kwargs: Any
    ) -> dict:
        session_id = await self.checkout()
        try:
            return await manager.execute(script, session_id=session_id, **kwargs)
        finally:
            self.checkin(session_id)


class PSKitManager:
    """Manages persistent PowerShell 7.6 sessions for agent-native command execution.

    Each session is a long-running pwsh process communicating via stdin/stdout
    using a marker-based protocol. Commands are safety-checked before execution,
    and results are optionally logged to Graphiti via the memory engine.
    """

    def __init__(
        self,
        project_root: str | Path | None = None,
        local_engine: Any = None,
            kan_engine: PSKitKANEngine | None = None,
    ) -> None:
        self._project_root = Path(project_root) if project_root else Path.cwd()
        self._local_engine = local_engine
        self._kan = kan_engine or PSKitKANEngine()
        self._sessions: dict[str, dict] = {}
        self._custom_tools: dict[str, str] = {}
        self._dangerous_commands = _DANGEROUS_COMMANDS
        self._elevated_review_commands = _ELEVATED_REVIEW_COMMANDS
        # Safety verdict cache: sha256(script) -> {"verdict": str, "ts": float}
        self._safety_cache: dict[str, dict] = {}
        # Read-only result cache (30s TTL)
        self._result_cache: _ResultCache = _ResultCache()
        # Session pool (lazily initialized)
        self._pool: PSKitSessionPool | None = None
        # Allow overriding the safety root to a parent directory (e.g., D:\Projects)
        # so agents can work across sibling projects
        env_root = os.getenv("PSKIT_ALLOWED_ROOT", "")
        if env_root:
            self._allowed_root = str(Path(env_root).resolve())
        else:
            self._allowed_root = str(self._project_root.resolve())
        self._pwsh_path: str | None = None

    # ------------------------------------------------------------------ cache

    def _safety_cache_key(self, script: str) -> str:
        return hashlib.sha256(script.encode()).hexdigest()[:48]

    def _get_cached_verdict(self, script: str) -> str | None:
        key = self._safety_cache_key(script)
        entry = self._safety_cache.get(key)
        if entry is None:
            return None
        if time.monotonic() - entry["ts"] > _SAFETY_CACHE_TTL:
            self._safety_cache.pop(key, None)
            return None
        return entry["verdict"]

    def _cache_verdict(self, script: str, verdict: str) -> None:
        if len(self._safety_cache) >= _SAFETY_CACHE_MAX:
            # Evict LRU by popping oldest insertion
            oldest = next(iter(self._safety_cache))
            self._safety_cache.pop(oldest, None)
        self._safety_cache[self._safety_cache_key(script)] = {
            "verdict": verdict,
            "ts": time.monotonic(),
        }

    def _is_readonly_command(self, script: str) -> bool:
        lowered = script.lower().strip()
        return any(lowered.startswith(p) for p in _READONLY_PREFIXES)

    # ----------------------------------------------------------------- telemetry

    def list_custom_tools(self) -> list[str]:
        return list(self._custom_tools.keys())

    async def execute_batch(
        self,
        scripts: list[str],
        session_id: str = "default",
        timeout: int = 120,
    ) -> list[dict]:
        """Execute multiple PS scripts in a single round-trip (pipe sessions only).

        Each script goes through the full safety pipeline independently.
        Blocked scripts get an inline error result; approved scripts are sent
        together in one named-pipe message.  Falls back to sequential execution
        for legacy stdin/stdout sessions.
        """
        if not scripts:
            return []

        # --- Parallel fast path: all-readonly batch over pool ---
        all_readonly = all(self._is_readonly_command(s) for s in scripts)
        if all_readonly and self._pool is not None and self._pool.initialized:
            logger.debug("[Batch] All-readonly batch — dispatching %d scripts in parallel", len(scripts))
            _inc("ps_batch_total")
            tasks = [
                asyncio.create_task(self._pool.execute_pooled(s, manager=self, timeout=timeout))
                for s in scripts
            ]
            raw = await asyncio.gather(*tasks)
            return [
                r if isinstance(r, dict) else {"success": False, "error": str(r)}
                for r in raw
            ]

        # --- Safety check every script ---
        approved_indices: list[int] = []
        results: list[dict | None] = [None] * len(scripts)

        for i, script in enumerate(scripts):
            blocked = await self._safety_check_only(script, session_id)
            if blocked is not None:
                results[i] = blocked
            else:
                approved_indices.append(i)

        if not approved_indices:
            return [r or {} for r in results]

        approved_scripts = [scripts[i] for i in approved_indices]

        session, session_created = await self._get_or_create_session(session_id)
        pipe: _NamedPipeClient | None = session.get("pipe")
        _inc("ps_commands_total")

        start = time.monotonic()

        if pipe and pipe.connected:
            try:
                batch_results = await pipe.execute_batch(
                    approved_scripts, timeout=float(timeout)
                )
                elapsed_ms = int((time.monotonic() - start) * 1000)
                for local_i, global_i in enumerate(approved_indices):
                    r = batch_results[local_i] if local_i < len(batch_results) else {}
                    results[global_i] = {
                        "success": r.get("success", False),
                        "output": r.get("output", ""),
                        "errors": r.get("errors", ""),
                        "session_id": session_id,
                        "execution_time_ms": r.get("duration_ms", 0),
                        "batch_total_ms": elapsed_ms,
                        "command": scripts[global_i],
                        "protocol": "pipe/batch",
                    }
            except Exception as exc:
                logger.warning("Batch execute failed: %s — falling back to sequential", exc)
                for i, script in zip(approved_indices, approved_scripts):
                    results[i] = await self.execute(script, session_id, timeout)
        else:
            # Legacy fallback: sequential
            for i, script in zip(approved_indices, approved_scripts):
                results[i] = await self.execute(script, session_id, timeout)

        session["command_count"] += len(approved_indices)
        session["last_command"] = datetime.now(UTC)
        return [r or {} for r in results]

    async def _safety_check_only(self, script: str, session_id: str) -> dict | None:
        """Run the safety pipeline only. Returns a blocked-result dict or None (approved)."""
        cached = self._get_cached_verdict(script)
        if cached == "safe":
            return None

        is_readonly = self._is_readonly_command(script)
        kan_result = await self._kan.score_risk(script)
        elevated_match = self._check_elevated_review(script)
        requires_gemma = elevated_match is not None

        if kan_result.get("risk_level") == "blocked" and not requires_gemma:
            return {"success": False, "errors": "Blocked by KAN safety pre-filter", "output": "", "command": script}

        dangerous = self._check_dangerous_commands(script)
        if dangerous:
            return {"success": False, "errors": f"Dangerous command blocked: '{dangerous}'", "output": "", "command": script}

        if not self._check_path_safety(script):
            return {"success": False, "errors": "Path safety check failed", "output": "", "command": script}

        skip_gemma = (
            is_readonly
            or (not requires_gemma and kan_result.get("risk_level") == "safe"
                and kan_result.get("risk_score", 1.0) < 0.2)
        )

        if not skip_gemma and self._local_engine is not None and hasattr(self._local_engine, "review_powershell_command"):
            try:
                safety_result = await self._local_engine.review_powershell_command(script)
                if isinstance(safety_result, dict) and safety_result.get("risk_level") == "blocked":
                    return {"success": False, "errors": "Blocked by safety review", "output": "", "command": script}
            except Exception:
                if requires_gemma:
                    return {"success": False, "errors": "Elevated command blocked: safety review unavailable", "output": "", "command": script}

        if not requires_gemma:
            self._cache_verdict(script, "safe")
        return None  # approved

    async def get_session_info(self, session_id: str = "default") -> dict:
        session = self._sessions.get(session_id)
        if session is None:
            return {"exists": False, "session_id": session_id}

        proc: asyncio.subprocess.Process = session["process"]
        pipe: _NamedPipeClient | None = session.get("pipe")
        return {
            "exists": True,
            "session_id": session_id,
            "pid": proc.pid,
            "alive": proc.returncode is None,
            "protocol": "pipe" if (pipe and pipe.connected) else "stdin/stdout",
            "created": session["created"].isoformat(),
            "command_count": session["command_count"],
            "last_command": session["last_command"].isoformat() if session["last_command"] else None,
        }

    async def _log_command(self, command: str, result: dict) -> None:
        if self._memory is None:
            return

        try:
            truncated_output = result.get("output", "")[:500]
            await self._memory.add_local_insight(
                file_path="powershell_session",
                analysis=f"PS Command: {command}\nResult: {truncated_output}",
                confidence="high",
                category="command_log",
            )
        except Exception as exc:
            logger.warning("Failed to log command to memory: %s", exc)

    def _check_path_safety(self, script: str) -> bool:
        windows_paths = re.findall(r'[A-Za-z]:\\[^\s\'"`;]+', script)
        unix_paths = re.findall(r'(?<!\w)/(?:usr|etc|var|tmp|home|root|opt|bin|sbin)[^\s\'"`;]*', script)

        for path_str in windows_paths:
            normalized = os.path.normpath(path_str)
            if not normalized.lower().startswith(self._allowed_root.lower()):
                logger.warning("Path outside project root detected: %s", path_str)
                return False

        for path_str in unix_paths:
            normalized = os.path.normpath(path_str)
            if not normalized.startswith(self._allowed_root):
                logger.warning("Path outside project root detected: %s", path_str)
                return False

        return True

    def _check_dangerous_commands(self, script: str) -> str | None:
        script_lower = script.lower()
        for pattern in self._dangerous_commands:
            if pattern.lower() in script_lower:
                logger.warning("Dangerous command pattern detected: %s", pattern)
                return pattern
        return None

    def _check_elevated_review(self, script: str) -> str | None:
        """Check if the script contains commands that require elevated Gemma review."""
        script_lower = script.lower()
        for pattern in self._elevated_review_commands:
            if pattern in script_lower:
                return pattern
        return None
