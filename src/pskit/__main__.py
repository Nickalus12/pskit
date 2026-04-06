"""PSKit CLI entry point.

Usage:
    pskit              start MCP server (default)
    pskit serve        start MCP server explicitly
    pskit doctor       check system dependencies and configuration
    pskit audit        show recent audit log with stats
    pskit version      print version and exit
"""
from __future__ import annotations

import sys


def _cmd_serve() -> None:
    from pskit.server import mcp
    mcp.run()


def _cmd_doctor() -> None:
    import os
    import subprocess
    from pathlib import Path

    try:
        from rich.console import Console
        from rich.table import Table
        _rich = True
    except ImportError:
        _rich = False

    checks: list[tuple[str, bool, str]] = []

    def _bin(name: str, flag: str = "--version") -> tuple[bool, str]:
        try:
            r = subprocess.run([name, flag], capture_output=True, text=True, timeout=5)
            ver = (r.stdout or r.stderr).strip().split("\n")[0][:60]
            return True, ver
        except Exception:
            return False, "not found"

    ok, ver = _bin("pwsh")
    checks.append(("PowerShell (pwsh)", ok, ver if ok else "NOT FOUND — required"))

    ok, ver = _bin("git")
    checks.append(("git", ok, ver if ok else "NOT FOUND — required"))

    ok, ver = _bin("rg", "--version")
    checks.append(("ripgrep (rg)", ok,
        f"{ver} — fast search active" if ok else "not found — Select-String fallback active"))

    ok, ver = _bin("nvidia-smi")
    checks.append(("nvidia-smi", ok, ver if ok else "not found — gpu_status will return error"))

    try:
        import urllib.request
        base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        urllib.request.urlopen(base + "/api/tags", timeout=2)
        checks.append(("Ollama", True, f"running at {base} — Tier 5 LLM review enabled"))
    except Exception:
        checks.append(("Ollama", False, "not reachable — Tier 5 review disabled (fail-open)"))

    from pskit.config import get_config
    cfg = get_config()
    checks.append(("Allowed root", True, cfg.allowed_root))
    checks.append(("Pool size", True, str(cfg.pool_size)))
    checks.append(("Safety model", True, cfg.safety_model))

    kan = Path(__file__).parent / "kan_model.pt"
    if kan.exists():
        checks.append(("KAN model", True, f"trained weights — {kan.stat().st_size // 1024}KB"))
    else:
        checks.append(("KAN model", False, "no trained weights — heuristic scorer active"))

    if _rich:
        from rich.console import Console
        from rich.table import Table
        t = Table(title="PSKit Doctor", header_style="bold cyan", show_header=True)
        t.add_column("Component", style="bold")
        t.add_column("", width=6)
        t.add_column("Detail")
        for name, ok, detail in checks:
            t.add_row(name, "[green]OK[/]" if ok else "[yellow]WARN[/]", detail)
        Console().print()
        Console().print(t)
        Console().print()
    else:
        print("\nPSKit Doctor\n" + "=" * 50)
        for name, ok, detail in checks:
            print(f"  [{'OK  ' if ok else 'WARN'}] {name}: {detail}")
        print()

    critical_ok = all(ok for n, ok, _ in checks if "pwsh" in n.lower() or n == "git")
    sys.exit(0 if critical_ok else 1)


def _cmd_audit() -> None:
    from pskit.audit import get_audit

    try:
        from rich.console import Console
        from rich.table import Table
        _rich = True
    except ImportError:
        _rich = False

    audit = get_audit()
    entries = audit.tail(50)
    stats = audit.stats()

    if not entries:
        print("No audit entries yet. Commands are logged once the MCP server runs.")
        return

    if _rich:
        from rich.console import Console
        from rich.table import Table
        t = Table(title=f"PSKit Audit (last {len(entries)})", header_style="bold cyan")
        t.add_column("Time", style="dim", width=19)
        t.add_column("Verdict", width=9)
        t.add_column("KAN", width=6)
        t.add_column("ms", width=6)
        t.add_column("Command")
        for e in entries:
            v = e.get("verdict", "")
            c = "green" if v == "safe" else "yellow" if v == "caution" else "red"
            t.add_row(
                e.get("ts", "")[:19].replace("T", " "),
                f"[{c}]{v}[/]",
                f"{e.get('kan', 0):.3f}",
                str(e.get("ms", "")),
                e.get("cmd", "")[:60],
            )
        con = Console()
        con.print()
        con.print(t)
        con.print(
            f"\n  Total: {stats['total']}  Blocked: {stats['blocked']}  "
            f"Avg KAN: {stats['avg_kan_score']:.3f}  Avg ms: {stats['avg_duration_ms']:.0f}\n"
        )
    else:
        for e in entries:
            print(f"[{e.get('ts','')[:19]}] {e.get('verdict',''):8} "
                  f"kan={e.get('kan',0):.3f} {e.get('cmd','')[:60]}")


def _cmd_version() -> None:
    from pskit import __version__
    print(f"pskit {__version__}")


def main() -> None:
    args = sys.argv[1:]
    cmd = args[0] if args else "serve"
    dispatch = {
        "serve":     _cmd_serve,
        "doctor":    _cmd_doctor,
        "audit":     _cmd_audit,
        "version":   _cmd_version,
        "--version": _cmd_version,
        "-v":        _cmd_version,
    }
    dispatch.get(cmd, _cmd_serve)()


if __name__ == "__main__":
    main()
