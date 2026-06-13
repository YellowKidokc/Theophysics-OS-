"""
POF2828 Service Manager — Dashboard + Process Control
Run: python service_manager.py
Dashboard: http://localhost:9999
"""
import json, os, socket, subprocess, signal, sys, time, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path
from datetime import datetime

PORT = 9999

# ── Service Registry ──────────────────────────────────────────────
# Each service: name, port, start command, working directory, description
SERVICES = [
    {
        "id": "clipsync",
        "name": "ClipSync Bridge",
        "port": 3456,
        "cmd": ["python", "sync_server.py"],
        "cwd": r"C:\Users\lowes\Downloads\Compressed\ai-hub-clipsync-master\ai-hub-clipsync-master",
        "desc": "Clipboard sync between devices"
    },
    {
        "id": "bil",
        "name": "BIL Server",
        "port": 8420,
        "cmd": ["python", "-c", "from bil.bil_server import start_bil_server; start_bil_server()"],
        "cwd": r"X:\BIL\behavioral-intelligence-layer-OBS-Plugin-Final-Claude",
        "desc": "Behavioral Intelligence Layer — preference learning"
    },
    {
        "id": "fis",
        "name": "FIS (File Intelligence)",
        "port": 8420,
        "cmd": ["python", "-m", "fis", "all"],
        "cwd": r"X:\file-intelligence-system-master\file-intelligence-system-master",
        "desc": "File watcher + NLP pipeline + clipboard monitor",
        "note": "Shares port 8420 with BIL — run one or the other"
    },
    {
        "id": "organize",
        "name": "Organize Server",
        "port": 8500,
        "cmd": ["python", "server.py"],
        "cwd": r"C:\Users\lowes\Desktop\Theophysics-OS-clone\1files",
        "desc": "File organization + scanning UI"
    },
    {
        "id": "activitywatch",
        "name": "ActivityWatch",
        "port": 5600,
        "cmd": None,
        "cwd": None,
        "desc": "Usage tracking — starts via its own shortcut",
        "managed": False
    },
    {
        "id": "syncthing",
        "name": "Syncthing",
        "port": 8384,
        "cmd": None,
        "cwd": None,
        "desc": "File sync — starts via its own service",
        "managed": False
    },
    {
        "id": "browseros",
        "name": "BrowserOS",
        "port": 9200,
        "cmd": None,
        "cwd": None,
        "desc": "Agentic browser automation",
        "managed": False
    },
    {
        "id": "postgres",
        "name": "PostgreSQL (local)",
        "port": 5432,
        "cmd": None,
        "cwd": None,
        "desc": "Local Postgres instance",
        "managed": False
    },
    {
        "id": "vite",
        "name": "Vite Dev Server",
        "port": 5173,
        "cmd": None,
        "cwd": None,
        "desc": "Frontend dev server (FORGE or similar)",
        "managed": False
    },
]

# Track PIDs of services we started
started_pids = {}


def check_port(port, host="127.0.0.1", timeout=0.5):
    """Check if a port is listening."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (ConnectionRefusedError, socket.timeout, OSError):
        return False


def get_pid_on_port(port):
    """Get PID listening on a port (Windows)."""
    try:
        result = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                parts = line.split()
                return int(parts[-1])
    except Exception:
        pass
    return None


def get_all_status():
    """Get status of all registered services."""
    statuses = []
    for svc in SERVICES:
        alive = check_port(svc["port"])
        pid = get_pid_on_port(svc["port"]) if alive else None
        manageable = svc.get("managed", True) and svc.get("cmd") is not None
        statuses.append({
            "id": svc["id"],
            "name": svc["name"],
            "port": svc["port"],
            "desc": svc["desc"],
            "note": svc.get("note", ""),
            "alive": alive,
            "pid": pid,
            "manageable": manageable,
            "started_by_us": svc["id"] in started_pids,
        })
    return statuses


def start_service(service_id):
    """Start a service by ID."""
    svc = next((s for s in SERVICES if s["id"] == service_id), None)
    if not svc or not svc.get("cmd"):
        return {"ok": False, "error": f"Service '{service_id}' not startable"}
    if check_port(svc["port"]):
        return {"ok": False, "error": f"Port {svc['port']} already in use"}
    if not Path(svc["cwd"]).exists():
        return {"ok": False, "error": f"Working dir not found: {svc['cwd']}"}
    try:
        proc = subprocess.Popen(
            svc["cmd"],
            cwd=svc["cwd"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
        )
        started_pids[service_id] = proc.pid
        time.sleep(1.5)
        alive = check_port(svc["port"])
        return {"ok": True, "pid": proc.pid, "alive": alive}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def stop_service(service_id):
    """Stop a service by ID."""
    svc = next((s for s in SERVICES if s["id"] == service_id), None)
    if not svc:
        return {"ok": False, "error": f"Unknown service '{service_id}'"}
    pid = get_pid_on_port(svc["port"])
    if not pid:
        started_pids.pop(service_id, None)
        return {"ok": False, "error": "Service not running"}
    try:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                       capture_output=True, timeout=5)
        started_pids.pop(service_id, None)
        time.sleep(0.5)
        return {"ok": True, "killed_pid": pid}
    except Exception as e:
        return {"ok": False, "error": str(e)}


DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>POF 2828 — Service Dashboard</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Segoe UI', system-ui, sans-serif;
    background: #0a0e17; color: #c8d6e5;
    min-height: 100vh; padding: 24px;
  }
  .header {
    text-align: center; margin-bottom: 32px;
    border-bottom: 1px solid #1e2a3a; padding-bottom: 20px;
  }
  .header h1 { font-size: 22px; color: #e8e8e8; letter-spacing: 2px; }
  .header .sub { font-size: 13px; color: #5a6a7a; margin-top: 6px; }
  .header .time { font-size: 12px; color: #3a4a5a; margin-top: 4px; }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 16px; max-width: 1100px; margin: 0 auto;
  }
  .card {
    background: #111827; border: 1px solid #1e2a3a;
    border-radius: 10px; padding: 18px 20px;
    transition: border-color 0.2s;
  }
  .card:hover { border-color: #2a3a4a; }
  .card-top { display: flex; align-items: center; justify-content: space-between; }
  .card-name { font-size: 15px; font-weight: 600; color: #e0e0e0; }
  .dot {
    width: 10px; height: 10px; border-radius: 50%;
    display: inline-block; margin-right: 8px;
    box-shadow: 0 0 6px currentColor;
  }
  .dot.on { background: #22c55e; color: #22c55e; }
  .dot.off { background: #ef4444; color: #ef4444; }
  .card-port {
    font-size: 12px; color: #5a7a9a;
    background: #0d1520; padding: 3px 10px;
    border-radius: 12px; font-family: monospace;
  }
  .card-desc { font-size: 12px; color: #5a6a7a; margin-top: 10px; line-height: 1.5; }
  .card-note { font-size: 11px; color: #b45309; margin-top: 6px; font-style: italic; }
  .card-pid { font-size: 11px; color: #3a5a3a; margin-top: 4px; font-family: monospace; }
  .card-actions { margin-top: 14px; display: flex; gap: 8px; }
  .btn {
    padding: 6px 16px; border-radius: 6px; border: none;
    font-size: 12px; font-weight: 600; cursor: pointer;
    transition: all 0.15s; font-family: inherit;
  }
  .btn-start { background: #166534; color: #bbf7d0; }
  .btn-start:hover { background: #15803d; }
  .btn-stop { background: #7f1d1d; color: #fecaca; }
  .btn-stop:hover { background: #991b1b; }
  .btn:disabled { opacity: 0.3; cursor: not-allowed; }
  .btn.loading { opacity: 0.5; pointer-events: none; }
  .refresh-bar {
    text-align: center; margin-top: 28px;
    font-size: 11px; color: #3a4a5a;
  }
  .summary {
    text-align: center; margin-bottom: 20px;
    font-size: 13px; color: #5a6a7a;
  }
  .summary span { font-weight: 700; }
  .summary .up { color: #22c55e; }
  .summary .down { color: #ef4444; }
</style>
</head>
<body>
<div class="header">
  <h1>POF 2828 — SERVICE DASHBOARD</h1>
  <div class="sub">Theophysics Research Initiative</div>
  <div class="time" id="clock"></div>
</div>
<div class="summary" id="summary"></div>
<div class="grid" id="grid"></div>
<div class="refresh-bar">Auto-refreshes every 5 seconds</div>

<script>
let services = [];

async function fetchStatus() {
  try {
    const r = await fetch('/api/status');
    services = await r.json();
    render();
  } catch(e) { console.error('Fetch failed:', e); }
}

function render() {
  const grid = document.getElementById('grid');
  const up = services.filter(s => s.alive).length;
  const down = services.filter(s => !s.alive).length;
  document.getElementById('summary').innerHTML =
    `<span class="up">${up} running</span> &middot; <span class="down">${down} stopped</span> &middot; ${services.length} total`;
  document.getElementById('clock').textContent = new Date().toLocaleString();

  grid.innerHTML = services.map(s => `
    <div class="card">
      <div class="card-top">
        <div><span class="dot ${s.alive ? 'on' : 'off'}"></span><span class="card-name">${s.name}</span></div>
        <span class="card-port">:${s.port}</span>
      </div>
      <div class="card-desc">${s.desc}</div>
      ${s.note ? `<div class="card-note">${s.note}</div>` : ''}
      ${s.pid ? `<div class="card-pid">PID ${s.pid}</div>` : ''}
      <div class="card-actions">
        ${s.manageable ? `
          <button class="btn btn-start" onclick="startSvc('${s.id}')" ${s.alive ? 'disabled' : ''}>Start</button>
          <button class="btn btn-stop" onclick="stopSvc('${s.id}')" ${!s.alive ? 'disabled' : ''}>Stop</button>
        ` : '<span style="font-size:11px;color:#3a4a5a">External — not managed</span>'}
      </div>
    </div>
  `).join('');
}

async function startSvc(id) {
  const btn = event.target; btn.classList.add('loading'); btn.textContent = '...';
  await fetch('/api/start?id=' + id);
  setTimeout(fetchStatus, 1500);
}

async function stopSvc(id) {
  const btn = event.target; btn.classList.add('loading'); btn.textContent = '...';
  await fetch('/api/stop?id=' + id);
  setTimeout(fetchStatus, 1000);
}

fetchStatus();
setInterval(fetchStatus, 5000);
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *a): pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")

    def _json(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self._cors()
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())

    def do_GET(self):
        p = urlparse(self.path)
        if p.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode())
        elif p.path == "/api/status":
            self._json(get_all_status())
        elif p.path == "/api/start":
            q = parse_qs(p.query)
            sid = q.get("id", [""])[0]
            self._json(start_service(sid))
        elif p.path == "/api/stop":
            q = parse_qs(p.query)
            sid = q.get("id", [""])[0]
            self._json(stop_service(sid))
        elif p.path == "/api/scan":
            # Scan all ports 1-65535 for listeners (limited to common range)
            common = [80,443,3000,3456,5000,5173,5432,5600,8000,8080,8090,
                      8384,8420,8500,8787,8888,9000,9100,9200,9999,22000,33333]
            found = []
            for port in common:
                if check_port(port):
                    pid = get_pid_on_port(port)
                    known = next((s["name"] for s in SERVICES if s["port"] == port), None)
                    found.append({"port": port, "pid": pid, "known_as": known})
            self._json(found)
        elif p.path == "/hub" or p.path == "/hub.html":
            hub_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hub.html")
            try:
                with open(hub_path, "rb") as f:
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html")
                    self.end_headers()
                    self.wfile.write(f.read())
            except:
                self._json({"error": "hub.html not found"}, 404)
        elif p.path == "/api/nerve-config":
            config_path = r"C:\Users\lowes\Desktop\Theophysics-OS-clone\nerve-full-fix-package\live_install\config\config.json"
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    self._json(json.loads(f.read()))
            except Exception as e:
                self._json({"error": str(e)}, 500)
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        p = urlparse(self.path)
        if p.path == "/api/nerve-config":
            config_path = r"C:\Users\lowes\Desktop\Theophysics-OS-clone\nerve-full-fix-package\live_install\config\config.json"
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode("utf-8")
                data = json.loads(body)
                with open(config_path, "w", encoding="utf-8") as f:
                    f.write(json.dumps(data, indent=2, ensure_ascii=False))
                self._json({"ok": True})
            except Exception as e:
                self._json({"error": str(e)}, 500)
        else:
            self._json({"error": "not found"}, 404)


NERVE_CONFIG_PATH = r"C:\Users\lowes\Desktop\Theophysics-OS-clone\nerve-full-fix-package\live_install\config\config.json"

if __name__ == "__main__":
    print(f"\n  POF 2828 Service Manager")
    print(f"  Dashboard: http://localhost:{PORT}")
    print(f"  Hub:       http://localhost:{PORT}/hub")
    print(f"  API:       http://localhost:{PORT}/api/status")
    print(f"  Services:  {len(SERVICES)} registered\n")
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()
