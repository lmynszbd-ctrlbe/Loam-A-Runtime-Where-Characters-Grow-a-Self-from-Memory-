#!/usr/bin/env python3
"""loam admin panel — 可视化管理面板，纯标准库。

Usage:
  python scripts/admin.py
  → http://127.0.0.1:8899
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import urllib.request
import urllib.error
import os
import time
from pathlib import Path

LOAM = os.environ.get("LOAM_URL", "http://127.0.0.1:8765").rstrip("/")
PORT = int(os.environ.get("ADMIN_PORT", "8899"))
SECRETS_HOME = Path(os.environ.get("LOAM_SECRETS_HOME", "~/.loam")).expanduser()
SECRETS_FILE = SECRETS_HOME / "secrets.json"
UPSTREAMS_FILE = SECRETS_HOME / "upstreams.json"


def read_json_file(path):
    """Read a config file. Returns {} if missing, {"_error": ...} on parse error."""
    try:
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return {"_error": str(e)}


def write_json_file(path, data):
    """Write a config file atomically, creating the directory + secure perms."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)
        try:
            os.chmod(path, 0o600)
        except Exception:
            pass
        return {"ok": True, "path": str(path)}
    except Exception as e:
        return {"error": str(e)}



def api(path, method="GET", body=None):
    try:
        if body is not None:
            data = json.dumps(body).encode()
            req = urllib.request.Request(f"{LOAM}{path}", data=data, method=method)
            req.add_header("Content-Type", "application/json")
        else:
            req = urllib.request.Request(f"{LOAM}{path}", method=method)
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>loam · admin</title>
<style>
:root{--bg:#0d1117;--fg:#c9d1d9;--accent:#58a6ff;--warn:#d29922;--err:#f85149;--ok:#3fb950;--card:#161b22;--border:#30363d;--muted:#8b949e;--input-bg:#0d1117}
*{margin:0;padding:0;box-sizing:border-box}
body{font:13px/1.6 -apple-system,BlinkMacSystemFont,sans-serif;background:var(--bg);color:var(--fg);display:flex;min-height:100vh}
nav{width:220px;background:var(--card);border-right:1px solid var(--border);padding:16px 0;flex-shrink:0}
nav .logo{font-size:16px;font-weight:700;color:var(--accent);padding:0 16px 16px;border-bottom:1px solid var(--border);margin-bottom:8px}
nav a{display:block;padding:8px 16px;color:var(--fg);text-decoration:none;font-size:13px;transition:background 0.15s}
nav a:hover,nav a.active{background:var(--border);color:#fff}
main{flex:1;padding:24px;overflow-y:auto;max-height:100vh}
h1{font-size:20px;margin-bottom:4px}
h2{font-size:16px;margin:20px 0 12px;color:var(--accent)}
.sub{color:var(--muted);font-size:12px;margin-bottom:20px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px;margin-bottom:16px}
.card{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:14px}
.card h3{font-size:12px;color:var(--muted);margin-bottom:8px;text-transform:uppercase;letter-spacing:0.5px}
.stat{display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid var(--border);font-size:13px}
.stat:last-child{border-bottom:none}
.val{font-weight:600;font-variant-numeric:tabular-nums}
.ok{color:var(--ok)}.warn{color:var(--warn)}.err{color:var(--err)}.muted{color:var(--muted)}
.bar{height:6px;border-radius:3px;background:var(--border);margin:8px 0;overflow:hidden}
.bar-fill{height:100%;border-radius:3px;transition:width 0.5s}
.bar-fill.ok{background:var(--ok)}.bar-fill.warn{background:var(--warn)}.bar-fill.err{background:var(--err)}
.trait{display:flex;align-items:center;gap:8px;padding:3px 0}
.trait-name{flex:1;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:200px}
.trait-bar{flex:2;height:8px;background:var(--border);border-radius:4px;overflow:hidden}
.trait-fill{height:100%;background:var(--accent);border-radius:4px;transition:width 0.5s}
.trait-val{font-size:11px;color:var(--muted);width:36px;text-align:right}
.trait-phase{font-size:10px;color:var(--muted);width:50px;text-align:right}
.btn{background:var(--accent);color:#fff;border:none;padding:6px 14px;border-radius:6px;cursor:pointer;font-size:13px;transition:opacity 0.15s}
.btn:hover{opacity:0.85}
.btn-sm{font-size:11px;padding:4px 10px}
.btn-danger{background:var(--err)}
.btn-ok{background:var(--ok)}
.btn-outline{background:transparent;border:1px solid var(--border)}
.btn-outline:hover{background:var(--border)}
.actions{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px}
input,textarea,select{background:var(--input-bg);color:var(--fg);border:1px solid var(--border);border-radius:6px;padding:8px 10px;font-size:13px;font-family:inherit;width:100%}
textarea{resize:vertical;min-height:100px;font-family:monospace;font-size:12px}
label{display:block;font-size:12px;color:var(--muted);margin-bottom:4px;margin-top:10px}
.form-group{margin-bottom:10px}
.toast{position:fixed;bottom:20px;right:20px;padding:10px 18px;border-radius:8px;font-size:13px;z-index:999;animation:fadeIn 0.3s}
.toast.ok{background:var(--ok);color:#000}
.toast.err{background:var(--err);color:#fff}
@keyframes fadeIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
.event{font-size:12px;padding:3px 0;border-bottom:1px solid var(--border);display:flex;gap:6px}
.event-dot{width:8px;height:8px;border-radius:50%;margin-top:4px;flex-shrink:0}
.narrative{font-size:13px;line-height:1.7;white-space:pre-wrap;max-height:300px;overflow-y:auto}
.timeline{max-height:400px;overflow-y:auto}
.changelog-entry{font-size:12px;padding:6px 0;border-bottom:1px solid var(--border)}
.changelog-entry .ts{color:var(--muted);margin-right:8px}
.const-row{display:flex;align-items:center;gap:8px;padding:4px 0;border-bottom:1px solid var(--border);font-size:12px}
.const-name{width:200px;font-weight:600;color:var(--accent);flex-shrink:0}
.const-val{width:80px;text-align:right;flex-shrink:0}
.const-desc{flex:1;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.const-input{width:80px;text-align:right;flex-shrink:0;padding:2px 6px}
.panel{display:none}
.panel.active{display:block}
.spinner{display:inline-block;width:14px;height:14px;border:2px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:spin 0.6s linear infinite;margin-right:6px}
@keyframes spin{to{transform:rotate(360deg)}}
</style>
</head>
<body>
<nav>
  <div class="logo">🧠 loam admin</div>
  <a href="#status" class="nav-link active" data-panel="status">📊 Status</a>
  <a href="#traits" class="nav-link" data-panel="traits">🧬 Traits</a>
  <a href="#memory" class="nav-link" data-panel="memory">💾 Memory</a>
  <a href="#config" class="nav-link" data-panel="config">⚙ Config</a>
  <a href="#constants" class="nav-link" data-panel="constants">🔧 Constants</a>
  <a href="#connect" class="nav-link" data-panel="connect">🔌 Connect</a>
  <a href="#actions" class="nav-link" data-panel="actions">▶ Actions</a>
</nav>
<main>
  <div id="toast-container"></div>

  <!-- STATUS -->
  <div id="panel-status" class="panel active">
    <h1>📊 Status</h1>
    <div class="sub" id="status-time">loading...</div>
    <div class="grid" id="status-grid"></div>
    <div class="card"><h3>🧬 Traits</h3><div id="status-traits"></div></div>
  </div>

  <!-- TRAITS -->
  <div id="panel-traits" class="panel">
    <h1>🧬 Traits</h1>
    <div class="sub">Character traits with strength, phase, and evidence count</div>
    <div class="actions">
      <button class="btn btn-sm" onclick="loadTraits()">🔄 Refresh</button>
    </div>
    <div class="card" id="traits-table"></div>
  </div>

  <!-- MEMORY -->
  <div id="panel-memory" class="panel">
    <h1>💾 Memory</h1>
    <div class="sub">Events, narrative, changelog, and network topology</div>
    <div class="actions">
      <button class="btn btn-sm" onclick="loadMemory()">🔄 Refresh</button>
      <button class="btn btn-sm btn-outline" onclick="loadNarrative()">📝 Narrative</button>
      <button class="btn btn-sm btn-outline" onclick="loadChangelog()">📋 Changelog</button>
      <button class="btn btn-sm btn-outline" onclick="loadNetwork()">🔗 Network</button>
    </div>
    <div id="memory-content"></div>
  </div>

  <!-- CONFIG -->
  <div id="panel-config" class="panel">
    <h1>⚙ Configuration</h1>
    <div class="sub">Edit runtime config, view current settings</div>
    <div class="actions">
      <button class="btn btn-sm" onclick="loadConfig()">🔄 Refresh</button>
    </div>
    <div class="card">
      <h3>Runtime Config</h3>
      <pre id="config-display" style="font-size:12px;max-height:400px;overflow-y:auto"></pre>
    </div>
    <div class="card" style="margin-top:12px">
      <h3>Update Config</h3>
      <div class="form-group">
        <label>JSON updates (merge)</label>
        <textarea id="config-updates" placeholder="{"context.max_matches": 12}"></textarea>
      </div>
      <button class="btn" onclick="updateConfig()">Apply</button>
    </div>
  </div>

  <!-- CONSTANTS -->
  <div id="panel-constants" class="panel">
    <h1>🔧 Constants</h1>
    <div class="sub">48 tunable parameters — hot-override in memory, reset on restart</div>
    <div class="actions">
      <button class="btn btn-sm" onclick="loadConstants()">🔄 Refresh</button>
      <button class="btn btn-sm btn-ok" onclick="applyConstants()">💾 Apply Overrides</button>
    </div>
    <div class="card" id="constants-list"></div>
  </div>

  <!-- CONNECT -->
  <div id="panel-connect" class="panel">
    <h1>🔌 Connect Your Client</h1>
    <div class="sub">Paste these into any OpenAI-compatible chat app (SillyTavern, Open WebUI, etc.)</div>
    <div class="grid">
      <div class="card">
        <h3>🔗 API Endpoint</h3>
        <div style="background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:12px;font-family:monospace;font-size:16px;text-align:center;margin:8px 0">
          http://127.0.0.1:8780/v1
        </div>
        <p class="muted" style="font-size:12px">This is your <strong>Base URL</strong> / <strong>API Host</strong> in the client settings.</p>
      </div>
      <div class="card">
        <h3>🔑 API Key</h3>
        <div style="background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:12px;font-family:monospace;font-size:16px;text-align:center;margin:8px 0">
          local-key
        </div>
        <p class="muted" style="font-size:12px">Anything works. The real auth is handled by your upstream provider.</p>
      </div>
      <div class="card">
        <h3>🤖 Model Name</h3>
        <div style="background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:12px;font-family:monospace;font-size:16px;text-align:center;margin:8px 0">
          relayA/deepseek-chat
        </div>
        <p class="muted" style="font-size:12px">Format: <code>provider/model</code>. Change based on your upstreams below.</p>
      </div>
    </div>

    <h2 style="margin-top:24px">🔧 Set Your API Keys</h2>
    <div class="sub">loam uses <strong>two</strong> separate keys. Fill in both, click Save, then restart to apply.</div>
    <div class="actions">
      <button class="btn btn-sm" onclick="loadApiConfig()">🔄 Reload from disk</button>
    </div>

    <div class="grid" style="grid-template-columns:1fr 1fr">
      <!-- secrets.json = loam digestion model -->
      <div class="card">
        <h3>💾 loam memory model — secrets.json</h3>
        <p class="muted" style="font-size:12px;margin-bottom:8px">The model loam uses to <strong>digest conversations into memory</strong> (background work, cheaper model is fine).</p>
        <div class="form-group">
          <label>API Key</label>
          <input id="sec-key" placeholder="sk-...">
        </div>
        <div class="form-group">
          <label>Base URL</label>
          <input id="sec-url" placeholder="https://api.deepseek.com">
        </div>
        <div class="form-group">
          <label>Model</label>
          <input id="sec-model" placeholder="deepseek-chat">
        </div>
        <button class="btn btn-ok" onclick="saveSecrets()">💾 Save secrets.json</button>
        <div id="sec-status" style="margin-top:8px;font-size:12px" class="muted"></div>
      </div>

      <!-- upstreams.json = chat model -->
      <div class="card">
        <h3>💬 Chat model — upstreams.json</h3>
        <p class="muted" style="font-size:12px;margin-bottom:8px">The model your chat client talks to (the <strong>replies you see</strong>). This is the "relayA" provider.</p>
        <div class="form-group">
          <label>Provider name</label>
          <input id="up-name" placeholder="relayA" value="relayA">
        </div>
        <div class="form-group">
          <label>API Key</label>
          <input id="up-key" placeholder="sk-...">
        </div>
        <div class="form-group">
          <label>Base URL</label>
          <input id="up-url" placeholder="https://api.deepseek.com">
        </div>
        <div class="form-group">
          <label>Default Model</label>
          <input id="up-model" placeholder="deepseek-chat">
        </div>
        <button class="btn btn-ok" onclick="saveUpstream()">💾 Save upstreams.json</button>
        <div id="up-status" style="margin-top:8px;font-size:12px" class="muted"></div>
      </div>
    </div>
    <div class="card" style="margin-top:12px">
      <p class="muted" style="font-size:12px">⚠ Changes are written to <code id="cfg-home">~/.loam</code>. loam reads these <strong>at startup</strong> — after saving, restart from the Actions tab or your terminal for them to take effect. Advanced multi-provider editing: edit <code>upstreams.json</code> directly (see raw view below).</p>
      <div class="form-group" style="margin-top:8px">
        <label>Raw upstreams.json (advanced — full multi-provider control)</label>
        <textarea id="up-raw" style="min-height:140px"></textarea>
      </div>
      <button class="btn" onclick="saveUpstreamRaw()">💾 Save raw upstreams.json</button>
      <div id="up-raw-status" style="margin-top:8px;font-size:12px" class="muted"></div>
    </div>
  </div>

  <!-- ACTIONS -->
  <div id="panel-actions" class="panel">
    <h1>▶ Actions</h1>
    <div class="sub">Manual operations</div>
    <div class="grid">
      <div class="card">
        <h3>🧪 Digest</h3>
        <p class="muted" style="font-size:12px;margin-bottom:8px">Run one digestion cycle</p>
        <button class="btn" onclick="doAction('digest')">Run Digest</button>
        <div id="digest-result" style="margin-top:8px;font-size:12px"></div>
      </div>
      <div class="card">
        <h3>🚰 Drain</h3>
        <p class="muted" style="font-size:12px;margin-bottom:8px">Process all queued turns</p>
        <button class="btn" onclick="doAction('drain')">Run Drain</button>
        <div id="drain-result" style="margin-top:8px;font-size:12px"></div>
      </div>
      <div class="card">
        <h3>📸 Snapshot</h3>
        <p class="muted" style="font-size:12px;margin-bottom:8px">Export living character card</p>
        <button class="btn" onclick="doAction('snapshot')">Export</button>
        <div id="snapshot-result" style="margin-top:8px;font-size:12px"></div>
      </div>
      <div class="card">
        <h3>🔄 Recompute</h3>
        <p class="muted" style="font-size:12px;margin-bottom:8px">Rebuild from journal</p>
        <button class="btn btn-danger" onclick="doAction('recompute')">Recompute</button>
        <div id="recompute-result" style="margin-top:8px;font-size:12px"></div>
      </div>
    </div>
  </div>
</main>

<script>
const API = '/api/proxy';

async function call(method, path, body) {
  const opts = {method};
  if (body) {
    opts.headers = {'Content-Type': 'application/json'};
    opts.body = JSON.stringify(body);
  }
  const r = await fetch(API + path, opts);
  return r.json();
}

function toast(msg, cls) {
  const t = document.createElement('div');
  t.className = 'toast ' + (cls||'ok');
  t.textContent = msg;
  document.getElementById('toast-container').appendChild(t);
  setTimeout(() => t.remove(), 3000);
}

// ---- navigation ----
document.querySelectorAll('.nav-link').forEach(a => {
  a.addEventListener('click', e => {
    e.preventDefault();
    document.querySelectorAll('.nav-link').forEach(x => x.classList.remove('active'));
    a.classList.add('active');
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    document.getElementById('panel-' + a.dataset.panel).classList.add('active');
    const fn = 'load' + a.dataset.panel.charAt(0).toUpperCase() + a.dataset.panel.slice(1);
    if (typeof window[fn] === 'function') window[fn]();
  });
});

// ---- STATUS ----
async function loadStatus() {
  const [stats, healthz] = await Promise.all([
    call('GET', '/stats'), call('GET', '/healthz')
  ]);
  document.getElementById('status-time').textContent = new Date().toLocaleString();

  const mem = stats.memory || {};
  const grid = document.getElementById('status-grid');
  grid.innerHTML = `
    <div class="card"><h3>📊 Overview</h3>
      <div class="stat"><span>Character</span><span class="val">${esc(stats.character||'-')}</span></div>
      <div class="stat"><span>Cycle</span><span class="val">${mem['周期']||'-'}</span></div>
      <div class="stat"><span>Grower</span><span class="val ${(stats.grower_alive?'ok':'err')}">${stats.grower_alive?'● Running':'● Stopped'}</span></div>
      <div class="stat"><span>Pending</span><span class="val">${stats.pending||0}</span></div>
    </div>
    <div class="card"><h3>💾 Storage</h3>
      <div class="stat"><span>Events</span><span class="val">${mem['事件']||0}</span></div>
      <div class="stat"><span>Traits</span><span class="val">${mem['特质']||0}</span></div>
      <div class="stat"><span>Kernel</span><span class="val ok">${mem['内核']||0}</span></div>
      <div class="stat"><span>Edges</span><span class="val">${mem['连线']||0}</span></div>
    </div>
    <div class="card"><h3>📝 Content</h3>
      <div class="stat"><span>Narratives</span><span class="val">${mem['自述版本']||0}</span></div>
      <div class="stat"><span>Changelog</span><span class="val">${mem['变更记录']||0}</span></div>
      <div class="stat"><span>Health</span><span class="val ${(healthz.ok?'ok':'err')}">${healthz.ok?'✓ OK':'✗ Error'}</span></div>
    </div>
  `;

  // Traits mini
  const ctx = await call('GET', '/context?q=status');
  const traits = (ctx.context||{}).traits||[];
  document.getElementById('status-traits').innerHTML = traits.length
    ? traits.map(t => {
        const s = (t.strength||0)*100;
        return `<div class="trait"><span class="trait-name">${esc(t.text||'?')}</span>
          <div class="trait-bar"><div class="trait-fill" style="width:${s}%"></div></div>
          <span class="trait-val">${s.toFixed(0)}%</span></div>`;
      }).join('')
    : '<span class="muted">No traits yet. Chat more to grow some.</span>';
}

// ---- TRAITS ----
async function loadTraits() {
  const ctx = await call('GET', '/context?q=status');
  const traits = (ctx.context||{}).traits||[];
  const explain = await call('GET', '/explain?kind=trait&limit=50');
  const changes = explain.changes||[];

  document.getElementById('traits-table').innerHTML = traits.length
    ? `<table style="width:100%;border-collapse:collapse;font-size:12px">
      <tr style="border-bottom:1px solid var(--border);color:var(--muted);text-align:left">
        <th style="padding:6px">Trait</th><th>Strength</th><th>Phase</th><th>Evidence</th><th>Kernel</th>
      </tr>
      ${traits.map(t => {
        const s = (t.strength||0)*100;
        const phase = t.phase||'?';
        const ev = t.evidence_count||0;
        const kernel = t.is_kernel ? '⭐' : '';
        return `<tr style="border-bottom:1px solid var(--border)">
          <td style="padding:6px">${esc(t.text||'?')}</td>
          <td><div class="trait-bar" style="width:120px"><div class="trait-fill" style="width:${s}%"></div></div> ${s.toFixed(0)}%</td>
          <td>${phase}</td><td>${ev}</td><td>${kernel}</td>
        </tr>`;
      }).join('')}
    </table>`
    : '<span class="muted">No traits yet.</span>';
}

// ---- MEMORY ----
async function loadMemory() {
  const [ctx, narr] = await Promise.all([
    call('GET', '/context?q=status'),
    call('GET', '/narrative')
  ]);
  const events = (ctx.context||{}).events||[];
  document.getElementById('memory-content').innerHTML = events.length
    ? `<h2>Recent Events (${events.length})</h2>
      <div class="timeline">${events.slice(0,30).map(e => {
        const v = (e.valence||0);
        const c = v>0.2?'#3fb950':v<-0.2?'#f85149':'#8b949e';
        return `<div class="event"><div class="event-dot" style="background:${c}"></div>
          <span>${esc(e.summary||'?')}</span></div>`;
      }).join('')}</div>`
    : '<span class="muted">No events yet.</span>';
}
async function loadNarrative() {
  const narr = await call('GET', '/narrative');
  document.getElementById('memory-content').innerHTML = `<h2>Self-Narrative</h2>
    <div class="card"><div class="narrative">${esc(narr.text||'No narrative yet.')}</div></div>`;
}
async function loadChangelog() {
  const explain = await call('GET', '/explain?kind=trait&limit=50');
  const changes = explain.changes||[];
  document.getElementById('memory-content').innerHTML = `<h2>Changelog (${changes.length})</h2>
    <div class="timeline">${changes.map(c => `
      <div class="changelog-entry">
        <span class="ts">${c.when||'?'}</span>
        <strong>${esc(c.target||'?')}</strong>
        <span class="muted">${esc(c.reason||'')}</span>
        ${c.before ? `<span class="muted"> | ${c.before} → ${c.after}</span>` : ''}
      </div>`).join('')}</div>`;
}
async function loadNetwork() {
  const net = await call('GET', '/network?limit=50');
  document.getElementById('memory-content').innerHTML = `
    <h2>Network Topology</h2>
    <div class="grid">
      <div class="card"><h3>Nodes</h3><div class="val ok">${net.total_nodes||0}</div></div>
      <div class="card"><h3>Edges</h3><div class="val">${net.total_edges||0}</div></div>
    </div>
    <div class="card" style="margin-top:12px">
      <h3>Top Nodes by Weight</h3>
      ${(net.nodes||[]).slice(0,20).map(n => `
        <div class="stat"><span style="font-size:11px;max-width:300px;overflow:hidden;text-overflow:ellipsis">${esc(n.id||'?')}</span>
        <span class="val">${(n.weight||0).toFixed(4)}</span></div>
      `).join('')}
    </div>`;
}

// ---- CONFIG ----
async function loadConfig() {
  const cfg = await call('GET', '/config');
  document.getElementById('config-display').textContent = JSON.stringify(cfg, null, 2);
}
async function updateConfig() {
  try {
    const updates = JSON.parse(document.getElementById('config-updates').value);
    const r = await call('POST', '/config/update', {updates, note: 'admin panel'});
    toast('Config updated', 'ok');
    loadConfig();
  } catch(e) {
    toast('Error: ' + e.message, 'err');
  }
}

// ---- CONSTANTS ----
async function loadConstants() {
  const data = await call('GET', '/constants');
  const consts = data.constants||{};
  const overrides = data.overrides||{};
  const keys = Object.keys(consts).sort();
  document.getElementById('constants-list').innerHTML = keys.map(k => {
    const v = consts[k];
    const ov = overrides[k];
    const isOverridden = !!ov;
    return `<div class="const-row" style="${isOverridden?'background:rgba(88,166,255,0.1)':''}">
      <span class="const-name">${k}</span>
      <input class="const-input" data-name="${k}" value="${isOverridden?ov.override:v}" style="${isOverridden?'border-color:var(--accent)':''}">
      <span class="const-val">${isOverridden?`<span class="warn">${ov.original}→${ov.override}</span>`:v}</span>
      <span class="const-desc">${isOverridden?'⚡ overridden':''}</span>
    </div>`;
  }).join('');
}
async function applyConstants() {
  const overrides = {};
  document.querySelectorAll('.const-input').forEach(inp => {
    const name = inp.dataset.name;
    const val = parseFloat(inp.value);
    if (!isNaN(val)) overrides[name] = val;
  });
  const r = await call('POST', '/constants', {overrides});
  const n = Object.keys(r.applied||{}).length;
  toast(`${n} constants applied`, 'ok');
  loadConstants();
}

// ---- CONNECT / API KEYS ----
async function loadApiConfig() {
  try {
    const cfg = await call('GET', '/admin/config');  // served by admin panel itself
    // secrets
    const s = cfg.secrets || {};
    document.getElementById('sec-key').value = s.api_key || '';
    document.getElementById('sec-url').value = s.base_url || '';
    document.getElementById('sec-model').value = s.model || '';
    // upstreams
    const u = cfg.upstreams || {};
    const providers = u.providers || {};
    const defName = u.default || Object.keys(providers)[0] || 'relayA';
    const p = providers[defName] || {};
    document.getElementById('up-name').value = defName;
    document.getElementById('up-key').value = p.api_key || '';
    document.getElementById('up-url').value = p.base_url || '';
    document.getElementById('up-model').value = p.default_model || '';
    document.getElementById('up-raw').value = Object.keys(u).length ? JSON.stringify(u, null, 2) : '';
    if (cfg.home) document.getElementById('cfg-home').textContent = cfg.home;
  } catch(e) {
    toast('Could not load config: ' + e.message, 'err');
  }
}

async function saveSecrets() {
  const body = {
    api_key: document.getElementById('sec-key').value.trim(),
    base_url: document.getElementById('sec-url').value.trim(),
    model: document.getElementById('sec-model').value.trim(),
  };
  if (!body.api_key || !body.base_url || !body.model) {
    toast('Fill in all three fields', 'err'); return;
  }
  const r = await call('POST', '/admin/secrets', body);
  const el = document.getElementById('sec-status');
  if (r.ok) { el.innerHTML = '<span class="ok">✓ saved to '+esc(r.path)+' — restart loam to apply</span>'; toast('secrets.json saved', 'ok'); }
  else { el.innerHTML = '<span class="err">'+esc(r.error||'failed')+'</span>'; toast('save failed', 'err'); }
}

async function saveUpstream() {
  const name = document.getElementById('up-name').value.trim() || 'relayA';
  const body = {
    name,
    api_key: document.getElementById('up-key').value.trim(),
    base_url: document.getElementById('up-url').value.trim(),
    default_model: document.getElementById('up-model').value.trim(),
  };
  if (!body.api_key || !body.base_url || !body.default_model) {
    toast('Fill in all fields', 'err'); return;
  }
  const r = await call('POST', '/admin/upstream', body);
  const el = document.getElementById('up-status');
  if (r.ok) {
    el.innerHTML = '<span class="ok">✓ saved to '+esc(r.path)+' — restart proxy to apply</span>';
    toast('upstreams.json saved', 'ok');
    loadApiConfig();
  } else { el.innerHTML = '<span class="err">'+esc(r.error||'failed')+'</span>'; toast('save failed', 'err'); }
}

async function saveUpstreamRaw() {
  let parsed;
  try { parsed = JSON.parse(document.getElementById('up-raw').value); }
  catch(e) { toast('Invalid JSON: ' + e.message, 'err'); return; }
  const r = await call('POST', '/admin/upstream-raw', parsed);
  const el = document.getElementById('up-raw-status');
  if (r.ok) { el.innerHTML = '<span class="ok">✓ saved to '+esc(r.path)+' — restart proxy to apply</span>'; toast('upstreams.json saved', 'ok'); loadApiConfig(); }
  else { el.innerHTML = '<span class="err">'+esc(r.error||'failed')+'</span>'; toast('save failed', 'err'); }
}

// alias so nav auto-loader (loadConnect) works when the tab opens
function loadConnect() { loadApiConfig(); }

// ---- ACTIONS ----
async function doAction(action) {
  const el = document.getElementById(action+'-result');
  el.innerHTML = '<span class="spinner"></span> running...';
  try {
    let r;
    switch(action) {
      case 'digest': r = await call('POST', '/digest', {limit: 20}); break;
      case 'drain': r = await call('POST', '/drain', {max_rounds: 50}); break;
      case 'snapshot':
        r = {message: 'Snapshot not available via API. Use CLI: python -m loam snapshot'};
        break;
      case 'recompute':
        r = {message: 'Recompute not available via API. Use CLI.'};
        break;
    }
    el.innerHTML = `<pre style="font-size:11px;max-height:200px;overflow-y:auto">${JSON.stringify(r,null,2)}</pre>`;
    toast(action + ' done', 'ok');
  } catch(e) {
    el.innerHTML = `<span class="err">${esc(e.message)}</span>`;
    toast(action + ' failed: ' + e.message, 'err');
  }
}

function esc(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

// ---- init ----
loadStatus();
</script>
</body>
</html>"""

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self._html(HTML)
        elif self.path == "/admin/config":
            self._json(self._read_config())
        elif self.path.startswith("/api/proxy"):
            self._proxy("GET")
        else:
            self._send(404, "not found")

    def do_POST(self):
        if self.path == "/admin/secrets":
            self._json(self._save_secrets())
        elif self.path == "/admin/upstream":
            self._json(self._save_upstream())
        elif self.path == "/admin/upstream-raw":
            self._json(self._save_upstream_raw())
        elif self.path.startswith("/api/proxy"):
            self._proxy("POST")
        else:
            self._send(404, "not found")

    # ---- config file handlers (admin owns these, not the loam backend) ----
    def _read_body(self):
        cl = int(self.headers.get("Content-Length", 0))
        if not cl:
            return {}
        try:
            return json.loads(self.rfile.read(cl))
        except Exception:
            return {}

    def _read_config(self):
        secrets = read_json_file(SECRETS_FILE)
        upstreams = read_json_file(UPSTREAMS_FILE)
        # never surface a parse error as if it were config content
        if isinstance(secrets, dict) and "_error" in secrets:
            secrets = {}
        if isinstance(upstreams, dict) and "_error" in upstreams:
            upstreams = {}
        return {"secrets": secrets, "upstreams": upstreams, "home": str(SECRETS_HOME)}

    def _save_secrets(self):
        body = self._read_body()
        data = {
            "api_key": (body.get("api_key") or "").strip(),
            "base_url": (body.get("base_url") or "").strip(),
            "model": (body.get("model") or "").strip(),
        }
        if not (data["api_key"] and data["base_url"] and data["model"]):
            return {"error": "api_key, base_url and model are all required"}
        return write_json_file(SECRETS_FILE, data)

    def _save_upstream(self):
        """Merge/update a single provider inside upstreams.json, preserving others."""
        body = self._read_body()
        name = (body.get("name") or "relayA").strip() or "relayA"
        provider = {
            "base_url": (body.get("base_url") or "").strip(),
            "api_key": (body.get("api_key") or "").strip(),
            "default_model": (body.get("default_model") or "").strip(),
        }
        if not (provider["base_url"] and provider["api_key"] and provider["default_model"]):
            return {"error": "base_url, api_key and default_model are all required"}
        current = read_json_file(UPSTREAMS_FILE)
        if not isinstance(current, dict) or "_error" in current:
            current = {}
        providers = current.get("providers")
        if not isinstance(providers, dict):
            providers = {}
        providers[name] = provider
        current["providers"] = providers
        current.setdefault("default", name)
        return write_json_file(UPSTREAMS_FILE, current)

    def _save_upstream_raw(self):
        body = self._read_body()
        if not isinstance(body, dict) or not body:
            return {"error": "expected a non-empty JSON object"}
        if "providers" not in body or not isinstance(body.get("providers"), dict):
            return {"error": "upstreams.json must contain a 'providers' object"}
        return write_json_file(UPSTREAMS_FILE, body)

    def _proxy(self, method):
        path = self.path.replace("/api/proxy", "")
        body = None
        if method == "POST":
            cl = int(self.headers.get("Content-Length", 0))
            if cl:
                body = json.loads(self.rfile.read(cl))
        result = api(path, method, body)
        self._json(result)

    def _json(self, data):
        b = json.dumps(data, ensure_ascii=False).encode()
        self._send_bytes(200, "application/json", b)

    def _html(self, content):
        self._send_bytes(200, "text/html; charset=utf-8", content.encode())

    def _send(self, code, text):
        self._send_bytes(code, "text/plain", text.encode())

    def _send_bytes(self, code, ct, b):
        self.send_response(code)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, *a): pass


def main():
    print(f"loam admin panel → http://127.0.0.1:{PORT}")
    print(f"loam backend → {LOAM}")
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()