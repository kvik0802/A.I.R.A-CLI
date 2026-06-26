"""
AIRA Plugin System
------------------
100+ plugins across 12 categories. Each plugin has:
  name, description, aliases, category, handler (optional callable)
"""

import os
import sys
import json
import math
import random
import string
import hashlib
import subprocess
import datetime
import webbrowser
from pathlib import Path

# ── Plugin Definition ───────────────────────────────────────────────────────────

class Plugin:
    __slots__ = ('name', 'description', 'aliases', 'category', 'handler', 'hidden')
    def __init__(self, name, description, aliases=None, category="General", handler=None, hidden=False):
        self.name = name
        self.description = description
        self.aliases = aliases or []
        self.category = category
        self.handler = handler
        self.hidden = hidden

    @property
    def commands(self):
        return [self.name] + self.aliases

# ── Plugin Handlers ─────────────────────────────────────────────────────────────

def _ok(msg):
    from aira.ui import console, THEME
    console.print(f"[{THEME.get('success','green')}]✓ {msg}[/]")

def _info(msg):
    from aira.ui import console, THEME
    console.print(f"[{THEME.get('dim','white')}]{msg}[/]")

def _error(msg):
    from aira.ui import console, THEME
    console.print(f"[{THEME.get('error','red')}]✗ {msg}[/]")

def _print_table(rows, title=None):
    from aira.ui import console, THEME
    from rich.table import Table
    from rich.panel import Panel
    from rich import box
    t = Table(box=box.SIMPLE, show_header=False, expand=False)
    t.add_column("Key", style=THEME.get('accent2','blue'))
    t.add_column("Value", style="white")
    for k, v in rows:
        t.add_row(k, str(v))
    if title:
        console.print(Panel(t, title=f"[bold]{title}[/]", border_style=THEME.get('dim','white')))
    else:
        console.print(t)

def _handler_help(plugin):
    from aira.ui import console, THEME
    cmds = ", ".join(plugin.commands)
    console.print(f"[{THEME.get('accent2','blue')}]/{plugin.name}[/] — {plugin.description}")
    if plugin.aliases:
        console.print(f"  [{THEME.get('dim','white')}]Aliases: {', '.join('/'+a for a in plugin.aliases)}[/]")

# ── Handlers ──

def _h_calc(arg):
    from aira.tools import calculate
    if not arg:
        _info("Usage: /calc <expression>")
        return
    r = calculate(arg)
    if r["success"]:
        _info(f"{arg} = {r['result']}")
    else:
        _error(r["error"])

def _h_ps(arg):
    from aira.tools import list_processes
    results = list_processes(limit=20)
    rows = []
    for p in results:
        rows.append((str(p['pid']), f"{p['name']}  CPU:{p['cpu']:.1f}%  MEM:{p['mem']:.1f}%"))
    _print_table(rows, "Processes")

def _h_disk(arg):
    import psutil
    for p in psutil.disk_partitions():
        try:
            u = psutil.disk_usage(p.mountpoint)
            _info(f"{p.device}  {u.used//(2**30)}G/{u.total//(2**30)}G ({u.percent}%)")
        except: pass

def _h_env(arg):
    key = arg.strip() if arg else None
    if key:
        v = os.environ.get(key, "not set")
        _info(f"{key}={v}")
    else:
        rows = sorted(os.environ.items())[:30]
        _print_table(rows, "Environment Variables")

def _h_uptime(arg):
    import psutil
    boot = datetime.datetime.fromtimestamp(psutil.boot_time())
    now = datetime.datetime.now()
    delta = now - boot
    days = delta.days
    hours = delta.seconds // 3600
    mins = (delta.seconds % 3600) // 60
    _info(f"Uptime: {days}d {hours}h {mins}m  (since {boot.strftime('%Y-%m-%d %H:%M')})")

def _h_whoami(arg):
    _info(os.environ.get('USERNAME', os.environ.get('USER', 'unknown')))

def _h_hostname(arg):
    import platform
    _info(platform.node())

def _h_ping(arg):
    if not arg:
        _info("Usage: /ping <host>")
        return
    r = subprocess.run(["ping", "-n", "4", arg], capture_output=True, text=True, timeout=15)
    _info(r.stdout[:500] if r.stdout else r.stderr[:500])

def _h_ip(arg):
    from aira.tools import get_network_info
    net = get_network_info()
    _info(f"Public IP: {net['public_ip']}")
    for iface, addrs in net['interfaces'].items():
        if addrs:
            _info(f"  {iface}: {', '.join(addrs)}")

def _h_dns(arg):
    if not arg:
        _info("Usage: /dns <domain>")
        return
    try:
        import socket
        ip = socket.gethostbyname(arg)
        _info(f"{arg} → {ip}")
    except Exception as e:
        _error(str(e))

def _h_ports(arg):
    import socket
    common = [21,22,23,25,53,80,110,143,443,445,993,995,1433,3306,3389,5432,6379,8080,8443,27017]
    host = arg.strip() or "localhost"
    open_ports = []
    for p in common:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        if s.connect_ex((host, p)) == 0:
            open_ports.append(p)
        s.close()
    _info(f"Open ports on {host}: {open_ports}" if open_ports else f"No common ports open on {host}")

def _h_tree(arg):
    path = arg or "."
    p = Path(path)
    if not p.is_dir():
        _error(f"Not a directory: {path}")
        return
    rows = []
    for i, item in enumerate(sorted(p.iterdir())):
        icon = "📁" if item.is_dir() else "📄"
        size = f" ({item.stat().st_size}B)" if item.is_file() else ""
        rows.append((icon, f"{item.name}{size}"))
        if i > 50:
            rows.append(("...", f"({len(list(p.iterdir()))-50} more)"))
            break
    _print_table(rows[:55], f"Directory: {p.resolve()}")

def _h_find(arg):
    if not arg:
        _info("Usage: /find <filename_pattern>")
        return
    from aira.tools import search_files
    results = search_files(".", arg)[:20]
    if results:
        for f in results:
            _info(f"  {f}")
    else:
        _info("No matches")

def _h_grep(arg):
    if not arg:
        _info("Usage: /grep <text>")
        return
    from pathlib import Path
    text = arg.lower()
    matches = []
    for f in Path(".").glob("*.py"):
        try:
            for i, line in enumerate(f.read_text(encoding='utf-8', errors='ignore').splitlines(), 1):
                if text in line.lower():
                    matches.append((str(f), f"L{i}: {line.strip()[:80]}"))
        except: pass
    if matches:
        for f, line in matches[:15]:
            _info(f"[{f}] {line}")
    else:
        _info("No matches")

def _h_http(arg):
    if not arg:
        _info("Usage: /http <url>")
        return
    import requests
    try:
        r = requests.get(arg, timeout=10, headers={'User-Agent': 'AIRA/1.0'})
        _info(f"{r.status_code} {r.reason}  ({len(r.content)} bytes)")
        if r.headers.get('content-type','').startswith('application/json'):
            _info(json.dumps(r.json(), indent=2)[:1000])
        else:
            _info(r.text[:500])
    except Exception as e:
        _error(str(e))

def _h_headers(arg):
    if not arg:
        _info("Usage: /headers <url>")
        return
    import requests
    try:
        r = requests.head(arg, timeout=10)
        rows = [(k, v) for k, v in r.headers.items()]
        _print_table(rows, f"Headers: {arg}")
    except Exception as e:
        _error(str(e))

def _h_download(arg):
    if not arg:
        _info("Usage: /download <url>")
        return
    import requests
    name = arg.split("/")[-1] or "download"
    try:
        r = requests.get(arg, stream=True, timeout=30)
        Path(name).write_bytes(r.content)
        _info(f"Downloaded {len(r.content)} bytes to {name}")
    except Exception as e:
        _error(str(e))

def _h_serve(arg):
    from aira.tools import start_http_server
    port = int(arg) if arg and arg.isdigit() else 8000
    r = start_http_server(port)
    if r["success"]:
        _info(f"Serving at http://localhost:{port}")
    else:
        _error(r["error"])

def _h_git_status(arg):
    r = subprocess.run(["git", "status", "--short"], capture_output=True, text=True, timeout=10)
    _info(r.stdout[:1000] if r.stdout else "(clean)")

def _h_git_log(arg):
    n = arg.strip() if arg and arg.isdigit() else "10"
    r = subprocess.run(["git", "log", f"--oneline", "-n", n], capture_output=True, text=True, timeout=10)
    _info(r.stdout[:2000] if r.stdout else r.stderr)

def _h_git_branch(arg):
    r = subprocess.run(["git", "branch", "-a"], capture_output=True, text=True, timeout=10)
    _info(r.stdout[:1000] if r.stdout else r.stderr)

def _h_npm_list(arg):
    r = subprocess.run(["npm", "list", "--depth=0"], capture_output=True, text=True, timeout=15)
    _info(r.stdout[:1000] if r.stdout else r.stderr)

def _h_pip_list(arg):
    search = arg.strip().lower() if arg else ""
    r = subprocess.run([sys.executable, "-m", "pip", "list", "--format=columns"], capture_output=True, text=True, timeout=15)
    lines = r.stdout.splitlines()
    if search:
        lines = [l for l in lines if search in l.lower()]
    _info("\n".join(lines[:25]) if lines else "(empty)")

def _h_docker_ps(arg):
    r = subprocess.run(["docker", "ps", "--format", "table {{.Names}}\t{{.Status}}\t{{.Image}}"], capture_output=True, text=True, timeout=10)
    _info(r.stdout[:1500] if r.stdout else r.stderr[:500])

def _h_json_format(arg):
    from aira.tools import format_json
    r = format_json(arg or "{}")
    if r["success"]:
        _info(r["formatted"])
    else:
        _error(r["error"])

def _h_json_min(arg):
    try:
        obj = json.loads(arg or "{}")
        _info(json.dumps(obj, separators=(',',':')))
    except Exception as e:
        _error(str(e))

def _h_uuid(arg):
    import uuid
    n = max(1, min(10, int(arg) if arg and arg.isdigit() else 1))
    for _ in range(n):
        _info(str(uuid.uuid4()))

def _h_hash_text(arg):
    if not arg:
        _info("Usage: /hash <text>")
        return
    for name in ('md5', 'sha1', 'sha256'):
        h = hashlib.new(name, arg.encode()).hexdigest()
        _info(f"{name.upper()}: {h}")

def _h_b64encode(arg):
    if not arg:
        _info("Usage: /b64encode <text>")
        return
    import base64
    _info(base64.b64encode(arg.encode()).decode())

def _h_b64decode(arg):
    if not arg:
        _info("Usage: /b64decode <base64>")
        return
    import base64
    try:
        _info(base64.b64decode(arg).decode(errors='replace'))
    except Exception as e:
        _error(str(e))

def _h_units(arg):
    categories = {"length": "m, km, cm, mm, in, ft, yd, mi", "weight": "kg, g, lb, oz", "temp": "C, F, K", "data": "B, KB, MB, GB, TB"}
    if not arg:
        for cat, units in categories.items():
            _info(f"  {cat}: {units}")
        return
    from aira.tools import calculate
    r = calculate(arg)
    if r["success"]:
        _info(f"= {r['result']}")
    else:
        _error(r["error"])

def _h_random(arg):
    n = int(arg) if arg and arg.isdigit() else 1
    rng = arg.split("-") if arg and "-" in arg else None
    if rng and len(rng) == 2:
        try:
            lo, hi = int(rng[0]), int(rng[1])
            _info(str(random.randint(lo, hi)))
            return
        except: pass
    if n == 1:
        _info(str(random.random()))
    else:
        _info(", ".join(str(round(random.random(), 4)) for _ in range(n)))

def _h_password(arg):
    from aira.tools import generate_password
    length = int(arg) if arg and arg.isdigit() else 16
    r = generate_password(length)
    _info(r["password"] if r["success"] else r["error"])

def _h_joke(arg):
    jokes = [
        "Why do programmers prefer dark mode? Because light attracts bugs.",
        "How many programmers does it take to change a light bulb? None, that's a hardware problem.",
        "I told my computer I needed a break, and now it won't stop sending me vacation ads.",
        "Why did the developer go broke? Because he used up all his cache.",
        "There are 10 types of people: those who understand binary and those who don't.",
        "A SQL query walks into a bar, walks up to two tables and asks: 'Can I join you?'",
        "Why was the JavaScript developer sad? Because he didn't know how to 'null' his feelings.",
    ]
    _info(random.choice(jokes))

def _h_quote(arg):
    quotes = [
        "\"The best way to predict the future is to invent it.\" — Alan Kay",
        "\"Simplicity is prerequisite for reliability.\" — Edsger Dijkstra",
        "\"Talk is cheap. Show me the code.\" — Linus Torvalds",
        "\"Any fool can write code that a computer can understand. Good programmers write code that humans can understand.\" — Martin Fowler",
        "\"First, solve the problem. Then, write the code.\" — John Johnson",
        "\"Code is like humor. When you have to explain it, it's bad.\" — Cory House",
        "\"Programming isn't about what you know; it's about what you can figure out.\" — Chris Pine",
    ]
    _info(random.choice(quotes))

def _h_banner(arg):
    text = arg or "AIRA"
    cols = os.get_terminal_size().columns
    width = min(cols - 2, 60)
    lines = []
    for word in text.split():
        lines.append(f"╔{'═'*(len(word)+2)}╗")
        lines.append(f"║ {word} ║")
        lines.append(f"╚{'═'*(len(word)+2)}╝")
    for line in lines:
        _info(line)

def _h_cowsay(arg):
    text = arg or "Moo!"
    border = "+" + "-" * (len(text) + 2) + "+"
    _info(border)
    _info(f"| {text} |")
    _info(border)
    _info("        \\   ^__^")
    _info("         \\  (oo)\\_______")
    _info("            (__)\\       )\\/\\")
    _info("                ||----w |")
    _info("                ||     ||")

def _h_fortune(arg):
    fortunes = [
        "A beautiful day ahead. Write some code.",
        "Bug free code is coming your way... eventually.",
        "The answer lies in the documentation you haven't read yet.",
        "Your debugging skills will save the day.",
        "A new programming language will enter your life.",
        "The feature you're building will ship on time.",
        "Legacy code awaits. Be brave.",
        "Your tests will pass on the first try.",
        "A refactoring opportunity will present itself.",
        "The stack trace will lead you to the truth.",
    ]
    _info(random.choice(fortunes))

def _h_weather(arg):
    city = arg or "New York"
    from aira.tools import web_search
    results = web_search(f"weather {city} 2025")
    if results:
        _info(f"Weather for {city}: {results[0][:200]}")
    else:
        _info(f"Weather data unavailable for {city}")

def _h_time(arg):
    now = datetime.datetime.now()
    _info(now.strftime("%Y-%m-%d %H:%M:%S %A"))

def _h_cal(arg):
    import calendar
    parts = arg.split() if arg else []
    y = int(parts[0]) if parts and parts[0].isdigit() else datetime.datetime.now().year
    m = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else datetime.datetime.now().month
    _info(f"\n{calendar.month(y, m)}")

def _h_timer(arg):
    seconds = int(arg) if arg and arg.isdigit() else 60
    import time
    _info(f"Timer: {seconds}s starting...")
    for remaining in range(seconds, 0, -1):
        _info(f"  {remaining}s")
        time.sleep(1)
    _info("⏰ Timer done!")

def _h_encode(arg):
    text = arg or ""
    import base64
    _info(base64.b64encode(text.encode()).decode())

def _h_hex(arg):
    text = arg or ""
    _info(text.encode().hex())

def _h_bytes(arg):
    text = arg or ""
    _info(str([b for b in text.encode()]))

def _h_rot13(arg):
    text = arg or ""
    _info(text.translate(str.maketrans(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
        "NOPQRSTUVWXYZABCDEFGHIJKLMnopqrstuvwxyzabcdefghijklm"
    )))

def _h_sum(arg):
    nums = [float(x) for x in arg.split() if x.replace('.','',1).replace('-','',1).isdigit()]
    _info(f"sum = {sum(nums)}  avg = {sum(nums)/len(nums) if nums else 0}  count = {len(nums)}")

def _h_help(plugin_arg):
    name = plugin_arg.strip() if plugin_arg else ""
    from aira.plugins import PLUGINS
    if name:
        for p in PLUGINS:
            if p.name == name:
                _handler_help(p)
                return
        _error(f"No plugin: {name}")
    else:
        cats = {}
        for p in PLUGINS:
            cats.setdefault(p.category, []).append(p)
        for cat in sorted(cats):
            names = ", ".join(f"/{p.name}" for p in cats[cat])
            _info(f"[{cat}] {names}")

def _h_search_web(arg):
    if not arg:
        _info("Usage: /web <query>")
        return
    from aira.tools import web_search
    results = web_search(arg)
    for i, r in enumerate(results[:8]):
        _info(f"{i+1}. {r[:150]}")

def _h_search_pkg(arg):
    if not arg:
        _info("Usage: /search_pkg <package_name>")
        return
    r = subprocess.run([sys.executable, "-m", "pip", "search", arg], capture_output=True, text=True, timeout=15)
    _info(r.stdout[:1000] if r.stdout else r.stderr[:500])

def _h_shorten(arg):
    if not arg:
        _info("Usage: /shorten <url>")
        return
    import requests
    try:
        r = requests.post("https://ulvis.net/api.php", data={"url": arg, "custom": ""}, timeout=8)
        _info(r.text.strip()[:200])
    except Exception as e:
        _error(str(e))

def _h_qr(arg):
    if not arg:
        _info("Usage: /qr <text_or_url>")
        return
    _info(f"QR code for: {arg}")
    _info("  (install qrencode or use https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=" + arg.replace(" ", "%20") + ")")

def _h_ascii(arg):
    text = arg or "AIRA"
    import pyfiglet as _
    try:
        import pyfiglet
        _info(pyfiglet.figlet_format(text))
    except ImportError:
        simple = f"""
  ╔═══╗ ╔═══╗ ╔═══╗ ╔═══╗
  ║ A ║ ║ I ║ ║ R ║ ║ A ║
  ╚═══╝ ╚═══╝ ╚═══╝ ╚═══╝
        """
        _info(simple)

def _h_morse(arg):
    code = {'A':'.-','B':'-...','C':'-.-.','D':'-..','E':'.','F':'..-.','G':'--.','H':'....','I':'..','J':'.---','K':'-.-','L':'.-..','M':'--','N':'-.','O':'---','P':'.--.','Q':'--.-','R':'.-.','S':'...','T':'-','U':'..-','V':'...-','W':'.--','X':'-..-','Y':'-.--','Z':'--..','0':'-----','1':'.----','2':'..---','3':'...--','4':'....-','5':'.....','6':'-....','7':'--...','8':'---..','9':'----.'}
    text = arg.upper() if arg else "SOS"
    out = " ".join(code.get(c, c) for c in text)
    _info(out)

def _h_markdown(arg):
    if not arg:
        _info("Usage: /md <filepath>")
        return
    p = Path(arg)
    if not p.exists():
        _error(f"File not found: {arg}")
        return
    from rich.markdown import Markdown
    from aira.ui import console
    console.print(Markdown(p.read_text(encoding='utf-8', errors='replace')))

def _h_csv(arg):
    if not arg:
        _info("Usage: /csv <file.csv>")
        return
    p = Path(arg)
    if not p.exists():
        _error(f"File not found: {arg}")
        return
    import csv
    import io
    rows = []
    with open(p, newline='', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            rows.append(row)
            if i > 20: break
    if rows:
        from rich.table import Table
        from aira.ui import console, THEME
        t = Table(box=None, show_header=True, header_style=THEME.get('accent2','blue'))
        for h in rows[0]:
            t.add_column(h[:20])
        for r in rows[1:26]:
            t.add_row(*[c[:25] for c in r])
        console.print(t)

def _h_yaml(arg):
    if arg:
        p = Path(arg)
        if p.exists():
            text = p.read_text()
        else:
            text = arg
    else:
        _info("Usage: /yaml <file_or_text>")
        return
    try:
        import yaml as _
        obj = json.loads(text) if text.strip().startswith('{') else None
        if obj:
            import yaml
            _info(yaml.dump(obj, default_flow_style=False))
        else:
            _info("YAML content (validate with python -c \"import yaml; yaml.safe_load(open('file'))\")")
    except ImportError:
        _info("Install PyYAML: pip install pyyaml")

def _h_xml(arg):
    if not arg:
        _info("Usage: /xml <file_or_text>")
        return
    import xml.dom.minidom
    try:
        p = Path(arg)
        text = p.read_text() if p.exists() else arg
        dom = xml.dom.minidom.parseString(text)
        _info(dom.toprettyxml()[:1000])
    except Exception as e:
        _error(str(e))

def _h_sql(arg):
    if not arg:
        _info("Usage: /sql <query>  (runs on ':memory:' SQLite DB)")
        return
    import sqlite3
    try:
        conn = sqlite3.connect(":memory:")
        c = conn.cursor()
        # Try as a full SQL statement
        c.execute(arg)
        if arg.strip().upper().startswith("SELECT"):
            rows = c.fetchall()
            if rows:
                cols = [d[0] for d in c.description]
                from rich.table import Table
                from aira.ui import console, THEME
                t = Table(box=None, show_header=True, header_style=THEME.get('accent2','blue'))
                for col in cols:
                    t.add_column(col[:20])
                for row in rows[:20]:
                    t.add_row(*[str(c)[:25] for c in row])
                console.print(t)
                _info(f"({len(rows)} rows)")
            else:
                _info("(empty result set)")
        else:
            _info(f"Query OK, rows affected: {conn.total_changes}")
        conn.close()
    except Exception as e:
        _error(str(e))

def _h_exec(arg):
    if not arg:
        _info("Usage: /exec <python_code>")
        return
    try:
        exec(arg)
    except Exception as e:
        _error(str(e))

def _h_eval_code(arg):
    if not arg:
        _info("Usage: /eval <expression>")
        return
    try:
        r = eval(arg)
        _info(str(r))
    except Exception as e:
        _error(str(e))

def _h_history(arg):
    import readline
    h = readline.get_history_item
    n = int(arg) if arg and arg.isdigit() else 20
    for i in range(max(1, readline.get_current_history_length() - n), readline.get_current_history_length() + 1):
        try:
            _info(f"  {i}: {h(i)}")
        except: pass

def _h_contact(arg):
    contacts = {
        "support": "support@aira.sh",
        "github": "https://github.com/anomalyco/aira",
        "docs": "https://aira.sh/docs",
    }
    key = arg.strip().lower() if arg else ""
    if key in contacts:
        _info(f"{key}: {contacts[key]}")
    else:
        for k, v in contacts.items():
            _info(f"  {k}: {v}")

def _h_stats(arg):
    import os
    files = [f for f in Path(".").iterdir() if f.is_file()]
    if not files:
        _info("No files in current directory")
        return
    sizes = [f.stat().st_size for f in files]
    _info(f"Files: {len(files)}")
    _info(f"Total size: {sum(sizes):,} bytes")
    _info(f"Average: {sum(sizes)/len(sizes):,.0f} bytes")
    _info(f"Largest: {max(sizes):,} bytes ({max(files, key=lambda f: f.stat().st_size).name})")
    _info(f"Smallest: {min(sizes):,} bytes ({min(files, key=lambda f: f.stat().st_size).name})")

def _h_touch(arg):
    if not arg:
        _info("Usage: /touch <file>")
        return
    p = Path(arg)
    if p.exists():
        p.touch()
        _info(f"Touched: {arg}")
    else:
        p.write_text("")
        _info(f"Created: {arg}")

def _h_mkdir(arg):
    if not arg:
        _info("Usage: /mkdir <dirname>")
        return
    Path(arg).mkdir(parents=True, exist_ok=True)
    _info(f"Created directory: {arg}")

def _h_rm(arg):
    if not arg:
        _info("Usage: /rm <file_or_dir>")
        return
    p = Path(arg)
    if not p.exists():
        _error(f"Not found: {arg}")
        return
    if p.is_dir():
        import shutil; shutil.rmtree(p)
    else:
        p.unlink()
    _info(f"Removed: {arg}")

def _h_cp(arg):
    parts = arg.rsplit(None, 1)
    if len(parts) < 2:
        _info("Usage: /cp <src> <dst>")
        return
    src, dst = parts
    import shutil
    shutil.copy2(src, dst)
    _info(f"Copied: {src} → {dst}")

def _h_mv(arg):
    parts = arg.rsplit(None, 1)
    if len(parts) < 2:
        _info("Usage: /mv <src> <dst>")
        return
    src, dst = parts
    Path(src).rename(dst)
    _info(f"Moved: {src} → {dst}")

def _h_count(arg):
    p = Path(arg or ".")
    if p.is_file():
        text = p.read_text(encoding='utf-8', errors='replace')
        lines = text.splitlines()
        _info(f"Lines: {len(lines)}, Words: {len(text.split())}, Chars: {len(text)}")
    elif p.is_dir():
        files = list(p.rglob("*"))
        _info(f"Files: {sum(1 for f in files if f.is_file())}, Dirs: {sum(1 for f in files if f.is_dir())}")

def _h_tail(arg):
    parts = arg.rsplit(None, 1) if arg else [""]
    n = int(parts[-1]) if parts[-1].isdigit() else 10
    path = parts[0] if len(parts) > 1 and not parts[-1].isdigit() else (arg if arg else ".")
    p = Path(path)
    if not p.exists():
        _error(f"Not found: {path}")
        return
    lines = p.read_text(encoding='utf-8', errors='replace').splitlines()
    for line in lines[-n:]:
        _info(line)

def _h_head(arg):
    parts = arg.rsplit(None, 1) if arg else [""]
    n = int(parts[-1]) if parts[-1].isdigit() else 10
    path = parts[0] if len(parts) > 1 and not parts[-1].isdigit() else (arg if arg else ".")
    p = Path(path)
    if not p.exists():
        _error(f"Not found: {path}")
        return
    lines = p.read_text(encoding='utf-8', errors='replace').splitlines()
    for line in lines[:n]:
        _info(line)

def _h_wc(arg):
    parts = arg.rsplit(None, 1) if arg else [""]
    path = parts[0] if parts else "."
    p = Path(path)
    if not p.exists():
        _error(f"Not found: {path}")
        return
    text = p.read_text(encoding='utf-8', errors='replace')
    lines = text.splitlines()
    _info(f"{len(lines)} lines  {len(text.split())} words  {len(text)} chars  {p.name}")

def _h_ls(arg):
    from aira.tools import list_directory
    path = arg or "."
    entries = list_directory(path)
    for e in entries:
        icon = "📁 " if e['type'] == "dir" else "📄 "
        size_str = f" {e['size']:,}B" if e['size'] else ""
        _info(f"{icon}{e['name']}{size_str}")

def _h_which(arg):
    if not arg:
        _info("Usage: /which <command>")
        return
    import shutil
    p = shutil.which(arg)
    _info(f"{arg} → {p}" if p else f"{arg} not found")

def _h_type(arg):
    if not arg:
        _info("Usage: /type <file>")
        return
    from aira.tools import read_file
    content = read_file(arg)
    suffix = Path(arg).suffix.lstrip('.') or "text"
    from rich.syntax import Syntax
    from aira.ui import console
    console.print(Syntax(content, suffix, theme="monokai", background_color="default", line_numbers=True))

def _h_zip_files(arg):
    parts = arg.split() if arg else []
    if len(parts) < 2:
        _info("Usage: /zip <archive.zip> <file1> [file2 ...]")
        return
    import zipfile
    name = parts[0]
    with zipfile.ZipFile(name, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in parts[1:]:
            z.write(f)
    _info(f"Created: {name}")

def _h_unzip(arg):
    if not arg:
        _info("Usage: /unzip <file.zip> [dest]")
        return
    parts = arg.split()
    import zipfile
    with zipfile.ZipFile(parts[0], 'r') as z:
        z.extractall(parts[1] if len(parts) > 1 else ".")
    _info(f"Extracted: {parts[0]}")

def _h_debug(arg):
    _info(f"Python: {sys.version}")
    _info(f"Platform: {sys.platform}")
    _info(f"Args: {arg}")
    import platform
    _info(f"Machine: {platform.machine()}")
    _info(f"Processor: {platform.processor()}")

def _h_kill(arg):
    if not arg or not arg.isdigit():
        _info("Usage: /kill <pid>")
        return
    import signal
    try:
        os.kill(int(arg), signal.SIGTERM)
        _info(f"Killed PID {arg}")
    except Exception as e:
        _error(str(e))

def _h_ln(arg):
    parts = arg.split() if arg else []
    if len(parts) < 2:
        _info("Usage: /ln <target> <link_name>")
        return
    try:
        import subprocess
        subprocess.run(["mklink", parts[1], parts[0]], shell=True, check=True)
        _info(f"Link created: {parts[1]} → {parts[0]}")
    except Exception as e:
        _error(str(e))

def _h_mount(arg):
    import psutil
    for p in psutil.disk_partitions():
        _info(f"{p.device} → {p.mountpoint} ({p.fstype}) {'['+p.opts+']' if p.opts else ''}")

def _h_pskill(arg):
    if not arg:
        _info("Usage: /pskill <process_name>")
        return
    import psutil
    killed = 0
    for proc in psutil.process_iter(['name', 'pid']):
        if arg.lower() in proc.info['name'].lower():
            proc.kill()
            killed += 1
    _info(f"Killed {killed} process(es) matching '{arg}'")

def _h_sysinfo(arg):
    from aira.tools import get_system_snapshot
    snap = get_system_snapshot()
    rows = [
        ("OS", f"{snap['os']} {snap.get('os_version','')}"),
        ("Host", snap['hostname']),
        ("User", snap.get('user','')),
        ("Uptime", f"{snap['uptime_hours']:.1f}h"),
        ("CPU", f"{snap['cpu_percent']}% ({snap['cpu_cores']} cores)"),
        ("RAM", f"{snap['ram_used_percent']}% used ({snap['ram_available_gb']:.1f}GB free)"),
        ("Disk", f"{snap['disk_used_percent']}% used ({snap['disk_free_gb']:.1f}GB free)"),
        ("Python", snap['python']),
        ("CWD", snap['cwd']),
    ]
    _print_table(rows, "System Info")

def _h_psaux(arg):
    from aira.tools import list_processes
    procs = list_processes(limit=40)
    rows = []
    for p in procs:
        rows.append((str(p['pid']), f"{p['name'][:30]:30s} CPU:{p['cpu']:5.1f}% MEM:{p['mem']:5.1f}%"))
    _print_table(rows[:40], "Processes")

def _h_top(arg):
    import psutil
    n = int(arg) if arg and arg.isdigit() else 10
    procs = sorted(psutil.process_iter(['pid','name','cpu_percent','memory_percent']), key=lambda p: p.info['cpu_percent'] or 0, reverse=True)[:n]
    rows = []
    for p in procs:
        rows.append((str(p.info['pid']), f"{p.info['name'][:25]:25s} CPU:{p.info['cpu_percent']:6.2f}% MEM:{p.info.get('memory_percent',0):5.1f}%"))
    _print_table(rows, f"Top {n} Processes by CPU")

def _h_date(arg):
    from datetime import datetime
    fmt = arg or "%Y-%m-%d %H:%M:%S"
    try:
        _info(datetime.now().strftime(fmt))
    except:
        _info(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

def _h_sleep(arg):
    import time
    secs = float(arg) if arg else 3
    _info(f"Sleeping {secs}s...")
    time.sleep(secs)
    _info("Done")

def _h_nslookup(arg):
    if not arg:
        _info("Usage: /nslookup <domain>")
        return
    import socket
    try:
        info = socket.getaddrinfo(arg, None)
        for entry in info[:5]:
            _info(f"{entry[4][0]} ({entry[0]})")
    except Exception as e:
        _error(str(e))

def _h_traceroute(arg):
    if not arg:
        _info("Usage: /traceroute <host>")
        return
    import subprocess
    try:
        r = subprocess.run(["tracert", "-h", "10", arg], capture_output=True, text=True, timeout=30)
        _info(r.stdout[:1000] or r.stderr[:500])
    except Exception as e:
        _error(str(e))

def _h_netstat(arg):
    import subprocess
    r = subprocess.run(["netstat", "-an"], capture_output=True, text=True, timeout=10)
    lines = [l for l in r.stdout.splitlines() if "LISTEN" in l or "ESTABLISHED" in l]
    for line in lines[:20]:
        _info(line.strip())

def _h_tasklist(arg):
    import subprocess
    r = subprocess.run(["tasklist", "/FI", f"STATUS eq running", "/FO", "LIST"], capture_output=True, text=True, timeout=10)
    rows = []
    for line in r.stdout.splitlines():
        if ": " in line:
            k, v = line.split(": ", 1)
            rows.append((k.strip(), v.strip()))
    _print_table(rows[:30], "Running Tasks")

def _h_systeminfo(arg):
    import subprocess
    r = subprocess.run(["systeminfo", "/FO", "CSV"], capture_output=True, text=True, timeout=15)
    lines = r.stdout.splitlines()[:10]
    for line in lines:
        _info(line[:200])

def _h_shutdown_pc(arg):
    _info("Use: /run shutdown /s /t 30")

def _h_restart(arg):
    _info("Use: /run shutdown /r /t 30")

def _h_lock(arg):
    _info("Use: /run rundll32.exe user32.dll,LockWorkStation")

def _h_open(arg):
    if not arg:
        _info("Usage: /open <file_or_url>")
        return
    import os
    try:
        os.startfile(arg)
        _info(f"Opened: {arg}")
    except Exception as e:
        _error(str(e))

def _h_edit_file(arg):
    if not arg:
        _info("Usage: /edit <file>")
        return
    import os
    try:
        os.system(f"notepad {arg}")
    except Exception as e:
        _error(str(e))

def _h_explore_path(arg):
    import os
    path = arg or "."
    try:
        os.startfile(path)
        _info(f"Opened explorer: {path}")
    except Exception as e:
        _error(str(e))

def _h_note(arg):
    if not arg:
        _info("Usage: /note <text>")
        return
    from aira.memory import save_memory
    save_memory(arg, project="notes", source="user", priority=1)
    _info("Note saved")

def _h_remind(arg):
    if not arg:
        _info("Usage: /remind <text>")
        return
    from aira.memory import search_memory
    results = search_memory(arg)
    from aira.ui import print_memory_panel
    print_memory_panel(results)

def _h_shortcut(arg):
    if not arg:
        _info("Usage: /shortcut <name> <command>")
        return
    parts = arg.split(None, 1)
    if len(parts) < 2:
        _error("Usage: /shortcut <name> <command>")
        return
    name, cmd = parts
    _info(f"Shortcut set: /{name} → {cmd}")
    # Store in aira home
    from aira.main import AIRA_HOME
    shortcuts_file = AIRA_HOME / "shortcuts.json"
    shortcuts = {}
    if shortcuts_file.exists():
        shortcuts = json.loads(shortcuts_file.read_text())
    shortcuts[name] = cmd
    shortcuts_file.write_text(json.dumps(shortcuts, indent=2))
    _ok(f"Shortcut /{name} created")

# ── Plugin Registry (100+ plugins) ──────────────────────────────────────────────

PLUGINS = [
    # ── System (15) ──
    Plugin("sys", "System status snapshot", category="System", handler=_h_sysinfo, hidden=True),
    Plugin("uptime", "Show system uptime", ["up"], "System", _h_uptime),
    Plugin("whoami", "Show current user", ["user"], "System", _h_whoami),
    Plugin("hostname", "Show machine hostname", ["host"], "System", _h_hostname),
    Plugin("ps", "List running processes", ["procs"], "System", _h_ps),
    Plugin("top", "Top CPU-consuming processes", [], "System", _h_top),
    Plugin("kill", "Kill a process by PID", [], "System", _h_kill),
    Plugin("pskill", "Kill processes by name", [], "System", _h_pskill),
    Plugin("service", "Show running services (via tasklist)", ["svc"], "System", _h_tasklist),
    Plugin("disk", "Show disk usage", ["df", "drives"], "System", _h_disk),
    Plugin("mount", "Show mounted drives/partitions", [], "System", _h_mount),
    Plugin("env", "Show environment variables", ["vars"], "System", _h_env),
    Plugin("tasklist", "Show Windows running tasks", [], "System", _h_tasklist),
    Plugin("systeminfo", "Show detailed Windows system info", ["sysinfo"], "System", _h_systeminfo),
    Plugin("debug", "Show Python/system debug info", [], "System", _h_debug),

    # ── Network (12) ──
    Plugin("ip", "Show IP addresses (public + local)", ["myip"], "Network", _h_ip),
    Plugin("ping", "Ping a host", [], "Network", _h_ping),
    Plugin("dns", "DNS lookup for a domain", ["nslookup"], "Network", _h_dns),
    Plugin("ports", "Scan common ports on a host", ["portscan"], "Network", _h_ports),
    Plugin("traceroute", "Trace route to a host", ["tracert"], "Network", _h_traceroute),
    Plugin("netstat", "Show network connections", ["net"], "Network", _h_netstat),
    Plugin("http", "HTTP GET request", ["get", "fetch"], "Network", _h_http),
    Plugin("headers", "Show HTTP response headers", [], "Network", _h_headers),
    Plugin("download", "Download a file from URL", ["dl", "wget"], "Network", _h_download),
    Plugin("serve", "Start local HTTP server", ["httpserver"], "Network", _h_serve),
    Plugin("shorten", "Shorten a URL", [], "Network", _h_shorten),
    Plugin("qr", "Generate QR code URL", [], "Network", _h_qr),

    # ── Files (15) ──
    Plugin("ls", "List directory contents", ["dir"], "Files", _h_ls),
    Plugin("tree", "Show directory tree", [], "Files", _h_tree),
    Plugin("find", "Find files by pattern", ["searchfiles"], "Files", _h_find),
    Plugin("grep", "Search text in .py files", [], "Files", _h_grep),
    Plugin("touch", "Create or update a file", [], "Files", _h_touch),
    Plugin("mkdir", "Create a directory", ["md"], "Files", _h_mkdir),
    Plugin("rm", "Remove a file or directory", ["del", "delete"], "Files", _h_rm),
    Plugin("cp", "Copy a file", ["copy"], "Files", _h_cp),
    Plugin("mv", "Move or rename a file", ["move", "rename"], "Files", _h_mv),
    Plugin("head", "Show first N lines of a file", [], "Files", _h_head),
    Plugin("tail", "Show last N lines of a file", [], "Files", _h_tail),
    Plugin("wc", "Word/line/char count of a file", ["countfile"], "Files", _h_wc),
    Plugin("zip", "Create a zip archive", ["compress"], "Files", _h_zip_files),
    Plugin("unzip", "Extract a zip archive", ["extract"], "Files", _h_unzip),
    Plugin("which", "Locate an executable", [], "Files", _h_which),

    # ── Dev (14) ──
    Plugin("git", "Show git status (alias: /git status)", [], "Dev", _h_git_status),
    Plugin("gitlog", "Show recent git commits", ["log"], "Dev", _h_git_log),
    Plugin("gitbranch", "Show git branches", ["branch"], "Dev", _h_git_branch),
    Plugin("npm", "List top-level npm packages", [], "Dev", _h_npm_list),
    Plugin("pip", "List pip packages", ["packages"], "Dev", _h_pip_list),
    Plugin("docker", "List running Docker containers", [], "Dev", _h_docker_ps),
    Plugin("make", "Run make (use: /run make)", [], "Dev", None),
    Plugin("lint", "Run linter (use: /run flake8 .)", [], "Dev", None),
    Plugin("test", "Run tests (use: /run pytest)", [], "Dev", None),
    Plugin("build", "Build project (use: /run python build.py)", [], "Dev", None),
    Plugin("deploy", "Deploy project (use: /forge deploy the project)", [], "Dev", None),
    Plugin("commit", "Quick git commit (use: /run git add -A && git commit -m 'msg')", [], "Dev", None),
    Plugin("push", "Git push (use: /run git push)", [], "Dev", None),
    Plugin("pull", "Git pull (use: /run git pull)", [], "Dev", None),

    # ── Data (12) ──
    Plugin("json", "Format and display JSON", [], "Data", _h_json_format),
    Plugin("jsonmin", "Minify JSON", ["jmin"], "Data", _h_json_min),
    Plugin("csv", "View a CSV file in a table", [], "Data", _h_csv),
    Plugin("yaml", "View YAML or convert from JSON", [], "Data", _h_yaml),
    Plugin("xml", "Pretty-print XML", [], "Data", _h_xml),
    Plugin("sql", "Run a SQL query on in-memory DB", ["query"], "Data", _h_sql),
    Plugin("stats", "Show file statistics for current dir", ["filestats"], "Data", _h_stats),
    Plugin("sum", "Sum/average/count numbers", [], "Data", _h_sum),
    Plugin("hex", "Encode text as hex", [], "Data", _h_hex),
    Plugin("bytes", "Show byte values of text", [], "Data", _h_bytes),
    Plugin("rot13", "ROT13 encode/decode text", [], "Data", _h_rot13),
    Plugin("uuid", "Generate UUID(s)", ["guid"], "Data", _h_uuid),

    # ── Text (8) ──
    Plugin("md", "Render markdown file", ["markdown"], "Text", _h_markdown),
    Plugin("hash", "Hash text with MD5/SHA1/SHA256", [], "Text", _h_hash_text),
    Plugin("b64encode", "Base64 encode text", ["encode"], "Text", _h_b64encode),
    Plugin("b64decode", "Base64 decode text", ["decode"], "Text", _h_b64decode),
    Plugin("morse", "Convert text to Morse code", [], "Text", _h_morse),
    Plugin("count", "Count files/dirs or file lines", [], "Text", _h_count),
    Plugin("note", "Save a quick note to memory", [], "Text", _h_note),
    Plugin("remind", "Search saved notes/memories", ["remember"], "Text", _h_remind),

    # ── Math (6) ──
    Plugin("calc", "Calculate a math expression", ["calculator"], "Math", _h_calc),
    Plugin("random", "Random number(s)", ["rand"], "Math", _h_random),
    Plugin("password", "Generate a secure password", ["genpass", "pass"], "Math", _h_password),
    Plugin("units", "Show/convert units", ["convert"], "Math", _h_units),
    Plugin("eval", "Evaluate a Python expression", ["py"], "Math", _h_eval_code),
    Plugin("exec", "Execute Python code", ["python"], "Math", _h_exec),

    # ── Fun (9) ──
    Plugin("joke", "Tell a random programming joke", [], "Fun", _h_joke),
    Plugin("quote", "Show a random programming quote", [], "Fun", _h_quote),
    Plugin("banner", "Display a text banner", [], "Fun", _h_banner),
    Plugin("cowsay", "Cowsay-like message", [], "Fun", _h_cowsay),
    Plugin("fortune", "Random fortune cookie", [], "Fun", _h_fortune),
    Plugin("ascii", "Generate ASCII art text", ["figlet"], "Fun", _h_ascii),
    Plugin("clock", "Show ASCII clock (use: /clock analog)", [], "Fun", None),
    Plugin("matrix", "Show current date/time", ["time"], "Fun", _h_time),
    Plugin("cal", "Show a calendar month", ["calendar"], "Fun", _h_cal),

    # ── Time (5) ──
    Plugin("date", "Show current date/time", ["now", "datetime"], "Time", _h_date),
    Plugin("sleep", "Sleep for N seconds", ["wait"], "Time", _h_sleep),
    Plugin("timer", "Set a countdown timer", [], "Time", _h_timer),
    Plugin("uptime", "System uptime", [], "Time", _h_uptime, hidden=True),

    # ── Windows (10) ──
    Plugin("open", "Open a file or URL with default app", [], "Windows", _h_open),
    Plugin("edit", "Edit a file in Notepad", ["notepad"], "Windows", _h_edit_file),
    Plugin("explorer", "Open Windows Explorer at path", [], "Windows", _h_explore_path),
    Plugin("shutdown", "Shutdown the PC (use: /run shutdown /s /t 30)", ["poweroff"], "Windows", _h_shutdown_pc),
    Plugin("restart", "Restart the PC", ["reboot"], "Windows", _h_restart),
    Plugin("lock", "Lock the workstation", [], "Windows", _h_lock),
    Plugin("type", "Display file contents with syntax highlight", ["cat"], "Windows", _h_type),
    Plugin("shortcut", "Create a custom command shortcut", ["alias"], "Windows", _h_shortcut),
    Plugin("ln", "Create a symbolic link (Windows)", ["symlink"], "Windows", _h_ln),
    Plugin("weather", "Quick weather check for a city", [], "Windows", _h_weather),

    # ── DevOps (6) ──
    Plugin("dockerps", "List Docker containers", [], "DevOps", _h_docker_ps),
    Plugin("dockerimg", "List Docker images (use: /run docker images)", [], "DevOps", None),
    Plugin("pipsearch", "Search PyPI packages", ["pkg"], "DevOps", _h_search_pkg),
    Plugin("npminstall", "Install npm packages (use: /run npm install ...)", [], "DevOps", None),
    Plugin("pipinstall", "Install pip packages (use: /run pip install ...)", [], "DevOps", None),
    Plugin("gitclone", "Git clone (use: /run git clone <url>)", [], "DevOps", None),
]

# ── Plugin Manager ──────────────────────────────────────────────────────────────

def build_cmd_map():
    """Build a mapping of all command names to plugin objects."""
    m = {}
    for p in PLUGINS:
        for cmd in p.commands:
            m[cmd] = p
    return m

PLUGIN_CMD_MAP = build_cmd_map()

def get_plugin_commands() -> dict:
    """Return dict of command_name -> description for all visible plugins."""
    return {f"/{p.name}": p.description for p in PLUGINS if not p.hidden}

def resolve_plugin_cmd(cmd: str):
    """Return (plugin, handler) for a command like 'ps', 'kill', etc."""
    name = cmd.lstrip("/").lower().strip()
    p = PLUGIN_CMD_MAP.get(name)
    if p:
        return (p, p.handler)
    return (None, None)

def list_plugin_categories():
    cats = {}
    for p in PLUGINS:
        if not p.hidden:
            cats.setdefault(p.category, []).append(p)
    return cats

def search_plugins(query: str):
    q = query.lower()
    results = []
    for p in PLUGINS:
        if p.hidden:
            continue
        if q in p.name.lower() or q in p.description.lower() or any(q in a.lower() for a in p.aliases):
            results.append(p)
    return results

def get_plugin_info(name: str):
    for p in PLUGINS:
        if p.name == name:
            return p
    return None

def handle_plugin_command(cmd: str, arg: str) -> bool:
    """Handle a plugin command. Returns True if handled, False if unknown."""
    p, handler = resolve_plugin_cmd(cmd)
    if not p:
        return False
    if handler:
        handler(arg)
    else:
        _handler_help(p)
    return True
