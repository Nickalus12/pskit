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
        abs_paths = 1.0 if re.search(r"[A-Za-z]:\\", command) else 0.0
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
        cmdlet_count = min(len(re.findall(r"[A-Z][a-z]+-[A-Z][a-zA-Z]+", command)) / 5.0, 1.0)
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
        return round(max(0.0, min(1.0, score)), 4)

    async def score_command(self, command: str) -> float:
        self._command_count += 1
        features = self.extract_features(command)
        return self._heuristic_score(features)

    def get_status(self) -> dict:
        return {
            "initialized": self._initialized,
            "model_loaded": self._model is not None,
            "num_features": NUM_FEATURES,
            "command_count": self._command_count,
        }
