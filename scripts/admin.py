#!/usr/bin/env python3
"""loam admin panel — 可视化管理面板，纯标准库。

Usage:
  python scripts/admin.py
  → http://127.0.0.1:8899
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import importlib
import subprocess
import sys
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
.light{--bg:#f6f8fa;--fg:#24292f;--accent:#0969da;--warn:#9a6700;--err:#cf222e;--ok:#1a7f37;--card:#ffffff;--border:#d0d7de;--muted:#656d76;--input-bg:#ffffff}
*{margin:0;padding:0;box-sizing:border-box}
body{font:13px/1.6 -apple-system,BlinkMacSystemFont,sans-serif;background:var(--bg);color:var(--fg);display:flex;min-height:100vh}
nav{width:220px;background:var(--card);border-right:1px solid var(--border);padding:16px 0;flex-shrink:0;z-index:10}
nav .logo{font-size:16px;font-weight:700;color:var(--accent);padding:0 16px 16px;border-bottom:1px solid var(--border);margin-bottom:8px;display:flex;justify-content:space-between;align-items:center}
nav .logo .theme-btn{background:none;border:1px solid var(--border);color:var(--fg);border-radius:4px;padding:2px 6px;cursor:pointer;font-size:12px}
nav .logo .theme-btn:hover{background:var(--border)}
nav a{display:block;padding:8px 16px;color:var(--fg);text-decoration:none;font-size:13px;transition:background 0.15s}
nav a:hover,nav a.active{background:var(--border);color:var(--fg)}
main{flex:1;padding:24px;overflow-y:auto;max-height:100vh}
h1{font-size:20px;margin-bottom:4px}
h2{font-size:16px;margin:20px 0 12px;color:var(--accent)}
.sub{color:var(--muted);font-size:12px;margin-bottom:20px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px;margin-bottom:16px}
.card{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:14px}
.card h3{font-size:12px;color:var(--muted);margin-bottom:8px;text-transform:uppercase;letter-spacing:0.5px;font-weight:600}
.stat{display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid var(--border);font-size:13px}
.stat:last-child{border-bottom:none}
.val{font-weight:600;font-variant-numeric:tabular-nums}
.ok{color:var(--ok)}.warn{color:var(--warn)}.err{color:var(--err)}.muted{color:var(--muted)}
.btn{background:var(--accent);color:#fff;border:none;padding:6px 14px;border-radius:6px;cursor:pointer;font-size:13px;transition:opacity 0.15s;white-space:nowrap}
.btn:hover{opacity:0.85}
.btn:disabled{opacity:0.5;cursor:not-allowed}
.btn-sm{font-size:11px;padding:4px 10px}
.btn-danger{background:var(--err)}
.btn-ok{background:var(--ok)}
.btn-outline{background:transparent;border:1px solid var(--border);color:var(--fg)}
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
@keyframes spin{to{transform:rotate(360deg)}}
.spinner{display:inline-block;width:14px;height:14px;border:2px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:spin 0.6s linear infinite;margin-right:6px;vertical-align:middle}
.btn-fetching{background:var(--border)!important;color:var(--muted)!important}
.bar{height:6px;border-radius:3px;background:var(--border);margin:8px 0;overflow:hidden}
.bar-fill{height:100%;border-radius:3px;transition:width 0.5s}
.bar-fill.ok{background:var(--ok)}.bar-fill.warn{background:var(--warn)}.bar-fill.err{background:var(--err)}
.trait{display:flex;align-items:center;gap:8px;padding:3px 0}
.trait-name{flex:1;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:200px}
.trait-bar{flex:2;height:8px;background:var(--border);border-radius:4px;overflow:hidden}
.trait-fill{height:100%;background:var(--accent);border-radius:4px;transition:width 0.5s}
.trait-val{font-size:11px;color:var(--muted);width:36px;text-align:right}
.trait-phase{font-size:10px;color:var(--muted);width:50px;text-align:right}
.event{font-size:12px;padding:3px 0;border-bottom:1px solid var(--border);display:flex;gap:6px}
.event-dot{width:8px;height:8px;border-radius:50%;margin-top:4px;flex-shrink:0}
.narrative{font-size:13px;line-height:1.7;white-space:pre-wrap;max-height:300px;overflow-y:auto}
.timeline{max-height:400px;overflow-y:auto}
.changelog-entry{font-size:12px;padding:6px 0;border-bottom:1px solid var(--border)}
.changelog-entry .ts{color:var(--muted);margin-right:8px}
.const-row{display:grid;grid-template-columns:180px 80px 120px;gap:4px 8px;align-items:center;padding:5px 0;border-bottom:1px solid var(--border);font-size:12px}
.const-name{font-weight:600;color:var(--accent)}
.const-val{text-align:right}
.const-desc{grid-column:1/-1;color:var(--muted);font-size:11px;line-height:1.5;padding:2px 0}
.const-input{width:80px;text-align:right;padding:2px 6px}
.panel{display:none}
.panel.active{display:block}
.banner{background:rgba(210,153,34,0.12);border:1px solid var(--warn);border-radius:8px;padding:10px 14px;margin-bottom:16px;font-size:12px;color:var(--warn);display:flex;align-items:center;gap:8px}
.banner strong{color:#f0c040}
.banner .banner-dismiss{background:none;border:none;color:var(--muted);cursor:pointer;font-size:16px;padding:0 4px;margin-left:auto;flex-shrink:0}
.banner .banner-dismiss:hover{color:var(--fg)}
.modal-overlay{position:fixed;inset:0;background:rgba(0,0,0,0.55);display:flex;align-items:center;justify-content:center;z-index:9999}
.modal-box{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:24px;max-width:420px;width:90%;text-align:center}
.modal-box h2{font-size:18px;margin-bottom:8px}
.modal-box p{color:var(--muted);font-size:13px;margin-bottom:16px;line-height:1.6}
.modal-box .modal-actions{display:flex;gap:8px;justify-content:center}
/* mobile */
#menu-toggle{display:none;background:none;border:none;color:var(--fg);font-size:20px;cursor:pointer;padding:4px 8px}
@media(max-width:768px){
  body{flex-direction:column}
  nav{width:100%;padding:8px 12px;display:flex;flex-wrap:wrap;align-items:center;gap:4px;border-right:none;border-bottom:1px solid var(--border);position:sticky;top:0;z-index:100}
  nav .logo{width:auto;flex:1;border:none;margin:0;padding:0;font-size:14px}
  nav a{font-size:11px;padding:4px 8px;border-radius:4px}
  #menu-toggle{display:block}
  nav .nav-links{display:none;width:100%;flex-direction:column}
  nav .nav-links.open{display:flex}
  main{padding:10px;max-height:none;overflow-x:hidden}
  h1{font-size:16px}
  .grid{grid-template-columns:1fr!important}
  .card{padding:10px}
  .card h3{font-size:11px}
  .const-row{grid-template-columns:130px 55px 1fr;font-size:11px}
  .const-input{width:55px}
  /* Connect: form rows stack vertically */
  .connect-form-row{grid-template-columns:1fr!important}
  .upstream-row{grid-template-columns:1fr 1fr!important;gap:4px;font-size:11px}
  .upstream-row .form-group{margin-bottom:4px}
  .upstream-row label{font-size:10px}
  .btn{font-size:11px;padding:4px 10px}
  .btn-sm{font-size:10px;padding:3px 8px}
  .actions{gap:4px}
  .banner{font-size:11px;padding:8px 10px}
}
</style>
</head>
<body>
<nav>
  <div class="logo">🧠 loam admin <button class="theme-btn" onclick="toggleTheme()" title="切换日间/夜间模式">☀️</button></div>
  <button id="menu-toggle" onclick="this.nextElementSibling.classList.toggle('open')">☰</button>
  <div class="nav-links">
  <a href="#status" class="nav-link active" data-panel="status">📊 Status</a>
  <a href="#traits" class="nav-link" data-panel="traits">🧬 Traits</a>
  <a href="#memory" class="nav-link" data-panel="memory">💾 Memory</a>
  <a href="#config" class="nav-link" data-panel="config">⚙ Config</a>
  <a href="#constants" class="nav-link" data-panel="constants">🔧 Constants</a>
  <a href="#connect" class="nav-link" data-panel="connect">🔌 Connect</a>
  <a href="#actions" class="nav-link" data-panel="actions">▶ Actions</a>
  </div>
</nav>
<main>
  <div id="toast-container"></div>
  <div class="banner" id="keep-running-banner" style="display:none">
    <span>⚠️ <strong>Keep these processes running!</strong> Closing the terminal kills loam, proxy, and admin panel. <a href="https://github.com/lmynszbd-ctrlbe/Loam-A-Runtime-Where-Characters-Grow-a-Self-from-Memory-/blob/main/docs/DEPLOY.md#keeping-processes-running" target="_blank" style="color:var(--accent)">Learn how →</a></span>
    <button class="banner-dismiss" onclick="this.parentElement.style.display='none'" title="Dismiss">×</button>
  </div>

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
    <h1>🔌 Connect</h1>
    <div class="sub">配置 API 密钥。loam 使用两套独立的模型：一套消化记忆，一套生成回复。</div>

    <!-- 顶部三卡片：告诉用户填到聊天客户端的三个值 -->
    <div class="grid" style="grid-template-columns:repeat(3, 1fr); margin-bottom:20px">
      <div class="card">
        <h3>🔗 填到聊天软件的 Base URL</h3>
        <div style="font-family:monospace;font-size:14px;text-align:center;padding:6px;background:var(--bg);border-radius:4px">http://127.0.0.1:8780/v1</div>
        <p class="muted" style="font-size:11px;margin-top:4px">复制到 SillyTavern / Open WebUI 等第三方软件的 API 地址栏。</p>
      </div>
      <div class="card">
        <h3>🔑 填到聊天软件的 API Key</h3>
        <div style="font-family:monospace;font-size:14px;text-align:center;padding:6px;background:var(--bg);border-radius:4px">local-key</div>
        <p class="muted" style="font-size:11px;margin-top:4px">填什么都行。loam 跑在你本地，不需要真正鉴权——真正的密钥在下面配置。</p>
      </div>
      <div class="card">
        <h3>🤖 聊天软件选什么供应商？</h3>
        <div style="font-family:monospace;font-size:14px;text-align:center;padding:6px;background:var(--bg);border-radius:4px">OpenAI 兼容</div>
        <p class="muted" style="font-size:11px;margin-top:4px">loam 的 proxy 是 OpenAI 兼容接口。聊天软件里选 <b>OpenAI / OpenAI 兼容</b> 即可，模型列表会自动从下面配置的上游 API 拉取。</p>
      </div>
    </div>

    <div class="actions" style="margin-bottom:16px">
      <button class="btn btn-sm" onclick="loadApiConfig()">🔄 从磁盘重新加载</button>
      <span class="muted" style="font-size:11px;margin-left:8px">保存位置：<code id="cfg-home">~/.loam</code> · proxy 热加载，保存后立即生效</span>
    </div>

    <!-- SECTION 1: loam memory API — 用于消化记忆，生成角色特质 -->
    <div class="card" style="margin-bottom:16px; border-left:3px solid var(--accent)">
      <h3>🧠 记忆生长模型 <span class="muted" style="font-weight:400;font-size:11px">— loam 用它来消化对话、提炼特质、让角色「生长」</span></h3>
      <p class="muted" style="font-size:11px;margin-bottom:10px">这个模型在后台默默工作，不直接生成你看到的回复。填你的 API 提供商给的 Base URL 和 Key，选一个便宜点的模型就行。</p>
      <div class="grid connect-form-row" style="grid-template-columns:1fr 1fr 1fr auto auto; gap:8px; align-items:end">
        <div class="form-group" style="margin:0">
          <label>Base URL（API 地址）</label>
          <input id="sec-url" placeholder="请填写">
        </div>
        <div class="form-group" style="margin:0">
          <label>API Key（密钥）</label>
          <input id="sec-key" placeholder="请填写" type="password">
        </div>
        <div class="form-group" style="margin:0">
          <label>Model（模型名）</label>
          <input id="sec-model" placeholder="请填写" list="sec-models-list">
          <datalist id="sec-models-list"></datalist>
        </div>
        <button class="btn btn-sm btn-outline" style="height:38px;align-self:end" class="btn-fetch" onclick="fetchModels('sec')" title="从提供商拉取可用模型列表">拉取</button>
        <button class="btn btn-ok" style="height:38px;align-self:end" onclick="saveSecrets()">💾 保存</button>
      </div>
      <div id="sec-status" style="margin-top:8px;font-size:12px" class="muted"></div>
    </div>

    <!-- SECTION 2: chat upstream APIs — 用于生成聊天回复 -->
    <div class="card" style="border-left:3px solid var(--ok)">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
        <h3 style="margin:0">💬 聊天回复模型 API <span class="muted" style="font-weight:400;font-size:11px">— 你聊天时实际生成回复的模型，可以配多个随时切换</span></h3>
        <button class="btn btn-sm btn-outline" onclick="addUpstreamRow()">+ 添加提供商</button>
      </div>
      <p class="muted" style="font-size:11px;margin-bottom:10px">填 Base URL 和 API Key，点「拉取」获取完整模型列表，然后点「💾 保存全部」。<br>DeepSeek → <code>https://api.deepseek.com</code> &nbsp;|&nbsp; OpenAI → <code>https://api.openai.com</code> &nbsp;|&nbsp; 其他兼容 API 填对应地址。</p>
      <div id="upstream-rows"></div>
      <div style="display:flex;align-items:end;gap:12px;margin-top:10px">
        <div class="form-group" style="margin:0">
          <label>默认提供商</label>
          <select id="up-default" style="width:auto;min-width:200px"></select>
        </div>
        <button class="btn btn-ok" style="height:38px" onclick="saveUpstreams()">💾 保存全部</button>
      </div>
      <div id="up-status" style="margin-top:8px;font-size:12px" class="muted"></div>
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

// callAdmin — direct to admin panel (not proxied to loam)
async function callAdmin(method, path, body) {
  const opts = {method};
  if (body) {
    opts.headers = {'Content-Type': 'application/json'};
    opts.body = JSON.stringify(body);
  }
  const r = await fetch(path, opts);
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
  const data = await callAdmin('GET', '/admin/constants');  // direct from admin, no loam needed
  const consts = data.constants||{};
  const overrides = data.overrides||{};
  const descs = data.descriptions||{};
  const keys = Object.keys(consts).sort();
  document.getElementById('constants-list').innerHTML = keys.map(k => {
    const v = consts[k];
    const ov = overrides[k];
    const isOverridden = !!ov;
    const desc = descs[k] || '';
    return `<div class="const-row" style="${isOverridden?'background:rgba(88,166,255,0.1)':''}">
      <span class="const-name" title="${escAttr(desc)}">${esc(k)}</span>
      <input class="const-input" data-name="${k}" value="${isOverridden?ov.override:v}" style="${isOverridden?'border-color:var(--accent)':''}">
      <span class="const-val">${isOverridden?`<span class="warn">${ov.original}→${ov.override}</span>`:v}</span>
      <span class="const-desc" title="${escAttr(desc)}">${isOverridden?'⚡ overridden':esc(desc)}</span>
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
let _upstreamData = {};  // {name: {base_url, api_key, default_model}}

async function loadApiConfig() {
  try {
    const cfg = await callAdmin('GET', '/admin/config');
    const s = cfg.secrets || {};
    document.getElementById('sec-key').value = s.api_key || '';
    document.getElementById('sec-url').value = s.base_url || '';
    const modelEl = document.getElementById('sec-model');
    if (modelEl.tagName === 'SELECT') {
      const opt = Array.from(modelEl.options).find(o => o.value === (s.model||''));
      if (opt) modelEl.value = s.model;
    } else {
      modelEl.value = s.model || '';
    }
    const u = cfg.upstreams || {};
    _upstreamData = u.providers || {};
    const defName = u.default || '';
    if (cfg.home) document.getElementById('cfg-home').textContent = cfg.home;
    renderUpstreamRows(defName);
    // upstream model values are fetched from API, no need to restore
  } catch(e) {
    toast('Could not load config: ' + e.message, 'err');
  }
}

function renderUpstreamRows(defName) {
  const container = document.getElementById('upstream-rows');
  const select = document.getElementById('up-default');
  const names = Object.keys(_upstreamData);
  if (!names.length) { _upstreamData = {}; }
  const sorted = Object.keys(_upstreamData).sort();

  container.innerHTML = sorted.map(name => {
    const p = _upstreamData[name] || {};
    return `<div class="upstream-row" id="up-row-${escAttr(name)}" style="display:grid;grid-template-columns:1fr 1fr 1fr auto auto;gap:8px;align-items:end;padding:8px 0;border-bottom:1px solid var(--border)">
      <div class="form-group" style="margin:0">
        <label>提供商名称</label>
        <input class="up-name-inp" value="${escAttr(name)}" placeholder="请填写" style="font-weight:600">
      </div>
      <div class="form-group" style="margin:0">
        <label>Base URL（如 https://api.deepseek.com）</label>
        <input class="up-url-inp" value="${escAttr(p.base_url||'')}" placeholder="请填写">
      </div>
      <div class="form-group" style="margin:0">
        <label>API Key（sk-...）</label>
        <input class="up-key-inp" type="password" value="${escAttr(p.api_key||'')}" placeholder="请填写">
      </div>
      <button class="btn btn-sm btn-outline" style="height:38px;align-self:end" class="btn-fetch" onclick="fetchModels('${escAttr(name)}')" title="拉取模型列表">拉取</button>
      <button class="btn btn-sm btn-danger" style="height:38px;align-self:end" onclick="removeUpstreamRow('${escAttr(name)}')">✕</button>
    </div>`;
  }).join('');

  // default select
  select.innerHTML = sorted.map(n => `<option value="${escAttr(n)}" ${n===defName?'selected':''}>${esc(n)}</option>`).join('');
  if (!sorted.length) select.innerHTML = '<option value="">— no providers —</option>';
}

function addUpstreamRow(name) {
  name = (name || '').trim();
  if (!name) {
    // generate a unique name
    let i = 1;
    while (_upstreamData['relay'+i]) i++;
    name = 'relay'+i;
  }
  if (!_upstreamData[name]) _upstreamData[name] = {base_url:'', api_key:'', default_model:''};
  renderUpstreamRows(document.getElementById('up-default').value);
}

function removeUpstreamRow(name) {
  delete _upstreamData[name];
  renderUpstreamRows(document.getElementById('up-default').value);
}

function collectUpstreamFromDOM() {
  const rows = document.querySelectorAll('#upstream-rows .upstream-row');
  const data = {};
  rows.forEach(row => {
    const name = (row.querySelector('.up-name-inp')?.value || '').trim();
    if (!name) return;
    const existing = _upstreamData[name] || {};
    data[name] = {
      base_url: (row.querySelector('.up-url-inp')?.value || '').trim(),
      api_key: (row.querySelector('.up-key-inp')?.value || '').trim(),
      default_model: existing.default_model || '',
    };
  });
  return data;
}

async function saveSecrets() {
  const modelEl = document.getElementById('sec-model');
  const modelVal = (modelEl.tagName === 'SELECT' ? modelEl.value : modelEl.value).trim();
  const body = {
    api_key: document.getElementById('sec-key').value.trim(),
    base_url: document.getElementById('sec-url').value.trim(),
    model: modelVal,
  };
  if (!body.api_key || !body.base_url || !body.model) {
    toast('Fill in all three fields for loam Memory API', 'err'); return;
  }
  const r = await callAdmin('POST', '/admin/secrets', body);
  const el = document.getElementById('sec-status');
  if (r.ok) { el.innerHTML = '<span class="ok">✓ saved — restart loam to apply</span>'; toast('Memory API saved', 'ok'); }
  else { el.innerHTML = '<span class="err">'+esc(r.error||'failed')+'</span>'; toast('save failed', 'err'); }
}

async function saveUpstreams() {
  const providers = collectUpstreamFromDOM();
  if (!Object.keys(providers).length) { toast('请至少添加一个提供商', 'err'); return; }
  for (const [name, p] of Object.entries(providers)) {
    if (!p.base_url || !p.api_key || !p.default_model) {
      toast('提供商 "'+name+'": 请填写所有字段', 'err'); return;
    }
  }
  const defName = document.getElementById('up-default').value;
  const body = {providers};
  if (defName && providers[defName]) body.default = defName;
  const el = document.getElementById('up-status');
  el.innerHTML = '<span class="spinner"></span> 正在保存并重启 proxy...';
  const r = await callAdmin('POST', '/admin/upstreams', body);
  if (r.ok) {
    _upstreamData = providers;
    // 自动重启 proxy 让它加载新配置
    try { await callAdmin('POST', '/admin/restart-proxy'); } catch(e) {}
    el.innerHTML = '<span class="ok">✓ 已保存并重启 proxy — 现在可以拉取模型了</span>';
    toast('聊天 API 已保存，proxy 已重启', 'ok');
  } else { el.innerHTML = '<span class="err">'+esc(r.error||'保存失败')+'</span>'; toast('保存失败', 'err'); }
}

function loadConnect() { loadApiConfig(); }

// ---- FETCH MODELS ----
async function fetchModels(section) {
  let url, key, targetId, btnId;
  if (section === 'sec') {
    url = document.getElementById('sec-url').value.trim();
    key = document.getElementById('sec-key').value.trim();
    targetId = 'sec-model';
    btnId = 'sec-status';
  } else {
    const row = document.getElementById('up-row-'+section);
    if (!row) { toast('Provider row not found', 'err'); return; }
    url = row.querySelector('.up-url-inp')?.value.trim() || '';
    key = row.querySelector('.up-key-inp')?.value.trim() || '';
    targetId = null; // will find in row
    btnId = 'up-status';
  }
  if (!url || !key) { toast('请先填写 Base URL 和 API Key', 'err'); return; }
  const statusEl = document.getElementById(btnId);
  if (statusEl) statusEl.innerHTML = '<span class="spinner"></span> 正在拉取模型列表...';
  document.querySelectorAll('.btn-fetch').forEach(b => { b.disabled = true; b.classList.add('btn-fetching'); });
  try {
    const r = await callAdmin('POST', '/admin/fetch-models', {base_url: url, api_key: key});
    if (r.models && r.models.length) {
      if (targetId) {
        // replace input with select
        const inp = document.getElementById(targetId);
        if (inp) {
          const sel = document.createElement('select');
          sel.id = targetId;
          sel.style.cssText = inp.style.cssText;
          sel.innerHTML = r.models.map(m => `<option value="${m}">${m}</option>`).join('');
          inp.parentNode.replaceChild(sel, inp);
        }
      } else {
        // upstream row: find model input and replace with select
        const row = document.getElementById('up-row-'+section);
        if (row) {
          const inp = row.querySelector('.up-key-inp');
          if (inp) {
            const sel = document.createElement('select');
            sel.className = 'up-key-inp';
            sel.style.cssText = inp.style.cssText;
            sel.innerHTML = r.models.map(m => `<option value="${m}">${m}</option>`).join('');
            inp.parentNode.replaceChild(sel, inp);
          }
        }
      }
      toast(`${r.models.length} 个模型已加载`, 'ok');
      if (statusEl) statusEl.innerHTML = `<span class="ok">✓ 已加载 ${r.models.length} 个模型</span>`;
    } else {
      toast('拉取失败：' + (r.error||'未返回模型'), 'err');
      if (statusEl) statusEl.innerHTML = `<span class="err">✗ ${r.error||'未返回模型'}</span>`;
    }
  } catch(e) {
    toast('拉取出错：' + e.message, 'err');
    if (statusEl) statusEl.innerHTML = `<span class="err">✗ ${e.message}</span>`;
  } finally {
    document.querySelectorAll('.btn-fetch').forEach(b => { b.disabled = false; b.classList.remove('btn-fetching'); });
  }
}

// ---- UPDATE CHECK ----
async function checkVersion() {
  try {
    const v = await callAdmin('GET', '/admin/version');
    if (!v.has_update) return;
    // show update modal
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `<div class="modal-box">
      <h2>🔔 Update Available</h2>
      <p>Your loam is at <code>${esc(v.local)}</code> — latest is <code style="color:var(--ok)">${esc(v.remote)}</code>.<br>Update now? (loam + proxy will restart)</p>
      <div class="modal-actions">
        <button class="btn btn-ok" id="update-btn-confirm">🔄 Update & Restart</button>
        <button class="btn btn-outline" id="update-btn-cancel">Later</button>
      </div>
    </div>`;
    document.body.appendChild(overlay);
    document.getElementById('update-btn-cancel').onclick = () => overlay.remove();
    document.getElementById('update-btn-confirm').onclick = async () => {
      const btn = document.getElementById('update-btn-confirm');
      btn.disabled = true; btn.textContent = '⏳ Updating...';
      const r = await callAdmin('POST', '/admin/update');
      if (r.ok) {
        overlay.querySelector('h2').textContent = '✓ Updated';
        overlay.querySelector('p').innerHTML = 'loam updated to <code>'+esc(v.remote)+'</code>. Restarting...<br>Page will reload in 5 seconds.';
        overlay.querySelector('.modal-actions').innerHTML = '';
        setTimeout(() => { location.reload(); }, 5000);
      } else {
        overlay.querySelector('p').innerHTML = '<span class="err">Update failed:</span> ' + esc(r.error||'unknown');
        btn.disabled = false; btn.textContent = '🔄 Retry';
      }
    };
    // auto-close after 60s if ignored
    setTimeout(() => { if (overlay.parentNode) overlay.remove(); }, 60000);
  } catch(e) { /* network error — silently ignore */ }
}

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
function escAttr(s) { return String(s).replace(/&/g,'&amp;').replace(/"/g,'"').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

// ---- theme ----
(function(){ if(localStorage.getItem('loam-theme')==='light') document.documentElement.classList.add('light'); })();
function toggleTheme(){
  const isLight = document.documentElement.classList.toggle('light');
  localStorage.setItem('loam-theme', isLight?'light':'dark');
  document.querySelector('.theme-btn').textContent = isLight?'🌙':'☀️';
}
(function(){ document.querySelector('.theme-btn').textContent = document.documentElement.classList.contains('light')?'🌙':'☀️'; })();

// ---- init ----
loadStatus();
// show keep-running banner
document.getElementById('keep-running-banner').style.display = 'flex';
// check for updates
checkVersion();
</script>
</body>
</html>"""

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self._html(HTML)
        elif self.path == "/admin/config":
            self._json(self._read_config())
        elif self.path == "/admin/version":
            self._json(self._version_info())
        elif self.path == "/admin/constants":
            self._json(self._read_constants_local())
        elif self.path.startswith("/api/proxy"):
            self._proxy("GET")
        else:
            self._send(404, "not found")

    def do_POST(self):
        if self.path == "/admin/secrets":
            self._json(self._save_secrets())
        elif self.path == "/admin/upstreams":
            self._json(self._save_upstreams())
        elif self.path == "/admin/fetch-models":
            self._json(self._fetch_models())
        elif self.path == "/admin/restart-proxy":
            self._json(self._restart_proxy())
        elif self.path == "/admin/update":
            self._json(self._run_update())
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

    def _save_upstreams(self):
        """Save the full providers map + default to upstreams.json."""
        body = self._read_body()
        providers = body.get("providers")
        if not isinstance(providers, dict) or not providers:
            return {"error": "expected a 'providers' object with at least one entry"}
        for name, p in providers.items():
            if not isinstance(p, dict):
                return {"error": f"provider '{name}' must be an object"}
            if not (p.get("base_url") and p.get("api_key")):
                return {"error": f"provider '{name}': base_url and api_key are required"}
        data = {"providers": providers}
        default = (body.get("default") or "").strip()
        if default and providers.get(default):
            data["default"] = default
        elif providers:
            data["default"] = list(providers.keys())[0]
        return write_json_file(UPSTREAMS_FILE, data)

    def _version_info(self):
        """Return local commit hash + fetch remote latest for comparison."""
        import subprocess
        local = ""
        remote = ""
        repo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        try:
            r = subprocess.run(["git", "-C", repo_dir, "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, timeout=10)
            local = r.stdout.strip()
        except Exception:
            pass
        try:
            r = subprocess.run(["git", "-C", repo_dir, "ls-remote", "origin", "HEAD"],
                              capture_output=True, text=True, timeout=15)
            remote = r.stdout.strip().split()[0][:7] if r.stdout.strip() else ""
        except Exception:
            pass
        has_update = bool(local and remote and local != remote)
        return {"local": local, "remote": remote, "has_update": has_update}

    def _run_update(self):
        """Run git pull and restart loam + proxy."""
        repo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        try:
            r = subprocess.run(["git", "-C", repo_dir, "pull", "--ff-only"],
                              capture_output=True, text=True, timeout=30)
            out = r.stdout.strip()
            if r.returncode != 0:
                out = (out + "\n" + r.stderr).strip()
                return {"error": "git pull failed", "detail": out[:300]}
            restart = []
            for proc_name in ["loam.__main__", "forced_flow_proxy", "scripts/admin.py", "scripts/dashboard.py"]:
                try:
                    subprocess.run(["pkill", "-f", proc_name], timeout=5)
                    restart.append(proc_name)
                except Exception:
                    pass
            try:
                subprocess.Popen(["python3", "-m", "loam", "run", "--grow-interval", "60"],
                                cwd=repo_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                restart.append("loam-restarted")
            except Exception:
                pass
            try:
                subprocess.Popen(["python3", "bridge/forced_flow_proxy.py"],
                                cwd=repo_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                restart.append("proxy-restarted")
            except Exception:
                pass
            return {"ok": True, "detail": out[:200], "restarted": restart}
        except Exception as e:
            return {"error": str(e)}

    def _read_constants_local(self):
        """Read constants + descriptions directly from constants.py, no loam backend needed."""
        import importlib
        try:
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            import loam.core.constants as C
            importlib.reload(C)
        except Exception:
            return {"constants": {}, "overrides": {}, "descriptions": {}, "error": "cannot import constants"}
        all_consts = {}
        for name in dir(C):
            if name.isupper() and not name.startswith('_') and name != 'DESCRIPTIONS':
                val = getattr(C, name)
                if isinstance(val, (int, float, bool, str)):
                    all_consts[name] = val
        descriptions = getattr(C, 'DESCRIPTIONS', {})
        return {"constants": all_consts, "overrides": {}, "descriptions": descriptions}

    def _restart_proxy(self):
        """Kill and restart the forced proxy process so it picks up new upstreams.json."""
        repo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # 先确保文件存在
        if not UPSTREAMS_FILE.exists():
            write_json_file(UPSTREAMS_FILE, {"default":"relayA","providers":{"relayA":{"base_url":"","api_key":"","default_model":""}}})
        # 强杀端口占用
        import subprocess as sp
        try:
            sp.run(["fuser", "-k", "8780/tcp"], timeout=5, capture_output=True)
        except Exception:
            try:
                sp.run(["pkill", "-9", "-f", "forced_flow_proxy"], timeout=5)
            except Exception:
                pass
        import time
        time.sleep(2)
        try:
            sp.Popen(
                ["python3", "bridge/forced_flow_proxy.py"],
                cwd=repo_dir,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                env={**os.environ, "PROXY_NO_AUTH": "1"}
            )
            return {"ok": True, "message": "proxy restarted"}
        except Exception as e:
            return {"error": str(e)}

    def _fetch_models(self):
        """Proxy a /v1/models call to a provider. Body: {base_url, api_key}."""
        body = self._read_body()
        url = (body.get("base_url") or "").strip()
        key = (body.get("api_key") or "").strip()
        if not url or not key:
            return {"error": "base_url and api_key are required"}
        url = url.rstrip("/")
        try:
            req = urllib.request.Request(f"{url}/models")
            req.add_header("Authorization", f"Bearer {key}")
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read())
            models = []
            for m in data.get("data", []):
                mid = m.get("id", "")
                if mid and not mid.startswith("ft:"):
                    models.append(mid)
            return {"models": models}
        except Exception as e:
            return {"error": str(e)}

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
    import socket
    print(f"loam admin panel → http://127.0.0.1:{PORT}")
    print(f"loam backend → {LOAM}")
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    srv.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()