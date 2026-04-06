"""PSKit MCP — Neural-safe PowerShell automation for AI agents."""
from pskit.kan_engine import PSKitKANEngine
from pskit.manager import PSKitManager, get_counters

__version__ = "0.1.0"
__all__ = ["PSKitManager", "PSKitKANEngine", "get_counters", "__version__"]
