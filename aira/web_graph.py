import json
import threading
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

AIRA_HOME = Path.home() / ".aira"
_server = None
_thread = None


def _get_graph_data() -> dict:
    nodes = []
    edges = []
    try:
        from aira.memory import get_all_memories, get_recent_sessions
        mems = get_all_memories()
        for m in mems[-50:]:
            nodes.append({"id": m["id"], "label": m["content"][:30], "group": "memory", "title": m["content"][:100]})
        sess = get_recent_sessions(10)
        for s in sess:
            nodes.append({"id": f"session_{s['id']}", "label": s.get("project", "?")[:20], "group": "session", "title": s.get("summary", "")[:100]})
        for i, m in enumerate(mems[-20:]):
            for j in range(i + 1, min(i + 4, len(mems[-20:]))):
                edges.append({"from": m["id"], "to": mems[-20:][j]["id"]})
    except Exception:
        pass
    try:
        from aira.miro import miro_list_projects
        for p in miro_list_projects():
            nodes.append({"id": f"proj_{p['name']}", "label": p["name"][:20], "group": "project", "title": p.get("desc", "")[:60]})
    except Exception:
        pass
    try:
        from aira.brain import AGENTS
        for name in AGENTS:
            nodes.append({"id": f"agent_{name}", "label": name[:20], "group": "agent", "title": f"Agent: {name}"})
    except Exception:
        pass
    return {"nodes": nodes, "edges": edges}


HTML = """<!DOCTYPE html>
<html><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AIRA Graph</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.6/dist/vis-network.min.js"></script>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.6/dist/dist/vis-network.min.css">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0a1a;color:#e0e0e0;font-family:monospace;overflow:hidden}
#toolbar{background:#12122a;padding:10px 20px;border-bottom:1px solid #2a2a4a;display:flex;align-items:center;gap:15px}
#toolbar h1{color:#e94560;font-size:16px;font-weight:bold}
#toolbar span{color:#4a4a7a;font-size:12px}
#toolbar .badge{background:#1a1a3a;padding:2px 10px;border-radius:10px;font-size:11px;color:#8a8acc}
#mynetwork{width:100vw;height:calc(100vh-50px)}
</style></head><body>
<div id="toolbar">
  <h1>&#9671; AIRA Graph</h1>
  <span class="badge" id="nodeCount">0 nodes</span>
  <span class="badge" id="edgeCount">0 edges</span>
  <span style="flex:1"></span>
  <span style="color:#4a4a7a;font-size:11px">drag to pan | scroll to zoom</span>
</div>
<div id="mynetwork"></div>
<script>
const container = document.getElementById('mynetwork');
const options = {
  nodes:{shape:'dot',size:12,font:{color:'#e0e0e0',size:11,face:'monospace'},borderWidth:2},
  edges:{width:1.5,color:{color:'#2a2a5a',highlight:'#e94560'}},
  groups:{
    memory:{color:{background:'#1a6b3c',border:'#2ecc71'}},
    session:{color:{background:'#1a3a6b',border:'#3498db'}},
    project:{color:{background:'#6b1a3a',border:'#e74c3c'}},
    agent:{color:{background:'#6b5a1a',border:'#f1c40f'}}
  },
  physics:{stabilization:{iterations:100}},
  interaction:{hover:true,tooltipDelay:200,hideEdgesOnDrag:true}
};
fetch('/api/graph').then(r=>r.json()).then(data=>{
  document.getElementById('nodeCount').textContent=data.nodes.length+' nodes';
  document.getElementById('edgeCount').textContent=data.edges.length+' edges';
  new vis.Network(container,data,options);
});
</script></body></html>"""


class _Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/graph":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(_get_graph_data()).encode())
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML.encode())

    def log_message(self, fmt, *args):
        pass


def web_start(port: int = 9090, open_browser: bool = True) -> dict:
    global _server, _thread
    if _server:
        return {"success": False, "error": "Already running", "url": f"http://127.0.0.1:{port}"}
    _server = HTTPServer(("127.0.0.1", port), _Handler)
    _thread = threading.Thread(target=_server.serve_forever, daemon=True)
    _thread.start()
    url = f"http://127.0.0.1:{port}"
    if open_browser:
        webbrowser.open(url)
    return {"success": True, "url": url}


def web_stop() -> dict:
    global _server, _thread
    if _server:
        _server.shutdown()
        _server = None
        _thread = None
        return {"success": True}
    return {"success": False, "error": "Not running"}
