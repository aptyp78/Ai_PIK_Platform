#!/usr/bin/env python3
import argparse
import datetime as dt
import html
import os
import subprocess
import signal
import sys
from typing import Dict, List, Optional, Tuple

try:
    import psutil  # type: ignore
except Exception as e:  # pragma: no cover
    print("Missing dependency: psutil\nInstall with: pip install psutil", file=sys.stderr)
    sys.exit(1)

try:
    from flask import Flask, jsonify, request
except Exception:
    print("Missing dependency: flask\nInstall with: pip install flask", file=sys.stderr)
    sys.exit(1)


app = Flask(__name__)
ACTION_TOKEN = os.environ.get("DASH_TOKEN", "")  # if set, required for mutating actions
REPO_ROOT = os.environ.get("REPO_ROOT", "/root/AiPIK")


VSCODE_KEYWORDS = (
    "vscode",  # generic
    "vscode-server",
    "remote\"ssh",
    "remote-ssh",
    "node"  # VSCode server/ptyhost/extension host are node processes
)


def safe_cmdline(p: psutil.Process) -> str:
    try:
        cl = p.cmdline()
        if not cl:
            return p.name()
        return " ".join(cl)
    except Exception:
        return p.name()


def in_vscode_chain(p: psutil.Process) -> Tuple[bool, int, Optional[psutil.Process]]:
    """Return (is_in_chain, depth_to_root_in_chain, chain_root).

    A process is considered part of VSCode if any ancestor's cmdline contains
    VSCODE_KEYWORDS (heuristic but practical for Remote-SSH sessions).
    """
    depth = 0
    chain_root: Optional[psutil.Process] = None
    try:
        for anc in [p] + list(p.parents()):
            depth += 1
            cl = safe_cmdline(anc).lower()
            if any(k in cl for k in VSCODE_KEYWORDS):
                chain_root = anc
                return True, depth, chain_root
        return False, depth, None
    except Exception:
        return False, depth, None


def process_snapshot(scope: str = "vscode") -> Dict:
    nodes: Dict[int, Dict] = {}
    parent_map: Dict[int, int] = {}

    # Map of PID -> GPU memory usage (MiB), best-effort
    gpu_proc_mem: Dict[int, int] = {}
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-compute-apps=pid,used_memory",
                "--format=csv,noheader,nounits",
            ],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        for line in out.strip().splitlines():
            if not line.strip():
                continue
            parts = [x.strip() for x in line.split(",")]
            if len(parts) >= 2:
                try:
                    pid = int(parts[0])
                    mem = int(parts[1])  # MiB
                    gpu_proc_mem[pid] = mem
                except Exception:
                    continue
    except Exception:
        pass

    def classify_role(name: str, cmd: str) -> str:
        low = (cmd or "").lower()
        nlow = (name or "").lower()
        if any(k in low for k in ("jupyter", "ipykernel", "nbconvert")) or nlow.startswith("jupyter"):
            return "Jupyter"
        if "vscode-server" in low:
            return "VSCode Server"
        if "ptyhost" in low:
            return "VSCode ptyhost"
        if "node" == nlow and "vscode" in low:
            return "VSCode node"
        if any(k in low for k in ("git ", " gsutil", "rclone", "ffmpeg", "rg ", " ripgrep", "curl ", "wget ", "tar ", "unzip ", "zip ")):
            return "Util/IO"
        if nlow in ("bash", "zsh", "sh"):
            return "Shell"
        if "python" in low:
            if REPO_ROOT and REPO_ROOT.lower() in low:
                # try to extract scripts/<name>.py
                if "scripts/" in low:
                    tail = low.split("scripts/", 1)[1]
                    scr = tail.split()[0]
                    return f"Script:{scr}"
                return "Project Python"
            return "Python"
        return "Other"

    for p in psutil.process_iter(attrs=["pid", "ppid", "name", "username", "create_time"]):
        try:
            ok, depth, root = in_vscode_chain(p)
            cpu = p.cpu_percent(interval=None)
            mem = p.memory_info().rss if p.is_running() else 0
            cmd = safe_cmdline(p)
            try:
                status = p.status()
            except Exception:
                status = "unknown"
            alive = p.is_running() and (status != getattr(psutil, "STATUS_ZOMBIE", "zombie"))
            try:
                cwd = p.cwd()
            except Exception:
                cwd = ""
            project = False
            if REPO_ROOT:
                rr = REPO_ROOT.rstrip("/").lower()
                if rr in (cmd or "").lower() or (cwd or "").lower().startswith(rr):
                    project = True
            role = classify_role(p.info.get("name") or "", cmd)
            gpum = gpu_proc_mem.get(p.pid, 0)
            started = dt.datetime.fromtimestamp(p.info.get("create_time", 0)).isoformat(timespec="seconds")
            node = {
                "pid": p.pid,
                "ppid": p.ppid(),
                "name": p.info.get("name"),
                "cmd": cmd,
                "cpu": cpu,
                "mem": mem,
                "user": p.info.get("username"),
                "start": started,
                "status": status,
                "alive": alive,
                "cwd": cwd,
                "project": project,
                "role": role,
                "gpu_mem": gpum,
            }
            # Scope filter
            s = (scope or "").lower()
            include = False
            if s in ("vscode", "code", "remote"):
                include = ok
            elif s in ("project", "repo"):
                include = bool(project)
            else:  # all
                include = True
            if not include:
                continue
            nodes[p.pid] = node
            parent_map[p.pid] = p.ppid()
        except Exception:
            continue

    # Build tree structure limited to selected nodes
    children: Dict[int, List[int]] = {pid: [] for pid in nodes.keys()}
    roots: List[int] = []
    for pid, ppid in parent_map.items():
        if ppid in nodes:
            children[ppid].append(pid)
        else:
            roots.append(pid)

    def build(pid: int, level: int = 0, root_pid: Optional[int] = None) -> Dict:
        n = nodes[pid].copy()
        if root_pid is None:
            root_pid = pid
        n["level"] = level
        n["root"] = root_pid
        # also annotate base node for flat list
        nodes[pid]["root"] = root_pid
        n["children"] = [build(c, level + 1, root_pid) for c in sorted(children.get(pid, []))]
        return n

    tree = [build(r) for r in sorted(roots)]

    # Root labels
    root_labels: Dict[int, str] = {}
    for r in roots:
        root_node = nodes.get(r, {})
        rname = (root_node.get("name") or str(r))
        rcmd = (root_node.get("cmd") or "").split()
        rcmd_s = " ".join(rcmd[:3]) if rcmd else ""
        root_labels[r] = f"{rname} · {r} · {rcmd_s}".strip()
    for n in nodes.values():
        n["root_label"] = root_labels.get(n.get("root", 0), str(n.get("root", "")))

    # GPU quick stats (best-effort)
    gpu = []
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        for line in out.strip().splitlines():
            name, util, mused, mtotal = [x.strip() for x in line.split(",")]
            gpu.append({
                "name": name,
                "util": int(util or 0),
                "mem_used": int(mused or 0),
                "mem_total": int(mtotal or 0),
            })
    except Exception:
        pass

    # Aggregations for groups
    def agg_init():
        return {"count": 0, "cpu": 0.0, "mem": 0, "gpu": 0, "alive": 0, "pids": []}

    grp_role: Dict[str, Dict] = {}
    grp_project: Dict[str, Dict] = {}
    grp_root: Dict[str, Dict] = {}
    for n in nodes.values():
        # role
        r = n.get("role") or "Other"
        a = grp_role.setdefault(r, agg_init())
        a["count"] += 1; a["cpu"] += float(n.get("cpu", 0) or 0); a["mem"] += int(n.get("mem", 0) or 0); a["gpu"] += int(n.get("gpu_mem", 0) or 0); a["alive"] += 1 if n.get("alive") else 0; a["pids"].append(n.get("pid"))
        # project
        pkey = "AiPIK" if n.get("project") else "Other"
        a = grp_project.setdefault(pkey, agg_init())
        a["count"] += 1; a["cpu"] += float(n.get("cpu", 0) or 0); a["mem"] += int(n.get("mem", 0) or 0); a["gpu"] += int(n.get("gpu_mem", 0) or 0); a["alive"] += 1 if n.get("alive") else 0; a["pids"].append(n.get("pid"))
        # root
        rk = n.get("root_label") or str(n.get("root"))
        a = grp_root.setdefault(rk, agg_init())
        a["count"] += 1; a["cpu"] += float(n.get("cpu", 0) or 0); a["mem"] += int(n.get("mem", 0) or 0); a["gpu"] += int(n.get("gpu_mem", 0) or 0); a["alive"] += 1 if n.get("alive") else 0; a["pids"].append(n.get("pid"))

    flat_nodes = list(nodes.values())
    return {
        "tree": tree,
        "nodes": flat_nodes,
        "count": len(nodes),
        "gpu": gpu,
        "groups": {"role": grp_role, "project": grp_project, "root": grp_root},
        "ts": dt.datetime.utcnow().isoformat() + "Z",
        "repo_root": REPO_ROOT,
    }


def render_table(node: Dict) -> str:
    indent = "&nbsp;" * (node.get("level", 0) * 4)
    mem_mb = node.get("mem", 0) / (1024 * 1024)
    cmd = html.escape(node.get("cmd", ""))
    return (
        f"<tr>"
        f"<td>{indent}{node.get('pid')}</td>"
        f"<td>{html.escape(node.get('name') or '')}</td>"
        f"<td>{node.get('cpu', 0):5.1f}</td>"
        f"<td>{mem_mb:8.1f}</td>"
        f"<td>{html.escape(node.get('user') or '')}</td>"
        f"<td>{html.escape(node.get('start') or '')}</td>"
        f"<td class=cmd>{cmd}</td>"
        f"</tr>"
        + "".join(render_table(c) for c in node.get("children", []))
    )


@app.get("/api/processes")
def api_processes():
    scope = (request.args.get("scope") or "vscode").lower()
    return jsonify(process_snapshot(scope))


def _require_token() -> Optional[str]:
    if not ACTION_TOKEN:
        return None  # no token required
    got = request.headers.get("X-Token") or request.args.get("token")
    if got != ACTION_TOKEN:
        return "forbidden"
    return None


@app.post("/api/signal")
def api_signal():
    err = _require_token()
    if err:
        return jsonify({"ok": False, "error": err}), 403
    data = request.get_json(silent=True) or {}
    try:
        pid = int(data.get("pid", 0))
    except Exception:
        return jsonify({"ok": False, "error": "bad pid"}), 400
    sig_name = str(data.get("sig", "TERM")).upper()
    if not sig_name.startswith("SIG"):
        sig_name = "SIG" + sig_name
    sig = getattr(signal, sig_name, None)
    if sig is None:
        return jsonify({"ok": False, "error": "bad signal"}), 400
    try:
        p = psutil.Process(pid)
        p.send_signal(sig)
        return jsonify({"ok": True, "pid": pid, "signal": sig_name})
    except psutil.NoSuchProcess:
        return jsonify({"ok": False, "error": "no such process"}), 404
    except Exception as e:  # pragma: no cover
        return jsonify({"ok": False, "error": str(e)}), 500


@app.get("/")
def home():
    # Modern, widget-like UI with client-side refresh
    return """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>VSCode Process Dashboard</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    :root {
      --bg: #f5f7fa;
      --card: #ffffffcc;
      --text: #111827;
      --muted: #6b7280;
      --accent: #0a84ff; /* macOS Tahoe-like blue */
      --border: #e5e7eb;
      --shadow: 0 10px 30px rgba(0,0,0,0.08);
      --radius: 14px;
    }
    * { box-sizing: border-box; }
    body { margin: 0; background: var(--bg); color: var(--text); font: 16px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
    header { position: sticky; top: 0; backdrop-filter: saturate(180%) blur(12px); background: #ffffffaa; border-bottom: 1px solid var(--border); padding: 12px 18px; z-index: 10; }
    h1 { margin: 0; font-size: 22px; }
    .sub { color: var(--muted); font-size: 13px; }
    main { padding: 18px; max-width: 1280px; margin: 0 auto; }

    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }
    .card { background: var(--card); border: 1px solid var(--border); border-radius: var(--radius); box-shadow: var(--shadow); padding: 12px; }
    .card h3 { margin: 0 0 8px 0; font-size: 16px; font-weight: 600; }
    .metric { font-size: 28px; font-weight: 700; }
    .muted { color: var(--muted); }
    .pill { display: inline-block; padding: 3px 8px; border-radius: 999px; background: #eef2ff; color: #3730a3; font-size: 11px; }
    .bar { height: 8px; background: #e5e7eb; border-radius: 99px; overflow: hidden; }
    .bar > span { display: block; height: 100%; background: var(--accent); }

    .toolbar { display:flex; gap:8px; align-items:center; margin: 8px 0 12px; }
    .search { flex:1; }
    .search input { width: 100%; padding: 8px 10px; border: 1px solid var(--border); border-radius: 10px; background: #fff; }

    /* Mini windows (process cards) */
    .pgrid { display:grid; grid-template-columns: repeat(auto-fill,minmax(280px,1fr)); gap:12px; margin-bottom:12px; }
    .p-card { border:1px solid var(--border); border-radius:12px; background:#fff; box-shadow: var(--shadow); overflow:hidden; }
    .p-titlebar { display:flex; align-items:center; gap:8px; padding:8px 10px; background:#f6f7f9; border-bottom:1px solid var(--border); }
    .lights { display:flex; gap:6px; }
    .light { width:10px; height:10px; border-radius:50%; background:#e5e7eb; }
    .light.red{ background:#ff5f57; }
    .light.yellow{ background:#febc2e; }
    .light.green{ background:#28c840; }
    .p-title { font-weight:600; font-size:13px; }
    .p-body { padding:10px; }
    .row { display:flex; gap:8px; align-items:center; margin:4px 0; }
    .kv { color:var(--muted); font-size:12px; }
    .actions { display:flex; gap:8px; margin-top:8px; }
    button { border:1px solid var(--border); background:#fff; border-radius:8px; padding:6px 10px; cursor:pointer; }
    button:hover { border-color:#cfd3d8; }
    .danger { color:#b00020; border-color:#ffb4b4; background:#fff8f8; }
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size:12px; }

    table { width: 100%; border-collapse: collapse; background: #fff; border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden; box-shadow: var(--shadow); }
    th, td { padding: 10px 12px; border-bottom: 1px solid var(--border); text-align: left; font-size: 15px; }
    th { background: #f8fafc; position: sticky; top: 64px; z-index: 5; }
    tbody tr:hover { background: #f9fafb; }
    .cmd { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 50vw; }

    /* Status dot */
    .status { margin-left:auto; display:flex; align-items:center; gap:6px; }
    .dot { width:12px; height:12px; border-radius:50%; background:#9ca3af; }
    .dot.alive { background:#28c840; animation: pulse 2s infinite; }
    .dot.idle { background:#f59e0b; }
    .dot.dead { background:#ef4444; }
    @keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(40,200,64,0.6);} 70% { box-shadow: 0 0 0 10px rgba(40,200,64,0);} 100% { box-shadow: 0 0 0 0 rgba(40,200,64,0);} }
  </style>
</head>
<body>
  <header>
    <h1>VSCode Dashboard <span class="sub" id="stamp">loading…</span></h1>
  </header>
  <main>
    <div class="grid" id="widgets">
      <div class="card"><h3>VSCode Processes</h3><div class="metric" id="w-proc">—</div><div class="muted" id="w-roots">— roots</div></div>
      <div class="card"><h3>Top CPU</h3><div class="metric" id="w-cpu">—</div><div class="muted" id="w-cpu-name">—</div></div>
      <div class="card"><h3>Top Memory</h3><div class="metric" id="w-mem">—</div><div class="muted" id="w-mem-name">—</div></div>
      <div class="card" id="gpu-slot-0"><h3>GPU</h3><div class="metric" id="w-gpu-util">—</div><div class="bar"><span id="w-gpu-bar" style="width:0%"></span></div><div class="muted" id="w-gpu-mem">—</div></div>
    </div>

    <div class="toolbar">
      <div class="search"><input id="filter" placeholder="Фильтр по команде/имени/PID…" autofocus></div>
      <select id="scope" style="padding:8px 10px; border:1px solid var(--border); border-radius:10px; background:#fff;">
        <option value="vscode">Scope: VSCode</option>
        <option value="project">Scope: Project</option>
        <option value="all">Scope: All</option>
      </select>
      <select id="state" style="padding:8px 10px; border:1px solid var(--border); border-radius:10px; background:#fff;">
        <option value="all">State: All</option>
        <option value="working">State: Working</option>
        <option value="sleeping">State: Sleeping</option>
      </select>
      <select id="groupby" style="padding:8px 10px; border:1px solid var(--border); border-radius:10px; background:#fff;">
        <option value="none">Group: None</option>
        <option value="role">Group: Role</option>
        <option value="project">Group: Project</option>
        <option value="root">Group: Root</option>
      </select>
      <input id="token" placeholder="token (опционально для действий)" style="width:240px; padding: 8px 10px; border: 1px solid var(--border); border-radius: 10px; background: #fff;" />
      <div class="pill" id="summary">—</div>
    </div>

    <div id="ggrid" class="pgrid"></div>

    <div class="pgrid" id="pgrid"></div>

    <table>
      <thead><tr><th>PID</th><th>Name</th><th>CPU%</th><th>RSS MiB</th><th>User</th><th>State</th><th>Started</th><th>Command</th></tr></thead>
      <tbody id="rows"><tr><td colspan="7">loading…</td></tr></tbody>
    </table>
  </main>

  <script>
    const rowsEl = document.getElementById('rows');
    const stampEl = document.getElementById('stamp');
    const filterEl = document.getElementById('filter');
    const tokenEl = document.getElementById('token');
    const groupEl = document.getElementById('groupby');
    const scopeEl = document.getElementById('scope');
    const stateEl = document.getElementById('state');
    tokenEl.value = localStorage.getItem('dash_token') || '';
    tokenEl.addEventListener('change', ()=> localStorage.setItem('dash_token', tokenEl.value));
    groupEl.value = localStorage.getItem('dash_groupby') || 'none';
    groupEl.addEventListener('change', ()=> { localStorage.setItem('dash_groupby', groupEl.value); render(lastSnap); });
    scopeEl.value = localStorage.getItem('dash_scope') || 'vscode';
    scopeEl.addEventListener('change', ()=> { localStorage.setItem('dash_scope', scopeEl.value); window.groupSel=null; tick(); });
    stateEl.value = localStorage.getItem('dash_state') || 'all';
    stateEl.addEventListener('change', ()=> { localStorage.setItem('dash_state', stateEl.value); render(lastSnap); });

    function flatten(tree, out=[]) {
      for (const n of tree) {
        out.push(n);
        if (n.children) flatten(n.children, out);
      }
      return out;
    }

    function humanMiB(x){ return (x/1024/1024).toFixed(1) + ' MiB'; }

    let lastSnap = null;
    function render(snap){
      lastSnap = snap;
      const all = (snap.nodes && snap.nodes.length) ? snap.nodes : flatten(snap.tree, []);
      const roots = snap.tree.length;
      // Widgets
      document.getElementById('w-proc').textContent = all.length;
      document.getElementById('w-roots').textContent = roots + ' roots';
      const topCpu = all.slice().sort((a,b)=> (b.cpu||0)-(a.cpu||0))[0] || {};
      document.getElementById('w-cpu').textContent = (topCpu.cpu||0).toFixed(1)+'%';
      document.getElementById('w-cpu-name').textContent = (topCpu.name||'') + ' · PID ' + (topCpu.pid||'');
      const topMem = all.slice().sort((a,b)=> (b.mem||0)-(a.mem||0))[0] || {};
      document.getElementById('w-mem').textContent = humanMiB(topMem.mem||0);
      document.getElementById('w-mem-name').textContent = (topMem.name||'') + ' · PID ' + (topMem.pid||'');
      if ((snap.gpu||[]).length){
        const g = snap.gpu[0];
        document.getElementById('w-gpu-util').textContent = g.util + '%';
        document.getElementById('w-gpu-bar').style.width = (g.util||0) + '%';
        document.getElementById('w-gpu-mem').textContent = `${g.mem_used}/${g.mem_total} MiB`;
      } else {
        document.getElementById('gpu-slot-0').style.display = 'none';
      }

      // Group cards
      const ggrid = document.getElementById('ggrid');
      const gby = groupEl.value;
      function fmtMiB(x){ return (x/1024/1024).toFixed(0)+' MiB'; }
      function groupCards(kind){
        const G = (snap.groups && snap.groups[kind]) ? snap.groups[kind] : {};
        const entries = Object.entries(G);
        if (!entries.length) { ggrid.innerHTML = ''; return; }
        const html = entries.map(([name, m])=>{
          const active = (name===window.groupSel)?' style="outline:2px solid var(--accent)"':'';
          return `
            <div class="p-card"${active} onclick="(window.groupSel==='${name}'?window.groupSel=null:window.groupSel='${name}'); render(lastSnap);" title="${name}">
              <div class="p-titlebar"><div class="p-title">${name}</div></div>
              <div class="p-body">
                <div class="row kv">Count <b>${m.count}</b> · Alive <b>${m.alive}</b></div>
                <div class="row kv">CPU <b>${m.cpu.toFixed(1)}%</b></div>
                <div class="row kv">RAM <b>${fmtMiB(m.mem)}</b> · GPU <b>${m.gpu} MiB</b></div>
              </div>
            </div>`; }).join('');
        ggrid.innerHTML = html;
      }
      if (gby==='role' || gby==='project' || gby==='root'){ groupCards(gby); } else { ggrid.innerHTML=''; window.groupSel=null; }

      // Mini-windows (cards) render with filter
      const q = (filterEl.value||'').toLowerCase();
      const match = (n)=> !q || String(n.pid).includes(q) || (n.name||'').toLowerCase().includes(q) || (n.cmd||'').toLowerCase().includes(q);
      const pgrid = document.getElementById('pgrid');
      const esc = (s)=> (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;');
      const card = (n)=> {
        const mem = (n.mem/1024/1024).toFixed(1);
        const cpu = (n.cpu||0).toFixed(1);
        const stat = (n.status||'').toLowerCase();
        const cls = n.alive ? 'alive' : (stat==='zombie' ? 'dead' : 'idle');
        const label = n.alive ? 'alive' : (stat||'idle');
        return `
        <div class="p-card" data-pid="${n.pid}">
          <div class="p-titlebar">
            <div class="lights"><span class="light red"></span><span class="light yellow"></span><span class="light green"></span></div>
            <div class="p-title">${esc(n.name)} · PID ${n.pid}</div>
            <div class="status"><span class="dot ${cls}"></span><span class="muted">${label}</span></div>
          </div>
          <div class="p-body">
            <div class="row kv">CPU <b>${cpu}%</b> · RSS <b>${mem} MiB</b></div>
            <div class="row kv">User ${esc(n.user)} · PPID ${n.ppid}</div>
            <div class="row kv">Started ${esc(n.start)} · State ${esc(n.status)}</div>
            <div class="row mono" title="${esc(n.cmd)}">${esc(n.cmd)}</div>
            <div class="actions">
              <button onclick="copyCmd(${n.pid})">Copy cmd</button>
              <button onclick="sendSig(${n.pid}, 'TERM')">SIGTERM</button>
              <button class="danger" onclick="sendSig(${n.pid}, 'KILL')">KILL</button>
            </div>
          </div>
        </div>`;
      };
      let list = all.filter(match);
      // State filter (working/sleeping)
      const state = (stateEl.value||'all');
      const CPU_THR = 1.0; // percent
      const isWorking = (n)=> ( (n.cpu||0) >= CPU_THR ) || ['running','disk-sleep','waking','waiting'].includes((n.status||'').toLowerCase());
      const isSleeping = (n)=> ['sleeping','idle'].includes((n.status||'').toLowerCase()) && ( (n.cpu||0) < CPU_THR );
      if (state === 'working') list = list.filter(isWorking);
      else if (state === 'sleeping') list = list.filter(isSleeping);
      if (gby==='role'){ list = list.filter(n=> (window.groupSel? (n.role===window.groupSel) : true)); }
      else if (gby==='project'){ list = list.filter(n=> (window.groupSel? ((n.project? 'AiPIK':'Other')===window.groupSel) : true)); }
      else if (gby==='root'){ list = list.filter(n=> (window.groupSel? (n.root_label===window.groupSel) : true)); }
      pgrid.innerHTML = list.map(card).join('') || '<div class="muted">Нет процессов</div>';

      // Table render (same filter)
      const fmt = (n)=> `
        <tr>
          <td>${n.pid}</td>
          <td>${n.name||''}</td>
          <td>${(n.cpu||0).toFixed(1)}</td>
          <td>${(n.mem/1024/1024).toFixed(1)}</td>
          <td>${n.user||''}</td>
          <td>${n.status||''}</td>
          <td>${n.start||''}</td>
          <td class="cmd">${(n.cmd||'').replace(/</g,'&lt;')}</td>
        </tr>`;
      const htmlRows = list.map(fmt).join('');
      rowsEl.innerHTML = htmlRows || '<tr><td colspan="7" class="muted">Нет совпадений</td></tr>';

      stampEl.textContent = `updated ${new Date().toLocaleTimeString()} · ${snap.count} procs`;
      document.getElementById('summary').textContent = `GPU: ${(snap.gpu&&snap.gpu[0])?snap.gpu[0].util+'%':''} · roots: ${roots} · shown: ${list.length}`;
    }

    async function tick(){
      try{
        const sc = encodeURIComponent(scopeEl.value || 'vscode');
        const r = await fetch('/api/processes?scope='+sc);
        const j = await r.json();
        render(j);
      }catch(e){/* ignore */}
      setTimeout(tick, 2000);
    }
    filterEl.addEventListener('input', ()=>tick());
    tick();

    // Actions
    function token(){ return tokenEl.value || localStorage.getItem('dash_token') || ''; }
    window.copyCmd = (pid)=>{
      const el = document.querySelector(`.p-card[data-pid="${pid}"] .mono`);
      if (el) navigator.clipboard.writeText(el.getAttribute('title') || el.textContent || '');
    };
    window.sendSig = async (pid, sig)=>{
      if (!confirm(`Отправить SIG${sig} процессу ${pid}?`)) return;
      const t = token();
      try{
        const r = await fetch('/api/signal' + (t?`?token=${encodeURIComponent(t)}`:''), {
          method: 'POST', headers: {'Content-Type':'application/json','X-Token':t},
          body: JSON.stringify({pid: pid, sig: sig})
        });
        if (!r.ok){ const j = await r.json().catch(()=>({error:r.statusText})); alert('Ошибка: '+(j.error||r.status)); return; }
      }catch(e){ alert('Ошибка запроса'); }
    };
  </script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser(description="VSCode-related process dashboard (web)")
    ap.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    ap.add_argument("--port", type=int, default=18080, help="Bind port (default: 18080)")
    args = ap.parse_args()

    app.run(host=args.host, port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
