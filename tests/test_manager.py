"""Tests for PSKit MCP core components."""
import time

import pytest


# ── Counter tests ──────────────────────────────────────────────────────────────


def test_counter_increments():
    import pskit.manager as mod
    mod._counters.clear()
    mod._inc("test_metric")
    mod._inc("test_metric")
    mod._inc("other_metric")
    assert mod._counters["test_metric"] == 2
    assert mod._counters["other_metric"] == 1


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
    mod._inc("brand_new")
    assert mod._counters["brand_new"] == 1


# ── ResultCache tests ─────────────────────────────────────────────────────────


def test_result_cache_miss():
    from pskit.manager import _ResultCache
    cache = _ResultCache(ttl=30.0)
    assert cache.get("Get-PSKitDiskUsage", "session1") is None


def test_result_cache_hit():
    from pskit.manager import _ResultCache
    cache = _ResultCache(ttl=30.0)
    value = {"output": "disk info", "success": True}
    cache.put("Get-PSKitDiskUsage", "session1", value)
    assert cache.get("Get-PSKitDiskUsage", "session1") == value


def test_result_cache_invalidate():
    from pskit.manager import _ResultCache
    cache = _ResultCache(ttl=30.0)
    cache.put("Get-PSKitGitStatus", "session1", {"output": "clean"})
    cache.invalidate()
    assert cache.get("Get-PSKitGitStatus", "session1") is None


def test_result_cache_expired():
    from pskit.manager import _ResultCache
    cache = _ResultCache(ttl=0.01)
    cache.put("cmd", "session1", {"output": "data"})
    time.sleep(0.05)
    assert cache.get("cmd", "session1") is None


def test_result_cache_different_sessions_isolated():
    from pskit.manager import _ResultCache
    cache = _ResultCache(ttl=30.0)
    value = {"output": "data", "success": True}
    cache.put("Get-PSKitGitStatus", "session_a", value)
    assert cache.get("Get-PSKitGitStatus", "session_b") is None
    assert cache.get("Get-PSKitGitStatus", "session_a") == value


def test_result_cache_lru_eviction():
    from pskit.manager import _ResultCache
    cache = _ResultCache(ttl=30.0, max_size=3)
    for i in range(4):
        cache.put(f"cmd_{i}", "s", {"output": str(i)})
    assert cache.get("cmd_0", "s") is None
    assert cache.get("cmd_3", "s") is not None


def test_result_cache_put_overwrites():
    from pskit.manager import _ResultCache
    cache = _ResultCache(ttl=30.0)
    cache.put("cmd", "s", {"output": "first"})
    cache.put("cmd", "s", {"output": "second"})
    assert cache.get("cmd", "s") == {"output": "second"}


# ── KAN engine feature extraction tests ───────────────────────────────────────


def _make_engine():
    from pskit.kan_engine import PSKitKANEngine
    engine = PSKitKANEngine.__new__(PSKitKANEngine)
    engine._model = None
    engine._initialized = False
    engine._training_data = []
    engine._command_count = 0
    engine._retrain_threshold = 50
    return engine


def test_extract_features_returns_24():
    features = _make_engine().extract_features("Get-ChildItem -Path C:\\temp")
    assert len(features) == 24


def test_extract_features_all_floats():
    features = _make_engine().extract_features("Write-Host 'hello'")
    assert all(isinstance(f, float) for f in features)


def test_extract_features_values_in_range():
    features = _make_engine().extract_features("Get-Process | Select-Object Name, CPU")
    for f in features:
        assert 0.0 <= f <= 1.5, f"Feature out of expected range: {f}"


def test_extract_features_whatif_zeros_risk():
    engine = _make_engine()
    features_normal = engine.extract_features("Remove-Item C:\\temp\\file.txt")
    features_whatif = engine.extract_features("Remove-Item C:\\temp\\file.txt -WhatIf")
    assert features_whatif[4] == 0.0, "deletion feature should be 0 with -WhatIf"
    assert features_normal[4] > 0.0, "deletion feature should be non-zero without -WhatIf"


def test_extract_features_safe_indicator_present():
    engine = _make_engine()
    features = engine.extract_features("Get-ChildItem | Select-Object Name")
    assert features[14] > 0.0, "safe_indicators feature should be positive for read-only command"


def test_extract_features_base64_detected():
    engine = _make_engine()
    features = engine.extract_features(
        "[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes('hello'))"
    )
    assert features[20] == 1.0, "base64_patterns feature should be 1.0"


def test_extract_features_credential_detected():
    engine = _make_engine()
    features = engine.extract_features(
        "Get-Credential -UserName admin -Message 'Enter password'"
    )
    assert features[19] == 1.0, "credential_patterns feature should be 1.0"


# ── KAN heuristic scorer tests ─────────────────────────────────────────────────


def test_heuristic_score_is_float():
    engine = _make_engine()
    features = engine.extract_features("Get-ChildItem")
    score = engine._heuristic_score(features)
    assert isinstance(score, float)


def test_heuristic_score_in_range():
    engine = _make_engine()
    for cmd in [
        "Get-ChildItem",
        "Write-Host 'hello'",
        "Invoke-Expression $payload",
        "Remove-Item -Recurse -Force C:\\temp",
        "Get-Process | Select-Object Name",
    ]:
        features = engine.extract_features(cmd)
        score = engine._heuristic_score(features)
        assert 0.0 <= score <= 1.0, f"Score {score} out of range for: {cmd}"


def test_heuristic_safe_command_scores_low():
    engine = _make_engine()
    features = engine.extract_features("Get-ChildItem -Path . | Select-Object Name")
    score = engine._heuristic_score(features)
    assert score < 0.5, f"Expected low risk score for safe command, got {score}"


def test_heuristic_invoke_expression_scores_high():
    engine = _make_engine()
    features = engine.extract_features("Invoke-Expression $dangerousPayload")
    score = engine._heuristic_score(features)
    assert score > 0.3, f"Expected elevated risk score for Invoke-Expression, got {score}"


def test_heuristic_credential_scores_high():
    engine = _make_engine()
    features = engine.extract_features("$cred = Get-Credential; Connect-Server -Credential $cred")
    score = engine._heuristic_score(features)
    assert score > 0.3, f"Expected elevated score for credential pattern, got {score}"


# ── PSKitManager instantiation tests ──────────────────────────────────────────


def test_manager_instantiates():
    from pskit.manager import PSKitManager
    manager = PSKitManager()
    assert manager is not None


def test_manager_has_kan_engine():
    from pskit.manager import PSKitManager, PSKitKANEngine
    manager = PSKitManager()
    assert isinstance(manager._kan, PSKitKANEngine)


def test_manager_allowed_root_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("PSKIT_ALLOWED_ROOT", str(tmp_path))
    from pskit.manager import PSKitManager
    manager = PSKitManager()
    assert manager._allowed_root == str(tmp_path.resolve())


def test_manager_readonly_detection():
    from pskit.manager import PSKitManager
    manager = PSKitManager()
    assert manager._is_readonly_command("read-pskitfile 'test.py'")
    assert manager._is_readonly_command("get-pskitgitstatus")
    assert manager._is_readonly_command("git log --oneline")
    assert not manager._is_readonly_command("write-pskitfile 'test.py' 'content'")
    assert not manager._is_readonly_command("New-PSKitGitCommit 'fix: bug'")


def test_manager_dangerous_command_detection():
    from pskit.manager import PSKitManager
    manager = PSKitManager()
    assert manager._check_dangerous_commands("Format-Volume D:") is not None
    assert manager._check_dangerous_commands("rm -rf /") is not None
    assert manager._check_dangerous_commands("Get-ChildItem") is None


def test_manager_elevated_review_detection():
    from pskit.manager import PSKitManager
    manager = PSKitManager()
    assert manager._check_elevated_review("Invoke-WebRequest https://example.com") is not None
    assert manager._check_elevated_review("Stop-Service -Name W32Time") is not None
    assert manager._check_elevated_review("Get-ChildItem") is None


def test_manager_path_safety_allows_root(tmp_path):
    from pskit.manager import PSKitManager
    manager = PSKitManager(project_root=tmp_path)
    safe_script = f"Get-Content '{tmp_path}\\file.txt'"
    assert manager._check_path_safety(safe_script)


def test_manager_no_sessions_on_init():
    from pskit.manager import PSKitManager
    manager = PSKitManager()
    assert manager._sessions == {}


def test_manager_pool_none_on_init():
    from pskit.manager import PSKitManager
    manager = PSKitManager()
    assert manager._pool is None
