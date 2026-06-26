"""
AIRA Terminal UI
----------------
Rich-powered TUI with live panels, animated status, color themes,
multiline input, autocomplete, and real-time AI suggestions.
Beats Hermes: fully themed, animated, context-aware prompt.
"""

import os
import sys
import json
import platform
from datetime import datetime
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich.table import Table
from rich.live import Live
from rich.spinner import Spinner
from rich.rule import Rule
from rich.syntax import Syntax
from rich import box
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.completion import WordCompleter

AIRA_HOME = Path.home() / ".aira"

# ── THEME SYSTEM ──────────────────────────────────────────────────────────────

THEMES = {
    "retro": {
        "accent":     "#FFD700",
        "accent2":    "#00FF41",
        "bg_panel":   "#0A0F14",
        "dim":        "#4A8A4A",
        "success":    "#00FF41",
        "warning":    "#FFD700",
        "error":      "#FF3333",
        "info":       "#00BFFF",
        "text":       "#00FF41",
        "skill":      "#00FF41",
        "memory":     "#00BFFF",
        "cmd":        "#00FF41",
    },
    "dark": {
        "accent":     "#C84B31",
        "accent2":    "#E8A87C",
        "bg_panel":   "#1C1C1C",
        "dim":        "#888888",
        "success":    "#58D68D",
        "warning":    "#F4D03F",
        "error":      "#EC407A",
        "info":       "#5DADE2",
        "text":       "#FFFFFF",
        "skill":      "#BB8FCE",
        "memory":     "#85C1E9",
        "cmd":        "#82E0AA",
    },
    "light": {
        "accent":     "#C84B31",
        "accent2":    "#D97706",
        "bg_panel":   "#F3F4F6",
        "dim":        "#9CA3AF",
        "success":    "#059669",
        "warning":    "#D97706",
        "error":      "#DC2626",
        "info":       "#2563EB",
        "text":       "#1F2937",
        "skill":      "#7C3AED",
        "memory":     "#1D4ED8",
        "cmd":        "#059669",
    },
    "glass": {
        "accent":     "#FF6B6B",
        "accent2":    "#FFD93D",
        "bg_panel":   "#1A1A2E22",
        "dim":        "#AAAAAA",
        "success":    "#6BCB77",
        "warning":    "#FFD93D",
        "error":      "#FF6B6B",
        "info":       "#4D96FF",
        "text":       "#EAEAEA",
        "skill":      "#C084FC",
        "memory":     "#60A5FA",
        "cmd":        "#34D399",
    },
    "neon": {
        "accent":     "#FF007F",
        "accent2":    "#00E5FF",
        "bg_panel":   "#0A0A0A",
        "dim":        "#555555",
        "success":    "#00FF41",
        "warning":    "#FFFF00",
        "error":      "#FF0055",
        "info":       "#00BFFF",
        "text":       "#F0F0F0",
        "skill":      "#BF00FF",
        "memory":     "#0080FF",
        "cmd":        "#00FF7F",
    },
    "ocean": {
        "accent":     "#E76F51",
        "accent2":    "#F4A261",
        "bg_panel":   "#0F1B2D",
        "dim":        "#7F8C9B",
        "success":    "#2A9D8F",
        "warning":    "#E9C46A",
        "error":      "#E63946",
        "info":       "#457B9D",
        "text":       "#F1FAEE",
        "skill":      "#A8DADC",
        "memory":     "#3498DB",
        "cmd":        "#2ECC71",
    },
}

def load_theme(name: str = None) -> dict:
    """Load a theme by name, falling back to config then dark."""
    if name and name in THEMES:
        return dict(THEMES[name])
    cfg_path = Path.home() / ".aira" / "config.json"
    try:
        cfg = json.loads(cfg_path.read_text())
        saved = cfg.get("theme", "dark")
        if saved in THEMES:
            return dict(THEMES[saved])
    except Exception:
        pass
    return dict(THEMES["retro"])

def set_theme(name: str) -> bool:
    """Save theme preference to config."""
    if name not in THEMES:
        return False
    cfg_path = Path.home() / ".aira" / "config.json"
    try:
        cfg = json.loads(cfg_path.read_text()) if cfg_path.exists() else {}
        cfg["theme"] = name
        cfg_path.write_text(json.dumps(cfg, indent=2))
        return True
    except Exception:
        return False

THEME = load_theme()

console = Console(highlight=False)


# ── BANNER ───────────────────────────────────────────────────────────────────

def print_banner(version: str = "1.0.0", project: str = "AIRA"):
    banner_art = r"""
     █████╗    ██╗   ██████╗     █████╗ 
    ██╔══██╗   ██║   ██╔══██╗   ██╔══██╗
    ███████║   ██║   ██████╔╝   ███████║
    ██╔══██║   ██║   ██╔══██╗   ██╔══██║
    ██║  ██║██╗██║██╗██║  ██║██╗██║  ██║
    ╚═╝  ╚═╝╚═╝╚═╝╚═╝╚═╝  ╚═╝╚═╝╚═╝  ╚═╝
    """
    console.print(f"[bold {THEME['accent']}]{banner_art}[/]")
    console.print(f"  [{THEME['accent']}]A.I.R.A. v{version}[/]")
    console.print(f"  [{THEME['dim']}]AUTONOMOUS INTELLIGENCE & REASONING AGENT[/]")
    console.print()
    # Status badges
    badges = (
        f"  [{THEME['accent']}]▶ Workspace:[/] [{THEME['accent2']}]{project}[/]  "
        f"[{THEME['dim']}]│[/]  [{THEME['info']}]{platform.system()} {platform.machine()}[/]  "
        f"[{THEME['dim']}]│[/]  [{THEME['dim']}]{datetime.now().strftime('%H:%M:%S')}[/]"
    )
    console.print(badges)
    console.print()


def print_help(commands: dict = None):
    if commands is None:
        commands = {}
    table = Table(box=box.SIMPLE, show_header=True, header_style=f"bold {THEME['accent']}", expand=False)
    table.add_column("Command", style=f"{THEME['accent2']}", min_width=22)
    table.add_column("Description", style="white")

    for cmd, desc in commands.items():
        table.add_row(cmd, desc)

    console.print(Panel(table, title=f"[bold {THEME['accent']}]⚡ AIRA Commands[/]",
                        border_style=THEME['accent'], padding=(0, 1)))


def print_ghost_help(commands: dict = None):
    """Show hidden/ghost commands panel."""
    if commands is None:
        commands = {}
    table = Table(box=box.SIMPLE, show_header=True, header_style=f"bold {THEME['warning']}", expand=False)
    table.add_column("Command", style=f"{THEME['warning']}", min_width=26)
    table.add_column("Description", style="white")

    for cmd, desc in commands.items():
        table.add_row(cmd, desc)

    console.print(Panel(
        table,
        title=f"[bold {THEME['warning']}]AIRA Ghost Commands[/]",
        subtitle=f"[{THEME['dim']}]Not shown in /help — power-user commands[/]",
        border_style=THEME['warning'],
        padding=(0, 1),
    ))


# ── PANELS ───────────────────────────────────────────────────────────────────

def print_system_panel(snapshot: dict):
    cpu_bar = _progress_bar(snapshot['cpu_percent'], 100, 20)
    ram_bar = _progress_bar(snapshot['ram_used_percent'], 100, 20)
    disk_bar = _progress_bar(snapshot['disk_used_percent'], 100, 20)

    lines = [
        f"[{THEME['dim']}]OS[/]       [{THEME['info']}]{snapshot['os']}[/]  [{THEME['dim']}]Hostname:[/] {snapshot['hostname']}",
        f"[{THEME['dim']}]Uptime[/]   [{THEME['accent2']}]{snapshot['uptime_hours']}h[/]",
        f"[{THEME['dim']}]CPU[/]      {cpu_bar} [{THEME['accent']}]{snapshot['cpu_percent']}%[/]  [{THEME['dim']}]{snapshot['cpu_cores']} cores[/]",
        f"[{THEME['dim']}]RAM[/]      {ram_bar} [{THEME['accent']}]{snapshot['ram_used_percent']}%[/]  [{THEME['dim']}]{snapshot['ram_available_gb']}GB free[/]",
        f"[{THEME['dim']}]Disk[/]     {disk_bar} [{THEME['accent']}]{snapshot['disk_used_percent']}%[/]  [{THEME['dim']}]{snapshot['disk_free_gb']}GB free[/]",
        f"[{THEME['dim']}]CWD[/]      [{THEME['accent2']}]{snapshot['cwd']}[/]",
    ]

    if snapshot.get('top_processes'):
        lines.append("")
        lines.append(f"[{THEME['dim']}]Top Processes:[/]")
        for p in snapshot['top_processes'][:3]:
            lines.append(f"  [{THEME['cmd']}]{p['name'][:18]:<18}[/] CPU [{THEME['accent']}]{p['cpu']:5.1f}%[/]  MEM [{THEME['info']}]{p['mem']:4.1f}%[/]")

    console.print(Panel("\n".join(lines), title=f"[bold {THEME['accent']}]⚙ System Status[/]",
                        border_style=THEME['bg_panel'], padding=(0, 1)))


def print_memory_panel(memories: list):
    if not memories:
        console.print(f"[{THEME['dim']}]No memories stored yet. Chat with AIRA to build memory.[/]")
        return

    table = Table(box=box.SIMPLE_HEAD, show_header=True, header_style=f"bold {THEME['memory']}", expand=True)
    table.add_column("ID", style=THEME['dim'], width=4)
    table.add_column("Project", style=THEME['accent2'], width=12)
    table.add_column("Pri", style=THEME['accent'], width=3)
    table.add_column("Content", style="white")
    table.add_column("Tags", style=THEME['dim'], width=16)

    for m in memories:
        pri_star = "★" * m.get('priority', 1)
        table.add_row(str(m['id']), m.get('project', 'AIRA'), pri_star,
                      m['content'][:80], m.get('tags', ''))

    console.print(Panel(table, title=f"[bold {THEME['memory']}]🧠 Memories ({len(memories)})[/]",
                        border_style=THEME['memory'], padding=(0, 0)))


def print_skills_panel(skills: list):
    if not skills:
        console.print(f"[{THEME['dim']}]No skills evolved yet. Solve complex tasks to auto-generate skills.[/]")
        return

    table = Table(box=box.SIMPLE_HEAD, show_header=True, header_style=f"bold {THEME['skill']}", expand=True)
    table.add_column("Skill", style=THEME['accent2'], width=24)
    table.add_column("Description", style="white")
    table.add_column("Used", style=THEME['dim'], width=5)
    table.add_column("Success", style=THEME['success'], width=8)

    for s in skills:
        success_pct = f"{s['success_rate']*100:.0f}%"
        table.add_row(s['name'], s['description'][:55], str(s['use_count']), success_pct)

    console.print(Panel(table, title=f"[bold {THEME['skill']}]⚡ Evolved Skills ({len(skills)})[/]",
                        border_style=THEME['skill'], padding=(0, 0)))


def print_sessions_panel(sessions: list):
    if not sessions:
        console.print(f"[{THEME['dim']}]No session history yet.[/]")
        return
    table = Table(box=box.SIMPLE_HEAD, show_header=True, header_style=f"bold {THEME['info']}", expand=True)
    table.add_column("ID", style=THEME['dim'], width=4)
    table.add_column("Project", style=THEME['accent2'], width=12)
    table.add_column("Messages", style=THEME['accent'], width=8)
    table.add_column("Summary", style="white")
    table.add_column("Started", style=THEME['dim'], width=16)

    for s in sessions:
        table.add_row(str(s['id']), s.get('project', 'AIRA'),
                      str(s.get('message_count', 0)),
                      (s.get('summary') or 'In progress')[:50],
                      (s.get('started_at') or '')[:16])

    console.print(Panel(table, title=f"[bold {THEME['info']}]📋 Session History[/]",
                        border_style=THEME['info'], padding=(0, 0)))


def print_search_results(results: list, query: str):
    if not results:
        console.print(f"[{THEME['error']}]No results for:[/] {query}")
        return
    console.print(f"\n[bold {THEME['accent']}]🔍 Search:[/] [{THEME['accent2']}]{query}[/]\n")
    for i, r in enumerate(results, 1):
        console.print(f"[{THEME['dim']}]{i}.[/] [bold {THEME['info']}]{r['title'][:70]}[/]")
        console.print(f"   {r['snippet'][:160]}")
        if r.get('url'):
            console.print(f"   [{THEME['dim']}]{r['url']}[/]")
        console.print()


def print_cmd_result(result: dict):
    status_color = THEME['success'] if result['success'] else THEME['error']
    status_icon = "✓" if result['success'] else "✗"
    header = f"[{status_color}]{status_icon}[/] [{THEME['dim']}]$ {result['cmd']}[/]  [{THEME['dim']}]{result['elapsed']:.2f}s  rc={result['returncode']}[/]"
    console.print(header)
    if result['stdout'].strip():
        console.print(Syntax(result['stdout'].strip(), "bash", theme="monokai", background_color="default", line_numbers=False))
    if result['stderr'].strip():
        console.print(f"[{THEME['error']}]{result['stderr'].strip()}[/]")


def print_ai_response(text: str):
    if not text.strip():
        return
    console.print(f"\n[bold {THEME['accent']}]◈ AIRA[/]  [{THEME['dim']}]{datetime.now().strftime('%H:%M:%S')}[/]")
    console.print(text)
    console.print()


def print_directive_notice(kind: str, detail: str):
    icons = {
        "memory": ("🧠", THEME['memory']),
        "skill":  ("⚡", THEME['skill']),
        "cmd":    ("⚙", THEME['cmd']),
        "search": ("🔍", THEME['info']),
        "subagent":("🤖", THEME['accent2']),
        "schedule":("⏰", THEME['warning']),
    }
    icon, color = icons.get(kind, ("•", THEME['dim']))
    console.print(f"  [{color}]{icon} {kind.upper()}:[/] [{THEME['dim']}]{detail}[/]")


def _progress_bar(value: float, total: float, width: int = 20) -> str:
    filled = int((value / total) * width)
    color = THEME['success']
    if value > 80:
        color = THEME['error']
    elif value > 60:
        color = THEME['warning']
    bar = "█" * filled + "░" * (width - filled)
    return f"[{color}]{bar}[/]"


# ── PROMPT SESSION ────────────────────────────────────────────────────────────

def build_prompt_session(project: str = "AIRA", commands: list = None) -> PromptSession:
    AIRA_HOME.mkdir(exist_ok=True)
    history_file = AIRA_HOME / "history.txt"

    style = Style.from_dict({
        'prompt':         f"{THEME.get('accent', '#FFD700')} bold",
        'project':        f"{THEME.get('accent2', '#00FF41')}",
        'path':           f"{THEME.get('dim', '#4A8A4A')}",
        '':               f"{THEME.get('text', '#00FF41')}",
        'cpu':            '#ffd700 bold',
        'ram':            '#00ff41 bold',
        'disk':           '#00bfff bold',
        'sep':            '#4a8a4a',
    })

    completer = None
    if commands:
        completer = WordCompleter(commands, ignore_case=True, sentence=True)

    return PromptSession(
        history=FileHistory(str(history_file)),
        auto_suggest=AutoSuggestFromHistory(),
        completer=completer,
        style=style,
        mouse_support=False,
        wrap_lines=True,
    )


def get_prompt_text(project: str, cwd: str) -> HTML:
    from aira.tools import overlay_data
    short_cwd = cwd.replace(str(Path.home()), "~")
    if len(short_cwd) > 30:
        short_cwd = "…" + short_cwd[-27:]

    try:
        res = overlay_data()
        res_str = (
            f'<span class="cpu">[CPU:{res["cpu"]}</span>'
            f'<span class="sep"> | </span>'
            f'<span class="ram">RAM:{res["ram"]}</span>'
            f'<span class="sep"> | </span>'
            f'<span class="disk">Disk:{res["disk"]}]</span> '
        )
    except Exception:
        res_str = ""

    return HTML(
        f'{res_str}'
        f'<hit style="class:path">{short_cwd}</hit> '
        f'<hit style="class:project">[{project}]</hit> '
        f'<hit style="class:prompt">◈ </hit>'
    )


def spinner_context(message: str):
    """Return a Rich Live spinner context."""
    return Live(
        Spinner("dots", text=f"[{THEME['dim']}]{message}[/]", style=THEME['accent']),
        console=console,
        refresh_per_second=12,
        transient=True
    )
