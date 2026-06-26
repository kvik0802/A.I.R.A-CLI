"""
AIRA Terminal — Main Loop
--------------------------
The core CLI agent loop: handles all commands, AI conversation,
directive execution, subagent spawning, skill evolution, and session management.
"""

import os
import sys
import json
import re
import platform
import subprocess
from pathlib import Path
from datetime import datetime

from aira import __version__
from aira.memory import (
    init_storage, save_memory, search_memory, get_all_memories,
    delete_memory, save_skill, get_skill, list_skills,
    start_session, end_session, get_recent_sessions,
    save_project, list_projects,
    save_custom_agent, get_custom_agent, list_custom_agents, delete_custom_agent
)
from aira.brain import (
    init_client, get_ai_response, parse_ai_directives,
    run_subagent, auto_generate_skill_from_conversation,
    fetch_models, AGENTS, AGENT_NAMES,
    PROVIDER_NAMES, PROVIDER_HELP, PROVIDER_MODELS, PROVIDER_REGISTRY,
    set_task_route, TASK_ROUTES,
    get_usage, reset_usage, estimate_cost,
)
from aira.tools import (
    execute_command, get_system_snapshot, get_network_info,
    web_search, fetch_url, read_file, write_file,
    list_directory, copy_to_clipboard, read_clipboard,
    save_schedule, load_schedules, delete_schedule, toggle_schedule,
    get_scheduler_log, init_scheduler,
    scan_directory, generate_project,
    start_http_server, stop_http_server, start_web_tunnel, stop_web_tunnel, list_tunnel_providers, search_files, list_processes,
    calculate, generate_password, format_json,
    cloud_aws, cloud_gcp, cloud_azure,
    discover_tests, run_pytest,
    get_sandbox_mode, set_sandbox_mode, execute_command_sandboxed,
    sandbox_check, sandbox_providers,
    generate_docs,
    analyze_image,
    fetch_template_index, install_template,
    diff_text, rich_diff, parse_diff, apply_hunk, apply_diff_hunk,
    save_checkpoint, restore_checkpoint, list_checkpoints,
    analyze_error, overlay_data,
    list_todos, todo_add, todo_done, todo_delete, todo_clear,
)
from aira.memory import (
    add_knowledge_edge, get_linked_memories, graph_search, auto_link_memories
)
from aira.ui import (
    console, print_banner, print_help, print_ghost_help,
    print_system_panel, print_memory_panel, print_skills_panel,
    print_sessions_panel, print_search_results, print_cmd_result,
    print_ai_response, print_directive_notice,
    build_prompt_session, get_prompt_text, spinner_context,
    THEME, THEMES
)
from aira.dashboard import dashboard_start, dashboard_stop
from aira.miro import (
    miro_list_projects, miro_create_project, miro_delete_project,
    miro_add_task, miro_move, miro_add_dep, miro_get_board, miro_decompose
)
from aira.gateway import (
    gateway_status, gateway_connect, gateway_disconnect,
    gateway_set_config, gateway_get_config, gateway_validate_token,
    set_message_handler
)
from aira.mcp_tools import (
    MCP_AVAILABLE, MCP_PRESETS, mcp_list_servers, mcp_add_server,
    mcp_remove_server, mcp_list_tools, mcp_call_tool,
    mcp_enable_preset, mcp_discover
)
from aira.plugins import (
    get_plugin_commands, handle_plugin_command,
    list_plugin_categories, search_plugins, get_plugin_info,
    PLUGINS
)
import requests
from rich.rule import Rule
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.tree import Tree
from rich.syntax import Syntax
from prompt_toolkit.formatted_text import HTML
AIRA_HOME = Path.home() / ".aira"
CONFIG_FILE = AIRA_HOME / "config.json"

# ── COMMANDS ──────────────────────────────────────────────────────────────────

COMMANDS = {
    "/help": "Show commands (use /AIRAghost for hidden panel)",
    "/clear": "Clear terminal",
    "/reset": "Reset conversation",
    "/exit": "Exit AIRA",
}

GHOST_COMMANDS = {
    "/forge <description>": "Autonomous project builder — AI creates files on Desktop",
    "/auto <task>": "Autonomous task mode — AI executes end-to-end without prompts",
    "/pulse": "Rich system pulse panel (CPU, RAM, disk, network)",
    "/forget <memory_id>": "Delete a stored memory by ID",
    "/genpass [length]": "Generate password and copy to clipboard",
    "/plugin list|search|info": "Browse and inspect the plugin system",
    "/quit, /q": "Exit aliases (same as /exit)",
    "/github": "Alias for /gh GitHub CLI wrapper",
    "/aws, /gcp, /azure": "Cloud shortcuts (also: /cloud aws ...)",
    "/vision <img> [prompt]": "Analyze image with AI vision",
    "/template": "Template marketplace (list/install)",
    "/doc generate": "Auto-generate docs from source AST",
    "/gateway": "Multi-platform bot gateway (telegram/discord/slack/signal)",
    "/mcp": "MCP server management (list/add/remove/tools/call)",
    "/miro": "Project kanban board (todo/doing/done with dependencies)",
    "/dashboard": "Start/stop local web dashboard",
    "/web [port|tunnel|local|stop]": "Start memory graph (add 'tunnel' for public URL)",
    "/serve [port|tunnel|local|stop]": "Alias for /web graph server",
    "/memory [query]": "List or search memories",
    "/remember <text>": "Save a memory",
    "/graph": "Knowledge graph search & link",
    "/subagent <task>": "Spawn an AI subagent",
    "/agent [name]": "List or spawn specialized agents",
    "/agent create <name> <desc>": "Create a custom agent",
    "/run <cmd>": "Execute a shell command",
    "/run --heal <cmd>": "Run command and auto-fix on failure",
    "/search <query>": "Web search",
    "/vault": "Encrypted credential store",
    "/gh <args>": "GitHub CLI wrapper",
    "/docker <args>": "Docker CLI wrapper with rich tables",
    "/cloud": "Cloud provider CLI wrappers (aws/gcp/azure)",
    "/test": "Test runner (discover & execute pytest)",
    "/sandbox on|off": "Toggle sandboxed execution (Docker/Daytona/Modal)",
    "/skills": "List evolved skills",
    "/skill <name>": "Show skill details",
    "/cron add/del/log": "Cron task scheduler",
    "/rollback <id>": "Restore from snapshot",
    "/config": "Show configuration",
    "/doctor": "Run self-diagnostics & health checks",
    "/cost": "Show estimated cost for this session",
    "/todo [add|done|del|clear]": "Task list manager (per project)",
    "/usage": "Show token usage for this session",
    "/diff [file]": "Show colored git diff of current changes",
    "/patch <file> [diff]": "Interactive hunk-by-hunk patch apply",
    "/overlay": "Toggle live resource monitor panel",
    "/scan [path]": "Scan directory tree with sizes & counts",
    "/build <type> <name>": "Generate project (33 types)",
    "/explore [path]": "Show file tree (depth 2)",
    "/sys": "System status snapshot",
    "/net": "Network info & public IP",
    "/weather": "Weather real-time data of your place",
    "/ls [path]": "List directory contents",
    "/read <file>": "Read file into context",
    "/copy <text>": "Copy text to clipboard",
    "/project <name>": "Switch active project",
    "/projects": "List all projects",
    "/sessions": "View recent sessions",
    "/schedule": "View scheduled tasks",
    "/history [pattern]": "Fuzzy search command history",
    "/snapshot": "Create/list directory snapshots",
    "/api": "Change AI provider, API key, and model",
    "/recap": "Instant session recap (no LLM call)",
    "/undo": "Undo last agent action (files + conversation)",
}

# ── CONFIG ────────────────────────────────────────────────────────────────────

def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_config(cfg: dict):
    AIRA_HOME.mkdir(exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(cfg, f, indent=2)


def setup_wizard():
    """First-run setup: provider, API key, project, preferences."""
    console.print(Panel(
        f"[bold {THEME['accent']}]Welcome to AIRA Terminal[/]\n"
        f"[{THEME['dim']}]Let's configure your agent.[/]",
        border_style=THEME['accent']
    ))

    # Provider selection
    console.print(f"\n[{THEME['accent2']}]Available AI Providers:[/]")
    for i, name in enumerate(PROVIDER_NAMES, 1):
        console.print(f"  [{THEME['accent']}]{i}.[/] [{THEME['info']}]{name.title()}[/]  [dim](key format: {PROVIDER_HELP[name]})[/]")

    provider_idx = 0
    while not (1 <= provider_idx <= len(PROVIDER_NAMES)):
        try:
            provider_idx = int(console.input(f"\n[{THEME['accent2']}]Select provider [1-{len(PROVIDER_NAMES)}][/] [dim](default: 1)[/]: ").strip() or "1")
        except ValueError:
            provider_idx = 0

    provider = PROVIDER_NAMES[provider_idx - 1]
    key_hint = PROVIDER_HELP[provider]

    api_key = ""
    while not api_key.strip():
        api_key = console.input(f"[{THEME['accent2']}]API Key[/] ({key_hint}): ").strip()
        if not api_key.strip():
            console.print(f"[{THEME['error']}]API key cannot be empty.[/]")

    # Fetch available models from provider's API
    default_model = PROVIDER_REGISTRY[provider]["default_model"]
    console.print(f"\n[{THEME['dim']}]Fetching available models from {provider.title()}...[/]")
    models = fetch_models(provider, api_key)

    if models:
        console.print(f"\n[{THEME['accent2']}]Available models for {provider.title()}:[/]")
        for i, m in enumerate(models, 1):
            tier_tag = f"[bold {THEME['success']}]FREE[/]" if m["tier"] == "free" else f"[{THEME['warning']}]PAID[/]"
            default_tag = f" [{THEME['dim']}](default)[/]" if m["id"] == default_model else ""
            desc = f" — {m['desc']}" if m.get("desc") else ""
            console.print(f"  [{THEME['accent']}]{i:2}.[/] {tier_tag} [{THEME['info']}]{m['name']}[/][dim]{desc}{default_tag}[/]")

        model_input = console.input(f"\n[{THEME['accent2']}]Select model [1-{len(models)}][/] [dim](press Enter for default '{default_model}'): [/]").strip()
        if model_input.isdigit() and 1 <= int(model_input) <= len(models):
            model = models[int(model_input) - 1]["id"]
        else:
            model = default_model
    else:
        model = console.input(f"[{THEME['accent2']}]Model ID[/] [dim](press Enter for '{default_model}'): [/]").strip()
        if not model:
            model = default_model

    default_project = console.input(f"[{THEME['accent2']}]Default project name[/] [dim](press Enter for 'AIRA')[/]: ").strip()
    if not default_project:
        default_project = "AIRA"

    cfg = {
        "provider": provider,
        "api_key": api_key,
        "model": model,
        "default_project": default_project,
        "auto_skill": True,
        "auto_memory": True,
        "show_directives": True,
        "setup_done": True,
        "created_at": datetime.now().isoformat()
    }
    save_config(cfg)
    console.print(f"\n[{THEME['success']}]✓ AIRA configured ({provider}). Starting agent...[/]\n")
    return cfg


# ── DIRECTIVE EXECUTOR ────────────────────────────────────────────────────────

def run_agent_chain(agent_chain: list, conversation: list, cfg: dict, current_project: str, api_key: str):
    """Execute a chain of agents in parallel, all working simultaneously."""
    from aira.brain import AGENTS, get_ai_response
    import threading
    from queue import Queue

    # Get the last user message
    user_messages = [m for m in conversation if m.get("role") == "user"]
    if not user_messages:
        console.print(f"[{THEME['error']}]No user message to process[/]")
        return
    last_user_msg = user_messages[-1]["content"]

    # Queue to collect results
    results = Queue()
    threads = []

    console.print(f"\n  [{THEME['accent']}]🚀 Starting {len(agent_chain)} agents in parallel...[/]\n")

    def run_agent(agent_name, queue):
        """Run a single agent and put result in queue."""
        agent_info = AGENTS.get(agent_name)
        if not agent_info:
            queue.put({"agent": agent_name, "error": f"Unknown agent"})
            return

        try:
            agent_system = f"You are {agent_info['name']}. {agent_info['system']}"
            response = get_ai_response(
                [{"role": "user", "content": last_user_msg}],
                current_project=current_project,
                custom_system=agent_system
            )
            queue.put({"agent": agent_name, "name": agent_info['name'], "response": response, "info": agent_info})
        except Exception as e:
            queue.put({"agent": agent_name, "error": str(e)})

    # Start all agents in parallel
    for agent_name in agent_chain:
        agent_info = AGENTS.get(agent_name)
        if agent_info:
            console.print(f"  [{THEME['accent']}]🤖 {agent_info['name']} ({agent_name})[/] - [{THEME['dim']}]{agent_info['description']}[/]")
            t = threading.Thread(target=run_agent, args=(agent_name, results))
            t.start()
            threads.append(t)

    # Wait for all agents to complete
    for t in threads:
        t.join()

    console.print(f"\n  [{THEME['success']}]✓ All agents completed[/]\n")

    # Process results
    while not results.empty():
        result = results.get()
        if "error" in result:
            console.print(f"  [{THEME['error']}]✗ {result['agent']}: {result['error']}[/]")
        else:
            console.print(f"  [{THEME['accent2']}]📋 {result['name']} output:[/]")
            console.print(f"  [{THEME['dim']}]{result['response'][:300]}...[/]\n")

            # Execute directives from this agent
            from aira.brain import parse_ai_directives
            directives = parse_ai_directives(result['response'])
            if any([directives["commands"], directives["memories"], directives["skills"]]):
                console.print(f"  [{THEME['accent']}]Executing directives from {result['name']}...[/]")
                execute_directives(directives, cfg, current_project, conversation)


def execute_directives(directives: dict, cfg: dict, current_project: str, conversation: list = None):
    """Process all AI directives: commands, memories, skills, subagents, searches."""
    import re as _re

    show = cfg.get("show_directives", True)
    api_key = cfg.get("api_key", "")

    if conversation is not None and directives.get("commands"):
        try:
            save_checkpoint(conversation)
        except Exception:
            pass

    # Track CWD across commands (fixes cd not persisting)
    current_cwd = os.getcwd()

    def _update_cwd(cmd: str, prev_cwd: str) -> str:
        """Extract directory changes from cd/mkdir commands."""
        # Match: cd <dir>, cd <dir> && ..., mkdir <dir> && cd <dir>, md <dir> && cd <dir>
        m = _re.search(r'(?:^|\|\||&&)\s*cd\s+(.+?)(?:\s*$|\s*&&|\s*\|\|)', cmd, _re.IGNORECASE)
        if not m:
            m = _re.search(r'(?:^|\|\||&&)\s*cd\s+(.+?)\s*$', cmd, _re.IGNORECASE)
        if m:
            target = m.group(1).strip().strip('"').strip("'")
            p = Path(target)
            if not p.is_absolute():
                p = Path(prev_cwd) / p
            if p.exists() and p.is_dir():
                return str(p.resolve())
            # Mkdir case: directory was just created by the command
            parent = Path(prev_cwd)
            if not p.is_absolute():
                p = parent / target
            return str(p.resolve())
        return prev_cwd

    # Execute shell commands
    for cmd in directives.get("commands", []):
        if show:
            print_directive_notice("cmd", cmd)

        current_cwd = _update_cwd(cmd, current_cwd)
        result = execute_command(cmd, cwd=current_cwd)
        print_cmd_result(result)

    # Save memories
    for mem in directives.get("memories", []):
        save_memory(
            content=mem["content"],
            project=mem.get("project", current_project),
            tags=mem.get("tags", []),
            priority=mem.get("priority", 1),
            source="aira"
        )
        if show:
            print_directive_notice("memory", mem["content"][:60])

    # Save skills
    for skill in directives.get("skills", []):
        save_skill(skill["name"], skill["description"], skill["steps"])
        if show:
            print_directive_notice("skill", f"{skill['name']} — {skill['description'][:50]}")

    # Web searches
    for query in directives.get("web_searches", []):
        if show:
            print_directive_notice("search", query)
        results = web_search(query)
        print_search_results(results, query)

    # Subagents
    for sa in directives.get("subagents", []):
        if show:
            print_directive_notice("subagent", sa["task"])
        with spinner_context(f"Subagent: {sa['task'][:50]}"):
            result = run_subagent(sa["task"], sa["context"], api_key, provider=cfg.get("provider", "anthropic"))
        console.print(f"  [{THEME['accent2']}]Subagent result:[/] {result[:300]}")

    # Agent chains
    for agent_chain in directives.get("agent_chains", []):
        if show:
            print_directive_notice("agent_chain", f" → ".join(agent_chain))
        run_agent_chain(agent_chain, conversation, cfg, current_project, api_key)

    # Schedules
    for sc in directives.get("schedules", []):
        save_schedule(sc["cron"], sc["task"])
        if show:
            print_directive_notice("schedule", f"[{sc['cron']}] {sc['task']}")


# ── COMMAND HANDLERS ──────────────────────────────────────────────────────────

def handle_command(inp: str, cfg: dict, current_project: list, conversation: list, session_id: int) -> bool:
    """
    Handle /commands. Returns False to exit, True to continue.
    current_project is a list[str] so we can mutate it in-place.
    """
    parts = inp.strip().split(None, 1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    # ── /exit ──
    if cmd in ("/exit", "/quit", "/q"):
        _shutdown(conversation, session_id, cfg, current_project[0])
        return False

    # ── /help ──
    elif cmd == "/help":
        print_help(COMMANDS)
        console.print(
            f"  [{THEME['dim']}]Ghost commands:[/] [{THEME['warning']}]/AIRAghost[/]"
        )

    # ── /AIRAghost ──
    elif cmd in ("/airaghost", "/aira-ghost"):
        print_ghost_help(GHOST_COMMANDS)

    # ── /clear ──
    elif cmd == "/clear":
        os.system("cls" if platform.system() == "Windows" else "clear")
        print_banner(__version__, current_project[0])

    # ── /reset ──
    elif cmd == "/reset":
        conversation.clear()
        console.print(f"[{THEME['success']}]✓ Conversation context reset.[/]")

    # ── /sys ──
    elif cmd == "/sys":
        with spinner_context("Collecting system info..."):
            snap = get_system_snapshot()
        print_system_panel(snap)

    # ── /net ──
    elif cmd == "/net":
        with spinner_context("Checking network..."):
            net = get_network_info()
        console.print(f"[bold {THEME['info']}]Network Info[/]")
        console.print(f"  Public IP: [{THEME['accent2']}]{net['public_ip']}[/]")
        for iface, addrs in net['interfaces'].items():
            if addrs:
                console.print(f"  [{THEME['dim']}]{iface}:[/] {', '.join(addrs)}")

    # ── /weather ──
    elif cmd == "/weather":
        location = arg or "Hyderabad"
        with spinner_context(f"Getting weather for {location}..."):
            results = web_search(f"weather {location} today live")
        if results:
            console.print(f"[bold {THEME['info']}]Weather for {location}[/]")
            for r in results[:3]:
                console.print(f"  [{THEME['accent2']}]{r.get('title', '')}[/]")
                console.print(f"  [{THEME['dim']}]{r.get('snippet', '')[:200]}[/]")
        else:
            console.print(f"[{THEME['error']}]Could not fetch weather data[/]")

    # ── /memory ──
    elif cmd == "/memory":
        if arg:
            results = search_memory(arg, project=current_project[0] if current_project[0] != "AIRA" else None)
            console.print(f"[{THEME['dim']}]Search results for:[/] [{THEME['accent2']}]{arg}[/]")
            print_memory_panel(results)
        else:
            mems = get_all_memories(limit=30)
            print_memory_panel(mems)

    # ── /remember ──
    elif cmd == "/remember":
        if arg:
            save_memory(arg, project=current_project[0], source="user", priority=2)
            console.print(f"[{THEME['success']}]✓ Saved to memory:[/] {arg[:60]}")
        else:
            console.print(f"[{THEME['error']}]Usage: /remember <text to remember>[/]")

    # ── /forget ──
    elif cmd == "/forget":
        try:
            mid = int(arg)
            delete_memory(mid)
            console.print(f"[{THEME['success']}]✓ Memory #{mid} deleted.[/]")
        except ValueError:
            console.print(f"[{THEME['error']}]Usage: /forget <memory_id>[/]")

    # ── /skills ──
    elif cmd == "/skills":
        skills = list_skills()
        print_skills_panel(skills)

    # ── /skill ──
    elif cmd == "/skill":
        if not arg:
            console.print(f"[{THEME['error']}]Usage: /skill <name>[/]")
        else:
            skill = get_skill(arg)
            if skill:
                console.print(Panel(
                    "\n".join(f"  [{THEME['dim']}]{i+1}.[/] {step}" for i, step in enumerate(skill['steps'])),
                    title=f"[bold {THEME['skill']}]⚡ {skill['name']}[/] — {skill['description']}",
                    border_style=THEME['skill']
                ))
            else:
                console.print(f"[{THEME['error']}]Skill not found: {arg}[/]")

    # ── /run ──
    elif cmd == "/run":
        if not arg:
            console.print(f"[{THEME['error']}]Usage: /run [--heal] <shell command>[/]")
        else:
            heal = arg.strip().startswith("--heal")
            cmd_arg = arg.strip()[7:].strip() if heal else arg.strip()
            if not cmd_arg:
                console.print(f"[{THEME['error']}]Usage: /run [--heal] <shell command>[/]")
                return
            try:
                save_checkpoint(conversation)
            except Exception:
                pass
            enabled, _ = get_sandbox_mode()
            with spinner_context(f"Running: {cmd_arg[:50]}"):
                if enabled:
                    result = execute_command_sandboxed(cmd_arg)
                else:
                    result = execute_command(cmd_arg)
            print_cmd_result(result)
            if not result["success"]:
                if not heal:
                    try:
                        ans_heal = console.input(f"\n[{THEME['warning']}]⚠ Command failed. Run self-healing diagnostics? [Y/n]: [/]").lower().strip() or "y"
                        if ans_heal in ("y", "yes"):
                            heal = True
                    except (KeyboardInterrupt, EOFError):
                        pass
                
                if heal:
                    analysis = analyze_error(cmd_arg, result.get("stdout", ""), result.get("stderr", ""))
                    console.print(f"\n[bold {THEME['warning']}]Healing...[/] Analyzing failure...")
                    try:
                        prompt = (
                            f"A command failed:\n\nCommand: {cmd_arg}\nError: {analysis['error'][:1500]}\n\n"
                            f"Affected files:\n" + "\n".join(analysis["files"][:5])
                        )
                        if analysis["context"]:
                            prompt += f"\n\nFile context:\n{analysis['context']}"
                        prompt += (
                            "\n\nPropose a minimal fix. Output a unified diff for each file to change, "
                            "wrapped in <DIFF file=\"path\">```diff\n...\n```</DIFF>"
                        )
                        resp = get_ai_response([{"role": "user", "content": prompt}], current_project=current_project[0])
                        diffs = []
                        for match in __import__("re").finditer(
                            r"<DIFF\s+file=\"([^\"]+)\">\s*```diff\s*\n(.*?)\n```\s*</DIFF>", resp, re.DOTALL
                        ):
                            diffs.append((match.group(1), match.group(2)))
                        if diffs:
                            console.print(f"\n  [{THEME['accent2']}]Proposed fixes:[/]")
                            for fpath, d in diffs:
                                console.print(f"    [{THEME['accent']}]{fpath}[/] ({len(d)} chars)")
                            console.print(f"  [{THEME['dim']}]Apply proposal and retry? [Y/n]: [/]", end="")
                            try:
                                ans = input().strip().lower()
                                if ans in ("", "y", "yes"):
                                    for fpath, d in diffs:
                                        actual = Path(fpath)
                                        if actual.exists():
                                            hh = parse_diff(d)
                                            for h in hh:
                                                apply_diff_hunk(fpath, h)
                                    console.print(f"[{THEME['success']}]✓ Fixes applied. Retrying...[/]")
                                    with spinner_context(f"Re-running: {cmd_arg[:50]}"):
                                        r2 = execute_command(cmd_arg)
                                    print_cmd_result(r2)
                                    if r2["success"]:
                                        console.print(f"[{THEME['success']}]✓ Healed successfully![/]")
                                else:
                                    console.print(f"[{THEME['dim']}]Skipped[/]")
                            except EOFError:
                                pass
                        else:
                            console.print(f"  [{THEME['dim']}]AI did not propose a structured fix.[/]")
                    except Exception as e:
                        console.print(f"[{THEME['error']}]Heal failed: {e}[/]")

    # ── /search ──
    elif cmd == "/search":
        if not arg:
            console.print(f"[{THEME['error']}]Usage: /search <query>[/]")
        else:
            with spinner_context(f"Searching: {arg[:50]}"):
                results = web_search(arg)
            print_search_results(results, arg)

    # ── /ls ──
    elif cmd == "/ls":
        path = arg or "."
        entries = list_directory(path)
        table = Table(box=box.SIMPLE, show_header=True, header_style=f"bold {THEME['dim']}")
        table.add_column("Type", width=4)
        table.add_column("Name", style=THEME['accent2'])
        table.add_column("Size", justify="right", style=THEME['dim'])
        table.add_column("Modified", style=THEME['dim'])
        for e in entries:
            icon = "📁" if e['type'] == "dir" else "📄"
            size_str = f"{e['size']:,}" if e['type'] == "file" else ""
            table.add_row(icon, e['name'], size_str, e['modified'])
        console.print(table)

    # ── /read ──
    elif cmd == "/read":
        if not arg:
            console.print(f"[{THEME['error']}]Usage: /read <filepath>[/]")
        else:
            content = read_file(arg)
            from rich.syntax import Syntax
            suffix = Path(arg).suffix.lstrip('.') or "text"
            console.print(Syntax(content, suffix, theme="monokai", background_color="default", line_numbers=True))
            # Inject into conversation context
            conversation.append({
                "role": "user",
                "content": f"[File context loaded: {arg}]\n{content[:3000]}"
            })
            console.print(f"[{THEME['success']}]✓ File injected into context.[/]")

    # ── /copy ──
    elif cmd == "/copy":
        if arg:
            ok = copy_to_clipboard(arg)
            console.print(f"[{THEME['success'] if ok else THEME['error']}]{'✓ Copied' if ok else '✗ Clipboard unavailable'}[/]")
        else:
            content = read_clipboard()
            console.print(f"[{THEME['dim']}]Clipboard:[/] {content[:200]}")

    # ── /project ──
    elif cmd == "/project":
        if arg:
            current_project[0] = arg
            save_project(arg, f"Project: {arg}")
            console.print(f"[{THEME['success']}]✓ Active project: [{THEME['accent2']}]{arg}[/][/]")
        else:
            console.print(f"Current project: [{THEME['accent2']}]{current_project[0]}[/]")

    # ── /projects ──
    elif cmd == "/projects":
        projects = list_projects()
        if not projects:
            console.print(f"[{THEME['dim']}]No projects yet. Use /project <name> to create one.[/]")
        else:
            table = Table(box=box.SIMPLE, show_header=True, header_style=f"bold {THEME['accent2']}")
            table.add_column("Name", style=THEME['accent2'])
            table.add_column("Description")
            table.add_column("Created", style=THEME['dim'])
            for p in projects:
                table.add_row(p['name'], p.get('description', ''), p['created_at'][:10])
            console.print(table)

    # ── /sessions ──
    elif cmd == "/sessions":
        sessions = get_recent_sessions(10)
        print_sessions_panel(sessions)

    # ── /subagent ──
    elif cmd == "/subagent":
        if not arg:
            console.print(f"[{THEME['error']}]Usage: /subagent <task description>[/]")
        else:
            try:
                with spinner_context(f"Subagent: {arg[:50]}"):
                    result = run_subagent(arg, f"Project: {current_project[0]}", cfg.get("api_key", ""), provider=cfg.get("provider", "anthropic"))
                console.print(Panel(result, title=f"[bold {THEME['accent2']}]🤖 Subagent Result[/]", border_style=THEME['accent2']))
            except Exception as e:
                console.print(f"[{THEME['error']}]Subagent failed: {e}[/]")

    # ── /schedule ──
    elif cmd == "/schedule":
        schedules = load_schedules()
        if not schedules:
            console.print(f"[{THEME['dim']}]No scheduled tasks.[/]")
        else:
            table = Table(box=box.SIMPLE, show_header=True, header_style=f"bold {THEME['warning']}")
            table.add_column("ID", style=THEME['dim'], width=4)
            table.add_column("Cron", style=THEME['accent2'])
            table.add_column("Task")
            table.add_column("Enabled", width=8)
            table.add_column("Runs", justify="right", width=5)
            for s in schedules:
                enabled = f"[{THEME['success']}]yes[/]" if s.get("enabled", True) else f"[{THEME['error']}]no[/]"
                table.add_row(str(s.get("id", "?")), s['cron'], s['task'][:40], enabled, str(s.get("run_count", 0)))
            console.print(table)
        console.print(f"\n  [{THEME['dim']}]Use /cron add <cron> <task> to add. /cron del <id> to remove.[/]")

    # ── /cron ──
    elif cmd == "/cron":
        parts2 = arg.split(None, 2) if arg else []
        sub = parts2[0].lower().strip() if parts2 else "list"
        if sub == "add" and len(parts2) >= 3:
            cr, task = parts2[1], parts2[2]
            sid = save_schedule(cr, task)
            console.print(f"[{THEME['success']}]✓ Scheduled: [{THEME['accent2']}]{cr}[/] → {task} (id={sid})[/]")
        elif sub == "del" and len(parts2) >= 2:
            sid = int(parts2[1])
            if delete_schedule(sid):
                console.print(f"[{THEME['success']}]✓ Deleted schedule #{sid}[/]")
            else:
                console.print(f"[{THEME['error']}]Schedule #{sid} not found[/]")
        elif sub == "toggle" and len(parts2) >= 2:
            sid = int(parts2[1])
            new_state = toggle_schedule(sid)
            if new_state is not False:
                state_str = f"[{THEME['success']}]enabled[/]" if new_state else f"[{THEME['error']}]disabled[/]"
                console.print(f"[{THEME['success']}]✓ Schedule #{sid} {state_str}[/]")
            else:
                console.print(f"[{THEME['error']}]Schedule #{sid} not found[/]")
        elif sub == "log":
            lines = get_scheduler_log(30)
            if lines:
                for line in lines:
                    console.print(f"  [{THEME['dim']}]{line}[/]")
            else:
                console.print(f"[{THEME['dim']}]No log entries yet.[/]")
        else:
            # Show crontab-style help
            console.print(f"[{THEME['accent2']}]Usage:[/]")
            console.print(f"  /cron add <cron> <task>   [{THEME['dim']}]Add a cron task[/]")
            console.print(f"  /cron del <id>            [{THEME['dim']}]Delete a task[/]")
            console.print(f"  /cron toggle <id>         [{THEME['dim']}]Enable/disable[/]")
            console.print(f"  /cron log                 [{THEME['dim']}]Scheduler log[/]")
            console.print(f"  /schedule                 [{THEME['dim']}]List all tasks[/]")
            console.print(f"\n  [{THEME['dim']}]Cron format: minute hour day month weekday (5 fields)")
            console.print(f"  Example: [/{THEME['accent2']}]0 9 * * 1-5[/] = every weekday at 9:00 AM[/]")

    # ── /todo ──
    elif cmd == "/todo":
        parts2 = arg.split(None, 1) if arg else []
        sub = parts2[0].lower().strip() if parts2 else "list"
        rest = parts2[1].strip() if len(parts2) > 1 else ""
        proj = current_project[0]

        if not parts2 or sub == "list":
            items = list_todos(proj)
            if not items:
                console.print(f"[{THEME['dim']}]No todos for project[/] [{THEME['accent2']}]{proj}[/]")
                console.print(f"  [{THEME['dim']}]Add one:[/] /todo add <task>  or  /todo <task>")
            else:
                table = Table(box=box.SIMPLE, show_header=True, header_style=f"bold {THEME['accent']}")
                table.add_column("ID", style=THEME['dim'], width=4)
                table.add_column("Status", width=6)
                table.add_column("Task", style="white")
                table.add_column("Created", style=THEME['dim'], width=16)
                open_count = 0
                for item in items:
                    done = item.get("done", False)
                    if not done:
                        open_count += 1
                    status = f"[{THEME['success']}]done[/]" if done else f"[{THEME['warning']}]open[/]"
                    table.add_row(
                        str(item.get("id", "?")),
                        status,
                        item.get("text", "")[:70],
                        (item.get("created_at") or "")[:16],
                    )
                console.print(Panel(
                    table,
                    title=f"[bold {THEME['accent']}]📋 Todos — {proj}[/] [{THEME['dim']}]({open_count} open)[/]",
                    border_style=THEME['accent'],
                ))
                console.print(
                    f"  [{THEME['dim']}]/todo add <task>  /todo done <id>  /todo del <id>  /todo clear [all][/]"
                )
        elif sub == "add":
            if not rest:
                console.print(f"[{THEME['error']}]Usage: /todo add <task description>[/]")
            else:
                r = todo_add(rest, proj)
                if r["success"]:
                    console.print(f"[{THEME['success']}]✓ Todo #{r['item']['id']} added:[/] {rest[:60]}")
                else:
                    console.print(f"[{THEME['error']}]✗ {r['error']}[/]")
        elif sub == "done" and rest.isdigit():
            r = todo_done(int(rest), proj)
            if r["success"]:
                console.print(f"[{THEME['success']}]✓ Todo #{rest} marked done[/]")
            else:
                console.print(f"[{THEME['error']}]✗ {r['error']}[/]")
        elif sub in ("del", "delete", "rm") and rest.isdigit():
            r = todo_delete(int(rest), proj)
            if r["success"]:
                console.print(f"[{THEME['success']}]✓ Todo #{rest} deleted[/]")
            else:
                console.print(f"[{THEME['error']}]✗ {r['error']}[/]")
        elif sub == "clear":
            done_only = rest.lower().strip() != "all"
            r = todo_clear(proj, done_only=done_only)
            label = "completed" if done_only else "all"
            console.print(f"[{THEME['success']}]✓ Cleared {r['removed']} {label} todo(s)[/]")
        elif sub not in ("add", "done", "del", "delete", "rm", "clear", "list"):
            r = todo_add(arg.strip(), proj)
            if r["success"]:
                console.print(f"[{THEME['success']}]✓ Todo #{r['item']['id']} added:[/] {arg.strip()[:60]}")
            else:
                console.print(f"[{THEME['error']}]✗ {r['error']}[/]")
        else:
            console.print(f"[{THEME['accent2']}]Usage:[/]")
            console.print(f"  /todo                      [{THEME['dim']}]List todos[/]")
            console.print(f"  /todo add <task>           [{THEME['dim']}]Add a task[/]")
            console.print(f"  /todo <task>               [{THEME['dim']}]Quick-add shorthand[/]")
            console.print(f"  /todo done <id>            [{THEME['dim']}]Mark complete[/]")
            console.print(f"  /todo del <id>             [{THEME['dim']}]Delete a task[/]")
            console.print(f"  /todo clear                [{THEME['dim']}]Clear completed[/]")
            console.print(f"  /todo clear all            [{THEME['dim']}]Clear everything[/]")

    # ── /graph ──
    elif cmd == "/graph":
        parts2 = arg.split(None, 1) if arg else []
        sub = parts2[0].lower().strip() if parts2 else "search"
        q = parts2[1] if len(parts2) > 1 else ""

        if sub == "search" and q:
            results = graph_search(q)
            if results:
                for r in results:
                    console.print(f"  [{THEME['accent2']}]#{r['id']}[/] {r['content']} [{THEME['dim']}]({r['project']})[/]")
                    for e in r.get("edges", []):
                        console.print(f"    └─[{THEME['warning']}]{e['relation']}[/] → #{e['target']} (w={e['weight']})")
            else:
                console.print(f"[{THEME['dim']}]No graph results for '{q}'[/]")

        elif sub == "link" and q:
            # /graph link <src_id> <relation> <target_id>
            link_parts = q.split()
            if len(link_parts) >= 3 and link_parts[0].isdigit() and link_parts[2].isdigit():
                src, rel, tgt = int(link_parts[0]), link_parts[1], int(link_parts[2])
                weight = float(link_parts[3]) if len(link_parts) > 3 else 1.0
                if add_knowledge_edge(src, tgt, rel, weight):
                    console.print(f"[{THEME['success']}]✓ Linked #{src} →({rel})→ #{tgt}[/]")
                else:
                    console.print(f"[{THEME['error']}]Failed to create edge[/]")
            else:
                console.print(f"[{THEME['error']}]Usage: /graph link <src_id> <relation> <target_id> [weight][/]")

        elif sub == "walk" and q and q.isdigit():
            mid = int(q)
            linked = get_linked_memories(mid, max_depth=2)
            if linked:
                console.print(f"[{THEME['accent2']}]Graph walk from #{mid}:[/]")
                for l in linked:
                    prefix = "  " * (l['depth'] - 1) + "└─"
                    console.print(f"  {prefix}[{THEME['warning']}]{l['relation']}[/] → [{THEME['accent2']}]#{l['id']}[/] {l['content']} [{THEME['dim']}](w={l['weight']})[/]")
            else:
                console.print(f"[{THEME['dim']}]No linked memories for #{mid}[/]")

        else:
            console.print(f"[{THEME['accent2']}]Usage:[/]")
            console.print(f"  /graph search <query>       [{THEME['dim']}]Search with graph context[/]")
            console.print(f"  /graph walk <memory_id>     [{THEME['dim']}]Walk graph from a node[/]")
            console.print(f"  /graph link <s> <rel> <t>   [{THEME['dim']}]Link two memories[/]")

    # ── /history ──
    elif cmd == "/history":
        try:
            from prompt_toolkit.history import FileHistory
            h = FileHistory(str(Path.home() / ".aira" / "history.txt"))
            entries = list(h.get_strings())
            if arg:
                q = arg.lower().strip()
                entries = [e for e in entries if q in e.lower()]
            if entries:
                for i, entry in enumerate(entries[-50:], 1):
                    console.print(f"  [{THEME['dim']}]{i:3}.[/] {entry}")
                console.print(f"\n  [{THEME['dim']}]({len(entries)} matches)[/]")
            else:
                console.print(f"[{THEME['dim']}]No history entries[/]")
        except Exception as e:
            console.print(f"[{THEME['error']}]History unavailable: {e}[/]")

    # ── /snapshot ──
    elif cmd == "/snapshot":
        parts2 = arg.split(None, 1) if arg else []
        sub = parts2[0].lower().strip() if parts2 else "list"
        if sub == "list":
            snaps = list_snapshots()
            if snaps:
                for s in snaps[:20]:
                    size_str = f"{s['size']/1024:.1f}KB" if s['size'] < 1024*1024 else f"{s['size']/(1024*1024):.1f}MB"
                    console.print(f"  [{THEME['accent2']}]{s['id']}[/]  [{THEME['dim']}]{s['time']}[/]  {size_str}  [{THEME['dim']}]{s['label']}[/]")
            else:
                console.print(f"[{THEME['dim']}]No snapshots yet[/]")
        elif sub == "create":
            label = parts2[1].strip() if len(parts2) > 1 else ""
            with spinner_context("Creating snapshot..."):
                r = create_snapshot(label=label)
            if r["success"]:
                console.print(f"[{THEME['success']}]✓ Snapshot: [{THEME['accent2']}]{r['snapshot_id']}[/] ({r['files']} files, {r['size']/1024:.1f}KB)[/]")
            else:
                console.print(f"[{THEME['error']}]✗ {r['error']}[/]")
        else:
            console.print(f"[{THEME['accent2']}]Usage:[/]")
            console.print(f"  /snapshot list                [{THEME['dim']}]List snapshots[/]")
            console.print(f"  /snapshot create [label]      [{THEME['dim']}]Create snapshot of current dir[/]")

    # ── /rollback ──
    elif cmd == "/rollback":
        if arg:
            with spinner_context(f"Restoring: {arg}"):
                r = restore_snapshot(arg.strip())
            if r["success"]:
                console.print(f"[{THEME['success']}]✓ Restored {r['files']} files from snapshot[/]")
            else:
                console.print(f"[{THEME['error']}]✗ {r['error']}[/]")
        else:
            console.print(f"[{THEME['error']}]Usage: /rollback <snapshot_id>[/]")

    # ── /undo ──
    elif cmd == "/undo":
        cps = list_checkpoints()
        if not cps:
            console.print(f"[{THEME['dim']}]No checkpoints available.[/]")
        else:
            r = restore_checkpoint()
            if r["success"]:
                console.print(f"[{THEME['success']}]✓ Restored checkpoint from {r['timestamp']}[/]")
                if r.get("conversation"):
                    conversation[:] = r["conversation"]
                    console.print(f"  [{THEME['dim']}]Conversation rolled back ({len(r['conversation'])} messages)[/]")
            else:
                console.print(f"[{THEME['error']}]✗ {r['error']}[/]")

    # ── /diff ──
    elif cmd == "/diff":
        import subprocess
        git_res = subprocess.run(["git", "diff", "--name-status"], capture_output=True, text=True)
        if git_res.returncode == 0:
            diff_res = subprocess.run(["git", "diff", "--color=always"] + ([arg] if arg else []), capture_output=True, text=True)
            if diff_res.stdout.strip():
                console.print(diff_res.stdout)
            else:
                console.print(f"[{THEME['dim']}]No git changes detected.[/]")
        else:
            cps = list_checkpoints()
            if not cps:
                console.print(f"[{THEME['error']}]No git repository or checkpoints found to diff against.[/]")
            else:
                latest_ts = cps[0]
                cp_file = Path.home() / ".aira" / "checkpoints" / f"cp_{latest_ts}.json"
                if cp_file.exists():
                    try:
                        data = json.loads(cp_file.read_text(encoding="utf-8"))
                        files = data.get("files", {})
                        if arg:
                            rel_path = str(Path(arg).relative_to(Path.cwd())) if Path(arg).is_absolute() else arg
                            if rel_path in files:
                                orig_content = files[rel_path]
                                fp = Path.cwd() / rel_path
                                curr_content = fp.read_text(encoding="utf-8") if fp.exists() else ""
                                rich_diff(orig_content, curr_content, rel_path)
                            else:
                                console.print(f"[{THEME['error']}]File '{arg}' not found in the latest checkpoint.[/]")
                        else:
                            changed = 0
                            for rel_path, orig_content in files.items():
                                fp = Path.cwd() / rel_path
                                curr_content = fp.read_text(encoding="utf-8") if fp.exists() else ""
                                if orig_content != curr_content:
                                    console.print(f"\n[bold {THEME['accent2']}]--- {rel_path} ---[/]")
                                    rich_diff(orig_content, curr_content, rel_path)
                                    changed += 1
                            if not changed:
                                console.print(f"[{THEME['dim']}]No changes compared to the latest checkpoint.[/]")
                    except Exception as e:
                        console.print(f"[{THEME['error']}]Failed to read checkpoint: {e}[/]")
                else:
                    console.print(f"[{THEME['error']}]Latest checkpoint file cp_{latest_ts}.json not found.[/]")

    # ── /patch ──
    elif cmd == "/patch":
        parts2 = arg.split(None, 1) if arg else []
        if not parts2:
            console.print(f"[{THEME['error']}]Usage: /patch <file> [patch_file_or_diff][/]")
        else:
            target_file = parts2[0].strip()
            diff_source = parts2[1].strip() if len(parts2) > 1 else ""

            diff_content = ""
            if diff_source and Path(diff_source).exists():
                try:
                    diff_content = Path(diff_source).read_text(encoding="utf-8")
                except Exception as e:
                    console.print(f"[{THEME['error']}]Failed to read patch file: {e}[/]")
            elif diff_source:
                diff_content = diff_source
            else:
                try:
                    diff_content = read_clipboard() or ""
                    if diff_content:
                        console.print(f"[{THEME['dim']}]Reading patch from clipboard...[/]")
                except Exception:
                    pass

            if not diff_content.strip():
                console.print(f"[{THEME['error']}]No diff content found. Paste a unified diff or pass a patch file.[/]")
            else:
                hunks = parse_diff(diff_content)
                if not hunks:
                    console.print(f"[{THEME['error']}]Failed to parse any valid diff hunks.[/]")
                else:
                    console.print(f"[{THEME['success']}]Found {len(hunks)} hunk(s).[/]")
                    try:
                        save_checkpoint(conversation)
                    except Exception:
                        pass
                    applied_count = 0
                    for idx, hunk in enumerate(hunks, 1):
                        hunk_file = hunk.get("file") or target_file
                        console.print(f"\n[bold {THEME['accent']}]Hunk {idx}/{len(hunks)} → {hunk_file} (line {hunk['old_start']}):[/]")
                        console.print(f"[dim]{hunk.get('header', '')}[/]")
                        for line in hunk["lines"]:
                            if line.startswith("+"):
                                console.print(f"[green]{line}[/]")
                            elif line.startswith("-"):
                                console.print(f"[red]{line}[/]")
                            else:
                                console.print(f"[dim]{line}[/]")

                        ans = console.input(
                            f"\n[{THEME['accent2']}]Apply? [y/n/q/e] (y=yes, n=skip, q=quit, e=edit hunk): [/]"
                        ).lower().strip() or "y"
                        if ans == "q":
                            break
                        if ans == "e":
                            edit_path = AIRA_HOME / "patch_edit.txt"
                            edit_path.write_text("\n".join(hunk["lines"]), encoding="utf-8")
                            console.print(f"  [{THEME['info']}]Hunk saved to {edit_path}. Edit and re-run /patch.[/]")
                            continue
                        if ans == "y":
                            res = apply_diff_hunk(hunk_file, hunk)
                            if res.get("success"):
                                console.print(f"[{THEME['success']}]✓ Applied hunk {idx}[/]")
                                applied_count += 1
                            else:
                                console.print(f"[{THEME['error']}]✗ Failed: {res.get('error', 'unknown')}[/]")
                        else:
                            console.print(f"[{THEME['dim']}]Skipped hunk {idx}[/]")
                    console.print(f"\n[{THEME['success']}]Completed: applied {applied_count}/{len(hunks)} hunk(s).[/]")

    # ── /vault ──
    elif cmd == "/vault":
        parts2 = arg.split(None, 1) if arg else []
        sub = parts2[0].lower().strip() if parts2 else "list"
        if sub == "list":
            services = vault_list()
            if services:
                for s in services:
                    console.print(f"  [{THEME['accent2']}]{s}[/]")
            else:
                console.print(f"[{THEME['dim']}]Vault is empty[/]")
        elif sub == "set" and len(parts2) >= 2:
            svc_val = parts2[1].split(None, 1)
            if len(svc_val) >= 2:
                if vault_set(svc_val[0], svc_val[1]):
                    console.print(f"[{THEME['success']}]✓ Saved credential: [{THEME['accent2']}]{svc_val[0]}[/][/]")
                else:
                    console.print(f"[{THEME['error']}]Failed to save[/]")
            else:
                console.print(f"[{THEME['error']}]Usage: /vault set <service> <value>[/]")
        elif sub == "get" and len(parts2) >= 2:
            val = vault_get(parts2[1])
            if val:
                console.print(f"  [{THEME['accent2']}]{parts2[1]}[/] = [{THEME['dim']}]{val[:40]}{'...' if len(val)>40 else ''}[/]")
            else:
                console.print(f"[{THEME['dim']}]No credential stored for '{parts2[1]}'[/]")
        elif sub == "del" and len(parts2) >= 2:
            if vault_delete(parts2[1]):
                console.print(f"[{THEME['success']}]✓ Deleted: {parts2[1]}[/]")
            else:
                console.print(f"[{THEME['error']}]Not found: {parts2[1]}[/]")
        else:
            console.print(f"[{THEME['accent2']}]Usage:[/]")
            console.print(f"  /vault list                  [{THEME['dim']}]List stored services[/]")
            console.print(f"  /vault set <svc> <val>       [{THEME['dim']}]Store credential[/]")
            console.print(f"  /vault get <svc>             [{THEME['dim']}]Retrieve credential[/]")
            console.print(f"  /vault del <svc>             [{THEME['dim']}]Delete credential[/]")

    # ── /gh / /github ──
    elif cmd in ("/gh", "/github"):
        if not arg:
            console.print(f"[{THEME['accent2']}]Usage:[/]")
            console.print(f"  /gh status              [{THEME['dim']}]GitHub CLI status[/]")
            console.print(f"  /gh pr list             [{THEME['dim']}]List PRs[/]")
            console.print(f"  /gh issue list          [{THEME['dim']}]List issues[/]")
            console.print(f"  /gh repo view           [{THEME['dim']}]View repo info[/]")
            console.print(f"  /gh <any gh args>       [{THEME['dim']}]Run arbitrary gh command[/]")
        elif arg.strip() == "status":
            if gh_check():
                console.print(f"[{THEME['success']}]✓ GitHub CLI (gh) is installed[/]")
            else:
                console.print(f"[{THEME['error']}]gh CLI not found. Install from https://cli.github.com/[/]")
        else:
            if not gh_check():
                console.print(f"[{THEME['error']}]gh CLI not installed[/]")
            else:
                with spinner_context(f"gh {arg[:50]}..."):
                    r = gh_run(arg.split())
                if r["success"]:
                    console.print(r["stdout"][:2000])
                else:
                    console.print(f"[{THEME['error']}]gh error: {r.get('stderr', r.get('error', 'unknown'))[:500]}[/]")

    # ── /docker ──
    elif cmd == "/docker":
        if not arg:
            console.print(f"[{THEME['accent2']}]Usage:[/]")
            console.print(f"  /docker ps              [{THEME['dim']}]List running containers[/]")
            console.print(f"  /docker build <path>    [{THEME['dim']}]Build image[/]")
            console.print(f"  /docker run <image>     [{THEME['dim']}]Run container[/]")
            console.print(f"  /docker images          [{THEME['dim']}]List images[/]")
            console.print(f"  /docker <any args>      [{THEME['dim']}]Run arbitrary docker cmd[/]")
        else:
            if not docker_check():
                console.print(f"[{THEME['error']}]Docker not found[/]")
            else:
                args_list = arg.split()
                if args_list[0] == "ps":
                    containers = docker_ps()
                    if containers:
                        dt = Table(box=box.SIMPLE, show_header=True, header_style=f"bold {THEME['accent2']}")
                        dt.add_column("ID", style=THEME['dim'], width=14)
                        dt.add_column("Image", style=THEME['info'])
                        dt.add_column("Status", style="white")
                        dt.add_column("Ports", style=THEME['dim'])
                        dt.add_column("Name", style=THEME['accent'])
                        for c in containers:
                            dt.add_row(c['id'], c['image'][:35], c['status'][:25], c['ports'][:30], c['name'])
                        console.print(dt)
                    else:
                        console.print(f"[{THEME['dim']}]No running containers[/]")
                else:
                    with spinner_context(f"docker {' '.join(args_list)}..."):
                        r = docker_run(args_list)
                    if r["success"]:
                        console.print(r["stdout"][:2000])
                    else:
                        console.print(f"[{THEME['error']}]docker: {r.get('stderr', r.get('error', ''))[:500]}[/]")

    # ── /model ──
    elif cmd == "/model":
        parts2 = arg.split(None, 2) if arg else []
        sub = parts2[0].lower().strip() if parts2 else ""

        # Comprehensive model map — 300+ OpenAI models generated from known patterns
        # Values are (provider, tier) tuples where tier is "free" or "paid"
        def _build_model_map():
            m = {}
            # OpenAI: gpt-4o family
            for base in ["gpt-4o", "gpt-4o-mini", "gpt-4o-turbo"]:
                m[base] = "openai"
                for d in ["2024-05-13", "2024-08-06", "2024-11-20", "2025-01-10", "2025-03-08", "2025-05-15"]:
                    m[f"{base}-{d}"] = "openai"
                for d in [f"2024-{m:02d}-{d:02d}" for m in range(5,13) for d in [1,15]]:
                    m[f"{base}-{d}"] = "openai"
            # OpenAI: gpt-4 family
            for base in ["gpt-4", "gpt-4-32k", "gpt-4-turbo", "gpt-4-turbo-preview"]:
                m[base] = "openai"
                for v in ["0613", "1106-preview", "0125-preview", "2024-04-09"]:
                    m[f"{base}-{v}"] = "openai"
            # OpenAI: gpt-4.1 family
            for base in ["gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano"]:
                m[base] = "openai"
                m[f"{base}-2025-04-14"] = "openai"
            # OpenAI: gpt-4.5
            m["gpt-4.5-preview"] = "openai"
            m["gpt-4.5-preview-2025-02-27"] = "openai"
            # OpenAI: gpt-3.5 family
            for base in ["gpt-3.5-turbo", "gpt-3.5-turbo-16k"]:
                m[base] = "openai"
                for v in ["0125", "1106", "0613", "0301"]:
                    m[f"{base}-{v}"] = "openai"
            # OpenAI: o1 family
            for base in ["o1", "o1-preview", "o1-mini"]:
                m[base] = "openai"
                for v in ["2024-09-12", "2024-12-17"]:
                    m[f"{base}-{v}"] = "openai"
            # OpenAI: o3 family
            for base in ["o3-mini", "o3-mini-high"]:
                m[base] = "openai"
                m[f"{base}-2025-01-31"] = "openai"
            # OpenAI: realtime
            m["gpt-4o-realtime"] = "openai"
            m["gpt-4o-realtime-2024-10-01"] = "openai"
            m["gpt-4o-mini-realtime"] = "openai"
            m["gpt-4o-mini-realtime-2024-12-17"] = "openai"
            # OpenAI: audio
            m["gpt-4o-audio-preview"] = "openai"
            m["gpt-4o-audio-preview-2024-10-01"] = "openai"
            m["gpt-4o-mini-audio-preview"] = "openai"
            m["gpt-4o-mini-audio-preview-2024-12-17"] = "openai"
            # OpenAI: chatgpt
            m["chatgpt-4o-latest"] = "openai"
            # OpenAI: embeddings
            for e in ["text-embedding-3-small", "text-embedding-3-large", "text-embedding-ada-002"]:
                m[e] = "openai"
            # OpenAI: DALL-E
            for d in ["dall-e-2", "dall-e-3"]:
                m[d] = "openai"
            # OpenAI: TTS
            for t in ["tts-1", "tts-1-hd"]:
                m[t] = "openai"
            # OpenAI: Whisper
            m["whisper-1"] = "openai"
            # Anthropic (all models: free + paid)
            # Claude 3 family (paid)
            for base in ["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"]:
                m[base] = "anthropic"
                for v in ["20240229", "20240307"]:
                    m[f"{base}-{v}"] = "anthropic"
                m[f"{base}-latest"] = "anthropic"
            # Claude 3.5 family (paid)
            for base in ["claude-3.5-sonnet", "claude-3.5-haiku"]:
                m[base] = "anthropic"
                for v in ["20240620", "20241022"]:
                    m[f"{base}-{v}"] = "anthropic"
                m[f"{base}-latest"] = "anthropic"
            # Claude 4 family (paid)
            for base in ["claude-sonnet-4-6", "claude-sonnet-4", "claude-opus-4", "claude-haiku-4"]:
                m[base] = "anthropic"
                for v in ["20250514", "20250601"]:
                    m[f"{base}-{v}"] = "anthropic"
                m[f"{base}-latest"] = "anthropic"
            # Legacy
            for base in ["claude-instant-1", "claude-instant-1.2", "claude-2", "claude-2.1"]:
                m[base] = "anthropic"
            # Gemini (all models: free + paid tiers)
            # Paid / Pro tier
            for base in ["gemini-1.5-pro", "gemini-2.5-pro", "gemini-2.0-flash-thinking"]:
                m[base] = "gemini"
                for v in ["001", "002", "latest", "exp"]:
                    m[f"{base}-{v}"] = "gemini"
            # Free tier
            for base in ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-2.5-flash"]:
                m[base] = "gemini"
                for v in ["001", "002", "latest", "exp"]:
                    m[f"{base}-{v}"] = "gemini"
            # Gemini 1.0
            for base in ["gemini-1.0-pro", "gemini-pro"]:
                m[base] = "gemini"
                m[f"{base}-001"] = "gemini"
                m[f"{base}-latest"] = "gemini"
            # Vision variants
            for base in ["gemini-1.5-pro-vision", "gemini-1.5-flash-vision", "gemini-2.0-flash-vision"]:
                m[base] = "gemini"
                for v in ["001", "latest"]:
                    m[f"{base}-{v}"] = "gemini"
            # Embeddings
            for base in ["text-embedding-004", "text-embedding-005", "gemini-embedding-exp-03-07"]:
                m[base] = "gemini"
            # AQA (attributed question answering)
            m["aqa"] = "gemini"
            # Gemma (open models via Gemini API)
            for base in ["gemma-2-2b", "gemma-2-9b", "gemma-2-27b", "gemma-3-12b", "gemma-3-27b"]:
                m[base] = "gemini"
            # Imagen (image generation)
            for base in ["imagen-3.0-generate-capability-001", "imagen-3.0-fast-generate-capability-001"]:
                m[base] = "gemini"
            # Groq (all models: free + paid)
            groq_bases = [
                "llama3-8b", "llama3-70b",
                "llama-3.1-8b", "llama-3.1-70b", "llama-3.1-405b",
                "llama-3.2-1b", "llama-3.2-3b", "llama-3.2-11b", "llama-3.2-90b",
                "llama-3.3-70b",
                "llama-4-scout-17b", "llama-4-maverick-17b",
                "mixtral-8x7b", "mixtral-8x22b",
                "gemma2-9b", "gemma2-27b", "gemma-7b",
                "deepseek-r1", "deepseek-r1-distill-llama-70b", "deepseek-r1-distill-llama-8b",
                "qwen-2.5-32b", "qwen-2.5-72b", "qwen-2.5-coder-32b",
                "qwq-32b",
                "whisper-large-v3", "whisper-large-v3-turbo",
                "distil-whisper-large-v3",
                "playai-tts", "playai-tts-arabic",
                "llama-guard-3-8b",
            ]
            for g in groq_bases:
                m[g] = "groq"
                for ctx in ["8k", "32k", "128k"]:
                    m[f"{g}-{ctx}"] = "groq"
            # DeepSeek (all models: free + paid)
            for base in ["deepseek-chat", "deepseek-coder", "deepseek-reasoner"]:
                m[base] = "deepseek"
                for v in ["v2", "v2.5", "latest"]:
                    m[f"{base}-{v}"] = "deepseek"
            m["deepseek-r1"] = "deepseek"
            m["deepseek-r1-distill"] = "deepseek"
            m["deepseek-v3"] = "deepseek"
            m["deepseek-v3-0324"] = "deepseek"
            for base in ["deepseek-v2", "deepseek-v2.5", "deepseek-coder-v2"]:
                m[base] = "deepseek"
            m["deepseek-chat-turbo"] = "deepseek"
            m["deepseek-chat-pro"] = "deepseek"
            # Mistral (all models: free + paid)
            for base in ["mistral-tiny", "mistral-small", "mistral-medium", "mistral-large", "codestral"]:
                m[base] = "mistral"
                for v in ["latest", "2402", "2407", "2409", "2411"]:
                    m[f"{base}-{v}"] = "mistral"
            m["mistral-small-2409"] = "mistral"
            m["mistral-large-2407"] = "mistral"
            m["mistral-large-2402"] = "mistral"
            m["codestral-2405"] = "mistral"
            m["codestral-2501"] = "mistral"
            for base in ["mistral-embed", "mistral-moderation", "mistral-saba"]:
                m[base] = "mistral"
            for base in ["ministral-3b", "ministral-8b"]:
                m[base] = "mistral"
                m[f"{base}-2410"] = "mistral"
            for base in ["open-mistral-7b", "open-mixtral-8x7b", "open-mixtral-8x22b", "open-codestral-mamba"]:
                m[base] = "mistral"
            for base in ["pixtral-12b", "pixtral-large"]:
                m[base] = "mistral"
            # Cohere
            for c in ["command-r", "command-r-plus", "command-r-08-2024", "command-nightly", "command-light"]:
                m[c] = "cohere"
            # xAI / Grok
            for x in ["grok-1", "grok-2", "grok-2-mini", "grok-2-vision"]:
                m[x] = "xai"
            # OpenRouter (339 models — live fetched from API, curated fallback)
            or_models = [
                "ai21/jamba-large-1.7", "aion-labs/aion-1.0", "aion-labs/aion-1.0-mini", "aion-labs/aion-2.0", "aion-labs/aion-rp-llama-3.1-8b",
                "allenai/olmo-3-32b-think", "amazon/nova-2-lite-v1", "amazon/nova-lite-v1", "amazon/nova-micro-v1", "amazon/nova-premier-v1",
                "amazon/nova-pro-v1", "anthracite-org/magnum-v4-72b", "anthropic/claude-3-haiku", "anthropic/claude-fable-5", "anthropic/claude-haiku-4.5",
                "anthropic/claude-opus-4", "anthropic/claude-opus-4.1", "anthropic/claude-opus-4.5", "anthropic/claude-opus-4.6", "anthropic/claude-opus-4.6-fast",
                "anthropic/claude-opus-4.7", "anthropic/claude-opus-4.7-fast", "anthropic/claude-opus-4.8", "anthropic/claude-opus-4.8-fast",
                "anthropic/claude-sonnet-4", "anthropic/claude-sonnet-4.5", "anthropic/claude-sonnet-4.6",
                "arcee-ai/coder-large", "arcee-ai/trinity-large-thinking", "arcee-ai/trinity-mini", "arcee-ai/virtuoso-large",
                "baidu/ernie-4.5-vl-424b-a47b", "bytedance-seed/seed-1.6", "bytedance-seed/seed-1.6-flash", "bytedance-seed/seed-2.0-lite",
                "bytedance-seed/seed-2.0-mini", "bytedance/ui-tars-1.5-7b", "cognitivecomputations/dolphin-mistral-24b-venice-edition:free",
                "cohere/command-a", "cohere/command-r-08-2024", "cohere/command-r-plus-08-2024", "cohere/command-r7b-12-2024", "cohere/north-mini-code:free",
                "deepcogito/cogito-v2.1-671b", "deepseek/deepseek-chat", "deepseek/deepseek-chat-v3-0324", "deepseek/deepseek-chat-v3.1",
                "deepseek/deepseek-r1", "deepseek/deepseek-r1-0528", "deepseek/deepseek-r1-distill-llama-70b",
                "deepseek/deepseek-v3.1-terminus", "deepseek/deepseek-v3.2", "deepseek/deepseek-v3.2-exp", "deepseek/deepseek-v4-flash", "deepseek/deepseek-v4-pro",
                "google/gemini-2.5-flash", "google/gemini-2.5-flash-image", "google/gemini-2.5-flash-lite", "google/gemini-2.5-flash-lite-preview-09-2025",
                "google/gemini-2.5-pro", "google/gemini-2.5-pro-preview", "google/gemini-2.5-pro-preview-05-06",
                "google/gemini-3-flash-preview", "google/gemini-3-pro-image", "google/gemini-3-pro-image-preview",
                "google/gemini-3.1-flash-image", "google/gemini-3.1-flash-image-preview", "google/gemini-3.1-flash-lite", "google/gemini-3.1-flash-lite-preview",
                "google/gemini-3.1-pro-preview", "google/gemini-3.1-pro-preview-customtools", "google/gemini-3.5-flash",
                "google/gemma-2-27b-it", "google/gemma-3-12b-it", "google/gemma-3-27b-it", "google/gemma-3-4b-it", "google/gemma-3n-e4b-it",
                "google/gemma-4-26b-a4b-it", "google/gemma-4-26b-a4b-it:free", "google/gemma-4-31b-it", "google/gemma-4-31b-it:free",
                "google/lyria-3-clip-preview", "google/lyria-3-pro-preview",
                "gryphe/mythomax-l2-13b", "ibm-granite/granite-4.0-h-micro", "ibm-granite/granite-4.1-8b",
                "inception/mercury-2", "inclusionai/ling-2.6-1t", "inclusionai/ling-2.6-flash", "inclusionai/ring-2.6-1t",
                "inflection/inflection-3-pi", "inflection/inflection-3-productivity", "kwaipilot/kat-coder-pro-v2",
                "liquid/lfm-2-24b-a2b", "liquid/lfm-2.5-1.2b-instruct:free", "liquid/lfm-2.5-1.2b-thinking:free",
                "mancer/weaver", "meta-llama/llama-3-8b-instruct", "meta-llama/llama-3.1-70b-instruct", "meta-llama/llama-3.1-8b-instruct",
                "meta-llama/llama-3.2-11b-vision-instruct", "meta-llama/llama-3.2-1b-instruct", "meta-llama/llama-3.2-3b-instruct",
                "meta-llama/llama-3.2-3b-instruct:free", "meta-llama/llama-3.3-70b-instruct", "meta-llama/llama-3.3-70b-instruct:free",
                "meta-llama/llama-4-maverick", "meta-llama/llama-4-scout", "meta-llama/llama-guard-4-12b",
                "microsoft/phi-4", "microsoft/phi-4-mini-instruct", "microsoft/wizardlm-2-8x22b",
                "minimax/minimax-01", "minimax/minimax-m1", "minimax/minimax-m2", "minimax/minimax-m2-her",
                "minimax/minimax-m2.1", "minimax/minimax-m2.5", "minimax/minimax-m2.7", "minimax/minimax-m3",
                "mistralai/codestral-2508", "mistralai/devstral-2512", "mistralai/ministral-14b-2512", "mistralai/ministral-3b-2512",
                "mistralai/ministral-8b-2512", "mistralai/mistral-large", "mistralai/mistral-large-2407", "mistralai/mistral-large-2512",
                "mistralai/mistral-medium-3", "mistralai/mistral-medium-3-5", "mistralai/mistral-medium-3.1",
                "mistralai/mistral-nemo", "mistralai/mistral-saba",
                "mistralai/mistral-small-24b-instruct-2501", "mistralai/mistral-small-2603", "mistralai/mistral-small-3.1-24b-instruct",
                "mistralai/mistral-small-3.2-24b-instruct", "mistralai/mixtral-8x22b-instruct", "mistralai/voxtral-small-24b-2507",
                "moonshotai/kimi-k2", "moonshotai/kimi-k2-0905", "moonshotai/kimi-k2-thinking", "moonshotai/kimi-k2.5",
                "moonshotai/kimi-k2.6", "moonshotai/kimi-k2.7-code",
                "morph/morph-v3-fast", "morph/morph-v3-large", "nex-agi/nex-n2-pro",
                "nousresearch/hermes-3-llama-3.1-405b", "nousresearch/hermes-3-llama-3.1-405b:free",
                "nousresearch/hermes-3-llama-3.1-70b", "nousresearch/hermes-4-405b", "nousresearch/hermes-4-70b",
                "nvidia/llama-3.3-nemotron-super-49b-v1.5", "nvidia/nemotron-3-nano-30b-a3b", "nvidia/nemotron-3-nano-30b-a3b:free",
                "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free", "nvidia/nemotron-3-super-120b-a12b",
                "nvidia/nemotron-3-super-120b-a12b:free", "nvidia/nemotron-3-ultra-550b-a55b", "nvidia/nemotron-3-ultra-550b-a55b:free",
                "nvidia/nemotron-3.5-content-safety:free", "nvidia/nemotron-nano-12b-v2-vl:free", "nvidia/nemotron-nano-9b-v2:free",
                "openai/gpt-3.5-turbo", "openai/gpt-3.5-turbo-0613", "openai/gpt-3.5-turbo-16k", "openai/gpt-3.5-turbo-instruct",
                "openai/gpt-4", "openai/gpt-4-turbo", "openai/gpt-4-turbo-preview",
                "openai/gpt-4.1", "openai/gpt-4.1-mini", "openai/gpt-4.1-nano",
                "openai/gpt-4o", "openai/gpt-4o-2024-05-13", "openai/gpt-4o-2024-08-06", "openai/gpt-4o-2024-11-20",
                "openai/gpt-4o-mini", "openai/gpt-4o-mini-2024-07-18",
                "openai/gpt-4o-mini-search-preview", "openai/gpt-4o-search-preview",
                "openai/gpt-5", "openai/gpt-5-chat", "openai/gpt-5-codex", "openai/gpt-5-image", "openai/gpt-5-image-mini",
                "openai/gpt-5-mini", "openai/gpt-5-nano", "openai/gpt-5-pro",
                "openai/gpt-5.1", "openai/gpt-5.1-chat", "openai/gpt-5.1-codex", "openai/gpt-5.1-codex-max", "openai/gpt-5.1-codex-mini",
                "openai/gpt-5.2", "openai/gpt-5.2-chat", "openai/gpt-5.2-codex", "openai/gpt-5.2-pro",
                "openai/gpt-5.3-chat", "openai/gpt-5.3-codex",
                "openai/gpt-5.4", "openai/gpt-5.4-image-2", "openai/gpt-5.4-mini", "openai/gpt-5.4-nano", "openai/gpt-5.4-pro",
                "openai/gpt-5.5", "openai/gpt-5.5-pro",
                "openai/gpt-audio", "openai/gpt-audio-mini", "openai/gpt-chat-latest",
                "openai/gpt-oss-120b", "openai/gpt-oss-120b:free", "openai/gpt-oss-20b", "openai/gpt-oss-20b:free", "openai/gpt-oss-safeguard-20b",
                "openai/o1", "openai/o1-pro", "openai/o3", "openai/o3-deep-research", "openai/o3-mini", "openai/o3-mini-high",
                "openai/o3-pro", "openai/o4-mini", "openai/o4-mini-deep-research", "openai/o4-mini-high",
                "openrouter/auto", "openrouter/bodybuilder", "openrouter/free", "openrouter/fusion", "openrouter/owl-alpha", "openrouter/pareto-code",
                "perceptron/perceptron-mk1", "perplexity/sonar", "perplexity/sonar-deep-research", "perplexity/sonar-pro",
                "perplexity/sonar-pro-search", "perplexity/sonar-reasoning-pro",
                "poolside/laguna-m.1", "poolside/laguna-m.1:free", "poolside/laguna-xs.2", "poolside/laguna-xs.2:free",
                "qwen/qwen-2.5-72b-instruct", "qwen/qwen-2.5-7b-instruct", "qwen/qwen-2.5-coder-32b-instruct",
                "qwen/qwen-plus", "qwen/qwen-plus-2025-07-28", "qwen/qwen-plus-2025-07-28:thinking",
                "qwen/qwen2.5-vl-72b-instruct",
                "qwen/qwen3-14b", "qwen/qwen3-235b-a22b", "qwen/qwen3-235b-a22b-2507", "qwen/qwen3-235b-a22b-thinking-2507",
                "qwen/qwen3-30b-a3b", "qwen/qwen3-30b-a3b-instruct-2507", "qwen/qwen3-30b-a3b-thinking-2507",
                "qwen/qwen3-32b", "qwen/qwen3-8b",
                "qwen/qwen3-coder", "qwen/qwen3-coder-30b-a3b-instruct", "qwen/qwen3-coder-flash", "qwen/qwen3-coder-next",
                "qwen/qwen3-coder-plus", "qwen/qwen3-coder:free",
                "qwen/qwen3-max", "qwen/qwen3-max-thinking",
                "qwen/qwen3-next-80b-a3b-instruct", "qwen/qwen3-next-80b-a3b-instruct:free", "qwen/qwen3-next-80b-a3b-thinking",
                "qwen/qwen3-vl-235b-a22b-instruct", "qwen/qwen3-vl-235b-a22b-thinking",
                "qwen/qwen3-vl-30b-a3b-instruct", "qwen/qwen3-vl-30b-a3b-thinking",
                "qwen/qwen3-vl-32b-instruct", "qwen/qwen3-vl-8b-instruct", "qwen/qwen3-vl-8b-thinking",
                "qwen/qwen3.5-122b-a10b", "qwen/qwen3.5-27b", "qwen/qwen3.5-35b-a3b", "qwen/qwen3.5-397b-a17b", "qwen/qwen3.5-9b",
                "qwen/qwen3.5-flash-02-23", "qwen/qwen3.5-plus-02-15", "qwen/qwen3.5-plus-20260420",
                "qwen/qwen3.6-27b", "qwen/qwen3.6-35b-a3b", "qwen/qwen3.6-flash", "qwen/qwen3.6-max-preview", "qwen/qwen3.6-plus",
                "qwen/qwen3.7-max", "qwen/qwen3.7-plus",
                "rekaai/reka-edge", "rekaai/reka-flash-3", "relace/relace-apply-3", "relace/relace-search",
                "sakana/fugu-ultra", "sao10k/l3-lunaris-8b", "sao10k/l3.1-70b-hanami-x1", "sao10k/l3.1-euryale-70b", "sao10k/l3.3-euryale-70b",
                "stepfun/step-3.5-flash", "stepfun/step-3.7-flash", "switchpoint/router",
                "tencent/hunyuan-a13b-instruct", "tencent/hy3-preview",
                "thedrummer/cydonia-24b-v4.1", "thedrummer/rocinante-12b", "thedrummer/skyfall-36b-v2", "thedrummer/unslopnemo-12b",
                "undi95/remm-slerp-l2-13b", "upstage/solar-pro-3", "writer/palmyra-x5",
                "x-ai/grok-4.20", "x-ai/grok-4.20-multi-agent", "x-ai/grok-4.3", "x-ai/grok-build-0.1",
                "xiaomi/mimo-v2.5", "xiaomi/mimo-v2.5-pro",
                "z-ai/glm-4.5", "z-ai/glm-4.5-air", "z-ai/glm-4.5v", "z-ai/glm-4.6", "z-ai/glm-4.6v",
                "z-ai/glm-4.7", "z-ai/glm-4.7-flash", "z-ai/glm-5", "z-ai/glm-5-turbo", "z-ai/glm-5.1", "z-ai/glm-5.2", "z-ai/glm-5v-turbo",
                "~anthropic/claude-fable-latest", "~anthropic/claude-haiku-latest", "~anthropic/claude-opus-latest",
                "~anthropic/claude-sonnet-latest", "~google/gemini-flash-latest", "~google/gemini-pro-latest",
                "~moonshotai/kimi-latest", "~openai/gpt-latest", "~openai/gpt-mini-latest",
            ]
            for o in or_models:
                m[o] = "openrouter"
            # Post-process: convert to (provider, tier) tuples
            FREE_MODELS = {
                "gpt-4o-mini", "gpt-4o-mini-2024-07-18",
                "gemini-1.5-flash", "gemini-1.5-flash-001", "gemini-1.5-flash-002",
                "gemini-2.0-flash", "gemini-2.0-flash-001", "gemini-2.0-flash-002",
                "gemini-2.0-flash-lite", "gemini-2.0-flash-lite-001",
                "gemini-2.5-flash", "gemini-2.5-flash-001",
                "gemma-2-2b", "gemma-2-9b", "gemma-2-27b",
                "gemma-3-4b-it", "gemma-3-12b-it", "gemma-3-27b-it",
                "text-embedding-004", "text-embedding-005",
                "llama3-8b", "llama3-70b", "llama-3.1-8b", "llama-3.1-70b",
                "llama-3.2-1b", "llama-3.2-3b", "llama-3.2-11b",
                "llama-3.3-70b", "llama-3.3-70b-instruct:free",
                "llama-3.2-3b-instruct:free",
                "gemma2-9b", "gemma-7b",
                "gemma2-9b-8k", "gemma2-9b-32k",
                "deepseek-chat", "deepseek-coder",
                "mistral-tiny", "mistral-small", "mistral-medium",
                "ministral-3b", "ministral-8b",
                "open-mistral-7b", "open-mixtral-8x7b",
                "llama3-8b-8k", "llama3-8b-32k", "llama3-8b-128k",
                "llama3-70b-8k", "llama3-70b-32k", "llama3-70b-128k",
                "mixtral-8x7b-8k", "mixtral-8x7b-32k", "mixtral-8x7b-128k",
                "whisper-large-v3", "whisper-large-v3-turbo", "distil-whisper-large-v3",
                "playai-tts", "playai-tts-arabic",
                "llama-guard-3-8b", "llama-guard-3-8b-8k",
                "qwq-32b", "deepseek-r1-distill-llama-8b", "deepseek-r1-distill-llama-70b",
                "gemini-1.0-pro", "gemini-pro",
                "aqa",
            }
            result = {}
            for k, v in m.items():
                is_free = k in FREE_MODELS or (":free" in k) or any(k.startswith(f) for f in ["llama-3.2-1b", "llama-3.2-3b", "llama-3.3-70b-instruct:free", "gemma-4-", "nvidia/nemotron", "nvidia/nemotron-nano", "poolside/", "liquid/lfm-2.5", "qwen/qwen3-next-80b", "nousresearch/hermes-3-llama-3.1-405b:free", "cohere/north-mini-code:free"])
                result[k] = (v, "free" if is_free else "paid")
            return result
        _MODEL_PROVIDER = _build_model_map()

        # /model with no args → two-step interactive picker: provider → model
        if not sub:
            from prompt_toolkit.layout import Layout, HSplit, Window
            from prompt_toolkit.layout.controls import FormattedTextControl
            from prompt_toolkit.widgets import RadioList, Label, Dialog, Button
            from prompt_toolkit.key_binding import KeyBindings, merge_key_bindings
            from prompt_toolkit.key_binding.bindings.focus import focus_next, focus_previous
            from prompt_toolkit.key_binding.defaults import load_key_bindings
            from prompt_toolkit.application import Application, current as app_cur
            from prompt_toolkit.styles import Style as PtStyle
            from prompt_toolkit.formatted_text import to_formatted_text
            from prompt_toolkit.filters import has_focus

            # ── Provider metadata: (icon, description, badge) ──
            _PMETA = {
                "anthropic": ("◉", "Claude · best reasoning", ""),
                "openai":    ("◆", "GPT-4o, o1, o3 models",  ""),
                "nvidia":    ("▣", "NIM · 100+ models",      "FREE"),
                "openrouter":("◎", "200+ · free tier",       "FREE"),
                "groq":      ("◈", "Ultra-fast inference",    "FREE"),
                "gemini":    ("✦", "Google · Flash free",     "FREE"),
                "ollama":    ("◇", "Local · completely free", "LOCAL"),
                "deepseek":  ("◆", "DeepSeek reasoning",     ""),
                "mistral":   ("◐", "Mistral AI models",      ""),
                "cohere":    ("◈", "Command R models",        ""),
                "xai":       ("◎", "Grok models",            ""),
            }
            # ── Model description hints ──
            _MHINTS = {
                "claude-opus-4-5": "Most powerful Claude",
                "claude-sonnet-4-5": "Best balance + speed",
                "claude-haiku-4-5": "Fastest & cheapest",
                "claude-3-5-sonnet-20241022": "Strong coding",
                "claude-3-haiku-20240307": "Compact & fast",
                "gpt-4o": "Latest GPT-4o", "gpt-4o-mini": "Fast & cheap",
                "gpt-4-turbo": "GPT-4 Turbo",
                "o1": "Advanced reasoning", "o1-mini": "Fast reasoning",
                "o3-mini": "Efficient reasoning",
                "gemini-2.5-flash": "Latest Flash", "gemini-2.0-flash": "Fast & free",
                "gemini-1.5-pro": "Best Gemini",
                "deepseek-chat": "General chat", "deepseek-coder": "Code specialist",
                "mistral-large-latest": "Most capable",
                "command-r-plus": "Best Cohere", "grok-2": "Latest Grok",
            }
            # ── Retro green terminal theme ──
            _PT = PtStyle.from_dict({
                "dialog": "bg:#0a0f14", "dialog.body": "bg:#0a0f14",
                "dialog frame.border": "#1a3a1a",
                "dialog frame.label": "fg:#ffd700 bold",
                "dialog shadow": "bg:#000000",
                "text": "#00ff41",
                "button": "bg:#1a3a1a #00ff41",
                "button.focused": "bg:#00ff41 #0a0f14 bold",
                "current-model": "#00ff41 bold",
            })

            # ═══════════════════════════════════════════════
            #  Provider Grid Picker (2D card grid navigation)
            # ═══════════════════════════════════════════════
            def _pick_provider(prov_list, cur_prov):
                COLS, IW = 4, 18  # 4 columns, 18-char inner card width
                sel = [next((i for i, p in enumerate(prov_list) if p == cur_prov), 0)]

                def _frags():
                    frags = []
                    N = len(prov_list)
                    for rs in range(0, N, COLS):
                        cards = [(rs + c, prov_list[rs + c]) for c in range(COLS) if rs + c < N]
                        for ln in ("top", "icon", "name", "desc", "bot"):
                            for j, (idx, pn) in enumerate(cards):
                                is_sel = idx == sel[0]
                                bs = "fg:#00ff41 bold" if is_sel else "fg:#1a3a1a"
                                bg = "bg:#162416 " if is_sel else ""
                                icon, desc, badge = _PMETA.get(pn, ("◆", pn, ""))
                                if ln == "top":
                                    frags.append((bs, "\u250c" + "\u2500" * IW + "\u2510"))
                                elif ln == "bot":
                                    frags.append((bs, "\u2514" + "\u2500" * IW + "\u2518"))
                                elif ln == "icon":
                                    frags.append((bs, "\u2502"))
                                    frags.append((f"{bg}#00ff41", f" {icon} "))
                                    rem = IW - 3
                                    if badge:
                                        bc = "#00ff41 bold" if badge == "FREE" else "#00bfff bold"
                                        frags.append((f"{bg}", " " * max(0, rem - len(badge))))
                                        frags.append((f"{bg}{bc}", badge))
                                    else:
                                        frags.append((f"{bg}", " " * rem))
                                    frags.append((bs, "\u2502"))
                                elif ln == "name":
                                    nm = pn.upper()
                                    if pn == cur_prov:
                                        nm += " \u25cf"
                                    ns = f"{bg}#ffd700 bold" if is_sel else f"{bg}#00ff41"
                                    frags.append((bs, "\u2502"))
                                    frags.append((ns, f" {nm}"))
                                    frags.append((f"{bg}", " " * max(0, IW - len(nm) - 1)))
                                    frags.append((bs, "\u2502"))
                                elif ln == "desc":
                                    dt = desc[:IW - 2]
                                    frags.append((bs, "\u2502"))
                                    frags.append((f"{bg}#4a8a4a", f" {dt}"))
                                    frags.append((f"{bg}", " " * max(0, IW - len(dt) - 1)))
                                    frags.append((bs, "\u2502"))
                                if j < len(cards) - 1:
                                    frags.append(("", " "))
                            frags.append(("", "\n"))
                    if frags:
                        frags.pop()  # remove trailing newline
                    return frags

                ctrl = FormattedTextControl(_frags, focusable=True, show_cursor=False)
                win = Window(content=ctrl, dont_extend_height=True, dont_extend_width=True)
                hdr = Label(text=f" {cur_prov} / {cfg.get('model', 'N/A')}\n", style="class:current-model")
                dialog = Dialog(title=" SELECT AI PROVIDER ",
                    body=HSplit([hdr, win]),
                    buttons=[
                        Button("Select", handler=lambda: app_cur.get_app().exit(result=prov_list[sel[0]])),
                        Button("Exit",   handler=lambda: app_cur.get_app().exit(result=None))])
                kb = KeyBindings()
                @kb.add("up", filter=has_focus(win))
                def _(e): sel[0] = max(0, sel[0] - COLS)
                @kb.add("down", filter=has_focus(win))
                def _(e): sel[0] = min(len(prov_list) - 1, sel[0] + COLS)
                @kb.add("left", filter=has_focus(win))
                def _(e): sel[0] = max(0, sel[0] - 1)
                @kb.add("right", filter=has_focus(win))
                def _(e): sel[0] = min(len(prov_list) - 1, sel[0] + 1)
                @kb.add("enter", filter=has_focus(win))
                def _(e): e.app.exit(result=prov_list[sel[0]])
                @kb.add("escape")
                def _(e): e.app.exit(result=None)
                kb.add("tab")(focus_next)
                kb.add("s-tab")(focus_previous)
                app = Application(layout=Layout(dialog, focused_element=win),
                    style=_PT, full_screen=True,
                    key_bindings=merge_key_bindings([load_key_bindings(), kb]))
                return app.run()

            # ═══════════════════════════════════════════════
            #  Model List Picker (with [FREE]/[PAID] badges)
            # ═══════════════════════════════════════════════
            def _pick_model(prov_name, model_data, cur_model):
                """model_data: list of (model_id, tier) tuples."""
                vals = [(m, m) for m, t in model_data]
                dflt = cur_model if cur_model in {m for m, _ in model_data} else None
                radio = RadioList(values=vals, default=dflt,
                    open_character="", select_character="", close_character="",
                    show_cursor=False)
                tier_map = dict(model_data)

                def _enter():
                    radio.current_value = radio.values[radio._selected_index][0]
                    app_cur.get_app().exit(result=radio.current_value)
                radio._handle_enter = _enter

                def _frags():
                    result = []
                    for i, (val, _) in enumerate(radio.values):
                        is_s = i == radio._selected_index
                        bg = "bg:#162416 " if is_s else ""
                        tier = tier_map.get(val, "paid")
                        if tier == "free":
                            result.append((f"{bg}bg:#0a3a0a #00ff41 bold", " FREE "))
                        else:
                            result.append((f"{bg}bg:#3a3a0a #ffd700 bold", " PAID "))
                        result.append((f"{bg}", "  "))
                        dn = val.split("/", 1)[1] if "/" in val else val
                        result.append((f"{bg}#00ff41 bold" if is_s else f"{bg}#00ff41", dn))
                        hint = _MHINTS.get(val, "")
                        if val == cur_model:
                            hint = "(current)" + (f" · {hint}" if hint else "")
                        if hint:
                            pad = max(1, 45 - len(dn))
                            result.append((f"{bg}", " " * pad))
                            result.append((f"{bg}#4a8a4a", hint))
                        if is_s:
                            result.append(("[SetCursorPosition]", ""))
                        result.append(("", "\n"))
                    if result:
                        result.pop()
                    return result

                radio._get_text_fragments = _frags
                radio.control.text = _frags
                def _ok():
                    radio.current_value = radio.values[radio._selected_index][0]
                    app_cur.get_app().exit(result=radio.current_value)
                dialog = Dialog(title=f" {prov_name.upper()} \u2014 AVAILABLE MODELS ",
                    body=HSplit([Label(text=f" {len(model_data)} models available\n"), radio], padding=1),
                    buttons=[Button("Select", handler=_ok),
                             Button("Back",   handler=lambda: app_cur.get_app().exit(result=None))])
                kb = KeyBindings()
                kb.add("tab")(focus_next)
                kb.add("s-tab")(focus_previous)
                @kb.add("escape")
                def _(e): e.app.exit(result=None)
                app = Application(layout=Layout(dialog, focused_element=radio),
                    style=_PT, full_screen=True,
                    key_bindings=merge_key_bindings([load_key_bindings(), kb]))
                return app.run()

            # ── Main loop: provider grid → model list ──
            providers = sorted(set(p for p, t in _MODEL_PROVIDER.values()))
            while True:
                current_prov = cfg.get('provider', 'anthropic')
                prov_selected = _pick_provider(providers, current_prov)
                if not prov_selected:
                    break  # Esc / Exit → done
                prov_model_data = sorted(
                    [(m, t) for m, (p, t) in _MODEL_PROVIDER.items() if p == prov_selected],
                    key=lambda x: (0 if x[1] == "free" else 1, x[0]))
                current_model = cfg.get('model', 'claude-sonnet-4-6')
                mod_selected = _pick_model(prov_selected, prov_model_data, current_model)
                if not mod_selected:
                    continue  # Back → provider picker
                from aira.brain import init_client as reinit_client
                cfg["provider"] = prov_selected
                cfg["model"] = mod_selected
                (AIRA_HOME / "config.json").write_text(json.dumps(cfg, indent=2))
                key = cfg.get("openrouter_key", cfg.get("api_key", "")) if prov_selected == "openrouter" else cfg.get("api_key", "")
                reinit_client(key, provider=prov_selected, model=mod_selected)
                console.print(f"[{THEME['success']}]\u2713 Switched to {prov_selected}/{mod_selected}[/]")
                break

        # /model <model_name> — auto-detect provider
        elif sub not in ("list", "set", "route", "reset"):
            model_name = sub
            auto_result = _MODEL_PROVIDER.get(model_name)
            if not auto_result:
                console.print(f"[{THEME['error']}]Unknown model. Use /model set <provider> <model>[/]")
                console.print(f"[{THEME['dim']}]Known models: {', '.join(list(_MODEL_PROVIDER)[:20])}...[/]")
            else:
                auto_prov, auto_tier = auto_result
                from aira.brain import init_client as reinit_client
                cfg["provider"] = auto_prov
                cfg["model"] = model_name
                (AIRA_HOME / "config.json").write_text(json.dumps(cfg, indent=2))
                reinit_client(cfg.get("api_key",""), provider=auto_prov, model=model_name)
                console.print(f"[{THEME['success']}]✓ Switched to {auto_prov}/{model_name}[/]")

        elif sub == "list":
            console.print(f"[{THEME['accent2']}]Current:[/] {cfg.get('provider', 'anthropic')} / {cfg.get('model', 'claude-sonnet-4-6')}")
            if TASK_ROUTES:
                console.print(f"\n[{THEME['accent2']}]Task routes:[/]")
                for task, (prov, mod) in TASK_ROUTES.items():
                    console.print(f"  [{THEME['dim']}]{task}:[/] {prov}/{mod}")
            console.print(f"\n[{THEME['accent']}]Available models ({len(_MODEL_PROVIDER)} total):[/]")
            prov_models = {}
            for mod, (prov, tier) in sorted(_MODEL_PROVIDER.items()):
                prov_models.setdefault(prov, []).append(mod)
            for prov, mods in sorted(prov_models.items()):
                active = "◈" if prov == cfg.get('provider') else " "
                display = ", ".join(mods[:12])
                remaining = len(mods) - 12
                if remaining > 0:
                    display += f" [{THEME['dim']}](+{remaining} more)[/]"
                console.print(f"  {active}[{THEME['accent2']}]{prov}:[/] [{THEME['dim']}]{display}[/]")
            console.print(f"\n[{THEME['dim']}]Use /model (no args) for interactive picker[/]")
        elif sub == "set" and len(parts2) >= 3:
            from aira.brain import init_client as reinit_client
            new_prov = parts2[1].lower()
            new_mod = parts2[2]
            if new_prov in PROVIDER_NAMES:
                cfg["provider"] = new_prov
                cfg["model"] = new_mod
                (AIRA_HOME / "config.json").write_text(json.dumps(cfg, indent=2))
                reinit_client(cfg.get("api_key",""), provider=new_prov, model=new_mod)
                console.print(f"[{THEME['success']}]✓ Default model: {new_prov}/{new_mod}[/]")
            else:
                console.print(f"[{THEME['error']}]Unknown provider: {new_prov}[/]")
                console.print(f"  [{THEME['dim']}]Available: {', '.join(PROVIDER_NAMES)}[/]")
        elif sub == "route" and len(parts2) >= 4:
            task_type = parts2[1].lower()
            new_prov = parts2[2].lower()
            new_mod = parts2[3]
            if new_prov in PROVIDER_NAMES:
                set_task_route(task_type, new_prov, new_mod)
                cfg.setdefault("task_routes", {})[task_type] = f"{new_prov}:{new_mod}"
                (AIRA_HOME / "config.json").write_text(json.dumps(cfg, indent=2))
                console.print(f"[{THEME['success']}]✓ Routed '{task_type}' → {new_prov}/{new_mod}[/]")
            else:
                console.print(f"[{THEME['error']}]Unknown provider: {new_prov}[/]")
        elif sub == "reset":
            TASK_ROUTES.clear()
            if "task_routes" in cfg:
                del cfg["task_routes"]
                (AIRA_HOME / "config.json").write_text(json.dumps(cfg, indent=2))
            console.print(f"[{THEME['success']}]✓ Task routes reset[/]")
        else:
            console.print(f"[{THEME['dim']}]Usage: /model <name>  or  /model set <provider> <model>[/]")

    # ── /scan ──
    elif cmd == "/scan":
        try:
            path = arg or "."
            with spinner_context(f"Scanning: {path}"):
                scan = scan_directory(path, max_depth=3)
            if "error" in scan:
                console.print(f"[{THEME['error']}]Error: {scan['error']}[/]")
            else:
                total_mb = scan["total_size"] / (1024*1024)
                tree = Tree(f"[bold {THEME['accent']}]{scan['path']}[/]")
                tree.label += f" [{THEME['dim']}]({scan['total_folders']} folders, {scan['total_files']} files, {total_mb:.1f}MB)[/]"
                for entry in scan["entries"][:60]:
                    if entry["depth"] >= 3:
                        continue
                    prefix = "  " * entry["depth"]
                    if entry["type"] == "dir":
                        tree.add(f"[{THEME['info']}]{entry['name']}/[/]")
                    else:
                        size_str = f"{entry['size']:,}B" if entry['size'] < 1024 else f"{entry['size']/1024:.1f}KB" if entry['size'] < 1024*1024 else f"{entry['size']/(1024*1024):.1f}MB"
                        tree.add(f"{entry['name']} [{THEME['dim']}]({size_str})[/]")
                console.print(tree)
                if scan["large_files"]:
                    console.print(f"\n[{THEME['warning']}]Large files (>10MB):[/]")
                    for f in scan["large_files"][:5]:
                        console.print(f"  [{THEME['dim']}]{f['name']}[/] ({f['size']/(1024*1024):.1f}MB)")
        except Exception as e:
            console.print(f"[{THEME['error']}]Scan failed: {e}[/]")

    # ── /build ──
    elif cmd == "/build":
        if not arg:
            types = "website, landing, portfolio, dashboard, blog, game, pwa, tailwind, bootstrap, react, webapp, express, flask, fastapi, api, python, cli, scraper, discord, script, batch, powershell, forge, photon, pixel, matter, ecs, search, render, workflow, audio, sprite, tilemap"
            console.print(f"[{THEME['accent2']}]Usage: /build <type> <name>[/]")
            console.print(f"[{THEME['dim']}]Types: {types}[/]")
        else:
            try:
                parts2 = arg.split(None, 1)
                btype = parts2[0].lower()
                bname = parts2[1].strip() if len(parts2) > 1 else btype
                with spinner_context(f"Building {btype}: {bname}"):
                    result = generate_project(btype, bname)
                if result["success"]:
                    console.print(f"[{THEME['success']}]✓ {btype} project created:[/] [{THEME['accent2']}]{result['path']}[/]")
                    for f in result["files"]:
                        console.print(f"  [{THEME['dim']}]└─[/] {f}")
                else:
                    console.print(f"[{THEME['error']}]✗ {result['error']}[/]")
            except Exception as e:
                console.print(f"[{THEME['error']}]Build failed: {e}[/]")

    # ── /explore ──
    elif cmd == "/explore":
        try:
            path = arg or "."
            with spinner_context(f"Exploring: {path}"):
                scan = scan_directory(path, max_depth=2)
            if "error" in scan:
                console.print(f"[{THEME['error']}]Error: {scan['error']}[/]")
            else:
                labels = {0: "📁", 1: "  ├─", 2: "  │  └─"}
                for entry in scan["entries"][:40]:
                    indent = "  " * entry["depth"]
                    icon = "📁 " if entry["type"] == "dir" else "📄 "
                    size_str = ""
                    if entry["type"] == "file":
                        s = entry["size"]
                        size_str = f" [{THEME['dim']}]({s:,}B)[/]" if s < 1024 else f" [{THEME['dim']}]({s/1024:.1f}KB)[/]" if s < 1024*1024 else f" [{THEME['dim']}]({s/(1024*1024):.1f}MB)[/]"
                    console.print(f"{indent}{icon}[{THEME['info']}]{entry['name']}[/]{size_str}")
        except Exception as e:
            console.print(f"[{THEME['error']}]Explore failed: {e}[/]")

    # ── /gateway ──
    elif cmd == "/gateway":
        parts2 = arg.split(None, 1) if arg else []
        sub = parts2[0].lower().strip() if parts2 else "status"

        if sub == "status" or not sub:
            statuses = gateway_status()
            t = Table(box=box.SIMPLE, show_header=True, header_style=f"bold {THEME['accent2']}")
            t.add_column("Platform", style=THEME['info'])
            t.add_column("Status", style="white")
            t.add_column("Error", style=THEME['error'])
            for p in ["telegram", "discord", "slack", "signal"]:
                s = next((x for x in statuses if x["platform"] == p), None)
                t.add_row(p, f"[green]● running[/]" if s and s["running"] else "[dim]○ stopped[/]", (s.get("error","") if s else "")[:40])
            console.print(t)
            cfg = gateway_get_config()
            for p, c in cfg.items():
                has_key = any(v for v in c.values())
                console.print(f"  {'[green]✓[/]' if has_key else '[dim]○[/]'} {p}: {'configured' if has_key else 'not set'}")

        elif sub in ("setup", "telegram", "discord", "slack", "signal"):
            platform = sub if sub != "setup" else (parts2[1].lower() if len(parts2) > 1 else "")
            if not platform:
                platform = console.input(f"[{THEME['accent2']}]Platform (telegram/discord/slack/signal): [/]").strip().lower()
            if platform not in ("telegram", "discord", "slack", "signal"):
                console.print(f"[{THEME['error']}]Unknown platform. Use: telegram, discord, slack, or signal[/]")
            else:
                prompts = {
                    "telegram": [("token", "Bot Token (from @BotFather)")],
                    "discord": [("token", "Bot Token (from Discord Developer Portal)")],
                    "slack": [("token", "Bot Token (xoxb-...)"), ("signing_secret", "Signing Secret (optional, press enter to skip)")],
                    "signal": [("phone", "Phone number (+1234567890)")],
                }
                valid = False
                while not valid:
                    for key, prompt in prompts[platform]:
                        val = console.input(f"[{THEME['accent2']}]{prompt}: [/]").strip()
                        if val:
                            gateway_set_config(platform, key, val)
                    with spinner_context(f"Validating {platform} credentials..."):
                        v = gateway_validate_token(platform)
                    if v["valid"]:
                        console.print(f"  [bold green]✓[/] Token valid — {v.get('info', 'ok')}")
                        valid = True
                    else:
                        console.print(f"  [bold red]✗[/] {v.get('error', 'Invalid')}")
                        retry = console.input(f"[{THEME['accent2']}]Retry? (y/n): [/]").strip().lower()
                        if retry != "y":
                            break
                if valid:
                    start = console.input(f"[{THEME['accent2']}]Start {platform} bot now? (y/n): [/]").strip().lower()
                    if start == "y":
                        r = gateway_connect(platform)
                        console.print(f"[{THEME['success'] if r['success'] else THEME['error']}]{'✓ Started' if r['success'] else '✗ ' + r['error']}[/]")

        elif sub == "stop" and len(parts2) >= 2:
            r = gateway_disconnect(parts2[1].lower())
            console.print(f"[{THEME['success'] if r['success'] else THEME['error']}]{'✓ Stopped' if r['success'] else '✗ ' + r['error']}[/]")

        else:
            s = gateway_status()
            running = [x["platform"] for x in s if x["running"]]
            console.print(f"[{THEME['accent2']}]Gateway status:[/] {len(running)}/4 running\n")
            console.print(f"  /gateway                  [{THEME['dim']}]Show status[/]")
            console.print(f"  /gateway telegram         [{THEME['dim']}]Setup & start Telegram bot[/]")
            console.print(f"  /gateway discord          [{THEME['dim']}]Setup & start Discord bot[/]")
            console.print(f"  /gateway slack            [{THEME['dim']}]Setup & start Slack bot[/]")
            console.print(f"  /gateway signal           [{THEME['dim']}]Setup & start Signal bot[/]")
            console.print(f"  /gateway stop <platform>  [{THEME['dim']}]Stop a bot[/]")

    # ── /mcp ──
    elif cmd == "/mcp":
        if not MCP_AVAILABLE:
            console.print(f"[{THEME['error']}]MCP SDK not installed. Run: pip install mcp[/]")
        else:
            parts2 = arg.split(None, 1) if arg else []
            sub = parts2[0].lower().strip() if parts2 else "list"
            if sub == "list" or not sub:
                servers = mcp_list_servers()
                if not servers:
                    console.print(f"[{THEME['dim']}]No MCP servers configured.[/]")
                else:
                    t = Table(box=box.SIMPLE, show_header=True, header_style=f"bold {THEME['accent2']}")
                    t.add_column("Name", style=THEME['info'])
                    t.add_column("Preset", style=THEME['dim'])
                    t.add_column("Command", style="white")
                    t.add_column("Args", style=THEME['dim'])
                    for s in servers:
                        is_preset = "yes" if s.get("args", "").startswith("-y") or "MCP_PRESETS" in str(type(s)) else ""
                        t.add_row(s["name"], "✓" if s["name"] in MCP_PRESETS else "", s["command"], s.get("args", ""))
                    console.print(t)
                console.print(f"\n  [{THEME['dim']}]/mcp enable <preset> [params] — quick-add a preset server[/]")
                console.print(f"  [{THEME['dim']}]/mcp presets — list available presets[/]")
                console.print(f"  [{THEME['dim']}]/mcp add <name> <command> [args] — manual add[/]")
                console.print(f"  [{THEME['dim']}]/mcp remove <name> — remove server[/]")
                console.print(f"  [{THEME['dim']}]/mcp tools <name> — list tools[/]")
                console.print(f"  [{THEME['dim']}]/mcp call <name> <tool> [json_args] — call tool[/]")
                console.print(f"  [{THEME['dim']}]/mcp discover — scan for existing MCP configs[/]")
            elif sub == "presets":
                t = Table(box=box.SIMPLE, show_header=True, header_style=f"bold {THEME['accent2']}")
                t.add_column("Preset", style=THEME['info'])
                t.add_column("Description", style="white")
                t.add_column("Usage", style=THEME['dim'])
                for name, p in sorted(MCP_PRESETS.items()):
                    usage = f"/mcp enable {name}" + (" <dirs>" if "{dirs}" in p["args"] else " <db>" if "{db}" in p["args"] else "")
                    t.add_row(name, p["description"], usage)
                console.print(t)
            elif sub == "enable" and len(parts2) >= 2:
                enable_parts = parts2[1].split(None, 1)
                preset_name = enable_parts[0]
                params = enable_parts[1] if len(enable_parts) > 1 else ""
                r = mcp_enable_preset(preset_name, params)
                if r["success"]:
                    console.print(f"[{THEME['success']}]✓ MCP preset enabled: {preset_name}[/]")
                else:
                    if "presets" in r:
                        console.print(f"[{THEME['error']}]✗ Unknown preset. Available: {', '.join(r['presets'])}[/]")
                    else:
                        console.print(f"[{THEME['error']}]✗ {r['error']}[/]")
            elif sub == "discover":
                found = mcp_discover()
                if not found:
                    console.print(f"[{THEME['dim']}]No existing MCP configs found.[/]")
                else:
                    console.print(f"[{THEME['accent2']}]Found MCP servers in local configs:[/]")
                    for f in found:
                        console.print(f"  [{THEME['accent']}]■[/] [{THEME['info']}]{f['name']}[/] ({f['source']}) — {f['command']} {f['args'][:50]}")

            elif sub == "add" and len(parts2) >= 2:
                add_parts = parts2[1].split(None, 1)
                name = add_parts[0]
                cmd_args = add_parts[1] if len(add_parts) > 1 else ""
                cmd_parts = cmd_args.split(None, 1) if cmd_args else []
                command = cmd_parts[0] if cmd_parts else ""
                args = cmd_parts[1] if len(cmd_parts) > 1 else ""
                if not command:
                    console.print(f"[{THEME['error']}]Usage: /mcp add <name> <command> [args][/]")
                else:
                    r = mcp_add_server(name, command, args)
                    if r["success"]:
                        console.print(f"[{THEME['success']}]✓ MCP server added: {name} ({command})[/]")
                    else:
                        console.print(f"[{THEME['error']}]✗ {r['error']}[/]")
            elif sub == "remove" and len(parts2) >= 2:
                r = mcp_remove_server(parts2[1])
                if r["success"]:
                    console.print(f"[{THEME['success']}]✓ MCP server removed: {parts2[1]}[/]")
                else:
                    console.print(f"[{THEME['error']}]✗ {r['error']}[/]")
            elif sub == "tools" and len(parts2) >= 2:
                with spinner_context(f"Connecting to MCP server: {parts2[1]}..."):
                    r = mcp_list_tools(parts2[1])
                if r["success"]:
                    console.print(f"[{THEME['accent2']}]Tools from {parts2[1]}:[/]")
                    for t in r["tools"]:
                        schema_str = json.dumps(t["inputSchema"], indent=1) if t.get("inputSchema") else "{}"
                        console.print(f"  [{THEME['accent']}]■[/] [bold]{t['name']}[/] — {t.get('description', '')}")
                        console.print(f"    [{THEME['dim']}]schema: {schema_str[:200]}[/]")
                else:
                    console.print(f"[{THEME['error']}]✗ {r['error']}[/]")
            elif sub == "call" and len(parts2) >= 2:
                call_parts = parts2[1].split(None, 2)
                server_name = call_parts[0]
                tool_name = call_parts[1] if len(call_parts) > 1 else ""
                json_args = call_parts[2] if len(call_parts) > 2 else "{}"
                if not tool_name:
                    console.print(f"[{THEME['error']}]Usage: /mcp call <server> <tool> [json_args][/]")
                else:
                    try:
                        args_dict = json.loads(json_args)
                    except json.JSONDecodeError:
                        args_dict = {}
                    with spinner_context(f"Calling {tool_name} on {server_name}..."):
                        r = mcp_call_tool(server_name, tool_name, args_dict)
                    if r["success"]:
                        result_text = r["result"]
                        if isinstance(result_text, list):
                            result_text = " ".join(str(x) for x in result_text)
                        console.print(f"[{THEME['success']}]✓ Result:[/]")
                        console.print(str(result_text)[:2000])
                    else:
                        console.print(f"[{THEME['error']}]✗ {r['error']}[/]")
            else:
                console.print(f"[{THEME['error']}]Usage: /mcp [list|add|remove|tools|call][/]")

    # ── /miro ──
    elif cmd == "/miro":
        args = arg.split(None, 2) if arg else []
        a = lambda i: args[i] if len(args) > i else ""

        if not args:
            projects = miro_list_projects()
            if not projects:
                console.print(f"[{THEME['dim']}]No projects. Start: /miro <name> \[add] <task>[/]")
            else:
                console.print(f"[bold {THEME['accent']}]Projects:[/]")
                for p in projects:
                    console.print(f"  [{THEME['accent']}]■[/] {p['name']} [{THEME['dim']}]({p['task_count']} tasks)[/] — {p.get('desc', '')[:40]}")
                console.print(f"\n  [{THEME['dim']}]/miro <name> — show board[/]")

        elif a(0) == "delete" and a(1):
            r = miro_delete_project(a(1))
            console.print(f"[{THEME['success'] if r['success'] else THEME['error']}]{'✓ Deleted' if r['success'] else '✗ ' + r['error']}[/]")

        elif a(0) == "go" and a(1):
            r = miro_move(a(1), "doing")
            console.print(f"[{THEME['success'] if r['success'] else THEME['error']}]{'✓ → Doing' if r['success'] else '✗ ' + r['error']}[/]")

        elif a(0) == "done" and a(1):
            r = miro_move(a(1), "done")
            console.print(f"[{THEME['success'] if r['success'] else THEME['error']}]{'✓ → Done' if r['success'] else '✗ ' + r['error']}[/]")

        elif a(0) == "plan" and a(1):
            project = a(1)
            goal = a(2) or project
            miro_create_project(project, goal)
            console.print(f"[{THEME['dim']}]Planning: {goal}...[/]")
            try:
                prompt = f"Break this goal into 3-8 numbered steps: {goal}"
                resp = get_ai_response([{"role": "user", "content": prompt}], current_project=current_project[0])
                steps = [s.strip().lstrip("123456789. )-") for s in resp.split("\n") if s.strip() and any(c.isdigit() for c in s[:3])]
                if not steps:
                    steps = [s.strip().lstrip("- ") for s in resp.split("- ") if s.strip()][:8]
            except Exception:
                steps = [goal]
            r = miro_decompose(project, goal, steps)
            if r["success"]:
                console.print(f"[{THEME['success']}]✓ Planned {len(r['tasks'])} steps for '{project}'[/]")
                board = miro_get_board(project)
                if board:
                    for item in board["columns"].get("todo", []):
                        console.print(f"  [{THEME['accent']}]■[/] {item['id']} {item['title']}")

        else:
            # /miro <project> [add] <task> — if task arg exists, add. Else show.
            project = a(0)
            rest = a(1)
            if rest and rest != "add" and rest != "show":
                r = miro_add_task(project, rest)
                if r["success"]:
                    all_tasks = miro_get_board(project)
                    count = sum(len(v) for v in all_tasks["columns"].values()) if all_tasks else 0
                    console.print(f"[{THEME['success']}]✓ Added to {project}[/] [{THEME['dim']}]({count} total)[/]")
                else:
                    if "not found" in r.get("error", ""):
                        miro_create_project(project, "")
                        r2 = miro_add_task(project, rest)
                        if r2["success"]:
                            console.print(f"[{THEME['success']}]✓ Created '{project}' + added task[/]")
            else:
                board = miro_get_board(project)
                if not board:
                    console.print(f"[{THEME['error']}]Project '{project}' not found. Use: /miro <name> <task> to create[/]")
                else:
                    colors = {"todo": THEME['dim'], "doing": THEME['warning'], "done": THEME['success']}
                    labels = {"todo": "📋 TODO", "doing": "🔄 DOING", "done": "✅ DONE"}
                    console.print(f"[bold {THEME['accent']}]Board: {board['name']}[/]  [{THEME['dim']}]{board['desc']}[/]")
                    for col in ["todo", "doing", "done"]:
                        items = board["columns"].get(col, [])
                        if items:
                            console.print(f"\n  [{colors[col]}]{labels[col]} ({len(items)})[/]")
                            for item in items:
                                b = ""
                                if item.get("blocked_by"):
                                    b = f" [{THEME['error']}](waits: {', '.join(item['blocked_by'][:2])})[/]"
                                console.print(f"    [{colors[col]}]■[/] {item['id']} {item['title']}{b}")
                    if not any(board["columns"].values()):
                        console.print(f"  [{THEME['dim']}]Empty. Add tasks: /miro {project} <task description>[/]")
                    console.print(f"\n  [{THEME['dim']}]/miro {project} <task>[/]  /miro go <id>[/]  /miro done <id>[/]  /miro plan {project} <goal>[/]")

    # ── /dashboard ──
    elif cmd == "/dashboard":
        if arg and arg.strip() == "stop":
            r = dashboard_stop()
            console.print(f"[{THEME['success'] if r['success'] else THEME['error']}]{'✓ Dashboard stopped' if r['success'] else '✗ ' + r['error']}[/]")
        else:
            port = int(arg) if arg and arg.isdigit() else 8080
            r = dashboard_start(port)
            if r["success"]:
                console.print(f"[{THEME['success']}]✓ Dashboard running at[/] [{THEME['accent2']}]{r['url']}[/]")
            else:
                console.print(f"[{THEME['error']}]✗ {r['error']}[/]")

    # ── /web / /serve ──
    elif cmd in ("/web", "/serve"):
        if arg and arg.strip().lower() == "stop":
            tr = stop_web_tunnel()
            r = stop_http_server()
            stopped = tr.get("success") or r.get("success")
            console.print(f"[{THEME['success'] if stopped else THEME['error']}]{'✓ Graph server stopped' if stopped else '✗ Nothing running'}[/]")
            if tr.get("success"):
                console.print(f"  [{THEME['dim']}]Tunnel closed: {tr.get('url', '')}[/]")
        else:
            parts = arg.split() if arg else []
            port = 8000
            host = "0.0.0.0"
            tunnel = False
            tunnel_provider = "auto"
            i = 0
            while i < len(parts):
                p = parts[i]
                low = p.lower()
                if low in ("local", "localhost", "offline"):
                    host = "127.0.0.1"
                elif low in ("public", "online", "network", "lan"):
                    host = "0.0.0.0"
                elif low in ("tunnel", "internet", "expose", "remote"):
                    tunnel = True
                    if i + 1 < len(parts) and parts[i + 1].lower() in ("cloudflared", "ngrok", "localtunnel"):
                        tunnel_provider = parts[i + 1].lower()
                        i += 1
                elif low in ("cloudflared", "ngrok", "localtunnel"):
                    tunnel = True
                    tunnel_provider = low
                elif p.isdigit():
                    port = int(p)
                i += 1

            result = start_http_server(port, host=host)
            if result["success"]:
                console.print(f"[{THEME['success']}]✓ Trajectory & memory graph running[/]")
                console.print(f"  [{THEME['accent2']}]Local:[/]   {result['local_url']}")
                if result.get("network_accessible"):
                    console.print(f"  [{THEME['accent2']}]Network:[/] {result['network_url']}")
                    console.print(f"  [{THEME['dim']}]Same Wi‑Fi: use Network URL[/]")
                if tunnel:
                    available = list_tunnel_providers()
                    if not available and tunnel_provider == "auto":
                        console.print(f"[{THEME['warning']}]No tunnel tools found.[/]")
                        console.print(f"  [{THEME['dim']}]Install cloudflared, ngrok, or Node.js+npx[/]")
                    else:
                        with spinner_context(f"Opening public tunnel ({tunnel_provider})..."):
                            tr = start_web_tunnel(port, provider=tunnel_provider)
                        if tr.get("success"):
                            console.print(f"  [{THEME['accent']}]Internet:[/] {tr['url']}")
                            console.print(f"  [{THEME['dim']}]Provider: {tr.get('provider', 'auto')} — share this URL worldwide[/]")
                            console.print(f"  [{THEME['warning']}]Public URL exposes your memory graph — stop with /web stop[/]")
                        else:
                            console.print(f"[{THEME['error']}]✗ Tunnel failed: {tr.get('error', 'unknown')}[/]")
                            if tr.get("hint"):
                                console.print(f"  [{THEME['dim']}]{tr['hint']}[/]")
                elif not result.get("network_accessible"):
                    console.print(f"  [{THEME['dim']}]Use /web tunnel for public internet access[/]")
                console.print(f"  [{THEME['dim']}]Dashboard: {result['path']}/index.html[/]")
                console.print(f"  [{THEME['dim']}]Stop with: /web stop[/]")
            else:
                if "Already running" in result.get("error", ""):
                    console.print(f"[{THEME['warning']}]Server already running[/]")
                    console.print(f"  [{THEME['accent2']}]Local:[/]   {result.get('local_url', result.get('url'))}")
                    if result.get("network_url") and result.get("network_url") != result.get("local_url"):
                        console.print(f"  [{THEME['accent2']}]Network:[/] {result['network_url']}")
                else:
                    console.print(f"[{THEME['error']}]✗ {result['error']}[/]")

    # ── /doctor ──
    elif cmd == "/doctor":
        console.print(f"[bold {THEME['accent']}]AIRA Diagnostics[/]")
        console.print(f"[{THEME['dim']}]Running health checks...[/]\n")
        checks = []
        def add(name, status, detail=""):
            icon = "[green]✓[/]" if status else "[red]✗[/]"
            detail_str = f"  [{THEME['dim']}]{detail}[/]" if detail else ""
            checks.append(f"  {icon} [{THEME['accent2']}]{name}[/]{detail_str}")
            return status

        # Python
        add("Python", True, f"{sys.version.split()[0]}")
        # Node
        try:
            v = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=5)
            add("Node.js", v.returncode == 0, v.stdout.strip() if v.returncode == 0 else "not found")
        except: add("Node.js", False, "not found")
        # Git
        try:
            v = subprocess.run(["git", "--version"], capture_output=True, text=True, timeout=5)
            add("Git", v.returncode == 0, v.stdout.strip()[:30] if v.returncode == 0 else "not found")
        except: add("Git", False, "not found")
        # API Key
        ak = cfg.get("api_key", "")
        add("API Key", bool(ak), f"{'set' if ak else 'missing'}")
        # Provider
        prov = cfg.get("provider", "")
        add("Provider", bool(prov), prov if prov else "not set")
        # Model
        mod = cfg.get("model", "")
        add("Model", bool(mod), mod if mod else "not set")
        # Internet
        try:
            import urllib.request
            urllib.request.urlopen("https://cloudflare-dns.com", timeout=5)
            add("Internet", True, "connected")
        except: add("Internet", False, "unreachable")
        # Config file
        cfg_ok = CONFIG_FILE.exists()
        add("Config File", cfg_ok, str(CONFIG_FILE) if cfg_ok else "missing")
        # AIRA Home
        home_ok = AIRA_HOME.exists()
        add("AIRA Home", home_ok, str(AIRA_HOME) if home_ok else "missing")
        # Docker
        try:
            v = subprocess.run(["docker", "--version"], capture_output=True, text=True, timeout=5)
            add("Docker", v.returncode == 0, v.stdout.strip()[:30] if v.returncode == 0 else "not found")
        except: add("Docker", False, "not found")
        # Memory DB
        db_path = AIRA_HOME / "memory.db"
        add("Memory DB", db_path.exists() or True, f"{'exists' if db_path.exists() else 'will be created on first use'}")
        # Memory read/write test
        try:
            from aira.memory import save_memory, search_memory
            save_memory("__doctor_test__", "__test__")
            hits = search_memory("__doctor_test__")
            add("Memory R/W", True, f"{len(hits)} results")
        except Exception as e:
            add("Memory R/W", False, str(e)[:40])
        # Disk space
        try:
            import shutil
            usage = shutil.disk_usage(AIRA_HOME)
            free_gb = usage.free / (1024**3)
            add("Disk Free", free_gb > 0.5, f"{free_gb:.1f}GB available")
        except: add("Disk Free", False, "unknown")

        # API Provider test - check actual config file
        try:
            actual_cfg = json.loads(CONFIG_FILE.read_text()) if CONFIG_FILE.exists() else {}
            ak = actual_cfg.get("api_key", "")
            prov = actual_cfg.get("provider", "")
            mod = actual_cfg.get("model", "")
            proj = actual_cfg.get("default_project", "AIRA")
            if ak and prov:
                try:
                    from aira.brain import get_ai_response
                    test = get_ai_response([{"role": "user", "content": "Say OK"}], current_project=proj)
                    add("AI Provider", bool(test), f"responded ({len(test)} chars)" if test else "empty")
                except Exception as e:
                    add("AI Provider", False, str(e)[:50])
            else:
                add("AI Provider", False, "no key/provider configured")
        except Exception as e:
            add("AI Provider", False, f"config error: {str(e)[:50]}")

        for c in checks:
            console.print(c)
        ok = sum(1 for c in checks if "[green]" in c)
        fail = sum(1 for c in checks if "[red]" in c)
        console.print(f"\n  [{THEME['dim']}]━━━━━━━━━━━━━━━━━━━━[/]")
        if fail == 0:
            console.print(f"  [bold green]All {ok} checks passed[/]")
        else:
            console.print(f"  [bold yellow]{ok} passed, {fail} failed[/]")

    # ── /recap ──
    elif cmd == "/recap":
        if not conversation:
            console.print(f"[{THEME['dim']}]No conversation to recap.[/]")
        else:
            msgs = conversation[-40:]
            user_msgs = [m for m in msgs if m.get("role") == "user"]
            asst_msgs = [m for m in msgs if m.get("role") == "assistant"]
            tool_calls = {"commands": 0, "memories": 0, "web": 0, "subagents": 0}
            files_mod = set()
            for m in asst_msgs:
                c = m.get("content", "")
                if "<CMD>" in c: tool_calls["commands"] += c.count("<CMD>")
                if "<MEMORY" in c: tool_calls["memories"] += c.count("<MEMORY")
                if "<WEB_SEARCH>" in c: tool_calls["web"] += c.count("<WEB_SEARCH>")
                if "<SUBAGENT" in c: tool_calls["subagents"] += c.count("<SUBAGENT")
                for match in __import__("re").findall(r"(?:write|patch|edit|create)\s+[\"']?([\w/\\.-]+)", c.lower()):
                    files_mod.add(match)
            last = user_msgs[-1]["content"][:120] if user_msgs else ""
            console.print(f"[bold {THEME['accent']}]Session Recap[/]")
            console.print(f"  [{THEME['accent2']}]Messages:[/] {len(msgs)} ({len(user_msgs)} user, {len(asst_msgs)} AI)")
            console.print(f"  [{THEME['accent2']}]Tool calls:[/] {sum(tool_calls.values())} total")
            for k, v in tool_calls.items():
                if v: console.print(f"    {k}: {v}")
            if files_mod:
                console.print(f"  [{THEME['accent2']}]Files touched:[/]")
                for f in sorted(files_mod)[:8]:
                    console.print(f"    {f}")
            console.print(f"  [{THEME['accent2']}]Last query:[/] {last}…" if len(last) == 120 else f"  [{THEME['accent2']}]Last query:[/] {last}")

    # ── /usage ──
    elif cmd == "/usage":
        from aira.brain import get_usage
        u = get_usage()
        mod = cfg.get("model", "unknown")
        cost = estimate_cost(mod, u["prompt"], u["completion"])
        console.print(f"[bold {THEME['accent']}]Token Usage[/]")
        console.print(f"  [{THEME['accent2']}]Prompt:[/]     {u['prompt']:,}")
        console.print(f"  [{THEME['accent2']}]Completion:[/] {u['completion']:,}")
        console.print(f"  [{THEME['accent2']}]Cached:[/]    {u['cached']:,}")
        console.print(f"  [{THEME['accent2']}]Total:[/]     {u['prompt'] + u['completion']:,}")
        console.print(f"  [{THEME['accent2']}]Est. cost:[/] ${cost:.6f}")

    # ── /cost ──
    elif cmd == "/cost":
        from aira.brain import get_usage
        u = get_usage()
        mod = cfg.get("model", "unknown")
        console.print(f"[bold {THEME['accent']}]Cost Estimate ({mod})[/]")
        console.print(f"  [{THEME['accent2']}]Tokens:[/] {u['prompt'] + u['completion']:,}")
        console.print(f"  [{THEME['accent2']}]Cost:[/]   ${estimate_cost(mod, u['prompt'], u['completion']):.6f}")

    # ── /pulse (secret) ──
    elif cmd == "/pulse":
        with spinner_context("Running system pulse..."):
            snap = get_system_snapshot()
            net = get_network_info()
        from rich.table import Table as RTable
        t = RTable(box=box.SIMPLE, show_header=False, expand=False)
        t.add_column("Metric", style=THEME['accent2'])
        t.add_column("Value", style="white")
        t.add_row("OS", f"{snap['os']} {snap.get('os_version', '')}")
        t.add_row("Host", snap['hostname'])
        t.add_row("Uptime", f"{snap['uptime_hours']:.1f}h")
        t.add_row("CPU", f"{snap['cpu_percent']}% ({snap['cpu_cores']} cores)")
        t.add_row("RAM", f"{snap['ram_used_percent']}% ({snap['ram_available_gb']:.1f}GB free)")
        t.add_row("Disk", f"{snap['disk_used_percent']}% ({snap['disk_free_gb']:.1f}GB free)")
        t.add_row("Python", snap['python'])
        t.add_row("Public IP", net['public_ip'])
        t.add_row("CWD", snap['cwd'])
        if snap.get('top_processes'):
            top = snap['top_processes'][0]
            t.add_row("Top CPU", f"{top['name']} ({top['cpu']:.1f}%)")
        console.print(Panel(t, title=f"[bold {THEME['accent']}]⚡ System Pulse[/]", border_style=THEME['accent']))

    # ── /forge (secret) ──
    elif cmd == "/forge":
        if not arg:
            console.print(f"[{THEME['error']}]Usage: /forge <description of what to create>[/]")
        else:
            console.print(f"[{THEME['dim']}]Forging: {arg[:80]}...[/]")
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            conversation.append({"role": "user", "content": f"Create this project NOW with complete working files. User's Desktop path: {desktop}. Save files there unless otherwise specified. Use Windows commands (mkdir, echo). No questions. Use <CMD> to create all files.\n\n{arg}"})
            try:
                save_checkpoint(conversation)
            except Exception:
                pass
            with spinner_context("AIRA forging..."):
                try:
                    memories = []
                    if cfg.get("auto_memory", True):
                        try:
                            memories = search_memory(arg[:100], limit=3)
                        except Exception:
                            pass
                    raw_response = get_ai_response(conversation, context_memories=memories, current_project=current_project[0])
                    directives = parse_ai_directives(raw_response)
                    print_ai_response(directives["clean_text"])
                    execute_directives(directives, cfg, current_project[0], conversation)
                    conversation.append({"role": "assistant", "content": raw_response})
                except Exception as e:
                    console.print(f"[{THEME['error']}]Forge failed: {e}[/]")

    # ── /auto ──
    elif cmd == "/auto":
        if not arg:
            console.print(f"[{THEME['error']}]Usage: /auto <task description>[/]")
        else:
            console.print(f"[{THEME['accent2']}]⚡ Auto mode:[/] {arg}")
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            conversation.append({"role": "user", "content": f"Execute this task NOW. User Desktop path: {desktop}. Use Windows commands (mkdir, echo, type nul). No questions. No confirmation. Use <CMD>.\n\nTASK: {arg}"})
            try:
                save_checkpoint(conversation)
            except Exception:
                pass
            with spinner_context("AIRA in auto mode..."):
                try:
                    memories = []
                    if cfg.get("auto_memory", True):
                        try:
                            memories = search_memory(arg[:100], limit=3)
                        except Exception:
                            pass
                    raw_response = get_ai_response(conversation, context_memories=memories, current_project=current_project[0])
                    directives = parse_ai_directives(raw_response)
                    print_ai_response(directives["clean_text"])
                    execute_directives(directives, cfg, current_project[0], conversation)
                    conversation.append({"role": "assistant", "content": raw_response})
                except Exception as e:
                    console.print(f"[{THEME['error']}]Auto task failed: {e}[/]")

    # ── /find ──
    elif cmd == "/find":
        if not arg:
            console.print(f"[{THEME['error']}]Usage: /find <text pattern>[/]")
        else:
            with spinner_context(f"Searching for: {arg[:50]}"):
                results = search_files(arg)
            if results:
                console.print(f"[{THEME['accent2']}]Found {len(results)} matches for:[/] {arg}")
                for r in results[:15]:
                    console.print(f"  [{THEME['dim']}]{r['file']}:{r['line']}[/] {r['match']}")
            else:
                console.print(f"[{THEME['dim']}]No matches for: {arg}[/]")

    # ── /ps ──
    elif cmd == "/ps":
        sort = arg or "cpu"
        procs = list_processes(sort_by=sort)
        pt = Table(box=box.SIMPLE, show_header=True, header_style=f"bold {THEME['accent2']}")
        pt.add_column("PID", style=THEME['dim'], width=6)
        pt.add_column("Name", style="white")
        pt.add_column("CPU%", justify="right", style=THEME['accent'])
        pt.add_column("MEM%", justify="right", style=THEME['info'])
        for p in procs[:20]:
            pt.add_row(str(p['pid']), p['name'][:35], f"{p['cpu']:.1f}", f"{p['mem']:.1f}")
        console.print(pt)

    # ── /calc ──
    elif cmd == "/calc":
        if not arg:
            console.print(f"[{THEME['error']}]Usage: /calc <expression>[/]")
        else:
            result = calculate(arg)
            if result["success"]:
                console.print(f"  [{THEME['accent2']}]{result['expression']}[/] = [bold {THEME['accent']}]{result['result']}[/]")
            else:
                console.print(f"[{THEME['error']}]Error: {result['error']}[/]")

    # ── /env ──
    elif cmd == "/env":
        et = Table(box=box.SIMPLE, show_header=False, expand=False)
        et.add_column("Variable", style=THEME['accent2'])
        et.add_column("Value", style=THEME['dim'])
        for k, v in sorted(os.environ.items()):
            if len(v) > 120:
                v = v[:120] + "..."
            et.add_row(k, v)
        console.print(Panel(et, title=f"[bold {THEME['info']}]Environment[/]", border_style=THEME['info']))

    # ── /json ──
    elif cmd == "/json":
        if not arg:
            console.print(f"[{THEME['error']}]Usage: /json <json_string>[/]")
        else:
            result = format_json(arg)
            if result["success"]:
                console.print(Syntax(result["formatted"], "json", theme="monokai", background_color="default"))
            else:
                console.print(f"[{THEME['error']}]Invalid JSON: {result['error']}[/]")

    # ── /genpass ──
    elif cmd == "/genpass":
        length = int(arg) if arg.isdigit() else 16
        if length < 4:
            length = 4
        pw = generate_password(length)
        console.print(f"  [{THEME['accent2']}]Generated:[/] [bold]{pw}[/]")
        copy_to_clipboard(pw)
        console.print(f"  [{THEME['success']}]✓ Copied to clipboard[/]")

    # ── /plugin ──
    elif cmd == "/plugin":
        parts2 = arg.split(None, 1) if arg else []
        sub = parts2[0].lower().strip() if parts2 else ""
        if sub == "list" or not sub:
            cats = list_plugin_categories()
            for cat in sorted(cats):
                names = ", ".join(f"/{p.name}" for p in cats[cat])
                console.print(f"  [{THEME['accent2']}]{cat}[/]  [{THEME['dim']}]{names}[/]")
            console.print(f"\n  [{THEME['dim']}]{len(PLUGINS)} plugins loaded.[/]")
            console.print(f"  [{THEME['dim']}]Use /plugin search <query> or /plugin info <name>[/]")
        elif sub == "search":
            query = parts2[1] if len(parts2) > 1 else ""
            results = search_plugins(query)
            if results:
                for p in results[:20]:
                    console.print(f"  [{THEME['accent2']}]/{p.name}[/] — {p.description} [{THEME['dim']}]({p.category})[/]")
            else:
                console.print(f"[{THEME['dim']}]No plugins matching '{query}'[/]")
        elif sub == "info":
            name = parts2[1].strip().lower() if len(parts2) > 1 else ""
            p = get_plugin_info(name)
            if p:
                cmds = ", ".join(p.commands)
                console.print(f"  [{THEME['accent2']}]Name:[/] {p.name}")
                console.print(f"  [{THEME['accent2']}]Description:[/] {p.description}")
                console.print(f"  [{THEME['accent2']}]Category:[/] {p.category}")
                console.print(f"  [{THEME['accent2']}]Commands:[/] /{cmds}")
                console.print(f"  [{THEME['accent2']}]Has handler:[/] {'Yes' if p.handler else 'No (use /run)'}")
            else:
                console.print(f"[{THEME['error']}]Plugin not found: {name}[/]")
        else:
            console.print(f"[{THEME['error']}]Usage: /plugin [list|search <q>|info <name>][/]")

    # ── /cloud / /aws / /gcp / /azure ──
    elif cmd in ("/cloud", "/aws", "/gcp", "/azure"):
        parts2 = arg.split(None, 1) if arg else []
        sub = parts2[0].lower().strip() if parts2 else "help"
        provider_map = {"/aws": cloud_aws, "/gcp": cloud_gcp, "/azure": cloud_azure}
        provider_name = {"/aws": "AWS", "/gcp": "GCP", "/azure": "Azure"}
        fn = provider_map.get(cmd)
        pname = provider_name.get(cmd, "Cloud")

        if cmd == "/cloud":
            if sub == "aws":
                with spinner_context(f"AWS {' '.join(parts2[1:])}..."):
                    r = cloud_aws(parts2[1].split() if len(parts2) > 1 else ["help"])
                console.print(r["stdout"][:1500] if r["success"] else f"[{THEME['error']}]{r.get('stderr', r.get('error',''))[:500]}[/]")
            elif sub == "gcp":
                with spinner_context(f"GCP {' '.join(parts2[1:])}..."):
                    r = cloud_gcp(parts2[1].split() if len(parts2) > 1 else ["help"])
                console.print(r["stdout"][:1500] if r["success"] else f"[{THEME['error']}]{r.get('stderr', r.get('error',''))[:500]}[/]")
            elif sub == "azure":
                with spinner_context(f"Azure {' '.join(parts2[1:])}..."):
                    r = cloud_azure(parts2[1].split() if len(parts2) > 1 else ["help"])
                console.print(r["stdout"][:1500] if r["success"] else f"[{THEME['error']}]{r.get('stderr', r.get('error',''))[:500]}[/]")
            else:
                console.print(f"[{THEME['accent2']}]Cloud Provider Commands:[/]")
                console.print(f"  /cloud aws <args>     [{THEME['dim']}]AWS CLI wrapper[/]")
                console.print(f"  /cloud gcp <args>     [{THEME['dim']}]GCP gcloud wrapper[/]")
                console.print(f"  /cloud azure <args>   [{THEME['dim']}]Azure CLI wrapper[/]")
                console.print(f"  /aws <args>           [{THEME['dim']}]Direct AWS access[/]")
                console.print(f"  /gcp <args>           [{THEME['dim']}]Direct GCP access[/]")
                console.print(f"  /azure <args>         [{THEME['dim']}]Direct Azure access[/]")
        else:
            args_list = arg.split() if arg else ["help"]
            with spinner_context(f"{pname} {' '.join(args_list)}..."):
                r = fn(args_list)
            console.print(r["stdout"][:1500] if r["success"] else f"[{THEME['error']}]{r.get('stderr', r.get('error',''))[:500]}[/]")

    # ── /test ──
    elif cmd == "/test":
        parts2 = arg.split(None, 1) if arg else []
        sub = parts2[0].lower().strip() if parts2 else "."
        if sub == "discover":
            tests = discover_tests(parts2[1] if len(parts2) > 1 else ".")
            if tests:
                for t in tests[:30]:
                    console.print(f"  [{THEME['dim']}]-[/] {t}")
                console.print(f"\n  [{THEME['dim']}]({len(tests)} tests found)[/]")
            else:
                console.print(f"[{THEME['dim']}]No test files found[/]")
        else:
            path = arg or "."
            with spinner_context(f"Running tests in {path}..."):
                result = run_pytest(path)
            if "error" in result:
                console.print(f"[{THEME['error']}]✗ {result['error']}[/]")
            else:
                dt = Table(box=box.SIMPLE, show_header=False, expand=False)
                dt.add_column("Metric", style=THEME['accent2'])
                dt.add_column("Value", style="white")
                dt.add_row("Passed", f"[{THEME['success']}]{result.get('passed', 0)}[/]")
                dt.add_row("Failed", f"[{THEME['error']}]{result.get('failed', 0)}[/]" if result.get('failed') else "0")
                dt.add_row("Errors", f"[{THEME['error']}]{result.get('errors', 0)}[/]" if result.get('errors') else "0")
                dt.add_row("Exit code", str(result.get('returncode', '?')))
                console.print(Panel(dt, title=f"[bold {THEME['accent']}]Test Results[/]", border_style=THEME['accent']))
                if result.get("output"):
                    console.print(f"\n[{THEME['dim']}]{result['output'][:500]}[/]")

    # ── /sandbox ──
    elif cmd == "/sandbox":
        parts = arg.split() if arg else []
        if parts and parts[0] in ("on", "true", "1", "enable"):
            provider = parts[1] if len(parts) > 1 and parts[1] in sandbox_providers else get_sandbox_mode()[1]
            if len(parts) > 1 and parts[1] not in sandbox_providers:
                console.print(f"[{THEME['error']}]Unknown: {parts[1]}. Options: {list(sandbox_providers)}[/]")
            elif len(parts) > 1 and not sandbox_check(parts[1]):
                console.print(f"[{THEME['error']}]✗ {parts[1]} not installed[/]")
            else:
                set_sandbox_mode(True, provider)
                console.print(f"[{THEME['success']}]✓ Sandbox {provider}[/]")
        elif parts and parts[0] in ("off", "false", "0", "disable"):
            set_sandbox_mode(False)
            console.print(f"[{THEME['success']}]✓ Sandbox off[/]")
        else:
            enabled, provider = get_sandbox_mode()
            state = f"[{THEME['success']}]on[/]" if enabled else f"[{THEME['dim']}]off[/]"
            console.print(f"  Sandbox: {state}  Provider: [{THEME['accent2']}]{provider}[/]")
            for name in sandbox_providers:
                ok = sandbox_check(name)
                icon = f"[{THEME['success']}]✓[/]" if ok else f"[{THEME['dim']}]✗[/]"
                console.print(f"  {icon} {name}")
            console.print(f"\n  [{THEME['dim']}]/sandbox on [docker|daytona|modal]  |  /sandbox off[/]")

    # ── /overlay ──
    elif cmd == "/overlay":
        try:
            from rich.live import Live
            from rich.table import Table as RTable
            from rich.layout import Layout
            data = overlay_data()
            layout = Layout()
            layout.split_column(Layout(name="top"), Layout(name="bottom"))
            live = Live(layout, refresh_per_second=2, screen=True)
            live.start()
            try:
                import signal as _sig
                stop = [False]
                def _h(*a): stop[0] = True
                _sig.signal(_sig.SIGINT, _h)
                while not stop[0]:
                    data = overlay_data()
                    t = RTable(box=box.SIMPLE, show_header=False, expand=False,
                               style="on #0a0a1a")
                    t.add_column("Metric", style="bold #e94560", width=12)
                    t.add_column("Value", style="#e0e0e0")
                    t.add_row("CPU", data["cpu"])
                    t.add_row("RAM", data["ram"])
                    t.add_row("Free", data["ram_gb"])
                    t.add_row("Disk", data["disk"])
                    t.add_row("Procs", str(data["processes"]))
                    session_msgs = len(conversation)
                    t.add_row("Messages", str(session_msgs))
                    from aira.brain import get_usage
                    u = get_usage()
                    t.add_row("Tokens", f"{u['prompt'] + u['completion']:,}")
                    layout["top"].update(Panel(t, title="[bold]Resource Overlay[/]", border_style="#e94560"))
                    _sig.pause() if hasattr(_sig, "pause") else None
                    import time
                    time.sleep(2)
            except KeyboardInterrupt:
                pass
            finally:
                live.stop()
                console.print(f"[{THEME['dim']}]Overlay closed[/]")
        except Exception as e:
            console.print(f"[{THEME['error']}]Overlay: {e}[/]")

    # ── /doc ──
    elif cmd == "/doc":
        parts2 = arg.split(None, 1) if arg else []
        sub = parts2[0].lower().strip() if parts2 else "generate"
        if sub == "generate":
            out = parts2[1] if len(parts2) > 1 else "docs"
            with spinner_context("Generating docs from source..."):
                r = generate_docs(out)
            if r["success"]:
                console.print(f"[{THEME['success']}]✓ Docs generated: [{THEME['accent2']}]{r['path']}[/] ({r['files']} functions documented)[/]")
            else:
                console.print(f"[{THEME['error']}]✗ {r['error']}[/]")
        else:
            console.print(f"[{THEME['accent2']}]Usage: /doc generate [output_dir][/]")

    # ── /vision ──
    elif cmd == "/vision":
        if not arg:
            console.print(f"[{THEME['error']}]Usage: /vision <image_path> [prompt][/]")
        else:
            try:
                parts2 = arg.rsplit(None, 1) if arg else [arg]
                img_path = parts2[0]
                prompt = parts2[1] if len(parts2) > 1 else "Describe this image in detail."
                with spinner_context("Analyzing image..."):
                    result = analyze_image(img_path, prompt)
                if result["success"]:
                    console.print(f"[{THEME['info']}]Vision result:[/]")
                    console.print(result["text"])
                else:
                    console.print(f"[{THEME['error']}]✗ {result['error']}[/]")
            except Exception as e:
                console.print(f"[{THEME['error']}]Vision analysis failed: {e}[/]")

    # ── /template ──
    elif cmd == "/template":
        parts2 = arg.split(None, 1) if arg else []
        sub = parts2[0].lower().strip() if parts2 else "list"
        if sub == "list":
            try:
                with spinner_context("Fetching template index..."):
                    templates = fetch_template_index()
                if templates:
                    for t in templates[:20]:
                        console.print(f"  [{THEME['accent2']}]{t.get('slug', '?')}[/] — {t.get('description', '')[:80]} [{THEME['dim']}]({t.get('author', 'community')})[/]")
                else:
                    console.print(f"[{THEME['dim']}]No templates available (check internet). Use /build for built-in types.[/]")
            except Exception as e:
                console.print(f"[{THEME['error']}]Failed to fetch templates: {e}[/]")
        elif sub == "install" and len(parts2) >= 2:
            try:
                slug = parts2[1].strip()
                dest = parts2[2] if len(parts2) > 2 else "."
                with spinner_context(f"Installing template: {slug}..."):
                    r = install_template(slug, dest)
                if r["success"]:
                    console.print(f"[{THEME['success']}]✓ Template installed: [{THEME['accent2']}]{r['path']}[/] ({r['files']} files)[/]")
                else:
                    console.print(f"[{THEME['error']}]✗ {r['error']}[/]")
            except Exception as e:
                console.print(f"[{THEME['error']}]Template installation failed: {e}[/]")
        else:
            console.print(f"[{THEME['accent2']}]Usage:[/]")
            console.print(f"  /template list               [{THEME['dim']}]Browse template marketplace[/]")
            console.print(f"  /template install <slug>     [{THEME['dim']}]Install a template[/]")

    # ── /agent ──
    elif cmd == "/agent":
        parts2 = arg.split(None, 1) if arg else []
        sub = parts2[0].lower().strip() if parts2 else ""

        # /agent create <name> <description>
        if sub == "create":
            rest = parts2[1] if len(parts2) > 1 else ""
            create_parts = rest.split(None, 1)
            if len(create_parts) < 1:
                console.print(f"[{THEME['error']}]Usage: /agent create <name> <description>[/]")
            else:
                agent_name = create_parts[0].lower()
                agent_desc = create_parts[1] if len(create_parts) > 1 else f"Custom agent: {agent_name}"
                prompt = console.input(f"[{THEME['accent2']}]System prompt for '{agent_name}'[/]: ").strip()
                if prompt:
                    save_custom_agent(agent_name, agent_desc, prompt)
                    console.print(f"[{THEME['success']}]✓ Custom agent '{agent_name}' created[/]")
                else:
                    console.print(f"[{THEME['error']}]System prompt cannot be empty[/]")

        # /agent delete <name>
        elif sub == "delete":
            name = parts2[1].strip().lower() if len(parts2) > 1 else ""
            if delete_custom_agent(name):
                console.print(f"[{THEME['success']}]✓ Agent '{name}' deleted[/]")
            else:
                console.print(f"[{THEME['error']}]Custom agent '{name}' not found[/]")

        # /agent <name> <task> — spawn agent
        elif sub and sub not in ("create", "delete", "list"):
            agent_info = AGENTS.get(sub) or get_custom_agent(sub)
            if not agent_info:
                console.print(f"[{THEME['error']}]Unknown agent: {sub}. Available: {', '.join(AGENT_NAMES)}[/]")
            else:
                task = parts2[1] if len(parts2) > 1 else console.input(f"[{THEME['accent2']}]Task for {agent_info['name']}[/]: ").strip()
                if task:
                    try:
                        console.print(f"  {agent_info.get('icon','🤖')} Spawning [{THEME['accent2']}]{agent_info['name']}[/]: {task}")
                        with spinner_context(f"{agent_info['name']} working..."):
                            result = run_subagent(
                                f"{agent_info['name']}: {task}",
                                f"Agent context: {agent_info.get('system', '')}\nTask: {task}",
                                cfg.get("api_key", ""),
                                provider=cfg.get("provider", "anthropic")
                            )
                        console.print(Panel(result, title=f"[bold {THEME['accent2']}]{agent_info.get('icon','🤖')} {agent_info['name']} Result[/]", border_style=THEME['accent2']))
                    except Exception as e:
                        console.print(f"[{THEME['error']}]Agent execution failed: {e}[/]")

        # /agent or /agent list — list agents
        else:
            agents_table = Table(box=box.SIMPLE, show_header=True, header_style=f"bold {THEME['accent2']}")
            agents_table.add_column("Agent", style=THEME['info'], width=14)
            agents_table.add_column("Description", style="white")
            agents_table.add_column("Type", style=THEME['dim'], width=8)
            for name, info in AGENTS.items():
                agents_table.add_row(f"{info.get('icon','')} {info['name']}", info['description'][:50], "built-in")
            for ca in list_custom_agents():
                agents_table.add_row(f"{ca.get('icon','🤖')} {ca['name']}", ca['description'][:50], "custom")
            console.print(Panel(agents_table, title=f"[bold {THEME['accent']}]🤖 AIRA Agents[/]", border_style=THEME['accent']))

    # ── /config ──
    elif cmd == "/config":
        table = Table(box=box.SIMPLE, show_header=False, expand=False)
        table.add_column("Key", style=THEME['accent2'])
        table.add_column("Value", style="white")
        safe_cfg = {k: v for k, v in cfg.items() if "key" not in k.lower()}
        for k, v in safe_cfg.items():
            table.add_row(k, str(v))
        console.print(Panel(table, title=f"[bold {THEME['dim']}]Config[/]", border_style=THEME['dim']))

    # ── /api ──
    elif cmd == "/api":
        console.print(Panel(
            f"[bold {THEME['accent']}]Change AI Configuration[/]\n"
            f"[{THEME['dim']}]Update provider, API key, and model.[/]",
            border_style=THEME['accent']
        ))

        # Provider selection
        console.print(f"\n[{THEME['accent2']}]Available AI Providers:[/]")
        for i, name in enumerate(PROVIDER_NAMES, 1):
            current_tag = f" [{THEME['success']}](current)[/]" if cfg.get("provider") == name else ""
            console.print(f"  [{THEME['accent']}]{i}.[/] [{THEME['info']}]{name.title()}[/][dim] (key format: {PROVIDER_HELP[name]}){current_tag}[/]")

        provider_idx = 0
        while not (1 <= provider_idx <= len(PROVIDER_NAMES)):
            try:
                default_idx = PROVIDER_NAMES.index(cfg.get("provider", "anthropic")) + 1 if cfg.get("provider") in PROVIDER_NAMES else 1
                provider_idx = int(console.input(f"\n[{THEME['accent2']}]Select provider [1-{len(PROVIDER_NAMES)}][/] [dim](current: {default_idx}, press Enter to keep current)[/]: ").strip() or str(default_idx))
            except ValueError:
                provider_idx = 0

        provider = PROVIDER_NAMES[provider_idx - 1]
        key_hint = PROVIDER_HELP[provider]

        # API key input
        console.print(f"\n[{THEME['dim']}]Current provider: [{THEME['accent']}]{provider.title()}[/][/]")
        current_key = cfg.get("api_key", "")
        if current_key:
            console.print(f"[{THEME['dim']}]Current API key: {current_key[:8]}...{current_key[-4:]}[/]")
        
        api_key = console.input(f"[{THEME['accent2']}]API Key[/] ({key_hint}) [dim](press Enter to keep current)[/]: ").strip()
        if not api_key and current_key:
            api_key = current_key
        elif not api_key:
            console.print(f"[{THEME['error']}]API key cannot be empty.[/]")
            return True

        # Fetch available models from provider's API
        default_model = PROVIDER_REGISTRY[provider]["default_model"]
        console.print(f"\n[{THEME['dim']}]Fetching available models from {provider.title()}...[/]")
        try:
            models = fetch_models(provider, api_key)
        except Exception as e:
            console.print(f"[{THEME['error']}]Failed to fetch models: {e}[/]")
            console.print(f"[{THEME['dim']}]Using default model: {default_model}[/]")
            models = None

        if models:
            console.print(f"\n[{THEME['accent2']}]Available models for {provider.title()}:[/]")
            current_model = cfg.get("model", "")
            for i, m in enumerate(models, 1):
                tier_tag = f"[bold {THEME['success']}]FREE[/]" if m["tier"] == "free" else f"[{THEME['warning']}]PAID[/]"
                current_tag = f" [{THEME['success']}](current)[/]" if m["id"] == current_model else ""
                desc = f" — {m['desc']}" if m.get("desc") else ""
                console.print(f"  [{THEME['accent']}]{i:2}.[/] {tier_tag} [{THEME['info']}]{m['name']}[/][dim]{desc}{current_tag}[/]")

            default_idx = next((i for i, m in enumerate(models) if m["id"] == current_model), 0) + 1 if current_model else 0
            model_input = console.input(f"\n[{THEME['accent2']}]Select model [1-{len(models)}][/] [dim](current: {default_idx}, press Enter for default '{default_model}'): [/]").strip()
            if model_input.isdigit() and 1 <= int(model_input) <= len(models):
                model = models[int(model_input) - 1]["id"]
            else:
                model = current_model if current_model else default_model
        else:
            current_model = cfg.get("model", "")
            model = console.input(f"[{THEME['accent2']}]Model ID[/] [dim](current: '{current_model}', press Enter for '{default_model}'): [/]").strip()
            if not model:
                model = current_model if current_model else default_model

        # Update config
        cfg["provider"] = provider
        cfg["api_key"] = api_key
        cfg["model"] = model
        save_config(cfg)

        # Reinitialize AI client
        try:
            init_client(api_key, provider=provider, model=model)
            console.print(f"\n[{THEME['success']}]✓ AI configuration updated:[/]")
            console.print(f"  [{THEME['accent2']}]Provider:[/] {provider.title()}")
            console.print(f"  [{THEME['accent2']}]Model:[/] {model}")
            console.print(f"  [{THEME['accent2']}]API Key:[/] {api_key[:8]}...{api_key[-4:] if len(api_key) > 12 else '***'}")
        except Exception as e:
            console.print(f"\n[{THEME['error']}]Failed to reinitialize AI client: {e}[/]")
            console.print(f"[{THEME['warning']}]Config saved but AI client not updated. Please restart AIRA.[/]")

    else:
        handled = handle_plugin_command(cmd, arg)
        if not handled:
            console.print(f"[{THEME['error']}]Unknown command: {cmd}[/]  [{THEME['dim']}]Type /help for commands.[/]")

    return True


# ── SHUTDOWN ──────────────────────────────────────────────────────────────────

def _shutdown(conversation: list, session_id: int, cfg: dict, project: str):
    if conversation and len(conversation) >= 2:
        console.print(f"[{THEME['dim']}]Summarizing session...[/]", end="\r")
        try:
            summary_msgs = conversation[-6:] if len(conversation) > 6 else conversation
            summary = get_ai_response(
                summary_msgs + [{"role": "user", "content": "Summarize this session in 1-2 sentences for future reference."}],
                current_project=project
            )
            end_session(session_id, summary[:500], len(conversation))

            # Auto-skill extraction
            if cfg.get("auto_skill", True):
                skill = auto_generate_skill_from_conversation(conversation, api_key=cfg.get("api_key", ""), provider=cfg.get("provider", "anthropic"))
                if skill:
                    save_skill(skill["name"], skill["description"], skill["steps"])
                    console.print(f"  [{THEME['skill']}]⚡ Auto-saved skill:[/] {skill['name']}")
        except Exception:
            end_session(session_id, "Session ended", len(conversation))

    console.print(f"\n[bold {THEME['accent']}]◈ AIRA offline.[/] [{THEME['dim']}]Session saved. See you next time.[/]\n")


# ── MAIN LOOP ─────────────────────────────────────────────────────────────────

def run():
    # Init storage
    init_storage()

    # Load or run setup
    cfg = load_config()
    if not cfg.get("setup_done"):
        cfg = setup_wizard()

    # Init background scheduler
    init_scheduler()

    # Init AI
    api_key = cfg.get("api_key", "")
    if not api_key:
        console.print(f"[{THEME['error']}]No API key found. Run: aira setup[/]")
        sys.exit(1)
    provider = cfg.get("provider", "anthropic")
    model = cfg.get("model", None)
    init_client(api_key, provider=provider, model=model)

    # State
    current_project = [cfg.get("default_project", "AIRA")]
    conversation: list = []
    session_id = start_session(current_project[0])
    reset_usage()

    # Banner
    os.system("cls" if platform.system() == "Windows" else "clear")
    print_banner(__version__, current_project[0])

    # Quick system snapshot on start
    try:
        snap = get_system_snapshot()
        console.print(
            f"[{THEME['dim']}]System:[/] [{THEME['info']}]{snap['os']}[/]  "
            f"CPU [{THEME['accent']}]{snap['cpu_percent']}%[/]  "
            f"RAM [{THEME['accent']}]{snap['ram_used_percent']}%[/]  "
            f"[{THEME['dim']}]{snap['cwd']}[/]\n"
        )
    except Exception:
        pass

    console.print(f"[{THEME['dim']}]Type a message to chat with AIRA, or[/] [{THEME['accent2']}]/help[/] [{THEME['dim']}]for commands.[/]\n")

    # Prompt session
    prompt_session = build_prompt_session(current_project[0], commands=list(COMMANDS.keys()))

    # ── Gateway message handler ──
    def _gateway_handler(text: str, user: str, platform: str) -> str | None:
        try:
            gw_conv = [
                {"role": "system", "content": f"You are AIRA on {platform}. User: {user}. Respond helpfully."},
                {"role": "user", "content": text}
            ]
            resp = get_ai_response(gw_conv, current_project=current_project[0])
            return resp[:4000]
        except Exception:
            return None
    set_message_handler(_gateway_handler)

    # ── MAIN LOOP ──
    while True:
        try:
            user_input = prompt_session.prompt(
                get_prompt_text(current_project[0], os.getcwd()),
                rprompt=HTML(f'<style color="{THEME["dim"]}">{datetime.now().strftime("%H:%M")}</style>')
            ).strip()
        except KeyboardInterrupt:
            console.print(f"\n[{THEME['dim']}](Ctrl+C — type /exit to quit)[/]")
            continue
        except EOFError:
            _shutdown(conversation, session_id, cfg, current_project[0])
            break

        if not user_input:
            continue

        # ── COMMAND MODE ──
        if user_input.startswith("/"):
            try:
                should_continue = handle_command(
                    user_input, cfg, current_project, conversation, session_id
                )
                if not should_continue:
                    break
                continue
            except Exception as e:
                console.print(f"[{THEME['error']}]Command error: {e}[/]")
                continue

        # ── AI CHAT MODE ──
        conversation.append({"role": "user", "content": user_input})

        # Pull relevant memories
        memories = []
        if cfg.get("auto_memory", True):
            try:
                memories = search_memory(user_input[:100], limit=5)
            except Exception:
                pass

        # Save checkpoint for /undo
        try:
            save_checkpoint(conversation)
        except Exception:
            pass

        # Get AI response
        with spinner_context("AIRA thinking..."):
            try:
                raw_response = get_ai_response(
                    conversation,
                    context_memories=memories,
                    current_project=current_project[0]
                )
            except Exception as e:
                console.print(f"[{THEME['error']}]AI Error: {e}[/]")
                conversation.pop()
                continue

        # Parse directives
        directives = parse_ai_directives(raw_response)

        # Print clean response text
        print_ai_response(directives["clean_text"])

        # Execute directives
        if any([directives["commands"], directives["memories"], directives["skills"],
                directives["subagents"], directives["agent_chains"], directives["web_searches"], directives["schedules"]]):
            execute_directives(directives, cfg, current_project[0], conversation)

        # Store AI turn in conversation
        conversation.append({"role": "assistant", "content": raw_response})

        # Keep conversation from ballooning (keep last 20 turns)
        if len(conversation) > 40:
            del conversation[:-40]


# ── ENTRY POINT ALIASES ───────────────────────────────────────────────────────

def main():
    """Entry point for pip install."""
    run()


if __name__ == "__main__":
    run()
