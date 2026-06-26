"""Dump all AIRA commands for documentation."""
import re
from pathlib import Path

from aira.main import COMMANDS
from aira.plugins import PLUGINS, build_cmd_map

main_text = Path("aira/main.py").read_text(encoding="utf-8")
handlers = re.findall(r"elif cmd (?:==|in) ([^\n:]+)", main_text)
expanded = []
for h in handlers:
    h = h.strip()
    if h.startswith("("):
        expanded.extend(re.findall(r'"(/[^"]+)"', h))
    else:
        expanded.append(h.strip('"'))

# Also catch exit handler
if 'if cmd in ("/exit"' in main_text:
    expanded.extend(["/exit", "/quit", "/q"])

cmd_map = build_cmd_map()

SECRET_MAIN = {
    "/forge": "SECRET — Fast autonomous project builder (creates files via AI directives)",
    "/auto": "SECRET — Autonomous task mode (AI executes without further prompts)",
    "/forget": "Delete memory by ID (main handler, not in /help)",
    "/genpass": "Generate password + copy to clipboard",
    "/plugin": "Plugin manager: list | search | info",
    "/pulse": "Rich system pulse panel",
    "/find": "Search file contents recursively (main handler)",
    "/ps": "List processes table (main handler, duplicates plugin)",
    "/calc": "Math calculator (main handler)",
    "/env": "Environment variables table (main handler)",
    "/json": "Format JSON string (main handler)",
    "/quit": "Exit alias",
    "/q": "Exit alias",
    "/github": "Alias for /gh",
    "/aws": "AWS CLI wrapper (also reachable via /cloud aws)",
    "/gcp": "GCP CLI wrapper",
    "/azure": "Azure CLI wrapper",
}

print("=" * 60)
print("AIRA TERMINAL — COMPLETE COMMAND LIST")
print("=" * 60)

print("\n## CORE COMMANDS (in /help panel)\n")
for k in sorted(COMMANDS.keys(), key=lambda x: x.lower()):
    print(f"  {k:<42} {COMMANDS[k]}")

print("\n## MAIN HANDLERS NOT IN /help\n")
for cmd in sorted(set(expanded)):
    if cmd in SECRET_MAIN:
        continue
    base = cmd.split()[0]
    in_help = any(h.startswith(cmd) or cmd.startswith(h.split()[0]) for h in COMMANDS)
    if not in_help and cmd.lstrip("/") not in cmd_map:
        print(f"  {cmd:<42} (handler in main.py, no description in COMMANDS)")

print("\n## SECRET / HIDDEN COMMANDS\n")
print("  --- Marked secret in source ---")
for cmd in ["/forge", "/auto"]:
    print(f"  {cmd:<42} {SECRET_MAIN[cmd]}")

print("\n  --- Hidden plugins (hidden=True, work but not in /help) ---")
for p in PLUGINS:
    if p.hidden:
        aliases = f"  aliases: {', '.join('/'+a for a in p.aliases)}" if p.aliases else ""
        print(f"  /{p.name:<41} {p.description}{aliases}")

print("\n  --- Aliases & shortcuts ---")
for cmd, desc in SECRET_MAIN.items():
    if cmd not in ("/forge", "/auto"):
        print(f"  {cmd:<42} {desc}")

print("\n## ALL PLUGIN COMMANDS (109 plugins + aliases)\n")
by_cat = {}
for p in PLUGINS:
    by_cat.setdefault(p.category, []).append(p)

for cat in sorted(by_cat):
    print(f"  [{cat}]")
    for p in sorted(by_cat[cat], key=lambda x: x.name):
        flag = " [HIDDEN]" if p.hidden else ""
        alias = f"  (aliases: {', '.join('/'+a for a in p.aliases)})" if p.aliases else ""
        handler = "" if p.handler else "  [help-only, use /run]"
        print(f"    /{p.name:<20}{p.description}{flag}{alias}{handler}")
    print()

print("## PLUGIN ALIAS ROUTING (type alias → resolves to plugin)\n")
for p in PLUGINS:
    for a in p.aliases:
        print(f"  /{a:<20} → /{p.name}")

print("\n## TOTALS")
print(f"  /help entries:        {len(COMMANDS)}")
print(f"  main.py handlers:     {len(set(expanded))}")
print(f"  plugins:              {len(PLUGINS)}")
print(f"  hidden plugins:       {sum(1 for p in PLUGINS if p.hidden)}")
print(f"  plugin aliases:       {sum(len(p.aliases) for p in PLUGINS)}")
print(f"  secret main commands: /forge, /auto")
