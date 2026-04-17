"""PSKit CLI — neural-safe PowerShell automation for AI agents."""
from __future__ import annotations

import sys

# ── Shared ────────────────────────────────────────────────────────────────────

def _is_tty() -> bool:
    return hasattr(sys.stderr, "isatty") and sys.stderr.isatty()


def _fix_encoding(stream) -> None:
    if hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass


def _con(stderr: bool = False, **kw):
    from rich.console import Console
    _fix_encoding(sys.stderr if stderr else sys.stdout)
    return Console(stderr=stderr, legacy_windows=False, highlight=False, **kw)


def _can_uni(con) -> bool:
    enc = getattr(con, "encoding", None) or ""
    return enc.lower().startswith("utf")


_LOGO = r"""
  ██████╗ ███████╗██╗  ██╗██╗████████╗
  ██╔══██╗██╔════╝██║ ██╔╝██║╚══██╔══╝
  ██████╔╝███████╗█████╔╝ ██║   ██║
  ██╔═══╝ ╚════██║██╔═██╗ ██║   ██║
  ██║     ███████║██║  ██╗██║   ██║
  ╚═╝     ╚══════╝╚═╝  ╚═╝╚═╝   ╚═╝"""


# ── Help ─────────────────────────────────────────────────────────────────────

def _cmd_help() -> None:
    import rich.box as box
    from rich.columns import Columns
    from rich.panel import Panel
    from rich.syntax import Syntax
    from rich.table import Table
    from rich.text import Text

    from pskit import __version__

    con = _con()
    uni = _can_uni(con)

    con.print()
    con.print(Text(_LOGO if uni else "  PSKit", style="bold cyan", no_wrap=True))
    con.print(
        f"  [bold white]v{__version__}[/]  [dim]·  Neural-safe PowerShell automation for AI agents[/]"
    )
    con.print()

    # Commands
    cmd = Table(show_header=False, box=None, padding=(0, 2), expand=False)
    cmd.add_column("", style="bold cyan", no_wrap=True, width=10)
    cmd.add_column("", no_wrap=False)
    cmd.add_column("", style="dim", no_wrap=True)
    cmd.add_row("serve",   "Start MCP server on stdio",           "default when piped to a client")
    cmd.add_row("",        "[dim]  --http[/]  Streamable HTTP",   "[dim]pskit serve --http --port 9000[/]")
    cmd.add_row("doctor",  "Live system health check",            "streaming · parallel · ~3s")
    cmd.add_row("audit",   "Command audit log + KAN scores",      "verdicts · score bars · stats")
    cmd.add_row("version", "Print version",                       "")
    con.print(Panel(cmd, title="[bold]Commands[/]", border_style="cyan",
                    box=box.ROUNDED, padding=(0, 1)))
    con.print()

    # Quick start + JSON config side by side
    qs = Table(show_header=False, box=None, padding=(0, 1), expand=False)
    qs.add_column("", style="dim", no_wrap=True, width=16)
    qs.add_column("", style="bold white")
    qs.add_row("pip",         "[cyan]pip install pskit-mcp[/]")
    qs.add_row("uvx",         "[cyan]uvx pskit-mcp[/]")
    qs.add_row("", "")
    qs.add_row("Claude Code", "[cyan]claude mcp add pskit[/]")
    qs.add_row("",            "[dim cyan]  -- uvx pskit-mcp[/]")

    cfg_json = '{\n  "mcpServers": {\n    "pskit": {\n      "command": "uvx",\n      "args": ["pskit-mcp"],\n      "env": {\n        "PSKIT_ALLOWED_ROOT": "C:\\\\Projects"\n      }\n    }\n  }\n}'
    con.print(Columns([
        Panel(qs,
              title="[bold]Install & Connect[/]",
              border_style="cyan", box=box.ROUNDED, padding=(0, 1), expand=True),
        Panel(Syntax(cfg_json, "json", theme="monokai", background_color="default"),
              title="[bold]claude_desktop_config.json[/]",
              border_style="dim cyan", box=box.ROUNDED, padding=(0, 1), expand=True),
    ], equal=True, expand=True))
    con.print()

    # Safety pipeline
    arr = "[dim]-->[/]" if not uni else "[dim]──>[/]"
    pipe = (f"[green]Cache[/] {arr} [cyan]KAN Neural[/] [dim](24 features, <1ms)[/] {arr} "
            f"[yellow]Blocklist[/] {arr} [yellow]Path Guard[/] {arr} "
            f"[magenta]Gemma LLM[/] [dim](optional)[/] {arr} [bold green]Execute[/]")
    con.print(Panel(pipe, title="[bold]5-Tier Safety Pipeline[/]",
                    border_style="dim cyan", box=box.ROUNDED, padding=(0, 1)))
    con.print()
    con.print("  [dim]38 tools  ·  6 prompts  ·  2 resources  ·  MIT  ·  github.com/Nickalus12/pskit[/]")
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
    from rich.panel import Panel
    from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

    from pskit import __version__

    con = _con(stderr=True)
    uni = _can_uni(con)

    con.print()
    con.print(Panel.fit(
        f"[bold cyan]{_LOGO if uni else 'PSKit'}[/]\n"
        f"[dim]v{__version__}  ·  Neural-safe PowerShell MCP server[/]",
        border_style="cyan", box=box.ROUNDED, padding=(0, 3),
    ))
    con.print()

    steps = [
        ("KAN neural scorer",   0.18),
        ("PowerShell module",   0.28),
        ("Session pool  1/3",   0.14),
        ("Session pool  2/3",   0.14),
        ("Session pool  3/3",   0.14),
        ("MCP transport",       0.10),
    ]

    with Progress(
        SpinnerColumn(spinner_name="dots2" if uni else "line", style="cyan"),
        TextColumn("[bold]{task.description:<26}"),
        BarColumn(bar_width=28, complete_style="cyan", finished_style="bold green",
                  pulse_style="dim cyan"),
        TextColumn("[dim]{task.fields[note]:<8}[/]"),
        TimeElapsedColumn(),
        console=con, transient=False,
    ) as prog:
        for desc, dur in steps:
            t = prog.add_task(desc, total=100, note="")
            n = max(10, int(dur * 60))
            for i in range(n):
                prog.update(t, completed=int((i + 1) / n * 100))
                time.sleep(dur / n)
            prog.update(t, completed=100,
                        description=f"[green]{desc}[/]",
                        note="[green]ready[/]")

    ok = "[bold green]✓[/]" if uni else "[bold green]+[/]"
    con.print()
    con.print(f"  {ok}  [bold white]Ready[/]  [dim]38 tools · 5-tier safety · 3 sessions · stdio[/]")
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
    from starlette.applications import Starlette
    from starlette.routing import Mount

    from pskit.server import mcp as _mcp_server
    if _is_tty():
        _startup_animation()
    _app = _mcp_server._get_server()  # type: ignore[attr-defined]
    session_manager = StreamableHTTPSessionManager(app=_app)

    @asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        async with session_manager.run():
            yield

    app = Starlette(routes=[Mount("/mcp", app=session_manager.handle_request)], lifespan=lifespan)
    if _is_tty():
        _con(stderr=True).print(f"\n  [bold cyan]HTTP[/]  [white]http://0.0.0.0:{port}/mcp[/]  [dim]streamable HTTP[/]\n")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


# ── Doctor ────────────────────────────────────────────────────────────────────

def _cmd_doctor() -> None:
    import os
    import subprocess
    import time
    import urllib.request
    from concurrent.futures import ThreadPoolExecutor

    _fix_encoding(sys.stdout)

    # ── individual checks ─────────────────────────────────────────────────────

    def _bin(name, flag="--version"):
        try:
            r = subprocess.run([name, flag], capture_output=True, text=True, timeout=6)
            return "ok", (r.stdout or r.stderr).strip().split("\n")[0][:55]
        except FileNotFoundError:
            return "warn", "not found"
        except subprocess.TimeoutExpired:
            return "warn", "timed out"
        except Exception as e:
            return "warn", str(e)[:55]

    def chk_pwsh():
        s, v = _bin("pwsh")
        return ("error", "NOT FOUND — required for all tools") if s == "warn" else ("ok", v)

    def chk_git():
        s, v = _bin("git")
        return ("error", "NOT FOUND — required for git tools") if s == "warn" else ("ok", v)

    def chk_rg():
        s, v = _bin("rg", "--version")
        if s == "warn":
            return "warn", "not found — Select-String fallback active"
        ver = v.split()[1] if len(v.split()) > 1 else v
        return "ok", f"{ver}  ·  fast search active"

    def chk_nvidia():
        s, v = _bin("nvidia-smi")
        return ("warn", "not found — gpu_status returns error") if s == "warn" else ("ok", v.split("\n")[0][:52])

    def chk_ollama():
        base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        try:
            urllib.request.urlopen(base + "/api/tags", timeout=1.5)
            return "ok", "running  ·  Tier 5 LLM review active"
        except Exception:
            return "warn", "not reachable  ·  Tier 5 disabled (fail-open)"

    def chk_root():
        from pskit.config import get_config
        return "ok", get_config().allowed_root

    def chk_pool():
        from pskit.config import get_config
        n = get_config().pool_size
        return "ok", f"{n} pre-warmed sessions"

    def chk_model():
        from pskit.config import get_config
        return "ok", get_config().safety_model

    def chk_kan():
        from pathlib import Path
        p = Path(__file__).parent / "kan_model.pt"
        return ("ok", f"trained  ·  {p.stat().st_size // 1024} KB") if p.exists() \
            else ("warn", "no trained weights  ·  heuristic active")

    CHECKS = [
        # (key, label, group, fn, is_required)
        ("pwsh",   "PowerShell 7+",  "Dependencies",   chk_pwsh,   True),
        ("git",    "Git",            "Dependencies",   chk_git,    True),
        ("rg",     "ripgrep",        "Dependencies",   chk_rg,     False),
        ("nvidia", "NVIDIA GPU",     "Dependencies",   chk_nvidia, False),
        ("ollama", "Ollama",         "Services",       chk_ollama, False),
        ("root",   "Allowed root",   "Configuration",  chk_root,   False),
        ("pool",   "Session pool",   "Configuration",  chk_pool,   False),
        ("model",  "Safety model",   "Configuration",  chk_model,  False),
        ("kan",    "KAN model",      "Configuration",  chk_kan,    False),
    ]

    try:
        from rich.console import Console
        from rich.live import Live
        from rich.table import Table
        _rich = True
    except ImportError:
        _rich = False

    if not _rich:
        for _, lbl, _, fn, _ in CHECKS:
            s, d = fn()
            print(f"  [{'OK' if s == 'ok' else '!!'}] {lbl}: {d}")
        sys.exit(0)

    from rich.console import Console
    from rich.live import Live
    from rich.table import Table

    con = Console(legacy_windows=False, highlight=False)
    uni = _can_uni(con)
    results: dict[str, tuple[str, str, float]] = {k: ("pending", "", 0.0) for k, *_ in CHECKS}
    t0 = time.monotonic()
    SPIN = "|/-\\"

    # ── status icons ──────────────────────────────────────────────────────────
    def _icon(status: str) -> str:
        if not uni:
            return {"ok": "[green]+[/]", "warn": "[yellow]![/]", "error": "[red]X[/]", "pending": "[dim].[/]"}[status]
        return {"ok": "[bold green]✓[/]", "warn": "[bold yellow]⚠[/]", "error": "[bold red]✗[/]", "pending": "[dim]·[/]"}[status]

    def build(frame: int = 0) -> Table:
        spin = SPIN[frame % len(SPIN)]
        t = Table(show_header=False, box=None, padding=(0, 0), expand=True, show_edge=False)
        t.add_column("", width=3, no_wrap=True)    # icon
        t.add_column("", width=18, no_wrap=True)   # label
        t.add_column("", ratio=1)                   # detail
        t.add_column("", width=8, no_wrap=True, justify="right")  # timing

        last_group = None
        for key, label, group, _, _ in CHECKS:
            if group != last_group:
                if last_group is not None:
                    t.add_row("", "", "", "")
                # Section header as a rule-style row
                t.add_row(
                    "",
                    f"[bold dim]{group}[/]",
                    "[dim]" + ("─" * 45) + "[/]",
                    "",
                )
                last_group = group

            status, detail, elapsed = results[key]

            if status == "pending":
                icon = f"[yellow]{spin}[/]"
                lbl_fmt = f"[dim]{label}[/]"
                det_fmt = "[dim]checking...[/]"
                tim_fmt = ""
            elif status == "ok":
                icon = _icon("ok")
                lbl_fmt = f"[bold]{label}[/]"
                det_fmt = f"[white]{detail}[/]"
                tim_fmt = f"[dim]{int(elapsed*1000)}ms[/]"
            elif status == "warn":
                icon = _icon("warn")
                lbl_fmt = f"[yellow]{label}[/]"
                det_fmt = f"[dim yellow]{detail}[/]"
                tim_fmt = f"[dim]{int(elapsed*1000)}ms[/]"
            else:
                icon = _icon("error")
                lbl_fmt = f"[bold red]{label}[/]"
                det_fmt = f"[red]{detail}[/]"
                tim_fmt = f"[dim]{int(elapsed*1000)}ms[/]"

            t.add_row(f" {icon}", f" {lbl_fmt}", f"  {det_fmt}", tim_fmt)

        return t

    # ── render loop ───────────────────────────────────────────────────────────
    con.print()
    # Header rule
    from pskit import __version__
    con.rule(f"[bold cyan]PSKit[/] [dim]v{__version__}[/]  [dim]System Health Check[/]",
             style="cyan")
    con.print()

    frame = 0
    with Live(build(frame), console=con, refresh_per_second=15,
              vertical_overflow="visible") as live:
        futures: dict = {}
        with ThreadPoolExecutor(max_workers=6) as pool:
            for key, _, __, fn, _req in CHECKS:
                futures[pool.submit(fn)] = key
            pending = set(futures.values())
            while pending:
                for fut in [f for f in futures if f.done() and futures[f] in pending]:
                    key = futures[fut]
                    elapsed = time.monotonic() - t0
                    try:
                        status, detail = fut.result()
                    except Exception as exc:
                        status, detail = "warn", str(exc)[:55]
                    results[key] = (status, detail, elapsed)
                    pending.discard(key)
                frame += 1
                live.update(build(frame))
                time.sleep(0.07)
        live.update(build(frame))

    # ── summary footer ────────────────────────────────────────────────────────
    ok_c   = sum(1 for s, _, __ in results.values() if s == "ok")
    warn_c = sum(1 for s, _, __ in results.values() if s == "warn")
    err_c  = sum(1 for s, _, __ in results.values() if s == "error")
    total_ms = int((time.monotonic() - t0) * 1000)

    con.print()
    if err_c:
        con.rule(f"[bold red]{_icon('error')}  {err_c} required check(s) failed[/]  [dim]{ok_c} ok · {warn_c} warnings · {total_ms}ms[/]", style="red")
    elif warn_c:
        con.rule(f"[bold green]{_icon('ok')}  {ok_c} passed[/]  [dim yellow]⚠ {warn_c} warning(s) · {total_ms}ms[/]", style="dim")
    else:
        con.rule(f"[bold green]{_icon('ok')}  All {ok_c} checks passed · {total_ms}ms[/]", style="green")
    con.print()

    critical = all(results.get(k, ("error", "", 0.0))[0] != "error" for k in ("pwsh", "git"))
    sys.exit(0 if critical else 1)


# ── Audit ─────────────────────────────────────────────────────────────────────

def _cmd_audit() -> None:
    _fix_encoding(sys.stdout)
    import rich.box as box

    try:
        from rich.columns import Columns  # noqa: F401  availability probe
        from rich.panel import Panel  # noqa: F401  availability probe
        from rich.table import Table  # noqa: F401  availability probe
        from rich.text import Text  # noqa: F401  availability probe
        _rich = True
    except ImportError:
        _rich = False

    from pskit.audit import get_audit
    audit = get_audit()
    entries = audit.tail(50)
    stats = audit.stats()

    if not entries:
        if _rich:
            con = __import__("rich.console", fromlist=["Console"]).Console(legacy_windows=False)
            con.print("\n  [dim]No audit entries yet. Run the server and use some tools first.[/]\n")
        else:
            print("\nNo audit entries yet.\n")
        return

    if not _rich:
        for e in entries:
            print(f"[{e.get('ts','')[:19]}] {e.get('verdict',''):8} kan={e.get('kan',0):.3f} {e.get('cmd','')[:60]}")
        return

    from rich.console import Console
    from rich.table import Table

    con = Console(legacy_windows=False, highlight=False)
    uni = _can_uni(con)
    FULL  = "█" if uni else "#"
    EMPTY = "░" if uni else "."

    def _bar(score: float, w: int = 8) -> str:
        filled = round(score * w)
        bar = FULL * filled + EMPTY * (w - filled)
        c = "green" if score < 0.3 else "yellow" if score < 0.7 else "red"
        return f"[{c}]{bar}[/{c}]"

    from pskit import __version__
    con.print()
    con.rule(f"[bold cyan]PSKit[/] [dim]v{__version__}[/]  [dim]Command Audit Log[/]", style="cyan")
    con.print()

    t = Table(
        show_header=True, header_style="bold dim",
        box=box.SIMPLE_HEAD, border_style="dim",
        padding=(0, 1), expand=False,
        show_edge=True,
    )
    t.add_column("Time",    style="dim", width=19, no_wrap=True)
    t.add_column("Verdict",             width=9,  no_wrap=True)
    t.add_column("Risk",                width=10, no_wrap=True)
    t.add_column("KAN",  justify="right", width=6, no_wrap=True)
    t.add_column("ms",   justify="right", width=6, no_wrap=True)
    t.add_column("Command")

    COLORS = {"safe": "green", "caution": "yellow", "blocked": "bold red"}

    for e in entries:
        v = e.get("verdict", "")
        vc = COLORS.get(v, "dim")
        kan = float(e.get("kan", 0.0))
        kc = "green" if kan < 0.3 else "yellow" if kan < 0.7 else "red"
        ok = e.get("ok", True)
        cmd = e.get("cmd", "")[:65]
        t.add_row(
            e.get("ts", "")[:19].replace("T", " "),
            f"[{vc}]{v}[/{vc}]",
            _bar(kan),
            f"[{kc}]{kan:.3f}[/{kc}]",
            str(e.get("ms", "")),
            cmd if ok else f"[dim red]{cmd}[/]",
        )

    con.print(t)
    con.print()

    # Stats footer with distribution bar
    total  = stats["total"]
    all_e  = audit.tail(total)
    safe_n = sum(1 for e in all_e if e.get("verdict") == "safe")
    caut_n = sum(1 for e in all_e if e.get("verdict") == "caution")
    blk_n  = sum(1 for e in all_e if e.get("verdict") == "blocked")

    if total > 0 and uni:
        W = 24
        dist = (
            f"[green]{'█' * max(1, round(safe_n  / total * W))}[/]"
            f"[yellow]{'█' * max(0, round(caut_n  / total * W))}[/]"
            f"[red]{'█'    * max(0, round(blk_n   / total * W))}[/]"
        )
    else:
        dist = ""

    con.rule(
        f"{dist}  [dim]total [bold]{total}[/]  "
        f"safe [green]{safe_n}[/]  caution [yellow]{caut_n}[/]  blocked [red]{blk_n}[/]  "
        f"·  avg KAN [bold]{stats['avg_kan_score']:.3f}[/]  "
        f"avg [bold]{stats['avg_duration_ms']:.0f}ms[/][/dim]",
        style="dim",
    )
    con.print()


# ── Version ───────────────────────────────────────────────────────────────────

def _cmd_version() -> None:
    from pskit import __version__
    _fix_encoding(sys.stdout)
    _con().print(
        f"[bold cyan]pskit[/] [white]{__version__}[/]  "
        "[dim]Neural-safe PowerShell MCP  ·  github.com/Nickalus12/pskit[/]"
    )


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    args = sys.argv[1:]
    cmd = args[0] if args else ""
    if not cmd:
        _cmd_help() if sys.stdout.isatty() else _serve_stdio()
        return
    {
        "serve": _cmd_serve, "doctor": _cmd_doctor, "audit": _cmd_audit,
        "version": _cmd_version, "--version": _cmd_version, "-v": _cmd_version,
        "--help": _cmd_help, "-h": _cmd_help,
    }.get(cmd, _cmd_serve)()


if __name__ == "__main__":
    main()
