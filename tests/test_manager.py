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
