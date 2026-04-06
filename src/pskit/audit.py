"""PSKit audit log — append-only JSONL at .pskit/audit.jsonl."""
from __future__ import annotations

import datetime as _dt
import json
import threading
from pathlib import Path
from typing import Any


class PSKitAudit:
    """Thread-safe append-only audit log for all executed commands."""

    def __init__(self, project_root: Path | None = None, max_entries: int = 10_000) -> None:
        self._root = project_root or Path.cwd()
        self._log_dir = self._root / ".pskit"
        self._log_path = self._log_dir / "audit.jsonl"
        self._max_entries = max_entries
        self._lock = threading.Lock()

    def _ensure_dir(self) -> None:
        self._log_dir.mkdir(exist_ok=True)
        gi = self._log_dir / ".gitignore"
        if not gi.exists():
            gi.write_text("audit.jsonl\n", encoding="utf-8")

    def record(
        self,
        command: str,
        session_id: str,
        safety_verdict: str,
        kan_score: float,
        success: bool,
        duration_ms: int,
        error: str = "",
    ) -> None:
        entry = {
            "ts": _dt.datetime.now(_dt.UTC).isoformat(),
            "cmd": command[:500],
            "session": session_id,
            "verdict": safety_verdict,
            "kan": round(kan_score, 4),
            "ok": success,
            "ms": duration_ms,
            "err": error[:200] if error else "",
        }
        with self._lock:
            try:
                self._ensure_dir()
                with open(self._log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry) + "\n")
                self._trim_if_needed()
            except Exception:
                pass

    def _trim_if_needed(self) -> None:
        try:
            lines = self._log_path.read_text(encoding="utf-8").splitlines()
            if len(lines) > self._max_entries:
                self._log_path.write_text(
                    "\n".join(lines[-self._max_entries:]) + "\n", encoding="utf-8"
                )
        except Exception:
            pass

    def tail(self, n: int = 50) -> list[dict[str, Any]]:
        try:
            lines = self._log_path.read_text(encoding="utf-8").splitlines()
            return [json.loads(ln) for ln in lines[-n:] if ln.strip()]
        except Exception:
            return []

    def stats(self) -> dict[str, Any]:
        entries = self.tail(self._max_entries)
        if not entries:
            return {"total": 0, "blocked": 0, "failed": 0, "avg_duration_ms": 0.0, "avg_kan_score": 0.0}
        total = len(entries)
        blocked = sum(1 for e in entries if e.get("verdict") == "blocked")
        failed = sum(1 for e in entries if not e.get("ok"))
        avg_ms = sum(e.get("ms", 0) for e in entries) / total
        avg_kan = sum(e.get("kan", 0.0) for e in entries) / total
        return {
            "total": total,
            "blocked": blocked,
            "failed": failed,
            "avg_duration_ms": round(avg_ms, 1),
            "avg_kan_score": round(avg_kan, 4),
        }


_audit: PSKitAudit | None = None


def get_audit(project_root: Path | None = None) -> PSKitAudit:
    global _audit
    if _audit is None:
        _audit = PSKitAudit(project_root)
    return _audit
