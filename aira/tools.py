"""
AIRA Tools Engine
-----------------
Shell execution, system monitoring, web search, file ops,
cron scheduling, and clipboard access.
"""

import os
import sys
import time
import subprocess
import platform
import psutil
import datetime
import json
import re
import threading
from pathlib import Path
from typing import Optional
import requests

AIRA_HOME = Path.home() / ".aira"


# ── SHELL EXECUTION ──────────────────────────────────────────────────────────

def execute_command(cmd: str, timeout: int = 30, cwd: str = None) -> dict:
    """Execute a shell command and return output + metadata."""
    start = datetime.datetime.now()
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd or os.getcwd()
        )
        elapsed = (datetime.datetime.now() - start).total_seconds()
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "elapsed": elapsed,
            "cmd": cmd
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "stdout": "", "stderr": f"Command timed out after {timeout}s", "returncode": -1, "elapsed": timeout, "cmd": cmd}
    except Exception as e:
        return {"success": False, "stdout": "", "stderr": str(e), "returncode": -1, "elapsed": 0, "cmd": cmd}


def get_shell():
    """Detect the best available shell."""
    system = platform.system()
    if system == "Windows":
        return "powershell.exe" if _cmd_exists("powershell.exe") else "cmd.exe"
    return os.environ.get("SHELL", "/bin/bash")


def _cmd_exists(cmd: str) -> bool:
    return subprocess.run(["which", cmd], capture_output=True).returncode == 0


# ── SYSTEM INFO ──────────────────────────────────────────────────────────────

def get_system_snapshot() -> dict:
    """Full system status: CPU, RAM, disk, processes."""
    cpu = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')

    top_procs = []
    for p in sorted(psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']),
                    key=lambda x: x.info.get('cpu_percent', 0) or 0, reverse=True)[:5]:
        top_procs.append({
            "pid": p.info['pid'],
            "name": p.info['name'],
            "cpu": p.info.get('cpu_percent', 0),
            "mem": round(p.info.get('memory_percent', 0), 1)
        })

    return {
        "os": platform.system(),
        "os_version": platform.version(),
        "hostname": platform.node(),
        "cpu_percent": cpu,
        "cpu_cores": psutil.cpu_count(),
        "ram_total_gb": round(mem.total / 1e9, 1),
        "ram_used_percent": mem.percent,
        "ram_available_gb": round(mem.available / 1e9, 1),
        "disk_total_gb": round(disk.total / 1e9, 1),
        "disk_used_percent": disk.percent,
        "disk_free_gb": round(disk.free / 1e9, 1),
        "uptime_hours": round((datetime.datetime.now().timestamp() - psutil.boot_time()) / 3600, 1),
        "top_processes": top_procs,
        "python": sys.version.split()[0],
        "cwd": os.getcwd()
    }


def get_network_info() -> dict:
    """Network interfaces and basic connectivity."""
    interfaces = {}
    for name, addrs in psutil.net_if_addrs().items():
        interfaces[name] = [a.address for a in addrs if a.family == 2]  # AF_INET

    # Quick connectivity check
    try:
        r = requests.get("https://api.ipify.org?format=json", timeout=3)
        public_ip = r.json().get("ip", "unknown")
    except Exception:
        public_ip = "offline"

    return {"interfaces": interfaces, "public_ip": public_ip}


# ── WEB SEARCH ──────────────────────────────────────────────────────────────

def web_search(query: str, num_results: int = 5) -> list:
    """DuckDuckGo instant answers (no API key needed)."""
    try:
        url = f"https://api.duckduckgo.com/?q={requests.utils.quote(query)}&format=json&no_html=1&skip_disambig=1"
        r = requests.get(url, timeout=5, headers={"User-Agent": "AIRA-Terminal/1.0"})
        data = r.json()

        results = []

        # Abstract
        if data.get("Abstract"):
            results.append({
                "title": data.get("Heading", "Result"),
                "snippet": data["Abstract"][:300],
                "url": data.get("AbstractURL", "")
            })

        # Related topics
        for topic in data.get("RelatedTopics", [])[:num_results]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append({
                    "title": topic.get("Text", "")[:60],
                    "snippet": topic.get("Text", "")[:200],
                    "url": topic.get("FirstURL", "")
                })

        return results[:num_results]
    except Exception as e:
        return [{"title": "Search Error", "snippet": str(e), "url": ""}]


def fetch_url(url: str, max_chars: int = 2000) -> str:
    """Fetch and extract text from a URL."""
    try:
        r = requests.get(url, timeout=8, headers={"User-Agent": "AIRA-Terminal/1.0"})
        # Basic HTML strip
        text = re.sub(r'<[^>]+>', ' ', r.text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:max_chars]
    except Exception as e:
        return f"[Error fetching URL: {e}]"


# ── FILE OPS ─────────────────────────────────────────────────────────────────

def read_file(path: str, max_chars: int = 5000) -> str:
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read(max_chars)
        return content
    except Exception as e:
        return f"[Error reading file: {e}]"


def write_file(path: str, content: str) -> dict:
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return {"success": True, "path": path, "size": len(content)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def list_directory(path: str = ".") -> list:
    try:
        entries = []
        for item in sorted(Path(path).iterdir()):
            stat = item.stat()
            entries.append({
                "name": item.name,
                "type": "dir" if item.is_dir() else "file",
                "size": stat.st_size,
                "modified": datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
            })
        return entries
    except Exception as e:
        return [{"name": str(e), "type": "error", "size": 0, "modified": ""}]


# ── CLIPBOARD ────────────────────────────────────────────────────────────────

def copy_to_clipboard(text: str) -> bool:
    try:
        import pyperclip
        pyperclip.copy(text)
        return True
    except Exception:
        return False


def read_clipboard() -> str:
    try:
        import pyperclip
        return pyperclip.paste()
    except Exception:
        return ""


# ── FILE SCANNING ────────────────────────────────────────────────────────────

def scan_directory(path: str = ".", max_depth: int = 3) -> dict:
    """Scan directory tree with sizes, counts, and large files."""
    root = Path(path).resolve()
    if not root.exists():
        return {"error": f"Path not found: {path}"}
    if not root.is_dir():
        return {"error": f"Not a directory: {path}"}

    result = {
        "path": str(root),
        "total_size": 0,
        "total_files": 0,
        "total_folders": 0,
        "max_depth_reached": 0,
        "entries": [],
        "large_files": []
    }

    def _scan(dir_path: Path, depth: int):
        if depth > max_depth:
            return
        if depth > result["max_depth_reached"]:
            result["max_depth_reached"] = depth
        try:
            for item in sorted(dir_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                try:
                    if item.is_dir():
                        result["total_folders"] += 1
                        folder_entry = {
                            "name": item.name,
                            "type": "dir",
                            "size": 0,
                            "file_count": 0,
                            "depth": depth,
                            "children": []
                        }
                        _scan(item, depth + 1)
                        entry = _make_entry(item, depth)
                        result["entries"].append(entry)
                    elif item.is_file():
                        result["total_files"] += 1
                        size = item.stat().st_size
                        result["total_size"] += size
                        entry = _make_entry(item, depth)
                        result["entries"].append(entry)
                        if size > 10 * 1024 * 1024:
                            result["large_files"].append(entry)
                except (PermissionError, OSError):
                    pass
        except (PermissionError, OSError):
            pass

    def _make_entry(item: Path, depth: int) -> dict:
        try:
            stat = item.stat()
            is_dir = item.is_dir()
            return {
                "name": item.name,
                "type": "dir" if is_dir else "file",
                "size": stat.st_size,
                "depth": depth,
                "modified": datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
            }
        except (OSError, PermissionError):
            return {"name": item.name, "type": "?", "size": 0, "depth": depth, "modified": ""}

    _scan(root, 0)
    return result


# ── PROJECT GENERATOR ────────────────────────────────────────────────────────

_PROJECT_TEMPLATES = {
    # ── Web ──
    "website": {
        "files": {
            "index.html": "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n  <meta charset=\"UTF-8\">\n  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n  <title>{name}</title>\n  <link rel=\"stylesheet\" href=\"style.css\">\n</head>\n<body>\n  <h1>Welcome to {name}</h1>\n  <script src=\"script.js\"></script>\n</body>\n</html>",
            "style.css": "* { margin: 0; padding: 0; box-sizing: border-box; }\nbody { font-family: system-ui, sans-serif; padding: 2rem; max-width: 900px; margin: 0 auto; }\nh1 { color: #333; }",
            "script.js": "console.log('{name} loaded');",
        },
        "description": "HTML5 website boilerplate"
    },
    "landing": {
        "files": {
            "index.html": "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n  <meta charset=\"UTF-8\">\n  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n  <title>{name}</title>\n  <link rel=\"stylesheet\" href=\"style.css\">\n</head>\n<body>\n  <header>\n    <nav><h2>{name}</h2><ul><li><a href=\"#\">Home</a></li><li><a href=\"#\">About</a></li><li><a href=\"#\">Contact</a></li></ul></nav>\n  </header>\n  <main>\n    <section class=\"hero\"><h1>Welcome to {name}</h1><p>Your tagline here</p><button>Get Started</button></section>\n    <section class=\"features\"><div class=\"card\"><h3>Feature 1</h3><p>Description</p></div><div class=\"card\"><h3>Feature 2</h3><p>Description</p></div><div class=\"card\"><h3>Feature 3</h3><p>Description</p></div></section>\n  </main>\n  <footer><p>&copy; 2025 {name}</p></footer>\n  <script src=\"script.js\"></script>\n</body>\n</html>",
            "style.css": "* { margin: 0; padding: 0; box-sizing: border-box; }\nbody { font-family: system-ui, sans-serif; line-height: 1.6; }\nnav { display: flex; justify-content: space-between; padding: 1rem 2rem; background: #1a1a2e; color: white; }\nnav ul { list-style: none; display: flex; gap: 1rem; }\nnav a { color: white; text-decoration: none; }\n.hero { text-align: center; padding: 4rem 2rem; background: linear-gradient(135deg, #667eea, #764ba2); color: white; }\n.hero h1 { font-size: 3rem; margin-bottom: 1rem; }\n.hero button { padding: 0.8rem 2rem; border: none; border-radius: 5px; background: white; color: #333; font-size: 1rem; cursor: pointer; }\n.features { display: grid; grid-template-columns: repeat(3, 1fr); gap: 2rem; padding: 4rem 2rem; }\n.card { padding: 2rem; border: 1px solid #ddd; border-radius: 8px; text-align: center; }\nfooter { text-align: center; padding: 2rem; background: #1a1a2e; color: white; }",
            "script.js": "document.querySelector('.hero button')?.addEventListener('click', () => alert('Welcome to {name}!'));",
        },
        "description": "Modern landing page with hero & features"
    },
    "portfolio": {
        "files": {
            "index.html": "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n  <meta charset=\"UTF-8\">\n  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n  <title>{name}</title>\n  <link rel=\"stylesheet\" href=\"style.css\">\n</head>\n<body>\n  <header><h1>{name}</h1><p>Developer & Creator</p></header>\n  <section class=\"about\"><h2>About</h2><p>Write something about yourself.</p></section>\n  <section class=\"projects\"><h2>Projects</h2><div class=\"grid\"><div class=\"card\"><h3>Project 1</h3><p>Description</p></div><div class=\"card\"><h3>Project 2</h3><p>Description</p></div><div class=\"card\"><h3>Project 3</h3><p>Description</p></div></div></section>\n  <section class=\"contact\"><h2>Contact</h2><p>email@example.com</p></section>\n  <footer><p>&copy; 2025 {name}</p></footer>\n  <script src=\"script.js\"></script>\n</body>\n</html>",
            "style.css": "* { margin: 0; padding: 0; box-sizing: border-box; }\nbody { font-family: system-ui, sans-serif; line-height: 1.6; color: #333; }\nheader { text-align: center; padding: 4rem 2rem; background: #f0f0f0; }\nheader h1 { font-size: 3rem; color: #2c3e50; }\nsection { padding: 3rem 2rem; max-width: 1000px; margin: 0 auto; }\nsection h2 { margin-bottom: 2rem; color: #2c3e50; }\n.grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.5rem; }\n.card { padding: 1.5rem; border: 1px solid #ddd; border-radius: 8px; }\nfooter { text-align: center; padding: 2rem; background: #2c3e50; color: white; }",
            "script.js": "console.log('{name} portfolio loaded');",
        },
        "description": "Portfolio website template"
    },
    "dashboard": {
        "files": {
            "index.html": "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n  <meta charset=\"UTF-8\">\n  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n  <title>{name}</title>\n  <link rel=\"stylesheet\" href=\"style.css\">\n</head>\n<body>\n  <aside class=\"sidebar\"><h2>{name}</h2><nav><a href=\"#\">Dashboard</a><a href=\"#\">Analytics</a><a href=\"#\">Users</a><a href=\"#\">Settings</a></nav></aside>\n  <main class=\"content\">\n    <header class=\"topbar\"><h1>Dashboard</h1><div class=\"user\">Admin</div></header>\n    <div class=\"cards\"><div class=\"stat\"><h3>Revenue</h3><p>$12,430</p></div><div class=\"stat\"><h3>Users</h3><p>1,234</p></div><div class=\"stat\"><h3>Orders</h3><p>456</p></div><div class=\"stat\"><h3>Growth</h3><p>+12%</p></div></div>\n    <div class=\"chart-placeholder\"><h3>Chart Area</h3></div>\n  </main>\n  <script src=\"script.js\"></script>\n</body>\n</html>",
            "style.css": "* { margin: 0; padding: 0; box-sizing: border-box; }\nbody { display: flex; font-family: system-ui, sans-serif; }\n.sidebar { width: 240px; background: #1a1a2e; color: white; padding: 2rem; height: 100vh; }\n.sidebar h2 { margin-bottom: 2rem; }\n.sidebar nav { display: flex; flex-direction: column; gap: 1rem; }\n.sidebar a { color: #aaa; text-decoration: none; padding: 0.5rem; border-radius: 4px; }\n.sidebar a:hover { background: #16213e; color: white; }\n.content { flex: 1; padding: 2rem; background: #f5f5f5; }\n.topbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem; }\n.cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1.5rem; margin-bottom: 2rem; }\n.stat { background: white; padding: 1.5rem; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }\n.stat h3 { color: #666; font-size: 0.9rem; }\n.stat p { font-size: 1.8rem; font-weight: bold; color: #333; }\n.chart-placeholder { background: white; padding: 3rem; border-radius: 8px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }",
            "script.js": "console.log('{name} dashboard loaded');",
        },
        "description": "Admin dashboard with sidebar & stats"
    },
    "blog": {
        "files": {
            "index.html": "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n  <meta charset=\"UTF-8\">\n  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n  <title>{name}</title>\n  <link rel=\"stylesheet\" href=\"style.css\">\n</head>\n<body>\n  <header><h1>{name}</h1><p class=\"subtitle\">Thoughts & Ideas</p></header>\n  <main>\n    <article><h2>First Post</h2><p class=\"date\">Jan 1, 2025</p><p>This is your first blog post. Edit or add more posts.</p></article>\n    <article><h2>Second Post</h2><p class=\"date\">Jan 5, 2025</p><p>Another blog post goes here.</p></article>\n  </main>\n  <footer><p>&copy; 2025 {name}</p></footer>\n  <script src=\"script.js\"></script>\n</body>\n</html>",
            "style.css": "* { margin: 0; padding: 0; box-sizing: border-box; }\nbody { font-family: 'Georgia', serif; line-height: 1.8; color: #333; max-width: 800px; margin: 0 auto; padding: 2rem; }\nheader { text-align: center; padding: 3rem 0; border-bottom: 1px solid #eee; margin-bottom: 3rem; }\nh1 { font-size: 2.5rem; color: #2c3e50; }\n.subtitle { color: #999; font-style: italic; }\narticle { margin-bottom: 3rem; padding-bottom: 2rem; border-bottom: 1px solid #f0f0f0; }\nh2 { color: #2c3e50; margin-bottom: 0.5rem; }\n.date { color: #999; font-size: 0.9rem; margin-bottom: 1rem; }\nfooter { text-align: center; padding: 2rem; color: #999; font-size: 0.9rem; }",
            "script.js": "console.log('{name} blog loaded');",
        },
        "description": "Simple blog template"
    },
    "game": {
        "files": {
            "index.html": "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n  <meta charset=\"UTF-8\">\n  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n  <title>{name}</title>\n  <link rel=\"stylesheet\" href=\"style.css\">\n</head>\n<body>\n  <h1>{name}</h1>\n  <canvas id=\"game\" width=\"600\" height=\"400\"></canvas>\n  <p id=\"score\">Score: 0</p>\n  <button onclick=\"resetGame()\">Restart</button>\n  <script src=\"game.js\"></script>\n</body>\n</html>",
            "style.css": "* { margin: 0; padding: 0; box-sizing: border-box; }\nbody { font-family: system-ui, sans-serif; text-align: center; padding: 2rem; background: #1a1a2e; color: white; }\nh1 { margin-bottom: 1rem; }\ncanvas { border: 2px solid #667eea; border-radius: 8px; background: #16213e; }\n#score { font-size: 1.5rem; margin: 1rem 0; }\nbutton { padding: 0.5rem 2rem; border: none; border-radius: 5px; background: #667eea; color: white; font-size: 1rem; cursor: pointer; }",
            "game.js": "const canvas = document.getElementById('game');\nconst ctx = canvas.getContext('2d');\nlet score = 0;\nlet player = { x: 300, y: 380, w: 40, h: 20 };\nlet bullets = [];\nlet enemies = [];\nfor (let i = 0; i < 5; i++) enemies.push({ x: i * 120 + 20, y: 30, w: 30, h: 20 });\nlet dx = 2;\nlet dy = 0;\nlet right = false, left = false;\ndocument.addEventListener('keydown', e => { if (e.key === 'ArrowRight') right = true; if (e.key === 'ArrowLeft') left = true; if (e.key === ' ') bullets.push({ x: player.x + 18, y: player.y - 10, w: 4, h: 10 }); });\ndocument.addEventListener('keyup', e => { if (e.key === 'ArrowRight') right = false; if (e.key === 'ArrowLeft') left = false; });\nfunction update() {\n  if (right) player.x += 5;\n  if (left) player.x -= 5;\n  if (player.x < 0) player.x = 0;\n  if (player.x > canvas.width - player.w) player.x = canvas.width - player.w;\n  bullets.forEach(b => b.y -= 5);\n  bullets = bullets.filter(b => b.y > 0);\n  enemies.forEach(e => { e.x += dx; });\n  enemies.forEach(e => { if (e.x <= 0 || e.x >= canvas.width - e.w) dx = -dx; });\n  bullets.forEach(b => { enemies.forEach(e => { if (b.x < e.x + e.w && b.x + b.w > e.x && b.y < e.y + e.h && b.y + b.h > e.y) { e.y = -100; score += 10; } }); });\n  enemies = enemies.filter(e => e.y < canvas.height);\n  enemies.forEach(e => { if (player.x < e.x + e.w && player.x + player.w > e.x && player.y < e.y + e.h && player.y + player.h > e.y) { alert('Game Over! Score: ' + score); resetGame(); } });\n}\nfunction draw() {\n  ctx.clearRect(0, 0, canvas.width, canvas.height);\n  ctx.fillStyle = '#667eea'; ctx.fillRect(player.x, player.y, player.w, player.h);\n  ctx.fillStyle = '#ff6b6b'; enemies.forEach(e => ctx.fillRect(e.x, e.y, e.w, e.h));\n  ctx.fillStyle = '#ffd93d'; bullets.forEach(b => ctx.fillRect(b.x, b.y, b.w, b.h));\n  document.getElementById('score').textContent = 'Score: ' + score;\n}\nfunction loop() { update(); draw(); requestAnimationFrame(loop); }\nfunction resetGame() { score = 0; player.x = 300; enemies = []; for (let i = 0; i < 5; i++) enemies.push({ x: i * 120 + 20, y: 30, w: 30, h: 20 }); bullets = []; }\nloop();",
        },
        "description": "HTML5 Canvas game (space shooter)"
    },
    "pwa": {
        "files": {
            "index.html": "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n  <meta charset=\"UTF-8\">\n  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n  <title>{name}</title>\n  <link rel=\"manifest\" href=\"manifest.json\">\n  <link rel=\"stylesheet\" href=\"style.css\">\n</head>\n<body>\n  <h1>{name} PWA</h1>\n  <p>This app works offline!</p>\n  <script src=\"app.js\"></script>\n</body>\n</html>",
            "style.css": "* { margin: 0; padding: 0; box-sizing: border-box; }\nbody { font-family: system-ui, sans-serif; padding: 2rem; text-align: center; }",
            "app.js": "if ('serviceWorker' in navigator) { navigator.serviceWorker.register('sw.js'); }\nconsole.log('{name} PWA loaded');",
            "sw.js": "self.addEventListener('install', e => { e.waitUntil(caches.open('v1').then(c => c.addAll(['index.html','style.css','app.js','manifest.json']))); });\nself.addEventListener('fetch', e => { e.respondWith(caches.match(e.request).then(r => r || fetch(e.request))); });",
            "manifest.json": json.dumps({"name": "{name}", "short_name": "{name}", "start_url": "/", "display": "standalone", "background_color": "#ffffff", "theme_color": "#333333"}, indent=2),
        },
        "description": "Progressive Web App with offline support"
    },
    "tailwind": {
        "files": {
            "index.html": "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n  <meta charset=\"UTF-8\">\n  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n  <title>{name}</title>\n  <script src=\"https://cdn.tailwindcss.com\"></script>\n</head>\n<body class=\"bg-gray-50 min-h-screen flex items-center justify-center\">\n  <div class=\"bg-white p-8 rounded-xl shadow-lg max-w-md w-full\">\n    <h1 class=\"text-3xl font-bold text-center text-gray-800 mb-4\">{name}</h1>\n    <p class=\"text-gray-600 text-center mb-6\">Built with Tailwind CSS</p>\n    <button class=\"w-full bg-indigo-600 text-white py-2 px-4 rounded-lg hover:bg-indigo-700 transition\">Get Started</button>\n  </div>\n</body>\n</html>",
        },
        "description": "Tailwind CSS (CDN) landing page"
    },
    "bootstrap": {
        "files": {
            "index.html": "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n  <meta charset=\"UTF-8\">\n  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n  <title>{name}</title>\n  <link href=\"https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css\" rel=\"stylesheet\">\n</head>\n<body>\n  <div class=\"container py-5\">\n    <h1 class=\"display-4 text-center\">{name}</h1>\n    <p class=\"lead text-center text-muted\">Built with Bootstrap 5</p>\n    <div class=\"row mt-5\">\n      <div class=\"col-md-4\"><div class=\"card\"><div class=\"card-body\"><h5 class=\"card-title\">Feature 1</h5><p class=\"card-text\">Description here.</p></div></div></div>\n      <div class=\"col-md-4\"><div class=\"card\"><div class=\"card-body\"><h5 class=\"card-title\">Feature 2</h5><p class=\"card-text\">Description here.</p></div></div></div>\n      <div class=\"col-md-4\"><div class=\"card\"><div class=\"card-body\"><h5 class=\"card-title\">Feature 3</h5><p class=\"card-text\">Description here.</p></div></div></div>\n    </div>\n  </div>\n  <script src=\"https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js\"></script>\n</body>\n</html>",
        },
        "description": "Bootstrap 5 landing page"
    },
    "react": {
        "files": {
            "index.html": "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n  <meta charset=\"UTF-8\">\n  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n  <title>{name}</title>\n  <script crossorigin src=\"https://unpkg.com/react@18/umd/react.development.js\"></script>\n  <script crossorigin src=\"https://unpkg.com/react-dom@18/umd/react-dom.development.js\"></script>\n  <script src=\"https://unpkg.com/@babel/standalone/babel.min.js\"></script>\n  <link rel=\"stylesheet\" href=\"style.css\">\n</head>\n<body>\n  <div id=\"root\"></div>\n  <script type=\"text/babel\" src=\"app.jsx\"></script>\n</body>\n</html>",
            "style.css": "* { margin: 0; padding: 0; box-sizing: border-box; }\nbody { font-family: system-ui, sans-serif; }",
            "app.jsx": "function App() {\n  const [count, setCount] = React.useState(0);\n  return (\n    <div style={{padding: '2rem', textAlign: 'center'}}>\n      <h1>{'{name}'}</h1>\n      <p>React app with Hooks</p>\n      <button onClick={() => setCount(c => c + 1)}>Clicked {count} times</button>\n    </div>\n  );\n}\nReactDOM.createRoot(document.getElementById('root')).render(<App />);",
        },
        "description": "React app (CDN, no build step)"
    },

    # ── Backend / API ──
    "webapp": {
        "files": {
            "index.html": "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n  <meta charset=\"UTF-8\">\n  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n  <title>{name}</title>\n  <link rel=\"stylesheet\" href=\"style.css\">\n</head>\n<body>\n  <div id=\"app\"></div>\n  <script src=\"app.js\"></script>\n</body>\n</html>",
            "style.css": "* { margin: 0; padding: 0; box-sizing: border-box; }\nbody { font-family: system-ui, sans-serif; }\n#app { min-height: 100vh; }",
            "app.js": "document.addEventListener('DOMContentLoaded', () => {\n  const app = document.getElementById('app');\n  app.innerHTML = '<h1>Welcome to {name}</h1>';\n});",
            "package.json": json.dumps({"name": "{name}", "version": "1.0.0", "private": True, "scripts": {"start": "npx serve ."}}, indent=2),
        },
        "description": "Full web app scaffold with package.json"
    },
    "express": {
        "files": {
            "server.js": "const express = require('express');\nconst app = express();\nconst port = process.env.PORT || 3000;\n\napp.get('/', (req, res) => {\n  res.json({ message: 'Hello from {name}!' });\n});\n\napp.listen(port, () => {\n  console.log('{name} running on port ' + port);\n});",
            "package.json": json.dumps({"name": "{name}", "version": "1.0.0", "private": True, "main": "server.js", "scripts": {"start": "node server.js"}, "dependencies": {"express": "^4.18.0"}}, indent=2),
            "README.md": "# {name}\n\nExpress.js API server\n\n```\nnpm install\nnpm start\n```",
        },
        "description": "Node.js Express API server"
    },
    "flask": {
        "files": {
            "app.py": "from flask import Flask, jsonify\napp = Flask(__name__)\n\n@app.route('/')\ndef home():\n    return jsonify({'message': 'Hello from {name}!'})\n\nif __name__ == '__main__':\n    app.run(debug=True, port=5000)",
            "requirements.txt": "flask>=3.0\n",
            "README.md": "# {name}\n\nFlask web app\n\n```\npip install -r requirements.txt\npython app.py\n```",
        },
        "description": "Python Flask web server"
    },
    "fastapi": {
        "files": {
            "main.py": "from fastapi import FastAPI\nfrom fastapi.responses import HTMLResponse\n\napp = FastAPI(title='{name}')\n\n@app.get('/')\nasync def root():\n    return HTMLResponse('<h1>Welcome to {name}</h1>')\n\n@app.get('/api')\nasync def api():\n    return {'message': 'Hello from {name}!'}",
            "requirements.txt": "fastapi>=0.100\nuvicorn>=0.20\n",
            "README.md": "# {name}\n\nFastAPI app\n\n```\npip install -r requirements.txt\nuvicorn main:app --reload\n```",
        },
        "description": "Python FastAPI backend"
    },
    "api": {
        "files": {
            "app.py": "from flask import Flask, jsonify, request\napp = Flask(__name__)\n\nitems = []\n\n@app.route('/api/items', methods=['GET'])\ndef get_items():\n    return jsonify(items)\n\n@app.route('/api/items', methods=['POST'])\ndef create_item():\n    data = request.get_json()\n    item = {'id': len(items) + 1, **data}\n    items.append(item)\n    return jsonify(item), 201\n\nif __name__ == '__main__':\n    app.run(debug=True, port=5000)",
            "requirements.txt": "flask>=3.0\nflask-cors>=4.0\n",
            "README.md": "# {name} API\n\nREST API with Flask\n\n```\npip install -r requirements.txt\npython app.py\n```\n\n## Endpoints\n- GET /api/items\n- POST /api/items",
        },
        "description": "REST API with Flask + CRUD example"
    },

    # ── Python ──
    "python": {
        "files": {
            "main.py": "#!/usr/bin/env python3\ndef main():\n    print(\"Hello from {name}!\")\n\nif __name__ == \"__main__\":\n    main()",
            "requirements.txt": "# {name} dependencies\n",
            "README.md": "# {name}\n\nProject description.\n",
        },
        "description": "Python project structure"
    },
    "cli": {
        "files": {
            "{name}.py": "#!/usr/bin/env python3\nimport argparse\n\ndef main():\n    parser = argparse.ArgumentParser(description='{name} CLI tool')\n    parser.add_argument('--name', default='World', help='Name to greet')\n    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')\n    args = parser.parse_args()\n\n    if args.verbose:\n        print(f'Running {__file__}')\n    print(f'Hello, {args.name}!')\n\nif __name__ == '__main__':\n    main()",
            "setup.py": "from setuptools import setup\nsetup(\n    name='{name}',\n    version='1.0.0',\n    py_modules=['{name}'],\n    entry_points={'console_scripts': ['{name}={name}:main']},\n)",
            "README.md": "# {name}\n\nCLI tool\n\n```\npip install -e .\n{name} --name Alice\n```",
        },
        "description": "Python CLI tool with argparse"
    },
    "scraper": {
        "files": {
            "scraper.py": "#!/usr/bin/env python3\nimport requests\nfrom bs4 import BeautifulSoup\nimport json\n\ndef scrape(url):\n    r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})\n    soup = BeautifulSoup(r.text, 'html.parser')\n    title = soup.title.string if soup.title else 'No title'\n    links = [a.get('href') for a in soup.find_all('a', href=True)][:10]\n    return {'title': title, 'links': links, 'url': url}\n\nif __name__ == '__main__':\n    import sys\n    url = sys.argv[1] if len(sys.argv) > 1 else 'https://example.com'\n    print(json.dumps(scrape(url), indent=2))",
            "requirements.txt": "requests>=2.28\nbeautifulsoup4>=4.12\n",
            "README.md": "# {name}\n\nWeb scraper\n\n```\npip install -r requirements.txt\npython scraper.py https://example.com\n```",
        },
        "description": "Python web scraper with BeautifulSoup"
    },

    # ── Bots ──
    "discord": {
        "files": {
            "bot.py": "import discord\nfrom discord.ext import commands\n\nbot = commands.Bot(command_prefix='!', intents=discord.Intents.default())\n\n@bot.event\nasync def on_ready():\n    print(f'{bot.user} is ready!')\n\n@bot.command()\nasync def hello(ctx):\n    await ctx.send(f'Hello from {ctx.author}!')\n\nbot.run('YOUR_TOKEN_HERE')",
            "requirements.txt": "discord.py>=2.3\n",
            "README.md": "# {name}\n\nDiscord bot\n\n1. Create bot at https://discord.com/developers\n2. Add token to bot.py\n3. Run: python bot.py",
        },
        "description": "Discord.py bot template"
    },

    # ── Scripts ──
    "script": {
        "files": {
            "main.sh": "#!/bin/bash\n# {name}\n\necho \"Hello from {name}!\"\n",
            "README.md": "# {name}\n\nScript description.\n",
        },
        "description": "Shell script template"
    },
    "batch": {
        "files": {
            "{name}.bat": "@echo off\nREM {name}\necho Hello from {name}!\npause\n",
        },
        "description": "Windows batch script"
    },
    "powershell": {
        "files": {
            "{name}.ps1": "# {name}\nWrite-Host \"Hello from {name}!\" -ForegroundColor Cyan\n",
        },
        "description": "PowerShell script"
    },

    # ── Engines ──
    "forge": {
        "files": {
            "forge.py": "#!/usr/bin/env python3\n\"\"\"{name} - Build engine.\"\"\"\nimport os\nimport sys\nimport json\nfrom pathlib import Path\n\nCONFIG = {}\n\ndef load_config():\n    cfg = Path('forge.json')\n    if cfg.exists():\n        return json.loads(cfg.read_text())\n    return {'name': '{name}', 'version': '1.0.0', 'steps': []}\n\ndef build():\n    config = load_config()\n    print(f'[{config[\"name\"]}] Starting build...')\n    for step in config.get('steps', []):\n        print(f'  -> {step}')\n    print(f'[{config[\"name\"]}] Build complete.')\n\ndef deploy():\n    print('Deploying {name}...')\n\ndef main():\n    cmd = sys.argv[1] if len(sys.argv) > 1 else 'build'\n    {'build': build, 'deploy': deploy}.get(cmd, lambda: print(f'Unknown: {cmd}'))()\n\nif __name__ == '__main__':\n    main()",
            "forge.json": json.dumps({"name": "{name}", "version": "1.0.0", "steps": ["lint", "test", "package", "deploy"]}, indent=2),
            "README.md": "# {name} - Forge Engine\n\nA build automation engine.\n\n```\npython forge.py build\npython forge.py deploy\n```",
        },
        "description": "Build/automation engine (Forge)"
    },
    "photon": {
        "files": {
            "engine.py": "#!/usr/bin/env python3\n\"\"\"{name} - Photon graphics engine.\"\"\"\nimport struct\nimport math\n\nclass Vector3:\n    def __init__(self, x=0, y=0, z=0):\n        self.x, self.y, self.z = x, y, z\n    def __add__(self, o): return Vector3(self.x+o.x, self.y+o.y, self.z+o.z)\n    def __sub__(self, o): return Vector3(self.x-o.x, self.y-o.y, self.z-o.z)\n    def dot(self, o): return self.x*o.x + self.y*o.y + self.z*o.z\n    def cross(self, o): return Vector3(self.y*o.z-self.z*o.y, self.z*o.x-self.x*o.z, self.x*o.y-self.y*o.x)\n    def norm(self): m = math.sqrt(self.dot(self)); return Vector3(self.x/m, self.y/m, self.z/m) if m else self\n    def __repr__(self): return f'V3({self.x:.2f},{self.y:.2f},{self.z:.2f})'\n\nclass Matrix4:\n    def __init__(self, data=None):\n        self.m = data or [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1]\n    def __matmul__(self, o):\n        r = [0]*16\n        for i in range(4):\n            for j in range(4):\n                for k in range(4):\n                    r[i*4+j] += self.m[i*4+k] * o.m[k*4+j]\n        return Matrix4(r)\n    @staticmethod\n    def rotate_x(angle):\n        c, s = math.cos(angle), math.sin(angle)\n        return Matrix4([1,0,0,0, 0,c,-s,0, 0,s,c,0, 0,0,0,1])\n    @staticmethod\n    def rotate_y(angle):\n        c, s = math.cos(angle), math.sin(angle)\n        return Matrix4([c,0,s,0, 0,1,0,0, -s,0,c,0, 0,0,0,1])\n    def transform(self, v):\n        return Vector3(\n            self.m[0]*v.x + self.m[1]*v.y + self.m[2]*v.z + self.m[3],\n            self.m[4]*v.x + self.m[5]*v.y + self.m[6]*v.z + self.m[7],\n            self.m[8]*v.x + self.m[9]*v.y + self.m[10]*v.z + self.m[11],\n        )\n\ndef main():\n    v = Vector3(1, 2, 3)\n    print(f'Vector: {v}')\n    m = Matrix4.rotate_y(math.pi/4)\n    print(f'Rotated: {m.transform(v)}')\n\nif __name__ == '__main__':\n    main()",
            "README.md": "# {name} - Photon Engine\n\nA 3D graphics/math engine in pure Python.\n\n```\npython engine.py\n```",
        },
        "description": "3D graphics/math engine (Photon)"
    },
    "pixel": {
        "files": {
            "pixel.py": "#!/usr/bin/env python3\n\"\"\"{name} - 2D pixel game engine.\"\"\"\nimport json\nfrom pathlib import Path\n\nclass Sprite:\n    def __init__(self, chars, w, h, color=None):\n        self.chars = chars\n        self.w, self.h = w, h\n        self.color = color or (255, 255, 255)\n        self.x = self.y = 0\n\nclass Scene:\n    def __init__(self, w=80, h=24):\n        self.w, self.h = w, h\n        self.sprites = []\n        self.bg = ' '\n    def add(self, sprite):\n        self.sprites.append(sprite)\n    def render(self):\n        grid = [[self.bg]*self.w for _ in range(self.h)]\n        for s in self.sprites:\n            for i, row in enumerate(s.chars):\n                for j, ch in enumerate(row):\n                    x, y = int(s.x) + j, int(s.y) + i\n                    if 0 <= x < self.w and 0 <= y < self.h and ch != ' ':\n                        grid[y][x] = ch\n        return '\\n'.join(''.join(row) for row in grid)\n    def tick(self): pass\n\nclass Game:\n    def __init__(self, name):\n        self.name = name\n        self.scene = Scene()\n        self.running = True\n    def setup(self): pass\n    def update(self): pass\n    def run(self):\n        self.setup()\n        while self.running:\n            self.update()\n            self.scene.tick()\n            print('\\033[2J\\033[H' + self.scene.render())\n            import time; time.sleep(0.1)\n\ndef main():\n    game = Game('{name}')\n    player = Sprite(['@'], 1, 1, (0, 255, 0))\n    game.scene.add(player)\n    print(f'{game.name} 2D engine ready!')\n    print('Run game.run() to start.')\n\nif __name__ == '__main__':\n    main()",
            "README.md": "# {name} - Pixel Engine\n\nA 2D pixel game engine for terminal games.\n\n```\npython pixel.py\n```",
        },
        "description": "2D pixel game engine (Pixel)"
    },
    "matter": {
        "files": {
            "physics.py": "#!/usr/bin/env python3\n\"\"\"{name} - Physics engine.\"\"\"\nimport math\n\nclass Vec2:\n    def __init__(self, x=0, y=0): self.x, self.y = x, y\n    def __add__(self, o): return Vec2(self.x+o.x, self.y+o.y)\n    def __sub__(self, o): return Vec2(self.x-o.x, self.y-o.y)\n    def __mul__(self, s): return Vec2(self.x*s, self.y*s)\n    def dot(self, o): return self.x*o.x + self.y*o.y\n    def len(self): return math.sqrt(self.dot(self))\n    def norm(self): l = self.len(); return Vec2(self.x/l, self.y/l) if l else self\n    def __repr__(self): return f'V({self.x:.2f},{self.y:.2f})'\n\nclass Body:\n    def __init__(self, pos, mass=1, vel=None):\n        self.pos = pos\n        self.vel = vel or Vec2()\n        self.mass = mass\n        self.force = Vec2()\n    def apply(self, f): self.force = self.force + f\n    def update(self, dt):\n        acc = self.force * (1/self.mass)\n        self.vel = self.vel + acc * dt\n        self.pos = self.pos + self.vel * dt\n        self.force = Vec2()\n\nclass World:\n    def __init__(self):\n        self.bodies = []\n        self.gravity = Vec2(0, 9.81)\n    def add(self, body): self.bodies.append(body)\n    def step(self, dt=1/60):\n        for b in self.bodies:\n            b.apply(self.gravity * b.mass)\n            b.update(dt)\n\ndef main():\n    world = World()\n    b = Body(Vec2(0, 100), mass=5)\n    world.add(b)\n    for _ in range(10):\n        world.step()\n        print(f'Pos: {b.pos.y:.2f}  Vel: {b.vel.y:.2f}')\n\nif __name__ == '__main__':\n    main()",
            "README.md": "# {name} - Matter Engine\n\nA 2D physics engine with gravity, forces, and collision ready.\n\n```\npython physics.py\n```",
        },
        "description": "2D physics engine (Matter)"
    },
    "ecs": {
        "files": {
            "ecs.py": "#!/usr/bin/env python3\n\"\"\"{name} - Entity-Component-System engine.\"\"\"\nfrom collections import defaultdict\n\nclass Entity:\n    _next_id = 0\n    def __init__(self):\n        self.id = Entity._next_id; Entity._next_id += 1\n        self.components = {}\n    def add(self, comp): self.components[type(comp).__name__] = comp; return self\n    def get(self, t): return self.components.get(t)\n    def has(self, t): return t in self.components\n\nclass Engine:\n    def __init__(self):\n        self.entities = {}\n        self.systems = []\n    def create_entity(self):\n        e = Entity(); self.entities[e.id] = e; return e\n    def add_system(self, sys): self.systems.append(sys); return self\n    def update(self, dt):\n        for sys in self.systems:\n            sys.run(self.entities.values(), dt)\n\nclass System:\n    def run(self, entities, dt): pass\n\n# Example components\nclass Position:\n    def __init__(self, x=0, y=0): self.x, self.y = x, y\nclass Velocity:\n    def __init__(self, vx=0, vy=0): self.vx, self.vy = vx, vy\n\nclass MovementSystem(System):\n    def run(self, entities, dt):\n        for e in entities:\n            pos = e.get('Position')\n            vel = e.get('Velocity')\n            if pos and vel:\n                pos.x += vel.vx * dt\n                pos.y += vel.vy * dt\n\ndef main():\n    engine = Engine()\n    engine.add_system(MovementSystem())\n    player = engine.create_entity().add(Position(0, 0)).add(Velocity(10, 5))\n    engine.update(1)\n    p = player.get('Position')\n    print(f'Player pos: ({p.x}, {p.y})')\n\nif __name__ == '__main__':\n    main()",
            "README.md": "# {name} - ECS Engine\n\nEntity-Component-System game engine.\n\n```\npython ecs.py\n```",
        },
        "description": "Entity-Component-System engine (ECS)"
    },
    "search": {
        "files": {
            "search.py": "#!/usr/bin/env python3\n\"\"\"{name} - Search engine.\"\"\"\nimport re\nimport math\nfrom collections import Counter\n\nclass SearchEngine:\n    def __init__(self):\n        self.docs = {}\n        self.index = {}  # term -> {doc_id -> count}\n    def add_doc(self, doc_id, text):\n        self.docs[doc_id] = text\n        tokens = re.findall(r'\\w+', text.lower())\n        counts = Counter(tokens)\n        for term, count in counts.items():\n            if term not in self.index:\n                self.index[term] = {}\n            self.index[term][doc_id] = count\n    def search(self, query):\n        tokens = re.findall(r'\\w+', query.lower())\n        n = len(self.docs)\n        scores = Counter()\n        for term in tokens:\n            if term not in self.index:\n                continue\n            idf = math.log((n + 1) / (len(self.index[term]) + 1)) + 1\n            for doc_id, count in self.index[term].items():\n                tf = 1 + math.log(count)\n                scores[doc_id] += tf * idf\n        return scores.most_common()\n\ndef main():\n    se = SearchEngine()\n    se.add_doc(1, 'Python is a great programming language')\n    se.add_doc(2, 'Search engines use complex algorithms')\n    se.add_doc(3, 'Python powers many web search tools')\n    results = se.search('python search')\n    for doc_id, score in results:\n        print(f'Doc {doc_id} (score {score:.2f}): {se.docs[doc_id]}')\n\nif __name__ == '__main__':\n    main()",
            "README.md": "# {name} - Search Engine\n\nA TF-IDF search engine with indexing and ranking.\n\n```\npython search.py\n```",
        },
        "description": "TF-IDF text search engine"
    },
    "render": {
        "files": {
            "renderer.py": "#!/usr/bin/env python3\n\"\"\"{name} - 3D rendering engine.\"\"\"\nimport math\n\nclass Vec3:\n    def __init__(self, x=0, y=0, z=0): self.x, self.y, self.z = x, y, z\n    def __add__(self, o): return Vec3(self.x+o.x, self.y+o.y, self.z+o.z)\n    def __sub__(self, o): return Vec3(self.x-o.x, self.y-o.y, self.z-o.z)\n    def __mul__(self, s): return Vec3(self.x*s, self.y*s, self.z*s)\n    def dot(self, o): return self.x*o.x + self.y*o.y + self.z*o.z\n    def cross(self, o): return Vec3(self.y*o.z-self.z*o.y, self.z*o.x-self.x*o.z, self.x*o.y-self.y*o.x)\n    def norm(self): m = math.sqrt(self.dot(self)); return Vec3(self.x/m, self.y/m, self.z/m) if m else self\n    def __repr__(self): return f'({self.x:.1f},{self.y:.1f},{self.z:.1f})'\n\nclass Ray:\n    def __init__(self, origin, direction):\n        self.origin, self.dir = origin, direction.norm()\n\nclass Sphere:\n    def __init__(self, center, radius, color):\n        self.center, self.radius, self.color = center, radius, color\n    def intersect(self, ray):\n        oc = ray.origin - self.center\n        a = ray.dir.dot(ray.dir)\n        b = 2 * oc.dot(ray.dir)\n        c = oc.dot(oc) - self.radius**2\n        d = b*b - 4*a*c\n        if d < 0: return None\n        t = (-b - math.sqrt(d)) / (2*a)\n        if t < 0: t = (-b + math.sqrt(d)) / (2*a)\n        return t if t > 0 else None\n    def normal(self, p): return (p - self.center).norm()\n\ndef render():\n    spheres = [Sphere(Vec3(0, 0, -5), 1, (255, 0, 0)), Sphere(Vec3(2, 0, -6), 1, (0, 255, 0)), Sphere(Vec3(-2, 0, -6), 1, (0, 0, 255))]\n    w, h = 40, 20\n    pixels = []\n    for y in range(h):\n        row = []\n        for x in range(w):\n            u = (x / w) * 2 - 1\n            v = (y / h) * 2 - 1\n            ray = Ray(Vec3(0, 0, 0), Vec3(u, v, -1))\n            color = (0, 0, 0)\n            nearest = float('inf')\n            for s in spheres:\n                t = s.intersect(ray)\n                if t and t < nearest:\n                    nearest = t\n                    color = s.color\n            ch = ' .,-:=+*#%@' if sum(color) > 0 else ' '\n            idx = int(sum(color) / 3 / 255 * (len(ch) - 1))\n            row.append(ch[idx])\n        pixels.append(''.join(row))\n    return '\\n'.join(pixels)\n\nif __name__ == '__main__':\n    print(render())",
            "README.md": "# {name} - Render Engine\n\nA software 3D raytracing renderer.\n\n```\npython renderer.py\n```",
        },
        "description": "3D ray-tracing render engine"
    },
    "workflow": {
        "files": {
            "engine.py": "#!/usr/bin/env python3\n\"\"\"{name} - Workflow automation engine.\"\"\"\nimport json\nfrom pathlib import Path\nimport subprocess\n\nclass Workflow:\n    def __init__(self, name):\n        self.name = name\n        self.steps = []\n        self.vars = {}\n    def add_step(self, name, cmd, depends_on=None):\n        self.steps.append({'name': name, 'cmd': cmd, 'depends_on': depends_on or []})\n    def run(self):\n        print(f'[{self.name}] Running {len(self.steps)} steps...')\n        done = set()\n        while len(done) < len(self.steps):\n            for step in self.steps:\n                if step['name'] in done: continue\n                deps = step['depends_on']\n                if all(d in done for d in deps):\n                    cmd = step['cmd']\n                    for k, v in self.vars.items():\n                        cmd = cmd.replace('{' + k + '}', str(v))\n                    print(f'  -> {step[\"name\"]}: {cmd}')\n                    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)\n                    if r.returncode == 0:\n                        done.add(step['name'])\n                        if r.stdout.strip():\n                            self.vars[step['name']] = r.stdout.strip()\n                    else:\n                        print(f'  !! Step \"{step[\"name\"]}\" failed: {r.stderr}')\n                        return False\n        print(f'[{self.name}] Complete.')\n        return True\n\ndef main():\n    wf = Workflow('{name}')\n    wf.add_step('build', 'echo \"building...\"')\n    wf.add_step('test', 'echo \"testing {build}\"', depends_on=['build'])\n    wf.add_step('deploy', 'echo \"deploying...\"', depends_on=['test'])\n    wf.run()\n\nif __name__ == '__main__':\n    main()",
            "README.md": "# {name} - Workflow Engine\n\nA workflow/DAG automation engine.\n\n```\npython engine.py\n```",
        },
        "description": "Workflow/DAG automation engine"
    },
    "audio": {
        "files": {
            "audio.py": "#!/usr/bin/env python3\n\"\"\"{name} - Audio engine.\"\"\"\nimport math\nimport struct\nimport wave\n\nSAMPLE_RATE = 44100\n\ndef note_freq(note):\n    return 440 * (2 ** ((note - 69) / 12))\n\ndef sine_wave(freq, duration, amp=0.5):\n    n = int(SAMPLE_RATE * duration)\n    return [int(amp * 32767 * math.sin(2 * math.pi * freq * t / SAMPLE_RATE)) for t in range(n)]\n\ndef square_wave(freq, duration, amp=0.5):\n    n = int(SAMPLE_RATE * duration)\n    return [int(amp * 32767 * (1 if math.sin(2 * math.pi * freq * t / SAMPLE_RATE) >= 0 else -1)) for t in range(n)]\n\ndef saw_wave(freq, duration, amp=0.5):\n    n = int(SAMPLE_RATE * duration)\n    return [int(amp * 32767 * (2 * ((freq * t / SAMPLE_RATE) % 1) - 1)) for t in range(n)]\n\ndef mix(*tracks):\n    length = max(len(t) for t in tracks)\n    result = []\n    for i in range(length):\n        s = sum(t[i] for t in tracks if i < len(t))\n        result.append(max(-32768, min(32767, s)))\n    return result\n\ndef save_wav(filename, samples):\n    with wave.open(filename, 'w') as w:\n        w.setnchannels(1)\n        w.setsampwidth(2)\n        w.setframerate(SAMPLE_RATE)\n        w.writeframes(struct.pack('<' + 'h' * len(samples), *samples))\n\ndef main():\n    c = note_freq(60); e = note_freq(64); g = note_freq(67)\n    melody = []\n    for freq in [c, e, g, e, c, e, g, e]:\n        melody.extend(sine_wave(freq, 0.2))\n    save_wav('output.wav', melody)\n    print(f'{len(melody) / SAMPLE_RATE:.1f}s audio saved to output.wav')\n\nif __name__ == '__main__':\n    main()",
            "README.md": "# {name} - Audio Engine\n\nA synthesized audio engine - generate WAV files with waveforms.\n\n```\npython audio.py\n```\n\nSupports sine, square, and saw waves.",
        },
        "description": "Audio synthesis engine (WAV)"
    },
    "sprite": {
        "files": {
            "sprite.py": "#!/usr/bin/env python3\n\"\"\"{name} - Sprite animation engine.\"\"\"\nimport time\nimport os\n\nclass Sprite:\n    def __init__(self, frames):\n        self.frames = frames\n        self.current = 0\n    def next(self):\n        self.current = (self.current + 1) % len(self.frames)\n        return self.frames[self.current]\n    def reset(self): self.current = 0\n\nclass Animation:\n    def __init__(self, sprite, interval=0.3):\n        self.sprite = sprite\n        self.interval = interval\n        self.last = 0\n    def get_frame(self):\n        now = time.time()\n        if now - self.last > self.interval:\n            self.sprite.next()\n            self.last = now\n        return self.sprite.frames[self.sprite.current]\n\nclass Animator:\n    def __init__(self):\n        self.animations = {}\n        self.current = None\n    def add(self, name, animation):\n        self.animations[name] = animation\n        if not self.current: self.current = name\n    def play(self, name): self.current = name\n    def get_frame(self):\n        if self.current and self.current in self.animations:\n            return self.animations[self.current].get_frame()\n        return ''\n\ndef make_pointer_frames():\n    return [\n        '  *  \\n *** \\n*****\\n *** \\n  *  ',\n        ' *** \\n*****\\n *** \\n  *  \\n     ',\n        '*****\\n *** \\n  *  \\n     \\n     ',\n    ]\n\ndef make_walk_frames():\n    return [\n        ' O \\n/|\\\\\\n/ \\\\',\n        ' O \\n/|\\\\\\n \\\\',\n        ' O \\n/|\\\\\\n/ \\\\',\n        ' O \\n/|\\\\\\n/ \\\\',\n    ]\n\ndef main():\n    animator = Animator()\n    animator.add('pointer', Animation(Sprite(make_pointer_frames()), 0.3))\n    animator.add('walk', Animation(Sprite(make_walk_frames()), 0.5))\n    print('Sprite engine ready! Frames: pointer, walk')\n\nif __name__ == '__main__':\n    main()",
            "README.md": "# {name} - Sprite Engine\n\nA sprite animation engine with frame-based animations.\n\n```\npython sprite.py\n```",
        },
        "description": "Sprite animation engine"
    },
    "tilemap": {
        "files": {
            "tilemap.py": "#!/usr/bin/env python3\n\"\"\"{name} - Tilemap engine.\"\"\"\nimport json\nfrom pathlib import Path\n\nclass TileMap:\n    TILES = {\n        '.': 'floor', '#': 'wall', 'W': 'water', 'T': 'tree',\n        'D': 'door', 'S': 'stairs', 'P': 'player', 'E': 'enemy',\n    }\n    CHARS = {v: k for k, v in TILES.items()}\n\n    def __init__(self, w=16, h=12):\n        self.w, self.h = w, h\n        self.data = [['.'] * w for _ in range(h)]\n        self.properties = {}\n\n    def from_string(self, s):\n        lines = s.strip().split('\\n')\n        self.h = len(lines)\n        self.w = max(len(l) for l in lines)\n        self.data = [list(l.ljust(self.w)) for l in lines]\n\n    def to_string(self):\n        return '\\n'.join(''.join(row) for row in self.data)\n\n    def set(self, x, y, tile):\n        if 0 <= x < self.w and 0 <= y < self.h:\n            self.data[y][x] = tile\n\n    def get(self, x, y):\n        if 0 <= x < self.w and 0 <= y < self.h:\n            return self.data[y][x]\n        return None\n\n    def find_all(self, tile):\n        return [(x, y) for y in range(self.h) for x in range(self.w) if self.data[y][x] == tile]\n\n    def save(self, path):\n        Path(path).write_text(self.to_string())\n\n    @staticmethod\n    def load(path):\n        t = TileMap()\n        t.from_string(Path(path).read_text())\n        return t\n\n    def render(self):\n        return self.to_string()\n\ndef main():\n    tm = TileMap()\n    tm.from_string('''\\\n################\n#..............#\n#..T....T......#\n#..............#\n#....P.........#\n#......WW......#\n#......WW......#\n#..............#\n#..............#\n#..T.......T...#\n#..............#\n################''')\n    print(tm.render())\n    print(f'\\nPlayer at: {tm.find_all(\"P\")}')\n    print(f'Trees at: {tm.find_all(\"T\")}')\n\nif __name__ == '__main__':\n    main()",
            "README.md": "# {name} - Tilemap Engine\n\nA tilemap engine for 2D grid-based games.\n\n```\npython tilemap.py\n```",
        },
        "description": "2D tilemap engine"
    },
}

_PROJECT_TYPES = list(_PROJECT_TEMPLATES.keys())


def generate_project(project_type: str, name: str, path: str = None) -> dict:
    """Generate a project from template."""
    ptype = project_type.lower().strip()
    if ptype not in _PROJECT_TEMPLATES:
        types = ", ".join(_PROJECT_TEMPLATES.keys())
        return {"success": False, "error": f"Unknown type '{ptype}'. Available: {types}"}

    template = _PROJECT_TEMPLATES[ptype]
    target = Path(path or ".").resolve() / name

    if target.exists():
        return {"success": False, "error": f"Already exists: {target}"}

    created_files = []
    try:
        target.mkdir(parents=True, exist_ok=False)
        for filename, content in template["files"].items():
            filepath = target / filename.replace("{name}", name)
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(content.replace("{name}", name), encoding="utf-8")
            created_files.append(str(filepath))
        return {
            "success": True,
            "type": ptype,
            "name": name,
            "path": str(target),
            "files": created_files,
            "description": template["description"]
        }
    except FileExistsError:
        return {"success": False, "error": f"Already exists: {target}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── UTILITIES ────────────────────────────────────────────────────────────────

_http_server = None
_http_thread = None
_tunnel_proc = None
_tunnel_url = None
_tunnel_provider = None


def _network_ip() -> str:
    """Best-effort LAN IP for browsing from other devices."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"


def stop_http_server() -> dict:
    """Stop the background trajectory/memory graph server and any public tunnel."""
    global _http_server, _http_thread
    stop_web_tunnel()
    if _http_server:
        _http_server.shutdown()
        _http_server = None
        _http_thread = None
        return {"success": True}
    return {"success": False, "error": "Not running"}


def start_http_server(port: int = 8000, path: str = ".", host: str = "0.0.0.0") -> dict:
    """Start trajectory & memory graph server (0.0.0.0 = LAN/online browseable)."""
    import http.server
    import socketserver
    import threading

    global _http_server, _http_thread
    bind = host or "0.0.0.0"
    lan_ip = _network_ip()
    if _http_server:
        urls = _server_urls(port, bind, lan_ip)
        return {"success": False, "error": "Already running", **urls}

    web_dir = Path.home() / ".aira" / "web"
    web_dir.mkdir(parents=True, exist_ok=True)
    html_file = web_dir / "index.html"
    
    dashboard_html = """<!DOCTYPE html>
<html>
<head>
    <title>AIRA Brain Visualizer</title>
    <meta charset="utf-8">
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {
            background-color: #0a0f14;
            color: #00ff41;
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
        }
        h1, h2 {
            color: #ffd700;
            border-bottom: 1px solid #00ff41;
            padding-bottom: 10px;
        }
        .container {
            display: flex;
            gap: 20px;
        }
        #graph {
            flex: 2;
            height: 600px;
            border: 1px solid #00ff41;
            background-color: #070a0e;
        }
        .sidebar {
            flex: 1;
            border: 1px solid #00ff41;
            padding: 15px;
            background-color: #070a0e;
            height: 570px;
            overflow-y: auto;
        }
        .node {
            stroke: #0a0f14;
            stroke-width: 1.5px;
            cursor: pointer;
        }
        .link {
            stroke: #00ff41;
            stroke-opacity: 0.4;
            stroke-width: 1.5px;
        }
        text {
            fill: #00ff41;
            font-size: 10px;
            pointer-events: none;
        }
        .session-item {
            margin-bottom: 10px;
            padding-bottom: 5px;
            border-bottom: 1px dashed #4a8a4a;
        }
        .badge {
            background-color: #ffd700;
            color: #0a0f14;
            padding: 2px 5px;
            font-weight: bold;
            font-size: 10px;
            border-radius: 3px;
        }
    </style>
</head>
<body>
    <h1>⚡ A.I.R.A. v2 // BRAIN DIAGNOSTICS & GRAPH</h1>
    <div class="container">
        <div id="graph"></div>
        <div class="sidebar">
            <h2>🧠 Memory Context Info</h2>
            <div id="info">Hover over a memory node to see details.</div>
            
            <h2>📋 Recent Sessions</h2>
            <div id="sessions">Loading sessions...</div>
        </div>
    </div>

    <script>
        fetch('/api/data')
            .then(res => res.json())
            .then(data => {
                renderGraph(data);
                renderSidebar(data);
            });

        function renderGraph(data) {
            const width = document.getElementById('graph').clientWidth;
            const height = document.getElementById('graph').clientHeight;

            const svg = d3.select("#graph")
                .append("svg")
                .attr("width", width)
                .attr("height", height);

            const simulation = d3.forceSimulation(data.nodes)
                .force("link", d3.forceLink(data.links).id(d => d.id).distance(100))
                .force("charge", d3.forceManyBody().strength(-150))
                .force("center", d3.forceCenter(width / 2, height / 2));

            const link = svg.append("g")
                .selectAll("line")
                .data(data.links)
                .join("line")
                .attr("class", "link");

            const node = svg.append("g")
                .selectAll("circle")
                .data(data.nodes)
                .join("circle")
                .attr("class", "node")
                .attr("r", d => 8 + (d.priority || 1) * 2)
                .attr("fill", d => d.priority === 3 ? "#ff3333" : d.priority === 2 ? "#ffd700" : "#00ff41")
                .on("mouseover", (event, d) => {
                    document.getElementById('info').innerHTML = `
                        <strong>ID:</strong> #${d.id}<br>
                        <strong>Project:</strong> ${d.project}<br>
                        <strong>Priority:</strong> ${d.priority}<br><br>
                        <strong>Memory Content:</strong><br>
                        ${d.text}
                    `;
                })
                .call(d3.drag()
                    .on("start", dragstarted)
                    .on("drag", dragged)
                    .on("end", dragended));

            const text = svg.append("g")
                .selectAll("text")
                .data(data.nodes)
                .join("text")
                .text(d => d.text.substring(0, 20) + '...')
                .attr("dx", 12)
                .attr("dy", 4);

            simulation.on("tick", () => {
                link
                    .attr("x1", d => d.source.x)
                    .attr("y1", d => d.source.y)
                    .attr("x2", d => d.target.x)
                    .attr("y2", d => d.target.y);

                node
                    .attr("cx", d => d.x)
                    .attr("cy", d => d.y);

                text
                    .attr("x", d => d.x)
                    .attr("y", d => d.y);
            });

            function dragstarted(event, d) {
                if (!event.active) simulation.alphaTarget(0.3).restart();
                d.fx = d.x;
                d.fy = d.y;
            }

            function dragged(event, d) {
                d.fx = event.x;
                d.fy = event.y;
            }

            function dragended(event, d) {
                if (!event.active) simulation.alphaTarget(0);
                d.fx = null;
                d.fy = null;
            }
        }

        function renderSidebar(data) {
            const container = document.getElementById('sessions');
            if (!data.sessions || data.sessions.length === 0) {
                container.innerHTML = "No recent sessions.";
                return;
            }
            container.innerHTML = data.sessions.map(s => `
                <div class="session-item">
                    <strong>Session #${s.session_id || s.id}</strong><br>
                    Project: <span class="badge">${s.project}</span><br>
                    Started: ${s.start_time || s.started || 'N/A'}<br>
                    Messages: ${s.messages || s.message_count || 0}
                </div>
            `).join('');
        }
    </script>
</body>
</html>
"""
    try:
        html_file.write_text(dashboard_html, encoding="utf-8")
    except Exception:
        pass

    serve_root = str(web_dir.resolve())

    class _Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=serve_root, **kwargs)

        def log_message(self, format, *args):
            pass

        def end_headers(self):
            self.send_header("Access-Control-Allow-Origin", "*")
            super().end_headers()

        def do_GET(self):
            if self.path.rstrip("/") == "/api/data":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()

                from aira.memory import get_all_memories, get_recent_sessions, list_projects, get_linked_memories
                try:
                    mems = get_all_memories(limit=100)
                    sessions = get_recent_sessions(limit=10)
                    projects = list_projects()
                except Exception:
                    mems = []
                    sessions = []
                    projects = []

                nodes = []
                links = []
                mem_map = {}
                for m in mems:
                    mem_map[m["id"]] = True
                    nodes.append({
                        "id": m["id"],
                        "text": m.get("content", ""),
                        "project": m.get("project", "default"),
                        "priority": m.get("priority", 1),
                        "group": "memory",
                    })

                for p in projects:
                    pid = f"proj_{p['name']}"
                    nodes.append({
                        "id": pid,
                        "text": p.get("description", p["name"])[:40],
                        "project": p["name"],
                        "priority": 2 if p.get("active") else 1,
                        "group": "project",
                    })

                for m in mems:
                    try:
                        linked = get_linked_memories(m["id"])
                        for link in linked:
                            target_id = link["id"] if isinstance(link, dict) else link
                            if target_id in mem_map:
                                links.append({"source": m["id"], "target": target_id})
                    except Exception:
                        pass

                for s in sessions:
                    sid = f"session_{s['id']}"
                    nodes.append({
                        "id": sid,
                        "text": (s.get("summary") or "Session")[:40],
                        "project": s.get("project", "AIRA"),
                        "priority": 1,
                        "group": "session",
                    })

                data = {
                    "nodes": nodes,
                    "links": links,
                    "sessions": sessions,
                    "projects": projects,
                }
                self.wfile.write(json.dumps(data, indent=2).encode("utf-8"))
                return

            if self.path in ("/", "/index.html"):
                self.path = "/index.html"
            super().do_GET()

    class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
        allow_reuse_address = True
        daemon_threads = True

    try:
        httpd = ThreadedTCPServer((bind, port), _Handler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        _http_server = httpd
        _http_thread = thread
        urls = _server_urls(port, bind, lan_ip)
        return {
            "success": True,
            "port": port,
            "host": bind,
            "path": str(web_dir),
            "network_accessible": bind == "0.0.0.0",
            **urls,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def _server_urls(port: int, bind: str, lan_ip: str) -> dict:
    local = f"http://127.0.0.1:{port}"
    network = f"http://{lan_ip}:{port}" if bind == "0.0.0.0" else local
    return {
        "url": local,
        "local_url": local,
        "network_url": network,
        "lan_ip": lan_ip,
    }


def list_tunnel_providers() -> list:
    """Tunnel backends available on this machine."""
    import shutil
    found = []
    if shutil.which("cloudflared"):
        found.append("cloudflared")
    if shutil.which("ngrok"):
        found.append("ngrok")
    if shutil.which("npx") or shutil.which("npx.cmd"):
        found.append("localtunnel")
    return found


def stop_web_tunnel() -> dict:
    """Stop an active public internet tunnel."""
    global _tunnel_proc, _tunnel_url, _tunnel_provider
    if _tunnel_proc and _tunnel_proc.poll() is None:
        try:
            _tunnel_proc.terminate()
            _tunnel_proc.wait(timeout=5)
        except Exception:
            try:
                _tunnel_proc.kill()
            except Exception:
                pass
    _tunnel_proc = None
    url = _tunnel_url
    prov = _tunnel_provider
    _tunnel_url = None
    _tunnel_provider = None
    if url:
        return {"success": True, "url": url, "provider": prov}
    return {"success": False, "error": "No tunnel running"}


def _read_tunnel_url_from_stream(proc, timeout: float = 45, patterns: list = None) -> str:
    """Block until a public HTTPS URL appears in tunnel process output."""
    import re
    import time

    patterns = patterns or [
        r"https://[a-z0-9-]+\.trycloudflare\.com",
        r"https://[a-z0-9-]+\.ngrok-free\.app",
        r"https://[a-z0-9-]+\.ngrok\.io",
        r"https://[a-z0-9-]+\.loca\.lt",
        r"https://[^\s\"']+",
    ]
    compiled = [re.compile(p, re.I) for p in patterns]
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            break
        for stream in (proc.stderr, proc.stdout):
            if not stream:
                continue
            try:
                line = stream.readline()
            except Exception:
                line = ""
            if not line:
                continue
            for rx in compiled:
                m = rx.search(line)
                if m:
                    url = (m.group(1) if m.lastindex else m.group(0)).rstrip(").,;")
                    if url.startswith("https://"):
                        return url
        time.sleep(0.15)
    return ""


def _start_cloudflared_tunnel(port: int) -> dict:
    import shutil
    import subprocess

    exe = shutil.which("cloudflared")
    if not exe:
        return {"success": False, "error": "cloudflared not installed"}
    proc = subprocess.Popen(
        [exe, "tunnel", "--url", f"http://127.0.0.1:{port}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    url = _read_tunnel_url_from_stream(
        proc, patterns=[r"https://[a-z0-9-]+\.trycloudflare\.com"]
    )
    if url:
        return {"success": True, "url": url, "provider": "cloudflared", "proc": proc}
    proc.terminate()
    return {"success": False, "error": "cloudflared started but no public URL detected"}


def _start_ngrok_tunnel(port: int) -> dict:
    import shutil
    import subprocess
    import time

    exe = shutil.which("ngrok")
    if not exe:
        return {"success": False, "error": "ngrok not installed"}
    proc = subprocess.Popen(
        [exe, "http", str(port), "--log=stdout"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    url = ""
    for _ in range(40):
        if proc.poll() is not None:
            break
        try:
            import requests
            r = requests.get("http://127.0.0.1:4040/api/tunnels", timeout=2)
            for t in r.json().get("tunnels", []):
                public = t.get("public_url", "")
                if public.startswith("https://"):
                    url = public
                    break
        except Exception:
            pass
        if url:
            break
        time.sleep(1)
    if not url:
        url = _read_tunnel_url_from_stream(
            proc, timeout=10, patterns=[r"https://[a-z0-9-]+\.ngrok[^\s\"']*"]
        )
    if url:
        return {"success": True, "url": url, "provider": "ngrok", "proc": proc}
    proc.terminate()
    return {"success": False, "error": "ngrok started but no public URL detected"}


def _start_localtunnel(port: int) -> dict:
    import shutil
    import subprocess

    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if not npx:
        return {"success": False, "error": "npx not installed (Node.js required)"}
    proc = subprocess.Popen(
        [npx, "--yes", "localtunnel", "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    url = _read_tunnel_url_from_stream(
        proc, patterns=[r"your url is:\s*(https://[^\s]+)", r"https://[a-z0-9-]+\.loca\.lt"]
    )
    if url:
        return {"success": True, "url": url, "provider": "localtunnel", "proc": proc}
    proc.terminate()
    return {"success": False, "error": "localtunnel started but no public URL detected"}


def start_web_tunnel(port: int = 8000, provider: str = "auto") -> dict:
    """
    Expose the local web server on the public internet via a tunnel.
    Tries cloudflared, ngrok, then localtunnel when provider=auto.
    """
    global _tunnel_proc, _tunnel_url, _tunnel_provider

    if _tunnel_proc and _tunnel_proc.poll() is None and _tunnel_url:
        return {"success": True, "url": _tunnel_url, "provider": _tunnel_provider}

    starters = {
        "cloudflared": _start_cloudflared_tunnel,
        "ngrok": _start_ngrok_tunnel,
        "localtunnel": _start_localtunnel,
    }
    order = list_tunnel_providers() if provider == "auto" else [provider]
    if provider != "auto" and provider not in starters:
        return {"success": False, "error": f"Unknown tunnel provider: {provider}"}

    errors = []
    for name in order:
        fn = starters.get(name)
        if not fn:
            continue
        result = fn(port)
        if result.get("success"):
            _tunnel_proc = result.pop("proc")
            _tunnel_url = result["url"]
            _tunnel_provider = result["provider"]
            return result
        errors.append(f"{name}: {result.get('error', 'failed')}")

    hint = (
        "Install one tunnel tool:\n"
        "  cloudflared — https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/\n"
        "  ngrok       — https://ngrok.com/download\n"
        "  localtunnel — npm install -g localtunnel  (or use npx)"
    )
    return {
        "success": False,
        "error": "; ".join(errors) if errors else "No tunnel providers available",
        "hint": hint,
        "providers": list_tunnel_providers(),
    }


def search_files(pattern: str, path: str = ".", max_results: int = 20) -> list:
    """Search file contents recursively."""
    results = []
    root = Path(path).resolve()
    try:
        for item in root.rglob("*"):
            if not item.is_file():
                continue
            ext = item.suffix.lower()
            if ext in (".exe", ".dll", ".pyc", ".bin", ".jpg", ".png", ".gif", ".zip", ".7z"):
                continue
            try:
                content = item.read_text(encoding="utf-8", errors="replace")
                if pattern.lower() in content.lower():
                    lines = content.split("\n")
                    for i, line in enumerate(lines):
                        if pattern.lower() in line.lower():
                            results.append({
                                "file": str(item.relative_to(root)),
                                "line": i + 1,
                                "match": line.strip()[:120]
                            })
                            if len(results) >= max_results:
                                return results
            except (PermissionError, OSError, UnicodeDecodeError):
                pass
    except (PermissionError, OSError):
        pass
    return results


def list_processes(sort_by: str = "cpu") -> list:
    """List running processes."""
    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            procs.append({
                "pid": p.info["pid"],
                "name": (p.info["name"] or "?")[:30],
                "cpu": round(p.info.get("cpu_percent", 0) or 0, 1),
                "mem": round(p.info.get("memory_percent", 0) or 0, 1),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    reverse = True
    if sort_by == "name":
        key = lambda x: x["name"].lower()
        reverse = False
    elif sort_by == "pid":
        key = lambda x: x["pid"]
        reverse = False
    elif sort_by == "mem":
        key = lambda x: x["mem"]
    else:
        key = lambda x: x["cpu"]

    procs.sort(key=key, reverse=reverse)
    return procs[:30]


def calculate(expression: str) -> dict:
    """Safe math calculation."""
    allowed = set("0123456789+-*/.()% pi e sqrt sin cos tan log abs floor ceil ")
    expr = expression.lower().strip()
    import math
    safe = {"__builtins__": {}, "math": math, "pi": math.pi, "e": math.e,
            "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan,
            "log": math.log, "abs": abs, "floor": math.floor, "ceil": math.ceil}
    try:
        result = eval(expr, safe)
        return {"success": True, "expression": expression, "result": result}
    except Exception as e:
        return {"success": False, "expression": expression, "error": str(e)}


def generate_password(length: int = 16) -> str:
    """Generate a secure random password."""
    import secrets
    import string
    chars = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    return "".join(secrets.choice(chars) for _ in range(length))


def format_json(data: str) -> dict:
    """Format and validate JSON string."""
    try:
        parsed = json.loads(data)
        formatted = json.dumps(parsed, indent=2)
        return {"success": True, "formatted": formatted}
    except json.JSONDecodeError as e:
        return {"success": False, "error": str(e)}


# ── SCHEDULING ───────────────────────────────────────────────────────────────

# ── TASK SCHEDULING ENGINE ─────────────────────────────────────────────────────

_scheduled_tasks: list = []
_scheduler_thread: Optional[threading.Thread] = None
_scheduler_running = False

SCHEDULE_FILE = Path.home() / ".aira" / "schedules.json"
SCHEDULER_LOG = Path.home() / ".aira" / "scheduler.log"

def _log_scheduler(msg: str):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(SCHEDULER_LOG, "a") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass

def save_schedule(cron: str, task: str, enabled: bool = True):
    schedules = load_schedules()
    schedules.append({
        "id": len(schedules) + 1,
        "cron": cron,
        "task": task,
        "enabled": enabled,
        "created": datetime.datetime.now().isoformat(),
        "last_run": None,
        "run_count": 0,
    })
    SCHEDULE_FILE.parent.mkdir(exist_ok=True)
    with open(SCHEDULE_FILE, 'w') as f:
        json.dump(schedules, f, indent=2)
    _restart_scheduler()
    return schedules[-1]["id"]


def load_schedules() -> list:
    if not SCHEDULE_FILE.exists():
        return []
    try:
        with open(SCHEDULE_FILE) as f:
            return json.load(f)
    except Exception:
        return []


def delete_schedule(schedule_id: int) -> bool:
    schedules = load_schedules()
    new_schedules = [s for s in schedules if s.get("id") != schedule_id]
    if len(new_schedules) == len(schedules):
        return False
    with open(SCHEDULE_FILE, 'w') as f:
        json.dump(new_schedules, f, indent=2)
    _restart_scheduler()
    return True


def toggle_schedule(schedule_id: int, enabled: bool = None) -> bool:
    schedules = load_schedules()
    for s in schedules:
        if s.get("id") == schedule_id:
            if enabled is not None:
                s["enabled"] = enabled
            else:
                s["enabled"] = not s.get("enabled", True)
            with open(SCHEDULE_FILE, 'w') as f:
                json.dump(schedules, f, indent=2)
            _restart_scheduler()
            return s["enabled"]
    return False


def _execute_scheduled_task(task: str):
    """Execute a scheduled task command."""
    _log_scheduler(f"Running: {task}")
    try:
        result = subprocess.run(task, shell=True, capture_output=True, text=True, timeout=120)
        status = "OK" if result.returncode == 0 else f"FAIL(rc={result.returncode})"
        _log_scheduler(f"  {status}: {result.stdout[:200]}{result.stderr[:200]}")
    except subprocess.TimeoutExpired:
        _log_scheduler(f"  TIMEOUT: {task}")
    except Exception as e:
        _log_scheduler(f"  ERROR: {e}")

    # Update schedule's last_run and run_count
    schedules = load_schedules()
    for s in schedules:
        if s.get("task") == task:
            s["last_run"] = datetime.datetime.now().isoformat()
            s["run_count"] = s.get("run_count", 0) + 1
            break
    with open(SCHEDULE_FILE, 'w') as f:
        json.dump(schedules, f, indent=2)


def _restart_scheduler():
    """Stop and restart the background scheduler to pick up changes."""
    global _scheduler_running
    _scheduler_running = False
    if _scheduler_thread and _scheduler_thread.is_alive():
        _scheduler_thread.join(timeout=2)
    _start_scheduler()


def _run_scheduler_loop():
    """Background loop that checks cron expressions and runs tasks."""
    global _scheduler_running
    _scheduler_running = True
    _log_scheduler("Scheduler started")

    try:
        from apscheduler.triggers.cron import CronTrigger
        HAS_APSCHEDULER = True
    except ImportError:
        HAS_APSCHEDULER = False
        _log_scheduler("APScheduler not installed, using simple timer")

    while _scheduler_running:
        try:
            now = datetime.datetime.now()
            schedules = load_schedules()
            for s in schedules:
                if not s.get("enabled", True):
                    continue
                cron_expr = s.get("cron", "")
                task = s.get("task", "")
                last_run = s.get("last_run")
                # If never run or last run was more than 1 minute ago
                if not last_run or (datetime.datetime.fromisoformat(last_run) < now - datetime.timedelta(minutes=1)):
                    if HAS_APSCHEDULER:
                        try:
                            trigger = CronTrigger.from_crontab(cron_expr)
                            next_time = trigger.get_next_fire_time(None, now)
                            if next_time and abs((next_time - now).total_seconds()) < 90:
                                _execute_scheduled_task(task)
                        except Exception:
                            _log_scheduler(f"Invalid cron: {cron_expr}")
                    else:
                        # Simple interval fallback: run if cron matches roughly
                        _execute_scheduled_task(task)
            for _ in range(30):
                if not _scheduler_running:
                    break
                time.sleep(2)
        except Exception as e:
            _log_scheduler(f"Scheduler error: {e}")
            time.sleep(30)
    _log_scheduler("Scheduler stopped")


def _start_scheduler():
    """Start the background scheduler daemon thread."""
    global _scheduler_thread, _scheduler_running
    if _scheduler_thread and _scheduler_thread.is_alive():
        return
    _scheduler_running = True
    _scheduler_thread = threading.Thread(target=_run_scheduler_loop, daemon=True, name="aira-scheduler")
    _scheduler_thread.start()


def init_scheduler():
    """Initialize and start the scheduler on AIRA startup."""
    _start_scheduler()


def get_scheduler_log(n: int = 20) -> list:
    """Return last N lines from scheduler log."""
    if not SCHEDULER_LOG.exists():
        return []
    try:
        lines = SCHEDULER_LOG.read_text().strip().splitlines()
        return lines[-n:]
    except Exception:
        return []


# ── SNAPSHOT / ROLLBACK ──────────────────────────────────────────────────────

SNAPSHOT_DIR = Path.home() / ".aira" / "snapshots"


def create_snapshot(path: str = ".", label: str = "") -> dict:
    """Snapshot a directory before destructive operations."""
    import zipfile
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_label = re.sub(r'[^a-zA-Z0-9_-]', '_', label)[:30] if label else "auto"
    snap_name = f"snap_{ts}_{safe_label}.zip"
    snap_path = SNAPSHOT_DIR / snap_name
    base = Path(path).resolve()
    if not base.is_dir():
        return {"success": False, "error": f"Not a directory: {path}"}
    count = 0
    with zipfile.ZipFile(snap_path, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in base.rglob("*"):
            if f.is_file() and f.stat().st_size < 50 * 1024 * 1024:
                z.write(f, f.relative_to(base))
                count += 1
    return {
        "success": True,
        "snapshot_id": snap_name.replace(".zip", ""),
        "path": str(snap_path),
        "size": snap_path.stat().st_size,
        "files": count,
        "label": safe_label,
    }


def list_snapshots() -> list:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    snaps = []
    for f in sorted(SNAPSHOT_DIR.glob("*.zip"), reverse=True):
        size = f.stat().st_size
        parts = f.stem.split("_", 3)
        ts = parts[1] if len(parts) > 1 else "?"
        label = parts[3] if len(parts) > 3 else "auto"
        snaps.append({
            "id": f.stem,
            "time": ts[:4] + "-" + ts[4:6] + "-" + ts[6:8] + " " + ts[8:10] + ":" + ts[10:12] if len(ts) >= 12 else ts,
            "size": size,
            "label": label,
        })
    return snaps


def restore_snapshot(snapshot_id: str, target: str = ".") -> dict:
    """Restore a snapshot to the target directory."""
    import zipfile
    snap_path = SNAPSHOT_DIR / f"{snapshot_id}.zip"
    if not snap_path.exists():
        return {"success": False, "error": f"Snapshot not found: {snapshot_id}"}
    try:
        with zipfile.ZipFile(snap_path, 'r') as z:
            z.extractall(target)
        return {"success": True, "path": str(Path(target).resolve()), "files": len(z.namelist())}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── CREDENTIAL VAULT ─────────────────────────────────────────────────────────

VAULT_FILE = Path.home() / ".aira" / "vault.json"

def _vault_key() -> bytes:
    """Derive a simple XOR key from machine ID for basic obfuscation."""
    import hashlib
    try:
        mid = subprocess.run(["wmic", "csproduct", "get", "uuid"], capture_output=True, text=True, timeout=5).stdout
    except Exception:
        mid = os.environ.get("COMPUTERNAME", "aira-default")
    return hashlib.sha256(mid.encode()).digest()

def _xor_obfuscate(data: bytes, key: bytes) -> bytes:
    return bytes(a ^ b for a, b in zip(data, key * (len(data) // len(key) + 1)))[:len(data)]


def vault_set(service: str, value: str) -> bool:
    """Store a credential in the encrypted vault."""
    VAULT_FILE.parent.mkdir(parents=True, exist_ok=True)
    vault = {}
    if VAULT_FILE.exists():
        try:
            encrypted = VAULT_FILE.read_bytes()
            decrypted = _xor_obfuscate(encrypted, _vault_key())
            vault = json.loads(decrypted)
        except Exception:
            vault = {}
    vault[service] = value
    try:
        data = json.dumps(vault).encode()
        encrypted = _xor_obfuscate(data, _vault_key())
        VAULT_FILE.write_bytes(encrypted)
        return True
    except Exception:
        return False


def vault_get(service: str) -> str:
    """Retrieve a credential from the encrypted vault."""
    if not VAULT_FILE.exists():
        return ""
    try:
        encrypted = VAULT_FILE.read_bytes()
        decrypted = _xor_obfuscate(encrypted, _vault_key())
        vault = json.loads(decrypted)
        return vault.get(service, "")
    except Exception:
        return ""


def vault_list() -> list:
    """List stored service names."""
    if not VAULT_FILE.exists():
        return []
    try:
        encrypted = VAULT_FILE.read_bytes()
        decrypted = _xor_obfuscate(encrypted, _vault_key())
        vault = json.loads(decrypted)
        return list(vault.keys())
    except Exception:
        return []

def vault_delete(service: str) -> bool:
    """Delete a credential from the vault."""
    if not VAULT_FILE.exists():
        return False
    try:
        encrypted = VAULT_FILE.read_bytes()
        decrypted = _xor_obfuscate(encrypted, _vault_key())
        vault = json.loads(decrypted)
        if service in vault:
            del vault[service]
            data = json.dumps(vault).encode()
            VAULT_FILE.write_bytes(_xor_obfuscate(data, _vault_key()))
            return True
    except Exception:
        pass
    return False


# ── GITHUB HELPERS ───────────────────────────────────────────────────────────

def gh_check() -> bool:
    """Check if gh CLI is installed."""
    try:
        r = subprocess.run(["gh", "--version"], capture_output=True, text=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


def gh_run(args: list) -> dict:
    """Run a gh CLI command."""
    try:
        r = subprocess.run(["gh"] + args, capture_output=True, text=True, timeout=60)
        return {
            "success": r.returncode == 0,
            "stdout": r.stdout.strip()[:2000],
            "stderr": r.stderr.strip()[:500],
            "returncode": r.returncode,
        }
    except Exception as e:
        return {"success": False, "error": str(e), "stdout": "", "stderr": str(e), "returncode": -1}


# ── DOCKER HELPERS ───────────────────────────────────────────────────────────

def docker_check() -> bool:
    try:
        r = subprocess.run(["docker", "--version"], capture_output=True, text=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


def docker_run(args: list) -> dict:
    try:
        r = subprocess.run(["docker"] + args, capture_output=True, text=True, timeout=120)
        return {
            "success": r.returncode == 0,
            "stdout": r.stdout.strip()[:3000],
            "stderr": r.stderr.strip()[:500],
            "returncode": r.returncode,
        }
    except Exception as e:
        return {"success": False, "error": str(e), "stdout": "", "stderr": str(e), "returncode": -1}


def docker_ps() -> list:
    r = docker_run(["ps", "--format", "{{.ID}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}\t{{.Names}}"])
    if not r["success"]:
        return []
    rows = []
    for line in r["stdout"].splitlines():
        parts = line.split("\t")
        if len(parts) >= 5:
            rows.append({"id": parts[0][:12], "image": parts[1], "status": parts[2], "ports": parts[3], "name": parts[4]})
    return rows


# ── CLOUD PROVIDER HOOKS ────────────────────────────────────────────────────

def cloud_aws(args: list) -> dict:
    """Run AWS CLI command."""
    try:
        r = subprocess.run(["aws"] + args, capture_output=True, text=True, timeout=60)
        return {"success": r.returncode == 0, "stdout": r.stdout.strip()[:3000], "stderr": r.stderr.strip()[:500]}
    except FileNotFoundError:
        return {"success": False, "error": "AWS CLI not installed. Run: pip install awscli"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def cloud_gcp(args: list) -> dict:
    """Run GCP gcloud CLI command."""
    try:
        r = subprocess.run(["gcloud"] + args, capture_output=True, text=True, timeout=60)
        return {"success": r.returncode == 0, "stdout": r.stdout.strip()[:3000], "stderr": r.stderr.strip()[:500]}
    except FileNotFoundError:
        return {"success": False, "error": "gcloud CLI not found. Install from https://cloud.google.com/sdk"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def cloud_azure(args: list) -> dict:
    """Run Azure CLI command."""
    try:
        r = subprocess.run(["az"] + args, capture_output=True, text=True, timeout=60)
        return {"success": r.returncode == 0, "stdout": r.stdout.strip()[:3000], "stderr": r.stderr.strip()[:500]}
    except FileNotFoundError:
        return {"success": False, "error": "Azure CLI not found. Install from https://docs.microsoft.com/cli/azure"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── TEST RUNNER ─────────────────────────────────────────────────────────────

def discover_tests(path: str = ".") -> list:
    """Discover pytest test files in a directory."""
    tests = []
    for f in Path(path).rglob("test_*.py"):
        tests.append(str(f))
    for f in Path(path).rglob("*_test.py"):
        tests.append(str(f))
    return sorted(tests)


def run_pytest(path: str = ".", test_names: list = None) -> dict:
    """Run pytest and return results."""
    import subprocess
    args = [sys.executable, "-m", "pytest", path, "-v", "--tb=short", "--no-header", "-q"]
    if test_names:
        args = [sys.executable, "-m", "pytest"] + test_names + ["-v", "--tb=short", "--no-header", "-q"]
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=120)
        lines = r.stdout.splitlines()
        passed = sum(1 for l in lines if "PASSED" in l)
        failed = sum(1 for l in lines if "FAILED" in l)
        errors = sum(1 for l in lines if "ERROR" in l)
        return {
            "success": r.returncode == 0,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "output": r.stdout.strip()[:2000],
            "returncode": r.returncode,
        }
    except FileNotFoundError:
        return {"success": False, "error": "pytest not installed. Run: pip install pytest"}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Tests timed out after 120s"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── SANDBOX ──────────────────────────────────────────────────────────────────

_sandbox_enabled = False
_sandbox_provider = "docker"

sandbox_providers = ["docker", "daytona", "modal"]


def get_sandbox_mode():
    return _sandbox_enabled, _sandbox_provider


def set_sandbox_mode(enabled: bool, provider: str = "docker"):
    global _sandbox_enabled, _sandbox_provider
    _sandbox_enabled = enabled
    _sandbox_provider = provider


def sandbox_check(provider: str = None) -> bool:
    p = provider or _sandbox_provider
    try:
        if p == "docker":
            return subprocess.run(["docker", "--version"], capture_output=True, text=True, timeout=5).returncode == 0
        elif p == "daytona":
            return subprocess.run(["daytona", "--version"], capture_output=True, text=True, timeout=5).returncode == 0
        elif p == "modal":
            try:
                import modal
                return True
            except ImportError:
                return False
        return False
    except Exception:
        return False


def execute_command_sandboxed(cmd: str, cwd: str = None) -> dict:
    global _sandbox_provider
    cwd = cwd or os.getcwd()
    try:
        if _sandbox_provider == "docker":
            if not sandbox_check("docker"):
                return {"success": False, "stderr": "Docker not available", "returncode": -1, "sandboxed": True}
            r = subprocess.run(
                ["docker", "run", "--rm", "-i", "--network", "none", "--read-only", "--tmpfs", "/tmp",
                 "-v", f"{Path(cwd).resolve()}:/workspace:ro", "-w", "/workspace",
                 "--memory", "512m", "--cpus", "1",
                 "python:3.11-slim", "sh", "-c", cmd],
                capture_output=True, text=True, timeout=120)
            return {"success": r.returncode == 0, "stdout": r.stdout.strip(), "stderr": r.stderr.strip(),
                    "returncode": r.returncode, "provider": "docker", "sandboxed": True}

        elif _sandbox_provider == "daytona":
            if not sandbox_check("daytona"):
                return {"success": False, "stderr": "Daytona not available", "returncode": -1, "sandboxed": True}
            subprocess.run(["daytona", "create", "--no-ide", "aira-sandbox"], capture_output=True, text=True, timeout=30)
            r = subprocess.run(
                ["daytona", "exec", "aira-sandbox", "--project", Path(cwd).name, "--", "sh", "-c", cmd],
                capture_output=True, text=True, timeout=120)
            return {"success": r.returncode == 0, "stdout": r.stdout.strip(), "stderr": r.stderr.strip(),
                    "returncode": r.returncode, "provider": "daytona", "sandboxed": True}

        elif _sandbox_provider == "modal":
            if not sandbox_check("modal"):
                return {"success": False, "stderr": "Modal not available", "returncode": -1, "sandboxed": True}
            import tempfile, shutil
            tmp = Path(tempfile.mkdtemp())
            stub = tmp / "run.py"
            stub.write_text(f'''import sys, subprocess, json
import modal
app = modal.App("aira-sandbox")
@app.function()
def run(cmd: str, cwd: str):
    import os
    if cwd: os.chdir(cwd)
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
    return {{"stdout": r.stdout, "stderr": r.stderr, "returncode": r.returncode}}
@app.local_entrypoint()
def main():
    print(json.dumps(run.remote(sys.argv[1], sys.argv[2])))
''')
            r = subprocess.run(["modal", "run", str(stub), cmd, cwd], capture_output=True, text=True, timeout=300)
            shutil.rmtree(tmp, ignore_errors=True)
            try:
                data = json.loads(r.stdout.strip().split("\n")[-1])
                return {"success": data["returncode"] == 0, "stdout": data["stdout"], "stderr": data["stderr"],
                        "returncode": data["returncode"], "provider": "modal", "sandboxed": True}
            except Exception:
                return {"success": r.returncode == 0, "stdout": r.stdout.strip(), "stderr": r.stderr.strip(),
                        "returncode": r.returncode, "provider": "modal", "sandboxed": True}
        else:
            return {"success": False, "stderr": f"Unknown provider: {_sandbox_provider}", "returncode": -1, "sandboxed": True}
    except subprocess.TimeoutExpired:
        return {"success": False, "stderr": "Timed out", "returncode": -1, "sandboxed": True}
    except Exception as e:
        return {"success": False, "stderr": str(e), "returncode": -1, "sandboxed": True}


# ── SELF-GENERATED DOCS ─────────────────────────────────────────────────────

def generate_docs(output_dir: str = "docs") -> dict:
    """Walk the codebase and generate markdown docs from docstrings."""
    import ast
    base = Path(__file__).parent
    docs_path = Path(output_dir)
    docs_path.mkdir(parents=True, exist_ok=True)

    count = 0
    for py_file in base.glob("**/*.py"):
        if "__pycache__" in str(py_file):
            continue
        try:
            with open(py_file, encoding="utf-8") as f:
                tree = ast.parse(f.read())
        except Exception:
            continue

        rel = py_file.relative_to(base.parent)
        md_lines = [f"# Module: `{rel}`", ""]

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                doc = ast.get_docstring(node)
                if doc:
                    sig = f"def {node.name}()"
                    md_lines.append(f"### `{node.name}`")
                    md_lines.append("")
                    md_lines.append(doc)
                    md_lines.append("")
                    count += 1
            elif isinstance(node, ast.ClassDef):
                doc = ast.get_docstring(node)
                if doc:
                    md_lines.append(f"## Class: `{node.name}`")
                    md_lines.append("")
                    md_lines.append(doc)
                    md_lines.append("")

        if count > 0 or len(md_lines) > 3:
            out_file = docs_path / rel.with_suffix(".md").name
            out_file.write_text("\n".join(md_lines), encoding="utf-8")

    return {"success": True, "path": str(docs_path.resolve()), "files": count}


# ── VISION / OCR ────────────────────────────────────────────────────────────

def analyze_image(image_path: str, prompt: str = "Describe this image in detail.") -> dict:
    """Send image to AI vision model and return description."""
    p = Path(image_path)
    if not p.exists():
        return {"success": False, "error": f"File not found: {image_path}"}

    # Try to use the current AI provider's vision capability
    from aira.brain import current_provider_instance, current_provider_name

    if not current_provider_instance:
        return {"success": False, "error": "AIRA brain not initialized"}

    try:
        ext = p.suffix.lower()
        if ext not in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
            return {"success": False, "error": f"Unsupported format: {ext}"}

        import base64
        data = base64.b64encode(p.read_bytes()).decode()

        provider = current_provider_name
        if provider == "anthropic":
            return _vision_anthropic(data, ext, prompt)
        elif provider in ("openai", "openrouter", "groq", "deepseek"):
            return _vision_openai_like(data, ext, prompt)
        elif provider == "gemini":
            return _vision_gemini(data, ext, prompt)
        else:
            return {"success": False, "error": f"Vision not supported for provider: {provider}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _vision_anthropic(b64_data: str, ext: str, prompt: str) -> dict:
    import anthropic
    from aira.brain import _current_api_key
    client = anthropic.Anthropic(api_key=_current_api_key)
    media_type = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "gif": "image/gif", "webp": "image/webp"}.get(ext.lstrip("."), "image/png")
    r = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [{"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64_data}}, {"type": "text", "text": prompt}]
        }]
    )
    return {"success": True, "text": r.content[0].text}


def _vision_openai_like(b64_data: str, ext: str, prompt: str) -> dict:
    from openai import OpenAI
    from aira.brain import _current_api_key, current_provider_name
    base_url = None
    if current_provider_name == "openrouter":
        base_url = "https://openrouter.ai/api/v1"
    elif current_provider_name == "groq":
        base_url = "https://api.groq.com/openai/v1"
    elif current_provider_name == "deepseek":
        base_url = "https://api.deepseek.com/v1"

    client = OpenAI(api_key=_current_api_key, base_url=base_url) if base_url else OpenAI(api_key=_current_api_key)
    media_type = {"png": "data:image/png", "jpg": "data:image/jpeg", "jpeg": "data:image/jpeg", "gif": "data:image/gif", "webp": "data:image/webp"}.get(ext.lstrip("."), "data:image/png")
    r = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=1024,
        messages=[{"role": "user", "content": [{"type": "image_url", "image_url": {"url": f"{media_type};base64,{b64_data}"}}, {"type": "text", "text": prompt}]}]
    )
    return {"success": True, "text": r.choices[0].message.content or ""}


def _vision_gemini(b64_data: str, ext: str, prompt: str) -> dict:
    import google.generativeai as genai
    from aira.brain import _current_api_key
    genai.configure(api_key=_current_api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")
    import PIL.Image
    import io, base64
    img = PIL.Image.open(io.BytesIO(base64.b64decode(b64_data)))
    r = model.generate_content([prompt, img])
    return {"success": True, "text": r.text}


# ── TEMPLATE MARKETPLACE ────────────────────────────────────────────────────

TEMPLATE_INDEX_URL = "https://raw.githubusercontent.com/anomalyco/aira-templates/main/index.json"
TEMPLATE_CACHE = Path.home() / ".aira" / "template_cache"


def fetch_template_index() -> list:
    """Fetch remote template index."""
    import requests
    try:
        r = requests.get(TEMPLATE_INDEX_URL, timeout=10)
        if r.status_code == 200:
            return r.json().get("templates", [])
    except Exception:
        pass
    return []


def install_template(slug: str, dest: str = ".") -> dict:
    """Install a template from the marketplace."""
    import requests, zipfile, io
    url = f"https://github.com/anomalyco/aira-templates/archive/main.zip"
    try:
        r = requests.get(url, timeout=30)
        if r.status_code != 200:
            return {"success": False, "error": f"Failed to fetch template index: HTTP {r.status_code}"}
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            base = f"aira-templates-main/templates/{slug}"
            matching = [n for n in z.namelist() if n.startswith(base)]
            if not matching:
                return {"success": False, "error": f"Template '{slug}' not found in marketplace"}
            for name in matching:
                if name.endswith("/"):
                    continue
                rel = name[len(base)+1:]
                if not rel:
                    continue
                data = z.read(name)
                (Path(dest) / rel).parent.mkdir(parents=True, exist_ok=True)
                (Path(dest) / rel).write_bytes(data)
        return {"success": True, "path": str(Path(dest).resolve()), "files": len(matching)}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── INLINE DIFF VIEWER ──────────────────────────────────────────────────────

def diff_text(original: str, modified: str, filename: str = "file") -> str:
    import difflib
    orig_lines = original.splitlines(keepends=True)
    mod_lines = modified.splitlines(keepends=True)
    diff = difflib.unified_diff(orig_lines, mod_lines, fromfile=f"a/{filename}", tofile=f"b/{filename}")
    return "".join(diff)


def rich_diff(original: str, modified: str, filename: str = "file"):
    from aira.ui import console, THEME
    from rich.text import Text
    import difflib
    orig_lines = original.splitlines()
    mod_lines = modified.splitlines()
    diff = list(difflib.Differ().compare(orig_lines, mod_lines))
    result = Text()
    for line in diff:
        if line.startswith("+ "):
            result.append(line + "\n", style="green")
        elif line.startswith("- "):
            result.append(line + "\n", style="red")
        elif line.startswith("? "):
            continue
        else:
            result.append(line + "\n", style="dim")
    console.print(result)


def parse_diff(diff_str: str) -> list:
    """Parse standard unified diff format into individual hunk objects."""
    hunks = []
    current = None
    current_file = None
    for line in diff_str.splitlines():
        if line.startswith("+++ "):
            current_file = line[4:].strip()
            if current_file.startswith("b/"):
                current_file = current_file[2:]
            elif current_file == "/dev/null":
                current_file = None
        elif line.startswith("@@"):
            if current:
                hunks.append(current)
            parts = line.split()
            old_start = int(parts[1].split(",")[0].lstrip("-")) if len(parts) > 1 else 0
            new_start = int(parts[2].split(",")[0].lstrip("+")) if len(parts) > 2 else 0
            current = {
                "file": current_file,
                "old_start": old_start,
                "new_start": new_start,
                "header": line,
                "lines": [],
            }
        elif current is not None:
            if line.startswith("\\"):
                continue
            current["lines"].append(line)
    if current:
        hunks.append(current)
    return hunks


def apply_hunk(filepath: str, hunk: dict) -> dict:
    """Apply a single diff hunk to a target file using line manipulation."""
    return apply_diff_hunk(filepath, hunk)


def apply_diff_hunk(filepath: str, hunk: dict) -> dict:
    """Cleanly edit target files by applying one parsed diff hunk."""
    target = filepath or hunk.get("file")
    if not target:
        return {"success": False, "error": "No target file specified"}
    fp = Path(target)
    try:
        lines = fp.read_text(encoding="utf-8").splitlines(keepends=True)
    except FileNotFoundError:
        lines = []
    old_start = max(hunk.get("old_start", 1) - 1, 0)
    old_lines = []
    new_lines = []
    for line in hunk.get("lines", []):
        if line.startswith("-"):
            old_lines.append(line[1:])
        elif line.startswith("+"):
            new_lines.append(line[1:])
        elif line.startswith(" "):
            old_lines.append(line[1:])
            new_lines.append(line[1:])
        else:
            old_lines.append(line)
            new_lines.append(line)
    replacement = [l + ("\n" if not l.endswith("\n") else "") for l in new_lines]
    result = lines[:old_start] + replacement + lines[old_start + len(old_lines):]
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text("".join(result), encoding="utf-8")
    return {"success": True, "file": str(fp)}


# ── CHECKPOINT / UNDO ────────────────────────────────────────────────────────

_checkpoint_dir = AIRA_HOME / "checkpoints"
_CHECKPOINT_SKIP_DIRS = {
    ".git", "__pycache__", ".aira", "node_modules", ".venv", "venv",
    "dist", "build", ".tox", ".mypy_cache", ".pytest_cache",
}
_CHECKPOINT_MAX_FILES = 500
_CHECKPOINT_MAX_BYTES = 512 * 1024


def save_checkpoint(conversation: list) -> str:
    _checkpoint_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    cp = _checkpoint_dir / f"cp_{ts}.json"
    files = {}
    cwd = Path.cwd()
    for f in cwd.rglob("*"):
        if len(files) >= _CHECKPOINT_MAX_FILES:
            break
        if not f.is_file():
            continue
        if any(part in _CHECKPOINT_SKIP_DIRS for part in f.parts):
            continue
        try:
            if f.stat().st_size > _CHECKPOINT_MAX_BYTES:
                continue
            files[str(f.relative_to(cwd))] = f.read_text(encoding="utf-8")
        except Exception:
            pass
    data = {"timestamp": ts, "files": files, "conversation": conversation[-20:] if conversation else []}
    cp.write_text(json.dumps(data, indent=2))
    return ts


def restore_checkpoint(ts: str = None) -> dict:
    if ts:
        cp = _checkpoint_dir / f"cp_{ts}.json"
    else:
        cps = sorted(_checkpoint_dir.glob("cp_*.json"), reverse=True)
        cp = cps[0] if cps else None
    if not cp or not cp.exists():
        return {"success": False, "error": "No checkpoint found"}
    data = json.loads(cp.read_text())
    cwd = Path.cwd()
    for rel, content in data["files"].items():
        p = cwd / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    try:
        cp.unlink()
    except Exception:
        pass
    return {"success": True, "timestamp": data["timestamp"], "conversation": data.get("conversation", [])}


def list_checkpoints() -> list:
    return sorted([str(f.stem)[3:] for f in _checkpoint_dir.glob("cp_*.json")], reverse=True)


# ── SELF-HEALING ─────────────────────────────────────────────────────────────

def analyze_error(cmd: str, stdout: str, stderr: str) -> dict:
    import difflib
    error_snippet = (stderr or "")[:2000]
    files_touched = set()
    for line in error_snippet.splitlines():
        for match in __import__("re").finditer(r'File\s+"([^"]+)"|\b(\w+\.\w+):\d+', line):
            f = match.group(1) or match.group(2)
            if f and not f.startswith(("<", "__")):
                files_touched.add(f)
    context = ""
    for f in list(files_touched)[:3]:
        fp = Path.cwd() / f
        if fp.exists():
            context += f"\n--- {f} ---\n" + fp.read_text(encoding="utf-8")[:1000]
    return {"error": error_snippet, "files": list(files_touched), "context": context}


# ── RESOURCE OVERLAY ─────────────────────────────────────────────────────────

def overlay_data() -> dict:
    snap = get_system_snapshot()
    return {
        "cpu": f"{snap['cpu_percent']}%",
        "ram": f"{snap['ram_used_percent']}%",
        "ram_gb": f"{snap['ram_available_gb']:.1f}GB free",
        "disk": f"{snap['disk_free_gb']:.1f}GB free",
        "processes": len(snap.get("top_processes", [])),
    }


# ── TODO LIST ────────────────────────────────────────────────────────────────

_todos_dir = AIRA_HOME / "todos"


def _load_todo_store(project: str = "AIRA") -> dict:
    _todos_dir.mkdir(parents=True, exist_ok=True)
    path = _todos_dir / f"{project}.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"items": [], "next_id": 1}


def _save_todo_store(project: str, store: dict):
    _todos_dir.mkdir(parents=True, exist_ok=True)
    (_todos_dir / f"{project}.json").write_text(json.dumps(store, indent=2), encoding="utf-8")


def list_todos(project: str = "AIRA") -> list:
    return _load_todo_store(project).get("items", [])


def todo_add(text: str, project: str = "AIRA") -> dict:
    text = (text or "").strip()
    if not text:
        return {"success": False, "error": "Task text required"}
    store = _load_todo_store(project)
    item = {
        "id": store.get("next_id", 1),
        "text": text,
        "done": False,
        "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    store.setdefault("items", []).append(item)
    store["next_id"] = item["id"] + 1
    _save_todo_store(project, store)
    return {"success": True, "item": item}


def todo_done(todo_id: int, project: str = "AIRA") -> dict:
    store = _load_todo_store(project)
    for item in store.get("items", []):
        if item.get("id") == todo_id:
            item["done"] = True
            _save_todo_store(project, store)
            return {"success": True, "item": item}
    return {"success": False, "error": f"Todo #{todo_id} not found"}


def todo_delete(todo_id: int, project: str = "AIRA") -> dict:
    store = _load_todo_store(project)
    items = store.get("items", [])
    for i, item in enumerate(items):
        if item.get("id") == todo_id:
            removed = items.pop(i)
            _save_todo_store(project, store)
            return {"success": True, "item": removed}
    return {"success": False, "error": f"Todo #{todo_id} not found"}


def todo_clear(project: str = "AIRA", done_only: bool = True) -> dict:
    store = _load_todo_store(project)
    items = store.get("items", [])
    if done_only:
        kept = [i for i in items if not i.get("done")]
        removed = len(items) - len(kept)
        store["items"] = kept
    else:
        removed = len(items)
        store["items"] = []
    _save_todo_store(project, store)
    return {"success": True, "removed": removed}
