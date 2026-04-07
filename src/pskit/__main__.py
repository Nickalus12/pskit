"""PSKit CLI — neural-safe PowerShell automation for AI agents.

Usage:
    pskit                  show help (if terminal) or start server (if piped)
    pskit serve            animated startup + MCP server on stdio
    pskit serve --http     MCP server on streamable HTTP
    pskit serve --port N   custom HTTP port
    pskit doctor           live streaming health check
    pskit audit            command audit log with KAN score visualization
    pskit version          print version
    pskit --help / -h      show help screen
"""
from __future__ import annotations

import sys


# ── Shared ────────────────────────────────────────────────────────────────────

def _is_tty() -> bool:
    return hasattr(sys.stderr, "isatty") and sys.stderr.isatty()


def _reconfigure(stream) -> None:
    if hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass


def _console(stderr: bool = False, **kw):
    from rich.console import Console
    _reconfigure(sys.stderr if stderr else sys.stdout)
    return Console(stderr=stderr, legacy_windows=False, highlight=False, **kw)


def _can_unicode(con) -> bool:
    enc = getattr(con, "encoding", None) or ""
    return enc.lower().startswith("utf")


# ── Brand ─────────────────────────────────────────────────────────────────────

_LOGO_UNICODE = r"""
  ██████╗ ███████╗██╗  ██╗██╗████████╗
  ██╔══██╗██╔════╝██║ ██╔╝██║╚══██╔══╝
  ██████╔╝███████╗█████╔╝ ██║   ██║
  ██╔═══╝ ╚════██║██╔═██╗ ██║   ██║
  ██║     ███████║██║  ██╗██║   ██║
  ╚═╝     ╚══════╝╚═╝  ╚═╝╚═╝   ╚═╝"""

_LOGO_ASCII = "  PSKit"


# ── Help ─────────────────────────────────────────────────────────────────────

def _cmd_help() -> None:
    from pskit import __version__
    import rich.box as box
    from rich.align import Align
    from rich.columns import Columns
    from rich.console import Console
    from rich.panel import Panel
    from rich.syntax import Syntax
    from rich.table import Table
    from rich.text import Text

    con = _console()
    uni = _can_unicode(con)

    # ── Logo ──────────────────────────────────────────────────────────────────
    con.print()
    logo = Text(_LOGO_UNICODE if uni else _LOGO_ASCII, style="bold cyan", no_wrap=True)
    con.print(logo)
    con.print(
        f"  [bold white]v{__version__}[/bold white]  "
        "[dim]·[/dim]  "
        "[dim]Neural-safe PowerShell automation for AI agents[/dim]"
    )
    con.print()

    # ── Commands ──────────────────────────────────────────────────────────────
    cmd = Table(show_header=False, box=None, padding=(0, 2), expand=False)
    cmd.add_column("cmd",    style="bold cyan",  no_wrap=True, width=12)
    cmd.add_column("desc",                       no_wrap=False)
    cmd.add_column("hint",   style="dim",        no_wrap=True)

    cmd.add_row("serve",   "Start MCP server on stdio",            "default when piped to a client")
    cmd.add_row("",        "[dim]  --http[/dim]  Streamable HTTP", "[dim]pskit serve --http --port 9000[/dim]")
    cmd.add_row("doctor",  "Live system health check",             "streaming · parallel · ~3s")
    cmd.add_row("audit",   "Command audit log + KAN scores",       "verdicts · score bars · stats")
    cmd.add_row("version", "Print version and exit",               "")

    con.print(Panel(
        cmd,
        title="[bold white]Commands[/bold white]",
        border_style="cyan",
        box=box.ROUNDED,
        padding=(0, 1),
    ))
    con.print()

    # ── Quick start — side by side ────────────────────────────────────────────
    claude_desktop_json = '''{
  "mcpServers": {
    "pskit": {
      "command": "uvx",
      "args": ["pskit-mcp"],
      "env": {
        "PSKIT_ALLOWED_ROOT": "C:\\\\Projects"
      }
    }
  }
}'''

    config_syn = Syntax(
        claude_desktop_json, "json",
        theme="monokai", background_color="default",
        padding=(0, 0),
    )

    qs_left = Table(show_header=False, box=None, padding=(0, 1), expand=False)
    qs_left.add_column("k", style="dim", no_wrap=True, width=17)
    qs_left.add_column("v", style="bold white")
    qs_left.add_row("pip",          "[cyan]pip install pskit-mcp[/cyan]")
    qs_left.add_row("uvx (no venv)", "[cyan]uvx pskit-mcp[/cyan]")
    qs_left.add_row("", "")
    qs_left.add_row("Claude Code",  "[cyan]claude mcp add pskit[/cyan]")
    qs_left.add_row("",             "[dim cyan]  -- uvx pskit-mcp[/dim cyan]")

    left_panel = Panel(
        qs_left,
        title="[bold white]Install & Connect[/bold white]",
        border_style="cyan",
        box=box.ROUNDED,
        padding=(0, 1),
        expand=True,
    )
    right_panel = Panel(
        config_syn,
        title="[bold white]claude_desktop_config.json[/bold white]",
        border_style="dim cyan",
        box=box.ROUNDED,
        padding=(0, 1),
        expand=True,
    )

    con.print(Columns([left_panel, right_panel], equal=True, expand=True))
    con.print()

    # ── Safety pipeline ───────────────────────────────────────────────────────
    if uni:
        pipe = (
            "[green]Cache[/green] [dim]──▶[/dim] "
            "[cyan]KAN Neural[/cyan] [dim](24 features, <1ms) ──▶[/dim] "
            "[yellow]Blocklist[/yellow] [dim]──▶[/dim] "
            "[yellow]Path Guard[/yellow] [dim]──▶[/dim] "
            "[magenta]Gemma LLM[/magenta] [dim](optional, fail-open) ──▶[/dim] "
            "[bold green]Execute[/bold green]"
        )
    else:
        pipe = (
            "[green]Cache[/green] --> "
            "[cyan]KAN Neural[/cyan] --> "
            "[yellow]Blocklist[/yellow] --> "
            "[yellow]Path Guard[/yellow] --> "
            "[magenta]Gemma LLM[/magenta] --> "
            "[bold green]Execute[/bold green]"
        )
    con.print(Panel(
        pipe,
        title="[bold white]5-Tier Safety Pipeline[/bold white]",
        border_style="dim cyan",
        box=box.ROUNDED,
        padding=(0, 1),
    ))
    con.print()

    # ── Stats footer ──────────────────────────────────────────────────────────
    stats = [
        "[cyan]38 tools[/cyan]",
        "[cyan]6 prompts[/cyan]",
        "[cyan]2 resources[/cyan]",
        "[dim]MIT license[/dim]",
        "[dim]github.com/Nickalus12/pskit[/dim]",
    ]
    con.print("  " + "  [dim]·[/dim]  ".join(stats))
    con.print()


# ── Serve ─────────────────────────────────────────────────────────────────────

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
        _serve_stdio()


def _serve_stdio() -> None:
    if _is_tty():
        _startup_animation()
    from pskit.server import mcp
    mcp.run()


def _startup_animation() -> None:
    import time
    import rich.box as box
    from pskit import __version__
    from rich.align import Align
    from rich.panel import Panel
    from rich.progress import (
        BarColumn, Progress, SpinnerColumn,
        TextColumn, TimeElapsedColumn,
    )
    from rich.text import Text

    con = _console(stderr=True)
    uni = _can_unicode(con)

    # Header banner
    con.print()
    con.print(Panel.fit(
        f"[bold cyan]{_LOGO_UNICODE if uni else 'PSKit'}[/bold cyan]\n"
        f"[dim]v{__version__}  ·  Neural-safe PowerShell MCP server[/dim]",
        border_style="cyan",
        box=box.ROUNDED,
        padding=(0, 3),
    ))
    con.print()

    steps = [
        ("KAN neural scorer",   0.20),
        ("PowerShell module",   0.30),
        ("Session pool (1/3)",  0.15),
        ("Session pool (2/3)",  0.15),
        ("Session pool (3/3)",  0.15),
        ("MCP server",          0.10),
    ]

    spinner = "dots2" if uni else "line"
    with Progress(
        SpinnerColumn(spinner_name=spinner, style="cyan"),
        TextColumn("[bold]{task.description:<28}"),
        BarColumn(
            bar_width=30,
            complete_style="cyan",
            finished_style="bold green",
            pulse_style="dim cyan",
        ),
        TextColumn("[dim]{task.fields[note]}[/dim]"),
        TimeElapsedColumn(),
        console=con,
        transient=False,
    ) as progress:
        for desc, duration in steps:
            task = progress.add_task(desc, total=100, note="")
            n = max(10, int(duration * 50))
            for i in range(n):
                progress.update(task, completed=int((i + 1) / n * 100))
                time.sleep(duration / n)
            progress.update(
                task, completed=100,
                description=f"[green]{desc}[/green]",
                note="[green]ready[/green]",
            )

    con.print()
    ready_text = (
        "  [bold green]✓  Ready[/bold green]  "
        "[dim]38 tools  ·  5-tier safety  ·  3 sessions  ·  stdio[/dim]"
    ) if uni else (
        "  [bold green]OK  Ready[/bold green]  "
        "[dim]38 tools  5-tier safety  3 sessions  stdio[/dim]"
    )
    con.print(ready_text)
    con.print()


def _serve_http(port: int = 8000) -> None:
    try:
        import uvicorn
    except ImportError:
        print("uvicorn required: pip install pskit-mcp[http]", file=sys.stderr)
        sys.exit(1)

    from collections.abc import AsyncIterator
    from contextlib import asynccontextmanager

    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
    from pskit.server import mcp as _mcp_server
    from starlette.applications import Starlette
    from starlette.routing import Mount

    if _is_tty():
        _startup_animation()

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
    if _is_tty():
        _console(stderr=True).print(
            f"  [bold cyan]HTTP[/bold cyan]  "
            f"[white]http://0.0.0.0:{port}/mcp[/white]  "
            f"[dim]streamable HTTP transport[/dim]\n"
        )
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


# ── Doctor ────────────────────────────────────────────────────────────────────

def _cmd_doctor() -> None:
    import os
    import subprocess
    import time
    import urllib.request
    from concurrent.futures import ThreadPoolExecutor
    import rich.box as box
    from rich.console import Console
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table

    _reconfigure(sys.stdout)

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

    def check_pwsh()    -> tuple[str, str]:
        s, v = _bin("pwsh"); return ("error", "NOT FOUND — required") if s == "warn" else ("ok", v)
    def check_git()     -> tuple[str, str]:
        s, v = _bin("git"); return ("error", "NOT FOUND — required") if s == "warn" else ("ok", v)
    def check_rg()      -> tuple[str, str]:
        s, v = _bin("rg", "--version")
        if s == "warn": return "warn", "not found — using Select-String fallback"
        ver = v.split()[1] if len(v.split()) > 1 else v
        return "ok", f"{ver} — fast search enabled"
    def check_nvidia()  -> tuple[str, str]:
        s, v = _bin("nvidia-smi"); return ("warn", "not found — gpu_status returns error") if s == "warn" else ("ok", v.split("\n")[0][:55])
    def check_ollama()  -> tuple[str, str]:
        base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        try:
            urllib.request.urlopen(base + "/api/tags", timeout=1.5)
            return "ok", f"running — Tier 5 LLM review enabled"
        except Exception:
            return "warn", "not reachable — Tier 5 disabled (fail-open)"
    def check_root()    -> tuple[str, str]:
        from pskit.config import get_config; return "ok", get_config().allowed_root
    def check_pool()    -> tuple[str, str]:
        from pskit.config import get_config; return "ok", f"{get_config().pool_size} pre-warmed sessions"
    def check_model()   -> tuple[str, str]:
        from pskit.config import get_config; return "ok", get_config().safety_model
    def check_kan()     -> tuple[str, str]:
        from pathlib import Path
        kan = Path(__file__).parent / "kan_model.pt"
        return ("ok", f"trained — {kan.stat().st_size // 1024} KB") if kan.exists() else ("warn", "no trained weights — heuristic active")

    CHECKS = [
        ("pwsh",   "PowerShell 7+",  "Dependencies",   check_pwsh),
        ("git",    "Git",            "Dependencies",   check_git),
        ("rg",     "ripgrep",        "Dependencies",   check_rg),
        ("nvidia", "NVIDIA GPU",     "Dependencies",   check_nvidia),
        ("ollama", "Ollama",         "Services",       check_ollama),
        ("root",   "Allowed root",   "Configuration",  check_root),
        ("pool",   "Session pool",   "Configuration",  check_pool),
        ("model",  "Safety model",   "Configuration",  check_model),
        ("kan",    "KAN model",      "Configuration",  check_kan),
    ]

    try:
        from rich.console import Console
        from rich.live import Live
        _rich = True
    except ImportError:
        _rich = False

    if not _rich:
        for _, label, _, fn in CHECKS:
            s, d = fn()
            print(f"  [{'OK' if s == 'ok' else '!!'}] {label}: {d}")
        sys.exit(0)

    SPIN = "|/-\\"
    con = Console(legacy_windows=False, highlight=False)
    uni = _can_unicode(con)
    results: dict[str, tuple[str, str]] = {k: ("pending", "") for k, *_ in CHECKS}
    start = time.monotonic()

    def build_panel(frame: int = 0) -> Panel:
        spin = SPIN[frame % len(SPIN)]
        t = Table(show_header=False, box=None, padding=(0, 1), expand=False)
        t.add_column("", width=3, no_wrap=True)
        t.add_column("", width=22, no_wrap=True)
        t.add_column("", ratio=1)

        last_group = None
        for key, label, group, _ in CHECKS:
            if group != last_group:
                if last_group is not None:
                    t.add_row("", "", "")
                t.add_row("", f"[bold dim]{group}[/bold dim]", "")
                last_group = group
            status, detail = results[key]
            if status == "pending":
                icon  = f"[bold yellow]{spin}[/bold yellow]"
                lbl   = f"[dim]{label}[/dim]"
                det   = "[dim]checking...[/dim]"
            elif status == "ok":
                icon  = "[bold green]✓[/bold green]" if uni else "[bold green]+[/bold green]"
                lbl   = f"[bold]{label}[/bold]"
                det   = detail
            elif status == "warn":
                icon  = "[bold yellow]⚠[/bold yellow]" if uni else "[bold yellow]![/bold yellow]"
                lbl   = f"[yellow]{label}[/yellow]"
                det   = f"[dim yellow]{detail}[/dim yellow]"
            else:
                icon  = "[bold red]✗[/bold red]" if uni else "[bold red]X[/bold red]"
                lbl   = f"[bold red]{label}[/bold red]"
                det   = f"[red]{detail}[/red]"
            t.add_row(icon, lbl, det)

        elapsed = time.monotonic() - start
        t.add_row("", "", "")
        t.add_row("", "", f"[dim]{elapsed:.1f}s[/dim]")
        return Panel(t, title="[bold white]PSKit Doctor[/bold white]",
                     border_style="cyan", box=box.ROUNDED, padding=(0, 1))

    con.print()
    frame = 0
    with Live(build_panel(frame), console=con, refresh_per_second=12,
              vertical_overflow="visible") as live:
        futures: dict = {}
        with ThreadPoolExecutor(max_workers=6) as pool:
            for key, _, __, fn in CHECKS:
                futures[pool.submit(fn)] = key
            pending = set(futures.values())
            while pending:
                for fut in [f for f in futures if f.done() and futures[f] in pending]:
                    key = futures[fut]
                    try:    results[key] = fut.result()
                    except Exception as e: results[key] = ("warn", str(e)[:55])
                    pending.discard(key)
                frame += 1
                live.update(build_panel(frame))
                time.sleep(0.08)
        live.update(build_panel(frame))

    ok_c   = sum(1 for s, _ in results.values() if s == "ok")
    warn_c = sum(1 for s, _ in results.values() if s == "warn")
    err_c  = sum(1 for s, _ in results.values() if s == "error")
    ms     = int((time.monotonic() - start) * 1000)
    con.print()
    if err_c:
        con.print(f"  [bold red]✗  {err_c} required check(s) failed[/bold red]  [dim]({ok_c} ok · {warn_c} warnings · {ms}ms)[/dim]")
    elif warn_c:
        ok_sym = "✓" if uni else "+"
        con.print(f"  [bold green]{ok_sym}  {ok_c} passed[/bold green]  [dim yellow]⚠ {warn_c} warning(s)  ({ms}ms)[/dim yellow]")
    else:
        ok_sym = "✓" if uni else "+"
        con.print(f"  [bold green]{ok_sym}  All {ok_c} checks passed[/bold green]  [dim]({ms}ms)[/dim]")
    con.print()
    sys.exit(0 if results.get("pwsh", ("error",""))[0] != "error"
             and results.get("git",  ("error",""))[0] != "error" else 1)


# ── Audit ─────────────────────────────────────────────────────────────────────

def _cmd_audit() -> None:
    _reconfigure(sys.stdout)
    import rich.box as box
    from rich.console import Console

    try:
        from rich.columns import Columns
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text
        _rich = True
    except ImportError:
        _rich = False

    from pskit.audit import get_audit
    audit = get_audit()
    entries = audit.tail(50)
    stats = audit.stats()

    if not entries:
        if _rich:
            Console(legacy_windows=False).print(
                "\n  [dim]No audit entries yet.[/dim]  "
                "Run the MCP server and use some tools first.\n"
            )
        else:
            print("\nNo audit entries yet.\n")
        return

    if not _rich:
        for e in entries:
            print(f"[{e.get('ts','')[:19]}] {e.get('verdict',''):8} kan={e.get('kan',0):.3f} {e.get('cmd','')[:60]}")
        return

    con = Console(legacy_windows=False, highlight=False)
    uni = _can_unicode(con)
    BLOCKS = " ▁▂▃▄▅▆▇█" if uni else " .::|||XX"

    def _bar(score: float, width: int = 8) -> str:
        filled = round(score * width)
        b = BLOCKS[-1] * filled + BLOCKS[1] * (width - filled)
        c = "green" if score < 0.3 else "yellow" if score < 0.7 else "red"
        return f"[{c}]{b}[/{c}]"

    con.print()
    con.print(Panel.fit(
        "[bold cyan]PSKit[/bold cyan] [dim]·[/dim] [white]Command Audit Log[/white]",
        border_style="cyan", box=box.ROUNDED, padding=(0, 2),
    ))
    con.print()

    t = Table(show_header=True, header_style="bold dim", box=box.ROUNDED,
              border_style="dim", padding=(0, 1), expand=False)
    t.add_column("Time",    style="dim",   width=19,  no_wrap=True)
    t.add_column("Verdict",               width=9,   no_wrap=True)
    t.add_column("Risk",                  width=10,  no_wrap=True)
    t.add_column("KAN",     justify="right", width=6, no_wrap=True)
    t.add_column("ms",      justify="right", width=6, no_wrap=True)
    t.add_column("Command")

    for e in entries:
        v = e.get("verdict", "")
        vc = {"safe": "green", "caution": "yellow", "blocked": "red"}.get(v, "dim")
        kan = float(e.get("kan", 0.0))
        kc = "green" if kan < 0.3 else "yellow" if kan < 0.7 else "red"
        ok = e.get("ok", True)
        cmd = e.get("cmd", "")[:64]
        t.add_row(
            e.get("ts", "")[:19].replace("T", " "),
            f"[{vc}]{v}[/{vc}]",
            _bar(kan),
            f"[{kc}]{kan:.3f}[/{kc}]",
            str(e.get("ms", "")),
            cmd if ok else f"[dim red]{cmd}[/dim red]",
        )

    con.print(t)
    con.print()

    total   = stats["total"]
    all_e   = audit.tail(total)
    safe_n  = sum(1 for e in all_e if e.get("verdict") == "safe")
    caut_n  = sum(1 for e in all_e if e.get("verdict") == "caution")
    blk_n   = sum(1 for e in all_e if e.get("verdict") == "blocked")

    if total > 0 and uni:
        seg = max(1, round(safe_n / total * 24))
        dist = (
            f"[green]{'█' * seg}[/green]"
            f"[yellow]{'█' * max(0, round(caut_n / total * 24))}[/yellow]"
            f"[red]{'█' * max(0, round(blk_n / total * 24))}[/red]"
        )
    else:
        dist = ""

    con.print(
        f"  {dist}  [dim]"
        f"total [bold]{total}[/bold]  "
        f"safe [green]{safe_n}[/green]  "
        f"caution [yellow]{caut_n}[/yellow]  "
        f"blocked [red]{blk_n}[/red]  "
        f"·  avg KAN [bold]{stats['avg_kan_score']:.3f}[/bold]  "
        f"avg [bold]{stats['avg_duration_ms']:.0f}ms[/bold][/dim]"
    )
    con.print()


# ── Version ───────────────────────────────────────────────────────────────────

def _cmd_version() -> None:
    from pskit import __version__
    _reconfigure(sys.stdout)
    _console().print(
        f"[bold cyan]pskit[/bold cyan] [white]{__version__}[/white]  "
        "[dim]Neural-safe PowerShell MCP server  ·  "
        "github.com/Nickalus12/pskit[/dim]"
    )


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    args = sys.argv[1:]
    cmd = args[0] if args else ""
    if not cmd:
        _cmd_help() if sys.stdout.isatty() else _serve_stdio()
        return
    {
        "serve":     _cmd_serve,
        "doctor":    _cmd_doctor,
        "audit":     _cmd_audit,
        "version":   _cmd_version,
        "--version": _cmd_version,
        "-v":        _cmd_version,
        "--help":    _cmd_help,
        "-h":        _cmd_help,
    }.get(cmd, _cmd_serve)()


if __name__ == "__main__":
    main()
