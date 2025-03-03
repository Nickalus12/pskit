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
