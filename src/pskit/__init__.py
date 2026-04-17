"""PSKit MCP — Neural-safe PowerShell automation for AI agents."""
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

from pskit.kan_engine import PSKitKANEngine
from pskit.manager import PSKitManager, get_counters

try:
    __version__ = _pkg_version("pskit-mcp")
except PackageNotFoundError:  # editable install before metadata installed
    __version__ = "0.0.0+dev"

__all__ = ["PSKitManager", "PSKitKANEngine", "get_counters", "__version__"]
