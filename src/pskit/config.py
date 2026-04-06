"""PSKit configuration — reads pskit.config.toml from project root.

Layered: defaults < pskit.config.toml < environment variables.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[no-redef,assignment]
    except ImportError:
        tomllib = None  # type: ignore[assignment]

_DEFAULTS: dict[str, Any] = {
    "allowed_root": None,
    "pool_size": 3,
    "safety_model": "gemma4:e2b",
    "ollama_base_url": "http://localhost:11434",
    "audit_enabled": True,
    "audit_max_entries": 10_000,
    "extra_blocklist": [],
}


class PSKitConfig:
    """Layered PSKit configuration."""

    def __init__(self, project_root: Path | None = None) -> None:
        self._root = project_root or Path.cwd()
        self._data: dict[str, Any] = dict(_DEFAULTS)
        self._load_toml()
        self._apply_env()

    def _load_toml(self) -> None:
        path = self._root / "pskit.config.toml"
        if not path.exists() or tomllib is None:
            return
        try:
            with open(path, "rb") as f:
                raw = tomllib.load(f)
            section = raw.get("pskit", raw)
            for key in _DEFAULTS:
                if key in section:
                    self._data[key] = section[key]
        except Exception:
            pass

    def _apply_env(self) -> None:
        if v := os.getenv("PSKIT_ALLOWED_ROOT"):
            self._data["allowed_root"] = v
        if v := os.getenv("PSKIT_POOL_SIZE"):
            try:
                self._data["pool_size"] = int(v)
            except ValueError:
                pass
        if v := os.getenv("PSKIT_SAFETY_MODEL"):
            self._data["safety_model"] = v
        if v := os.getenv("OLLAMA_BASE_URL"):
            self._data["ollama_base_url"] = v

    @property
    def allowed_root(self) -> str:
        v = self._data["allowed_root"]
        return str(Path(v).resolve()) if v else str(self._root.resolve())

    @property
    def pool_size(self) -> int:
        return int(self._data["pool_size"])

    @property
    def safety_model(self) -> str:
        return str(self._data["safety_model"])

    @property
    def ollama_base_url(self) -> str:
        return str(self._data["ollama_base_url"])

    @property
    def audit_enabled(self) -> bool:
        return bool(self._data["audit_enabled"])

    @property
    def audit_max_entries(self) -> int:
        return int(self._data["audit_max_entries"])

    @property
    def extra_blocklist(self) -> list[str]:
        return list(self._data.get("extra_blocklist", []))

    def as_dict(self) -> dict[str, Any]:
        return {
            "allowed_root": self.allowed_root,
            "pool_size": self.pool_size,
            "safety_model": self.safety_model,
            "ollama_base_url": self.ollama_base_url,
            "audit_enabled": self.audit_enabled,
            "audit_max_entries": self.audit_max_entries,
            "extra_blocklist": self.extra_blocklist,
        }


_config: PSKitConfig | None = None


def get_config(project_root: Path | None = None) -> PSKitConfig:
    global _config
    if _config is None:
        _config = PSKitConfig(project_root)
    return _config
