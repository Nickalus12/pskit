"""PSKit CLI entry point.

Usage:
    pskit                  start MCP server on stdio (default)
    pskit serve            start MCP server on stdio explicitly
    pskit serve --http     start MCP server on streamable HTTP (port 8000)
    pskit serve --port N   use custom HTTP port
    pskit doctor           live system health check with streaming results
    pskit audit            show recent audit log with stats
    pskit version          print version and exit
"""
from __future__ import annotations

import sys


def _cmd_serve() -> None:
    args = sys.argv[2:]
    if "--http" in args:
        port = 8000
        for i, a in enumerate(args):
            if a in ("--port", "-p") and i + 1 < len(args):
                try:
                    port = int(args[i + 1])
                except ValueError:
                    pass
        _serve_http(port)
    else:
        from pskit.server import mcp
        mcp.run()


def _serve_http(port: int = 8000) -> None:
    try:
        import uvicorn
    except ImportError:
        print("uvicorn is required for HTTP mode: pip install pskit-mcp[http]")
        sys.exit(1)

    from collections.abc import AsyncIterator
    from contextlib import asynccontextmanager

    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
    from pskit.server import mcp as _mcp_server
    from starlette.applications import Starlette
    from starlette.routing import Mount

    _app = _mcp_server._get_server()  # type: ignore[attr-defined]
    session_manager = StreamableHTTPSessionManager(app=_app)

    @asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        async with session_manager.run():
            yield

    app = Starlette(
        routes=[Mount("/mcp", app=session_manager.handle_request)],
        lifespan=lifespan,
    )
    print(f"PSKit MCP server listening on http://0.0.0.0:{port}/mcp")
    uvicorn.run(app, host="0.0.0.0", port=port)


def _cmd_doctor() -> None:
    """Live streaming health check — each result appears as it completes."""
    import os
    import subprocess
    import time
    import urllib.request
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from pathlib import Path

    # Force UTF-8 so Rich can render Unicode on Windows Terminal
    import io
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass

    try:
        from rich.console import Console
        from rich.live import Live
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text
        _rich = True
    except ImportError:
        _rich = False

    # ── Individual check functions (run in threads) ─────────────────────────

    def _bin(name: str, flag: str = "--version") -> tuple[str, str]:
        try:
            r = subprocess.run([name, flag], capture_output=True, text=True, timeout=6)
            ver = (r.stdout or r.stderr).strip().split("\n")[0][:55]
            return "ok", ver
        except FileNotFoundError:
            return "warn", "not found"
        except subprocess.TimeoutExpired:
            return "warn", "timed out"
        except Exception as e:
            return "warn", str(e)[:55]

    def check_pwsh() -> tuple[str, str]:
        status, ver = _bin("pwsh")
        if status == "warn":
            return "error", "NOT FOUND — required for all tools"
        return "ok", ver

    def check_git() -> tuple[str, str]:
        status, ver = _bin("git")
        if status == "warn":
            return "error", "NOT FOUND — required for git tools"
        return "ok", ver

    def check_rg() -> tuple[str, str]:
        status, ver = _bin("rg", "--version")
        if status == "warn":
            return "warn", "not found — using Select-String fallback (slower)"
        return "ok", f"{ver.split()[1] if ver.split() else ver} — fast search enabled"

    def check_nvidia() -> tuple[str, str]:
        status, ver = _bin("nvidia-smi")
        if status == "warn":
            return "warn", "not found — gpu_status tool will return error"
        # Extract just the driver version, not the whole table
        line = ver.split("\n")[0][:55]
        return "ok", line

    def check_ollama() -> tuple[str, str]:
        base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        try:
            urllib.request.urlopen(base + "/api/tags", timeout=1.5)
            return "ok", f"running at {base} — Tier 5 LLM review enabled"
        except Exception:
            return "warn", f"not reachable — Tier 5 review disabled (fail-open)"

    def check_config() -> tuple[str, str]:
        from pskit.config import get_config
        cfg = get_config()
        return "ok", cfg.allowed_root

    def check_pool() -> tuple[str, str]:
        from pskit.config import get_config
        cfg = get_config()
        return "ok", f"{cfg.pool_size} pre-warmed sessions"

    def check_safety_model() -> tuple[str, str]:
        from pskit.config import get_config
        cfg = get_config()
        return "ok", cfg.safety_model

    def check_kan() -> tuple[str, str]:
        kan = Path(__file__).parent / "kan_model.pt"
        if kan.exists():
            kb = kan.stat().st_size // 1024
            return "ok", f"trained weights loaded ({kb} KB)"
        return "warn", "no trained weights — heuristic scorer active (still works)"

    # ── Check definitions: (key, label, group, fn) ──────────────────────────

    CHECK_DEFS = [
        ("pwsh",    "PowerShell 7+",  "Dependencies",   check_pwsh),
        ("git",     "Git",            "Dependencies",   check_git),
        ("rg",      "ripgrep",        "Dependencies",   check_rg),
        ("nvidia",  "NVIDIA GPU",     "Dependencies",   check_nvidia),
        ("ollama",  "Ollama",         "Services",       check_ollama),
        ("root",    "Allowed root",   "Configuration",  check_config),
        ("pool",    "Session pool",   "Configuration",  check_pool),
        ("model",   "Safety model",   "Configuration",  check_safety_model),
        ("kan",     "KAN model",      "Configuration",  check_kan),
    ]

    SPINNER_FRAMES = "|/-\\"

    # ── Fallback (no Rich) ───────────────────────────────────────────────────

    if not _rich:
        print("\nPSKit Doctor\n" + "=" * 50)
        for key, label, group, fn in CHECK_DEFS:
            print(f"  checking {label}...", end="", flush=True)
            status, detail = fn()
            sym = "OK  " if status == "ok" else "WARN"
            print(f"\r  [{sym}] {label}: {detail}")
        sys.exit(0)

    # ── Rich live streaming display ──────────────────────────────────────────

    console = Console(legacy_windows=False, highlight=False)
    results: dict[str, tuple[str, str]] = {k: ("pending", "") for k, *_ in CHECK_DEFS}
    start = time.monotonic()

    def build_table(frame: int = 0) -> Table:
        spin = SPINNER_FRAMES[frame % len(SPINNER_FRAMES)]
        t = Table(show_header=False, box=None, padding=(0, 1), expand=False)
        t.add_column("", width=3, no_wrap=True)
        t.add_column("", width=22, no_wrap=True)
        t.add_column("", ratio=1)

        last_group = None
        for key, label, group, _ in CHECK_DEFS:
            if group != last_group:
                if last_group is not None:
                    t.add_row("", "", "")
                t.add_row("", f"[bold dim]{group}[/bold dim]", "")
                last_group = group

            status, detail = results[key]
            if status == "pending":
                icon = f"[bold yellow]{spin}[/bold yellow]"
                label_fmt = f"[dim]{label}[/dim]"
                detail_fmt = "[dim]checking...[/dim]"
            elif status == "ok":
                icon = "[bold green]✓[/bold green]"
                label_fmt = f"[bold]{label}[/bold]"
                detail_fmt = detail
            elif status == "warn":
                icon = "[bold yellow]⚠[/bold yellow]"
                label_fmt = f"[yellow]{label}[/yellow]"
                detail_fmt = f"[dim yellow]{detail}[/dim yellow]"
            else:  # error
                icon = "[bold red]✗[/bold red]"
                label_fmt = f"[bold red]{label}[/bold red]"
                detail_fmt = f"[red]{detail}[/red]"

            t.add_row(icon, label_fmt, detail_fmt)

        elapsed = time.monotonic() - start
        t.add_row("", "", "")
        t.add_row("", "", f"[dim]{elapsed:.1f}s[/dim]")
        return t

    # Banner
    console.print()
    console.print(Panel.fit(
        "[bold cyan]PSKit[/bold cyan] [dim]·[/dim] [white]System Health Check[/white]",
        border_style="dim cyan",
        padding=(0, 2),
    ))
    console.print()

    frame = 0
    with Live(build_table(frame), console=console, refresh_per_second=12,
              vertical_overflow="visible") as live:

        futures = {}
        with ThreadPoolExecutor(max_workers=6) as pool:
            for key, label, group, fn in CHECK_DEFS:
                futures[pool.submit(fn)] = key

            pending = set(futures.values())
            while pending:
                done_futures = {f for f in futures if f.done() and futures[f] in pending}
                for fut in done_futures:
                    key = futures[fut]
                    try:
                        results[key] = fut.result()
                    except Exception as exc:
                        results[key] = ("warn", str(exc)[:55])
                    pending.discard(key)

                frame += 1
                live.update(build_table(frame))
                time.sleep(0.08)

        # Final render — all complete
        live.update(build_table(frame))

    # Summary footer
    ok_count = sum(1 for s, _ in results.values() if s == "ok")
    warn_count = sum(1 for s, _ in results.values() if s == "warn")
    err_count = sum(1 for s, _ in results.values() if s == "error")
    total_ms = int((time.monotonic() - start) * 1000)

    console.print()
    if err_count:
        console.print(
            f"  [bold red]✗[/bold red]  {err_count} required check(s) failed  "
            f"[dim]({ok_count} ok, {warn_count} warnings, {total_ms}ms)[/dim]"
        )
    elif warn_count:
        console.print(
            f"  [bold green]✓[/bold green]  {ok_count} checks passed  "
            f"[dim yellow]⚠ {warn_count} warning(s)  ({total_ms}ms)[/dim yellow]"
        )
    else:
        console.print(
            f"  [bold green]✓[/bold green]  All {ok_count} checks passed  "
            f"[dim]({total_ms}ms)[/dim]"
        )
    console.print()

    critical_ok = results.get("pwsh", ("error", ""))[0] != "error" and \
                  results.get("git", ("error", ""))[0] != "error"
    sys.exit(0 if critical_ok else 1)


def _cmd_audit() -> None:
    import time
    from pskit.audit import get_audit

    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table
        _rich = True
    except ImportError:
        _rich = False

    audit = get_audit()
    entries = audit.tail(50)
    stats = audit.stats()

    if not entries:
        if _rich:
            from rich.console import Console
            Console().print(
                "\n  [dim]No audit entries yet.[/dim]  "
                "Commands are logged once the MCP server runs.\n"
            )
        else:
            print("\nNo audit entries yet. Run pskit and use some tools first.\n")
        return

    if _rich:
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table

        console = Console()
        console.print()
        console.print(Panel.fit(
            "[bold cyan]PSKit[/bold cyan] [dim]·[/dim] [white]Command Audit Log[/white]",
            border_style="dim cyan",
            padding=(0, 2),
        ))
        console.print()

        t = Table(show_header=True, header_style="bold dim", box=None,
                  padding=(0, 2), expand=False)
        t.add_column("Time", style="dim", width=19, no_wrap=True)
        t.add_column("Verdict", width=9, no_wrap=True)
        t.add_column("KAN", width=7, justify="right", no_wrap=True)
        t.add_column("ms", width=6, justify="right", no_wrap=True)
        t.add_column("Command")

        for e in entries:
            v = e.get("verdict", "")
            if v == "safe":
                verdict_fmt = "[green]safe[/green]"
            elif v == "caution":
                verdict_fmt = "[yellow]caution[/yellow]"
            else:
                verdict_fmt = "[bold red]blocked[/bold red]"

            kan = e.get("kan", 0.0)
            kan_color = "green" if kan < 0.3 else "yellow" if kan < 0.7 else "red"
            kan_fmt = f"[{kan_color}]{kan:.3f}[/{kan_color}]"

            ok = e.get("ok", True)
            cmd = e.get("cmd", "")[:62]
            cmd_fmt = cmd if ok else f"[dim red]{cmd}[/dim red]"

            t.add_row(
                e.get("ts", "")[:19].replace("T", " "),
                verdict_fmt,
                kan_fmt,
                str(e.get("ms", "")),
                cmd_fmt,
            )

        console.print(t)
        console.print()

        # Stats bar
        total = stats["total"]
        blocked = stats["blocked"]
        avg_kan = stats["avg_kan_score"]
        avg_ms = stats["avg_duration_ms"]
        console.print(
            f"  [dim]Total [bold]{total}[/bold]"
            f"  ·  Blocked [bold red]{blocked}[/bold red]"
            f"  ·  Avg KAN [bold]{avg_kan:.3f}[/bold]"
            f"  ·  Avg [bold]{avg_ms:.0f}ms[/bold][/dim]"
        )
        console.print()
    else:
        print(f"\nPSKit Audit Log (last {len(entries)})\n")
        for e in entries:
            print(
                f"[{e.get('ts','')[:19]}] {e.get('verdict',''):8} "
                f"kan={e.get('kan',0):.3f} {e.get('cmd','')[:60]}"
            )
        print(f"\nTotal: {stats['total']}  Blocked: {stats['blocked']}\n")


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
