import json
import os
import threading
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from datetime import datetime

AIRA_HOME = Path.home() / ".aira"
DASHBOARD_FILE = AIRA_HOME / "dashboard.html"
_dashboard_server = None
_dashboard_thread = None


def _build_html():
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AIRA Dashboard</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: system-ui, sans-serif; background: #0f0f1a; color: #e0e0e0; min-height: 100vh; }
  .sidebar { position: fixed; left: 0; top: 0; bottom: 0; width: 200px; background: #1a1a2e; padding: 1.5rem; }
  .sidebar h1 { color: #e94560; font-size: 1.3rem; margin-bottom: 2rem; }
  .sidebar a { display: block; color: #aaa; text-decoration: none; padding: 0.5rem 0; border-bottom: 1px solid #222; }
  .sidebar a:hover, .sidebar a.active { color: #e94560; }
  .main { margin-left: 200px; padding: 2rem; }
  .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
  .card { background: #1a1a2e; padding: 1.5rem; border-radius: 8px; border-left: 3px solid #e94560; }
  .card h3 { color: #888; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 0.5rem; }
  .card .value { font-size: 2rem; font-weight: bold; color: #fff; }
  .card .sub { color: #666; font-size: 0.8rem; margin-top: 0.3rem; }
  table { width: 100%; border-collapse: collapse; margin: 1rem 0; }
  th { text-align: left; color: #888; font-size: 0.8rem; text-transform: uppercase; padding: 0.5rem; border-bottom: 1px solid #333; }
  td { padding: 0.5rem; border-bottom: 1px solid #222; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; }
  .badge.todo { background: #333; color: #aaa; }
  .badge.doing { background: #f0a500; color: #000; }
  .badge.done { background: #00c853; color: #000; }
  .badge.running { background: #00c853; }
  .badge.stopped { background: #ff1744; }
  .status-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }
  .dot-green { background: #00c853; }
  .dot-red { background: #ff1744; }
  .dot-yellow { background: #f0a500; }
  pre { background: #1a1a2e; padding: 1rem; border-radius: 4px; overflow-x: auto; font-size: 0.85rem; }
  .section-title { color: #e94560; margin: 1.5rem 0 0.5rem; font-size: 1.1rem; }
  @media (max-width: 768px) { .sidebar { width: 60px; padding: 0.5rem; } .sidebar h1, .sidebar a span { display: none; } .main { margin-left: 60px; } }
</style>
</head>
<body>
<div class="sidebar">
  <h1>AIRA</h1>
  <a href="/" class="active" onclick="loadView('overview')">&#9679; Overview</a>
  <a href="/miro" onclick="loadView('miro')">&#9776; Miro</a>
  <a href="/projects" onclick="loadView('projects')">&#128194; Projects</a>
  <a href="/gateway" onclick="loadView('gateway')">&#127760; Gateway</a>
  <a href="/model" onclick="loadView('model')">&#9881; Model</a>
</div>
<div class="main" id="content"><div class="cards" id="stat-cards"></div><div id="detail"></div></div>
<script>
async function api(path) { try { const r=await fetch('/api'+path); return await r.json(); } catch(e) { return {}; } }
function escape(s) { const d=document.createElement('div'); d.textContent=s||''; return d.innerHTML; }

function renderOverview(data) {
  const cards = document.getElementById('stat-cards');
  cards.innerHTML = Object.entries(data.stats||{}).map(([k,v])=>
    `<div class="card"><h3>${escape(k)}</h3><div class="value">${escape(v)}</div></div>`
  ).join('');
  document.getElementById('detail').innerHTML = `
    <div class="section-title">&#128197; Sessions</div>
    <table>${(data.sessions||[]).map(s=>'<tr><td>'+escape(s.id)+'</td><td>'+escape(s.project||'')+'</td><td>'+escape(s.created||'')+'</td><td>'+escape(s.message_count||'0')+' msgs</td></tr>').join('')}</table>
    <div class="section-title">&#9881; Config</div>
    <pre>${escape(JSON.stringify(data.config||{},null,2))}</pre>
  `;
}

function renderMiro(data) {
  const cols = {'todo':'📋 TODO','doing':'🔄 DOING','done':'✅ DONE'};
  document.getElementById('stat-cards').innerHTML = `<div class="card"><h3>Project</h3><div class="value">${escape(data.board?.name||'-')}</div><div class="sub">${escape(data.board?.desc||'')}</div></div>`;
  let html = '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:1rem">';
  for (const col of ['todo','doing','done']) {
    html += '<div style="background:#1a1a2e;padding:1rem;border-radius:8px"><h3 style="color:#888;margin-bottom:0.5rem">'+cols[col]+'</h3>';
    for (const item of (data.board?.columns?.[col]||[]))
      html += '<div style="padding:0.5rem;margin:0.3rem 0;background:#16213e;border-radius:4px"><b>'+escape(item.id)+'</b> '+escape(item.title)+(item.blocked_by?' <span style="color:#ff1744;font-size:0.8rem">(blocked)</span>':'')+'</div>';
    html += '</div>';
  }
  document.getElementById('detail').innerHTML = html+'</div>';
}

function renderProjects(data) {
  document.getElementById('stat-cards').innerHTML = `<div class="card"><h3>Total Projects</h3><div class="value">${(data.projects||[]).length}</div></div>`;
  document.getElementById('detail').innerHTML = `
    <table>${(data.projects||[]).map(p=>'<tr><td>'+escape(p.name)+'</td><td>'+escape(p.desc||'')+'</td><td>'+p.task_count+' tasks</td></tr>').join('')}</table>
  `;
}

function renderGateway(data) {
  const platforms = data.gateway||[];
  document.getElementById('stat-cards').innerHTML = `<div class="card"><h3>Active Gateways</h3><div class="value">${platforms.filter(p=>p.running).length}/${platforms.length}</div></div>`;
  document.getElementById('detail').innerHTML = `
    <table>${platforms.map(p=>'<tr><td><span class="status-dot '+(p.running?'dot-green':'dot-red')+'"></span>'+escape(p.platform)+'</td><td><span class="badge '+(p.running?'running':'stopped')+'">'+(p.running?'Running':'Stopped')+'</span></td><td>'+escape(p.error||'')+'</td></tr>').join('')}</table>
  `;
}

function renderModel(data) {
  document.getElementById('stat-cards').innerHTML = `<div class="card"><h3>Current Model</h3><div class="value">${escape(data.model?.model||'-')}</div><div class="sub">${escape(data.model?.provider||'')}</div></div>`;
  document.getElementById('detail').innerHTML = `
    <div class="section-title">Available Providers</div>
    <table>${(data.model?.providers||[]).map(p=>'<tr><td>'+escape(p)+'</td></tr>').join('')}</table>
  `;
}

async function loadView(view) {
  document.querySelectorAll('.sidebar a').forEach(a=>a.classList.remove('active'));
  event?.target?.classList?.add('active');
  const data = await api('/'+view);
  if (view==='overview') renderOverview(data);
  else if (view==='miro') renderMiro(data);
  else if (view==='projects') renderProjects(data);
  else if (view==='gateway') renderGateway(data);
  else if (view==='model') renderModel(data);
}
loadView('overview');
</script>
</body>
</html>"""


class _Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/api/"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            data = _get_api_data(self.path[5:])
            self.wfile.write(json.dumps(data).encode())
        else:
            html = _build_html()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(html.encode())

    def log_message(self, fmt, *args):
        pass


def _get_api_data(endpoint: str) -> dict:
    from aira.miro import miro_list_projects, miro_get_board
    from aira.gateway import gateway_status, gateway_get_config
    data = {}
    if endpoint in ("overview", ""):
        cfg = {}
        try:
            from aira.main import AIRA_HOME as AH, CONFIG_FILE
            if CONFIG_FILE.exists():
                cfg = json.loads(CONFIG_FILE.read_text())
                cfg = {k: v for k, v in cfg.items() if "key" not in k.lower()}
        except: pass
        sessions = []
        try:
            from aira.memory import get_recent_sessions
            sessions = get_recent_sessions(10)
        except: pass
        data["stats"] = {
            "Python": os.sys.version.split()[0],
            "Projects": len(miro_list_projects()),
            "Sessions": len(sessions),
            "Platform": os.name,
        }
        data["sessions"] = sessions
        data["config"] = cfg
    elif endpoint == "miro":
        projects = miro_list_projects()
        pname = projects[0]["name"] if projects else ""
        data["board"] = miro_get_board(pname) if pname else None
    elif endpoint == "projects":
        data["projects"] = miro_list_projects()
    elif endpoint == "gateway":
        data["gateway"] = gateway_status()
        data["gateway_config"] = gateway_get_config()
    elif endpoint == "model":
        try:
            from aira.main import _MODEL_PROVIDER, CONFIG_FILE
            cfg = json.loads(CONFIG_FILE.read_text()) if CONFIG_FILE.exists() else {}
            data["model"] = {"provider": cfg.get("provider",""), "model": cfg.get("model","")}
            data["model"]["providers"] = sorted(set(p for p,t in _MODEL_PROVIDER.values())) if '_MODEL_PROVIDER' in dir() else []
        except: pass
    return data


def dashboard_start(port: int = 8080, open_browser: bool = True) -> dict:
    global _dashboard_server, _dashboard_thread
    if _dashboard_server:
        return {"success": False, "error": "Dashboard already running"}
    try:
        _dashboard_server = HTTPServer(("127.0.0.1", port), _Handler)
        _dashboard_thread = threading.Thread(
            target=_dashboard_server.serve_forever, daemon=True
        )
        _dashboard_thread.start()
        url = f"http://127.0.0.1:{port}"
        if open_browser:
            try:
                webbrowser.open(url)
            except Exception:
                pass
        return {"success": True, "url": url, "port": port}
    except Exception as e:
        return {"success": False, "error": str(e)}


def dashboard_stop() -> dict:
    global _dashboard_server, _dashboard_thread
    if _dashboard_server:
        _dashboard_server.shutdown()
        _dashboard_server = None
        _dashboard_thread = None
        return {"success": True}
    return {"success": False, "error": "Not running"}
