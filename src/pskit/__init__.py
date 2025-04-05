"""PSKit MCP — Neural-safe PowerShell automation for AI agents."""
from pskit.manager import PSKitManager, get_counters
from pskit.kan_engine import PSKitKANEngine

__version__ = "0.1.0"
__all__ = ["PSKitManager", "PSKitKANEngine", "get_counters", "__version__"]
