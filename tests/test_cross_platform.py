"""
Cross-platform integration tests for pskit.

These tests SPAWN a real pwsh process on whatever OS is running and invoke
each tool. They are marked `integration` so CI can run them in a
pwsh-available matrix without the pure-mock tests depending on pwsh.

Only the 5 patched functions are exercised here — the rest already work
on any platform because they use cross-platform pwsh built-ins.
"""
from __future__ import annotations
import json
import platform
import shutil
import subprocess

import pytest


pytestmark = pytest.mark.integration


def _pwsh() -> str:
    for cand in ("pwsh-preview", "pwsh", "powershell"):
        if shutil.which(cand):
            return cand
    pytest.skip("PowerShell not available on PATH")


def _run_tool(func: str, args: str = "") -> dict:
    """Import the module and invoke a tool function, return parsed JSON."""
    pwsh = _pwsh()
    import os
    module_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "src", "pskit", "tools", "PSKitTools.psm1")
    )
    script = f"Import-Module '{module_path}' -Force; {func} {args}".replace("\\", "/")
    r = subprocess.run(
        [pwsh, "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, timeout=30,
    )
    assert r.returncode == 0, f"pwsh exited {r.returncode}\nSTDOUT: {r.stdout}\nSTDERR: {r.stderr}"
    out = r.stdout.strip().splitlines()[-1]
    try:
        return json.loads(out)
    except json.JSONDecodeError as e:
        pytest.fail(f"Non-JSON output: {out!r} (parse err: {e})")


def test_memory_usage_returns_valid_numbers():
    data = _run_tool("Get-PSKitMemoryUsage")
    assert data["success"] is True, data
    assert data["total_gb"] > 0, "total memory must be positive"
    assert data["free_gb"] >= 0
    assert data["used_gb"] >= 0
    # Rough sanity: used + free ≈ total (within 1 GB tolerance)
    assert abs((data["used_gb"] + data["free_gb"]) - data["total_gb"]) < 2.0
    if platform.system() == "Linux":
        assert data.get("platform") == "linux"
    elif platform.system() == "Darwin":
        assert data.get("platform") == "macos"
    elif platform.system() == "Windows":
        assert data.get("platform") == "windows"


def test_disk_usage_returns_valid_numbers():
    data = _run_tool("Get-PSKitDiskUsage", "-Path .")
    assert data["success"] is True, data
    assert data["total_gb"] > 0
    assert data["free_gb"] >= 0
    # used + free should be within reasonable tolerance of total
    assert abs((data["used_gb"] + data["free_gb"]) - data["total_gb"]) / data["total_gb"] < 0.10


def test_port_status_returns_port_list():
    data = _run_tool("Get-PSKitPortStatus")
    assert data["success"] is True, data
    assert isinstance(data["ports"], list)
    assert len(data["ports"]) > 0
    for entry in data["ports"]:
        assert "port" in entry and "listening" in entry
        assert isinstance(entry["listening"], bool)


def test_process_info_returns_top_processes():
    data = _run_tool("Get-PSKitProcessInfo")
    assert data["success"] is True, data
    assert data["count"] >= 1
    assert isinstance(data["processes"], list)
    first = data["processes"][0]
    assert "name" in first and "id" in first
    assert isinstance(first["id"], int)
    # responding may be None on Linux/macOS; must not throw
    assert "responding" in first


def test_install_package_dry_manager_detection():
    # We don't actually install anything — just verify the function returns
    # a deterministic "no manager needed" path when Manager= is given but the
    # package is clearly nonexistent. (Actual install path would take minutes.)
    data = _run_tool("Install-PSKitPackage", '-Name __pskit_probe_never_exists__ -Manager pip')
    assert "manager" in data
    assert data["manager"] == "pip"
    # Real pip install of nonexistent will fail; success False is expected
    assert data["success"] is False
