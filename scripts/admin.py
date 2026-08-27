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
import socket
import re
from pathlib import Path

LOAM = os.environ.get("LOAM_URL", "http://127.0.0.1:8765").rstrip("/")
PORT = int(os.environ.get("ADMIN_PORT", "8900"))
def _loam_home() -> Path:
    """Return the loam config directory, with LOAM_HOME/Termux fallbacks."""
    if "LOAM_HOME" in os.environ:
        return Path(os.environ["LOAM_HOME"])
    p = Path("~/.loam").expanduser()
    if not p.exists() and os.name != "nt":
        termux = Path("/data/data/com.termux/files/home/.loam")
        if termux.exists():
            return termux
    return p


SECRETS_HOME = _loam_home()
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

:root {
  --bg: #090d16;
  --bg-subtle: #0f1523;
  --bg-card: rgba(18, 26, 43, 0.72);
  --bg-card-hover: rgba(24, 34, 56, 0.85);
  --bg-card-solid: #121a2b;
  --border: rgba(120, 160, 255, 0.14);
  --border-hover: rgba(120, 160, 255, 0.35);
  --border-strong: rgba(120, 160, 255, 0.45);
  --fg: #e2e8f4;
  --fg-dim: #94a3b8;
  --muted: #64748b;
  --accent: #60a5fa;
  --accent-rgb: 96, 165, 250;
  --accent-grad: linear-gradient(135deg, #60a5fa 0%, #a855f7 100%);
  --accent-2: #c084fc;
  --warn: #f59e0b;
  --err: #f43f5e;
  --ok: #10b981;
  --input-bg: rgba(10, 15, 26, 0.65);
  --radius-sm: 8px;
  --radius: 14px;
  --radius-lg: 20px;
  --shadow-sm: 0 2px 8px rgba(0,0,0,0.25);
  --shadow: 0 8px 24px -6px rgba(0,0,0,0.45);
  --shadow-lg: 0 16px 40px -10px rgba(0,0,0,0.65), 0 0 20px rgba(96, 165, 250, 0.08);
  --glass: blur(16px) saturate(1.3);
  --glow: radial-gradient(1000px 500px at 5% -5%, rgba(96, 165, 250, 0.15), transparent 60%),
          radial-gradient(800px 450px at 95% 5%, rgba(192, 132, 252, 0.12), transparent 55%),
          radial-gradient(700px 600px at 50% 115%, rgba(16, 185, 129, 0.08), transparent 60%);
}

.light {
  --bg: #f8fafc;
  --bg-subtle: #f1f5f9;
  --bg-card: rgba(255, 255, 255, 0.88);
  --bg-card-hover: rgba(255, 255, 255, 0.98);
  --bg-card-solid: #ffffff;
  --border: rgba(148, 163, 184, 0.22);
  --border-hover: rgba(59, 130, 246, 0.45);
  --border-strong: rgba(59, 130, 246, 0.55);
  --fg: #0f172a;
  --fg-dim: #475569;
  --muted: #94a3b8;
  --accent: #2563eb;
  --accent-rgb: 37, 99, 235;
  --accent-grad: linear-gradient(135deg, #2563eb 0%, #7c3aed 100%);
  --accent-2: #7c3aed;
  --warn: #d97706;
  --err: #e11d48;
  --ok: #059669;
  --input-bg: rgba(255, 255, 255, 0.95);
  --shadow-sm: 0 2px 6px rgba(15,23,42,0.06);
  --shadow: 0 8px 24px -6px rgba(15,23,42,0.1);
  --shadow-lg: 0 16px 36px -8px rgba(15,23,42,0.14);
  --glow: radial-gradient(1000px 500px at 5% -5%, rgba(37, 99, 235, 0.08), transparent 60%),
          radial-gradient(800px 450px at 95% 5%, rgba(124, 58, 237, 0.06), transparent 55%),
          radial-gradient(700px 600px at 50% 115%, rgba(5, 150, 105, 0.05), transparent 60%);
}

* { margin: 0; padding: 0; box-sizing: border-box; }
::selection { background: rgba(var(--accent-rgb), 0.3); }

html { scroll-behavior: smooth; }
body {
  font: 13.5px/1.65 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'PingFang SC', 'Noto Sans SC', sans-serif;
  background-color: var(--bg);
  color: var(--fg);
  display: flex;
  min-height: 100vh;
  letter-spacing: -0.01em;
  -webkit-font-smoothing: antialiased;
  position: relative;
  overflow-x: hidden;
}

body::before {
  content: '';
  position: fixed;
  inset: 0;
  background-image: var(--glow);
  pointer-events: none;
  z-index: 0;
}

nav {
  width: 250px;
  flex-shrink: 0;
  padding: 24px 16px 28px;
  z-index: 20;
  background: var(--bg-card);
  backdrop-filter: var(--glass);
  -webkit-backdrop-filter: var(--glass);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 12px;
  position: sticky;
  top: 0;
  height: 100vh;
  overflow-y: auto;
}

nav .logo {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 6px 14px;
  border-bottom: 1px solid var(--border);
}

nav .logo .theme-btn {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--fg-dim);
  width: 32px;
  height: 32px;
  border-radius: 9px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

nav .logo .theme-btn:hover {
  background: rgba(var(--accent-rgb), 0.12);
  border-color: var(--accent);
  color: var(--fg);
  transform: rotate(15deg) scale(1.05);
}

.nav-links {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 4px;
  flex: 1;
}

nav a.nav-link, nav a {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  color: var(--fg-dim);
  text-decoration: none;
  font-size: 13px;
  font-weight: 550;
  border-radius: 10px;
  transition: all 0.2s ease;
  position: relative;
}

nav a:hover {
  color: var(--fg);
  background: rgba(var(--accent-rgb), 0.08);
  transform: translateX(3px);
}

nav a.active {
  font-weight: 650;
  box-shadow: 0 4px 14px rgba(var(--accent-rgb), 0.35);
}

#menu-toggle {
  display: none;
  background: transparent;
  border: 1px solid var(--border);
  color: var(--fg);
  padding: 6px 10px;
  border-radius: 8px;
  cursor: pointer;
}

main {
  flex: 1;
  padding: 32px 40px 60px;
  max-width: 1320px;
  margin: 0 auto;
  z-index: 10;
  width: 100%;
}

.panel {
  display: none;
  animation: fadeIn 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}
.panel.active {
  display: block;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

.card, .grid > div, section {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
  backdrop-filter: var(--glass);
  -webkit-backdrop-filter: var(--glass);
  box-shadow: var(--shadow);
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
}

.card:hover {
  border-color: var(--border-hover);
  box-shadow: var(--shadow-lg);
  transform: translateY(-2px);
}

button, .btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  font-family: inherit;
  font-size: 13px;
  font-weight: 600;
  padding: 8px 16px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: var(--bg-card);
  color: var(--fg);
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  outline: none;
  text-decoration: none;
}

button:hover, .btn:hover {
  border-color: var(--accent);
  background: rgba(var(--accent-rgb), 0.12);
  color: var(--accent);
  transform: translateY(-1px);
}

.btn-primary, .btn-accent {
  box-shadow: 0 4px 14px rgba(var(--accent-rgb), 0.35);
}
.btn-primary:hover, .btn-accent:hover {
  box-shadow: 0 6px 20px rgba(var(--accent-rgb), 0.5);
  transform: translateY(-2px);
}

.btn-ok { background: var(--ok); color: #fff; border-color: transparent; }
.btn-err, .btn-danger { background: var(--err); color: #fff; border-color: transparent; }
.btn-warn { background: var(--warn); color: #fff; border-color: transparent; }

input, textarea, select {
  font-family: inherit;
  font-size: 13px;
  background: var(--input-bg);
  color: var(--fg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 8px 12px;
  outline: none;
  transition: all 0.2s ease;
}

input:focus, textarea:focus, select:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(var(--accent-rgb), 0.2);
}

pre, code {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 12.5px;
}
pre {
  background: rgba(5, 8, 15, 0.85);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 14px;
  color: #cbd5e1;
  overflow-x: auto;
  line-height: 1.5;
}
.light pre { background: #1e293b; color: #f8fafc; }

::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(120,160,255,0.18); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: rgba(120,160,255,0.36); }


/* 侧边栏折叠与移动端样式 */
:root {
  --sidebar-width: 250px;
  --sidebar-collapsed-width: 70px;
}

body {
  display: flex;
  flex-direction: row;
  overflow-x: hidden;
}

nav {
  width: var(--sidebar-width);
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1), transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 100;
  display: flex;
  flex-direction: column;
}

/* 折叠状态 */
body.sidebar-collapsed nav {
  width: var(--sidebar-collapsed-width);
}
body.sidebar-collapsed .logo-text .gradient-text,
body.sidebar-collapsed .logo-text .version-badge,
body.sidebar-collapsed .nav-content label,
body.sidebar-collapsed #current-persona-display,
body.sidebar-collapsed .nav-links a {
  display: none;
  opacity: 0;
}
body.sidebar-collapsed .nav-links a {
  justify-content: center;
  padding: 10px 0;
  display: flex;
  font-size: 18px; /* 只显示图标(emoji) */
  color: transparent;
  text-shadow: 0 0 0 var(--text-color);
}
body.sidebar-collapsed #collapse-icon {
  transform: rotate(180deg);
}

main {
  flex: 1;
  margin-left: 0;
  transition: margin-left 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.mobile-header {
  display: none;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  z-index: 90;
}

.nav-toggle-btn {
  background: transparent;
  border: none;
  color: var(--text-color);
  cursor: pointer;
  padding: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.sidebar-overlay {
  display: none;
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
  z-index: 95;
  opacity: 0;
  transition: opacity 0.3s ease;
}

/* 移动端响应式 */
@media (max-width: 768px) {
  .mobile-header {
    display: flex;
  }
  body {
    flex-direction: column;
  }
  nav {
    position: fixed;
    top: 0;
    left: 0;
    height: 100vh;
    transform: translateX(-100%);
    box-shadow: 4px 0 24px rgba(0,0,0,0.2);
  }
  nav.mobile-open {
    transform: translateX(0);
  }
  .sidebar-overlay.active {
    display: block;
    opacity: 1;
  }
  .desktop-only {
    display: none !important;
  }
  main {
    height: calc(100vh - 56px);
  }
}
</style>
</head>
<body>
<!-- 移动端顶部标题栏 -->
<header class="mobile-header">
  <div style="display:flex;align-items:center;gap:6px;font-size:18px;">
    <span>🌱</span>
    <span style="font-weight:800;background:linear-gradient(135deg,#7aa2ff,#c792ea);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent">loam</span>
  </div>
  <button id="menu-btn" class="nav-toggle-btn" onclick="toggleSidebar()">
    <svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round">
      <line x1="3" y1="12" x2="21" y2="12"></line>
      <line x1="3" y1="6" x2="21" y2="6"></line>
      <line x1="3" y1="18" x2="21" y2="18"></line>
    </svg>
  </button>
</header>
<!-- 侧边栏遮罩 -->
<div id="sidebar-overlay" class="sidebar-overlay" onclick="toggleSidebar()"></div>

<nav id="sidebar">
  <div class="logo">
    <div class="logo-text">
      <span>🌱</span>
      <span class="gradient-text">loam</span>
      <span class="version-badge">v0.7.0</span>
    </div>
    <div style="display:flex;gap:4px;">
        <button class="theme-btn" onclick="toggleTheme()" title="切换日间/夜间模式">☀️</button>
        <button id="collapse-btn" class="theme-btn desktop-only" onclick="toggleCollapse()" title="折叠/展开侧边栏">
            <svg id="collapse-icon" viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"></polyline></svg>
        </button>
    </div>
  </div>
  <div class="nav-content">
    <div style="padding:0 14px 12px;margin-bottom:8px;border-bottom:1px solid var(--border)">
      <label style="margin-top:0;font-size:10.5px;text-transform:uppercase;letter-spacing:0.05em;color:var(--muted)">🎭 当前角色</label>
      <div style="font-size:13px;font-weight:600;padding:6px 0 0;"><span id="current-persona-display">-</span></div>
    </div>
    <div class="nav-links">
      <a href="#" onclick="showPanel('status')" id="nav-status" class="active">✨ 运行状态</a>
      <a href="#" onclick="showPanel('demo')" id="nav-demo">🎮 演示大厅</a>
      <a href="#" onclick="showPanel('persona')" id="nav-persona">🎭 性格卡片</a>
      <a href="#" onclick="showPanel('memory')" id="nav-memory">🧠 记忆总线</a>
      <a href="#" onclick="showPanel('config')" id="nav-config">⚙️ 系统配置</a>
      <a href="#" onclick="showPanel('constants')" id="nav-constants">🧊 常数环境</a>
      <a href="#" onclick="showPanel('connections')" id="nav-connections">🔌 外部连接</a>
      <a href="#" onclick="showPanel('actions')" id="nav-actions">⚡ 动作中心</a>
    </div>
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

  <!-- DEMO -->
  <div id="panel-demo" class="panel">
    <h1>✨ 零成本试玩 (Demo 演化沙盒)</h1>
    <div class="sub">无需填写 API Key，不消耗 Token。点击播放即可直观体验 10 轮经历如何推动特质从萌芽到质变！</div>
    
    <div class="actions" style="margin-bottom:16px">
      <button class="btn btn-ok" id="demo-play-btn" onclick="startDemoSimulation()">▶ 播放演化推演</button>
      <button class="btn btn-outline" onclick="resetDemoSimulation()">🔄 重置沙盒</button>
      <span class="muted" id="demo-status-text" style="font-size:12px;margin-left:12px">准备就绪，点击开始播放</span>
    </div>

    <div class="grid" style="grid-template-columns: 1.2fr 1fr; gap:16px">
      <!-- 左边：模拟对话流 -->
      <div class="card">
        <h3>💬 模拟交互流 (Transcript Stream)</h3>
        <div id="demo-dialogue-stream" style="display:flex;flex-direction:column;gap:8px;max-height:420px;overflow-y:auto;padding-right:4px">
          <div class="muted" style="text-align:center;padding:20px;font-size:12px">点击上方“播放演化推演”观察对话与特质联动</div>
        </div>
      </div>

      <!-- 右边：特质动态发光曲线 -->
      <div class="card">
        <h3>🧬 实时特质蓄水池 (Real-time Plasticity)</h3>
        <div id="demo-traits-monitor" style="display:flex;flex-direction:column;gap:12px;margin-top:10px">
          <!-- 动态注入特质条 -->
        </div>
      </div>
    </div>
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
    <h1>💾 Memory & Neural Topology</h1>
    <div class="sub">Events, narrative, changelog, and dynamic neural network graph</div>
    <div class="actions">
      <button class="btn btn-sm" onclick="loadMemory()">🔄 Refresh Events</button>
      <button class="btn btn-sm btn-outline" onclick="loadNarrative()">📝 Narrative</button>
      <button class="btn btn-sm btn-outline" onclick="loadChangelog()">📋 Changelog</button>
      <button class="btn btn-sm btn-ok" onclick="loadNetworkGraph()">🌐 动态神经拓扑图</button>
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
    <h1>🔧 Constants & Persona (双模调参)</h1>
    <div class="sub">支持 5 大性格宏观旋钮 / 一键预设卡，亦可精细微调 48 项底层物理常数并一键持久化</div>

    <!-- 模式切换 Tabs -->
    <div style="display:flex;gap:8px;margin-bottom:16px;border-bottom:1px solid var(--border);padding-bottom:8px">
      <button class="btn btn-sm btn-ok" id="tab-btn-macro" onclick="switchConstantsMode('macro')">🎭 性格气质大旋钮 (简易模式)</button>
      <button class="btn btn-sm btn-outline" id="tab-btn-micro" onclick="switchConstantsMode('micro')">🔬 48 项物理常数 (专家模式)</button>
    </div>

    <!-- 简易模式：5大性格大旋钮 + 4套预设卡 -->
    <div id="constants-macro-view">
      <!-- 预设卡 -->
      <div class="card" style="margin-bottom:16px">
        <h3>✨ 一键性格预设 (Preset Personas)</h3>
        <p class="muted" style="font-size:11px;margin-bottom:12px">点击直接应用预设性格模型，底层常数将自动按权重映射调节并持久化</p>
        <div class="grid" style="grid-template-columns:repeat(4, 1fr);gap:10px">
          <div class="card preset-card" onclick="applyPersonaPreset('aloof')" style="cursor:pointer;text-align:center;padding:12px;background:var(--bg);border:1px solid var(--border);transition:all 0.2s">
            <div style="font-size:24px">🧊</div>
            <div style="font-weight:600;font-size:13px;margin:4px 0">高冷孤傲</div>
            <div class="muted" style="font-size:10px">慢热防备 · 自愈极强</div>
          </div>
          <div class="card preset-card" onclick="applyPersonaPreset('gentle')" style="cursor:pointer;text-align:center;padding:12px;background:var(--bg);border:1px solid var(--border);transition:all 0.2s">
            <div style="font-size:24px">🌸</div>
            <div style="font-weight:600;font-size:13px;margin:4px 0">温柔包容</div>
            <div class="muted" style="font-size:10px">共情敏锐 · 富于理解</div>
          </div>
          <div class="card preset-card" onclick="applyPersonaPreset('cheerful')" style="cursor:pointer;text-align:center;padding:12px;background:var(--bg);border:1px solid var(--border);transition:all 0.2s">
            <div style="font-size:24px">🐶</div>
            <div style="font-weight:600;font-size:13px;margin:4px 0">乐天小狗</div>
            <div class="muted" style="font-size:10px">超级易感 · 回血神速</div>
          </div>
          <div class="card preset-card" onclick="applyPersonaPreset('fragile')" style="cursor:pointer;text-align:center;padding:12px;background:var(--bg);border:1px solid var(--border);transition:all 0.2s">
            <div style="font-size:24px">🥀</div>
            <div style="font-weight:600;font-size:13px;margin:4px 0">敏感易碎</div>
            <div class="muted" style="font-size:10px">多疑内耗 · 脑补发散</div>
          </div>
        </div>
      </div>

      <!-- 5个大滑块 -->
      <div class="card" style="margin-bottom:16px">
        <h3>🎛️ 5 大性格气质大旋钮</h3>
        <div style="display:flex;flex-direction:column;gap:16px;margin-top:14px">
          <div>
            <div style="display:flex;justify-content:space-between;margin-bottom:4px">
              <label style="font-weight:600;font-size:13px">🌿 敏感度 / 易感性</label>
              <span id="knob-val-sensitivity" style="font-family:monospace;font-size:13px;color:var(--accent)">0.50</span>
            </div>
            <input type="range" id="knob-sensitivity" min="0" max="1" step="0.01" value="0.5" style="width:100%" oninput="onKnobChange()">
            <div class="muted" style="font-size:11px">钝感慢热 ↔ 极度敏锐脆皮（影响推动力与情绪冲顶速度）</div>
          </div>

          <div>
            <div style="display:flex;justify-content:space-between;margin-bottom:4px">
              <label style="font-weight:600;font-size:13px">🗿 沉稳度 / 执拗度</label>
              <span id="knob-val-stubbornness" style="font-family:monospace;font-size:13px;color:var(--accent)">0.50</span>
            </div>
            <input type="range" id="knob-stubbornness" min="0" max="1" step="0.01" value="0.5" style="width:100%" oninput="onKnobChange()">
            <div class="muted" style="font-size:11px">随和变通 ↔ 顽固不化（影响特质固化天花板与抗撼动门槛）</div>
          </div>

          <div>
            <div style="display:flex;justify-content:space-between;margin-bottom:4px">
              <label style="font-weight:600;font-size:13px">💧 自愈力 / 情绪消化</label>
              <span id="knob-val-resilience" style="font-family:monospace;font-size:13px;color:var(--accent)">0.50</span>
            </div>
            <input type="range" id="knob-resilience" min="0" max="1" step="0.01" value="0.5" style="width:100%" oninput="onKnobChange()">
            <div class="muted" style="font-size:11px">持久内耗 ↔ 迅速回血（影响快态消退速率与情绪渗漏）</div>
          </div>

          <div>
            <div style="display:flex;justify-content:space-between;margin-bottom:4px">
              <label style="font-weight:600;font-size:13px">🛡️ 戒备度 / 多疑性</label>
              <span id="knob-val-vigilance" style="font-family:monospace;font-size:13px;color:var(--accent)">0.50</span>
            </div>
            <input type="range" id="knob-vigilance" min="0" max="1" step="0.01" value="0.5" style="width:100%" oninput="onKnobChange()">
            <div class="muted" style="font-size:11px">单纯直率 ↔ 高度防备（影响入脑置信门槛与反讽识别）</div>
          </div>

          <div>
            <div style="display:flex;justify-content:space-between;margin-bottom:4px">
              <label style="font-weight:600;font-size:13px">✨ 联想力 / 脑洞发散</label>
              <span id="knob-val-creativity" style="font-family:monospace;font-size:13px;color:var(--accent)">0.50</span>
            </div>
            <input type="range" id="knob-creativity" min="0" max="1" step="0.01" value="0.5" style="width:100%" oninput="onKnobChange()">
            <div class="muted" style="font-size:11px">一板一眼 ↔ 发散连篇（影响神经连线扩散跨度与跳数）</div>
          </div>
        </div>

        <div style="display:flex;gap:10px;margin-top:18px">
          <button class="btn btn-ok" onclick="savePersonaKnobs()">💾 保存并持久化此性格</button>
          <button class="btn btn-outline" onclick="resetPersonaKnobs()">🔄 重置为默认平衡态</button>
        </div>
      </div>
    </div>

    <!-- 专家模式：48项物理常数 -->
    <div id="constants-micro-view" style="display:none">
      <div class="actions" style="margin-bottom:12px">
        <button class="btn btn-sm" onclick="loadConstants()">🔄 Refresh</button>
        <button class="btn btn-sm btn-ok" onclick="applyConstants()">💾 Save & Persist Overrides</button>
        <button class="btn btn-sm btn-outline" onclick="clearConstants()">🗑 Reset All Defaults</button>
      </div>
      <div class="card" id="constants-list"></div>
    </div>
  </div>

  <!-- CONNECT -->
  <div id="panel-connect" class="panel">
    <h1>🔌 Connect</h1>
    <div class="sub">配置 API 密钥。loam 使用两套独立的模型：一套消化记忆，一套生成回复。</div>

    <!-- 顶部三卡片：告诉用户填到聊天客户端的三个值 -->
    <div class="grid" style="grid-template-columns:repeat(3, 1fr); margin-bottom:20px">
      <div class="card">
        <h3>🔗 填到聊天软件的 Base URL</h3>
        <div id="client-base-url" style="font-family:monospace;font-size:14px;text-align:center;padding:6px;background:var(--bg);border-radius:4px">http://127.0.0.1:8781/v1</div>
        <div id="client-base-url-alt" style="font-family:monospace;font-size:12px;text-align:center;padding:4px;background:var(--bg);border-radius:4px;margin-top:4px;color:var(--accent);min-height:1.5em"><span class="spinner"></span> 正在检测可用地址...</div>
        <div id="client-base-url-err" style="color:var(--err);font-size:11px;text-align:center;margin-top:4px;min-height:1.5em"></div>
        <p class="muted" style="font-size:11px;margin-top:4px"><b>同一设备：</b>用 127.0.0.1。<b>不同 App（如 Operit）：</b>用下方带 IP 的地址。<b>不同设备：</b>手机和电脑必须连同一个 WiFi。</b></p>
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
      <p class="muted" style="font-size:11px;margin-bottom:10px">填 Base URL 和 API Key，点「拉取」获取完整模型列表，然后点「💾 保存全部」。</p>
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

  <!-- ACTIONS → GROWTH -->
  <div id="panel-actions" class="panel">
    <h1>🌱 记忆生长</h1>
    <div class="sub">loam 后台自动消化对话，提炼特质和记忆。你也可以手动触发。</div>

    <!-- 机制说明 -->
    <div class="card" style="margin-bottom:16px; border-left:3px solid var(--accent)">
      <h3>⚙️ 生长机制（不费钱）</h3>
      <div class="grid" style="grid-template-columns:repeat(3,1fr);gap:12px">
        <div style="text-align:center;padding:8px">
          <div style="font-size:24px">📦</div>
          <div style="font-weight:600;font-size:14px">攒够 <span id="growth-batch">20</span> 轮对话</div>
          <div class="muted" style="font-size:11px">才消化一次，不是每轮都消化</div>
        </div>
        <div style="text-align:center;padding:8px">
          <div style="font-size:24px">⏳</div>
          <div style="font-weight:600;font-size:14px">或 <span id="growth-idle">15</span> 分钟无新对话</div>
          <div class="muted" style="font-size:11px">聊完一段就自动消化</div>
        </div>
        <div style="text-align:center;padding:8px">
          <div style="font-size:24px">💰</div>
          <div style="font-weight:600;font-size:14px">每 20 轮 ≈ 1~3 次 API</div>
          <div class="muted" style="font-size:11px">比你聊天消耗的 API 少得多</div>
        </div>
      </div>
      <p class="muted" style="font-size:11px;margin-top:8px">🔍 loam 每 <b>60 秒</b> 检查一次是否满足条件，不是每 60 秒调一次 API。</p>
    </div>

    <!-- 可调参数 -->
    <div class="card" style="margin-bottom:16px">
      <h3>🎛️ 消化参数</h3>
      <div class="grid" style="grid-template-columns:repeat(3,1fr);gap:12px">
        <div class="form-group">
          <label>触发回合数（攒够多少轮就消化）</label>
          <input id="grow-batch" type="number" min="5" max="200" value="20" style="width:100px">
          <span class="muted" style="font-size:10px;display:block">建议 15~30，太小会频繁调用 API</span>
        </div>
        <div class="form-group">
          <label>空闲等待（秒，无新对话后多久消化）</label>
          <input id="grow-idle" type="number" min="60" max="3600" value="900" style="width:100px">
          <span class="muted" style="font-size:10px;display:block">建议 600~900（10~15 分钟）</span>
        </div>
        <div class="form-group">
          <label>检查间隔（秒，多久看一眼要不要消化）</label>
          <input id="grow-interval" type="number" min="10" max="600" value="60" style="width:100px">
          <span class="muted" style="font-size:10px;display:block">建议 30~60，只是检查频率不是调用频率</span>
        </div>
      </div>
      <div style="display:flex;gap:8px;align-items:center;margin-top:8px">
        <button class="btn btn-ok" onclick="saveGrowthSettings()">💾 保存设置</button>
        <span class="muted" style="font-size:11px">⚠️ 建议使用默认值，修改后需重启 loam 生效</span>
      </div>
      <div id="growth-settings-status" style="margin-top:8px;font-size:12px"></div>
    </div>

    <!-- 手动操作与备份迁移 -->
    <div class="grid">
      <div class="card">
        <h3>🧪 手动消化</h3>
        <p class="muted" style="font-size:12px;margin-bottom:8px">立即消化当前攒下的所有对话</p>
        <button class="btn" onclick="doAction('digest')">🫕 立即消化</button>
        <div id="digest-result" style="margin-top:8px;font-size:12px"></div>
      </div>
      <div class="card">
        <h3>🚰 全部清空</h3>
        <p class="muted" style="font-size:12px;margin-bottom:8px">处理所有队列中的对话（可能较慢）</p>
        <button class="btn" onclick="doAction('drain')">🚿 全部处理</button>
        <div id="drain-result" style="margin-top:8px;font-size:12px"></div>
      </div>
      <div class="card">
        <h3>📦 一键数据备份迁移</h3>
        <p class="muted" style="font-size:12px;margin-bottom:8px">打包全套 SQLite + 状态文件为 tar.gz</p>
        <button class="btn btn-ok" onclick="doAction('backup_export')">💾 导出完整备份包</button>
        <div id="backup-result" style="margin-top:8px;font-size:12px"></div>
      </div>
      <div class="card">
        <h3>🔄 重建记忆</h3>
        <p class="muted" style="font-size:12px;margin-bottom:8px">从原始对话重新构建所有记忆</p>
        <button class="btn btn-danger" onclick="doAction('recompute')">⚠️ 重建</button>
        <div id="recompute-result" style="margin-top:8px;font-size:12px"></div>
      </div>
    </div>
  </div>
</main>

<script>
// 侧边栏与移动端交互
function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebar-overlay');
  sidebar.classList.toggle('mobile-open');
  if (sidebar.classList.contains('mobile-open')) {
    overlay.classList.add('active');
  } else {
    overlay.classList.remove('active');
  }
}

function toggleCollapse() {
  document.body.classList.toggle('sidebar-collapsed');
  // 保存状态到 localStorage (可选)
  localStorage.setItem('sidebar-collapsed', document.body.classList.contains('sidebar-collapsed'));
}

// 页面加载时恢复折叠状态
document.addEventListener('DOMContentLoaded', () => {
  if (localStorage.getItem('sidebar-collapsed') === 'true' && window.innerWidth > 768) {
    document.body.classList.add('sidebar-collapsed');
  }
  // 点击面板链接时，如果是移动端，自动收起侧边栏
  document.querySelectorAll('.nav-links a').forEach(link => {
    link.addEventListener('click', () => {
      if (window.innerWidth <= 768) {
        toggleSidebar();
      }
    });
  });
});

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
    if (a.dataset.panel === 'demo') {
      renderDemoTraits();
      return;
    }
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
async function loadNetworkGraph() {
  const net = await call('GET', '/network?limit=80');
  const nodes = net.nodes || [];
  const edges = net.edges || [];

  document.getElementById('memory-content').innerHTML = `
    <h2>🌐 动态神经拓扑图 (Neural Topology)</h2>
    <div class="grid" style="margin-bottom:12px">
      <div class="card"><h3>神经元节点数 (Nodes)</h3><div class="val ok">${net.total_nodes || nodes.length}</div></div>
      <div class="card"><h3>赫布突触连线 (Edges)</h3><div class="val">${net.total_edges || edges.length}</div></div>
    </div>
    <div class="card" style="padding:10px;text-align:center">
      <canvas id="neural-canvas" width="800" height="460" style="width:100%;max-width:800px;height:460px;background:#080c14;border-radius:6px;border:1px solid var(--border)"></canvas>
      <div class="muted" style="font-size:11px;margin-top:8px">💡 节点大小代表回忆显著性，连线粗细代表赫布突触强度（共同激活越多连线越深）</div>
    </div>
  `;

  drawNeuralCanvas(nodes, edges);
}

function drawNeuralCanvas(nodes, edges) {
  const canvas = document.getElementById('neural-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const w = canvas.width, h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  if (!nodes.length) {
    ctx.fillStyle = '#6e7681';
    ctx.font = '14px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('暂无记忆神经节点，请先进行对话或在试玩模式体验', w / 2, h / 2);
    return;
  }

  // 计算节点布局（环形 + 随机发散力导向）
  const nodeMap = {};
  const cx = w / 2, cy = h / 2;
  const count = Math.min(nodes.length, 36);
  for (let i = 0; i < count; i++) {
    const angle = (i / count) * 2 * Math.PI;
    const dist = 110 + (i % 3) * 55;
    nodeMap[nodes[i].id] = {
      x: cx + Math.cos(angle) * dist,
      y: cy + Math.sin(angle) * dist,
      weight: nodes[i].weight || 0.5,
      id: nodes[i].id,
    };
  }

  // 1. 画边（发光连线）
  edges.forEach(e => {
    const src = nodeMap[e.source];
    const dst = nodeMap[e.target];
    if (src && dst) {
      ctx.beginPath();
      ctx.moveTo(src.x, src.y);
      ctx.lineTo(dst.x, dst.y);
      ctx.strokeStyle = `rgba(122, 162, 255, ${Math.min(0.8, (e.weight || 0.3) * 1.5)})`;
      ctx.lineWidth = Math.max(1, (e.weight || 0.2) * 3);
      ctx.stroke();
    }
  });

  // 2. 画节点（带外发光圆）
  for (const n of Object.values(nodeMap)) {
    const r = Math.max(5, Math.min(18, n.weight * 18));
    
    // 渐变外光晕
    const grad = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, r * 2);
    grad.addColorStop(0, 'rgba(88, 166, 255, 0.8)');
    grad.addColorStop(1, 'rgba(88, 166, 255, 0)');
    ctx.beginPath();
    ctx.arc(n.x, n.y, r * 2, 0, 2 * Math.PI);
    ctx.fillStyle = grad;
    ctx.fill();

    // 核心圆点
    ctx.beginPath();
    ctx.arc(n.x, n.y, r, 0, 2 * Math.PI);
    ctx.fillStyle = '#7aa2ff';
    ctx.shadowColor = '#58a6ff';
    ctx.shadowBlur = 10;
    ctx.fill();
    ctx.shadowBlur = 0;

    // 节点标签
    ctx.fillStyle = '#c9d1d9';
    ctx.font = '10px monospace';
    ctx.textAlign = 'center';
    const label = n.id.length > 12 ? n.id.slice(0, 10) + '..' : n.id;
    ctx.fillText(label, n.x, n.y + r + 12);
  }
}

async function loadNetwork() {
  await loadNetworkGraph();
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

// ---- DEMO SIMULATION (Zero-cost Sandbox) ----
const DEMO_TRAITS = [
  { name: "同理心 / 共情", strength: 0.15, pending: 0.05, phase: "sprouting", color: "var(--accent)" },
  { name: "边界感 / 戒备", strength: 0.70, pending: 0.02, phase: "hardened", color: "var(--warn)" },
  { name: "幽默感 / 讽刺", strength: 0.35, pending: 0.08, phase: "growing", color: "var(--ok)" },
];

const DEMO_SCRIPTS = [
  { user: "其实我今天心里挺难受的，项目搞砸了...", char: "怎么会这样？要不要跟我说说发生了什么？先喝口水别急。", delta: { "同理心 / 共情": +0.12, "边界感 / 戒备": -0.05 }, note: "检测到脆弱倾诉，同理心蓄水池上涨，戒备降低" },
  { user: "你别管我了，反正我也没人在乎。", char: "话不能这么说，至少现在我就在这里听你说话呢。", delta: { "同理心 / 共情": +0.18, "幽默感 / 讽刺": -0.02 }, note: "坚定陪伴信号，触发共情突破门槛" },
  { user: "噗，你一个AI还挺会安慰人。", char: "那可不，本赛博崽子可是持证上岗的暖心特工！", delta: { "幽默感 / 讽刺": +0.15, "同理心 / 共情": +0.05 }, note: "轻松调侃互动，幽默感特质被激活" },
  { user: "哈哈谢谢你，我感觉好多了。", char: "随时都在！难受了就来找我聊天，充充电再出发。", delta: { "同理心 / 共情": +0.22, "边界感 / 戒备": -0.08 }, note: "【质变达成】同理心蓄水溢出，特质进入成长态(Growing)！" },
];

let _demoPlaying = false;
let _demoStep = 0;
let _demoTimer = null;

function renderDemoTraits() {
  const container = document.getElementById('demo-traits-monitor');
  if (!container) return;
  container.innerHTML = DEMO_TRAITS.map(t => {
    const total = Math.min(1.0, t.strength + t.pending);
    const strPct = Math.round(t.strength * 100);
    const pendPct = Math.round(t.pending * 100);
    return `<div style="background:var(--bg);padding:10px 14px;border-radius:6px;border:1px solid var(--border)">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
        <span style="font-weight:600;font-size:13px">${esc(t.name)}</span>
        <span style="font-size:11px;padding:2px 6px;border-radius:4px;background:rgba(255,255,255,0.06);color:${t.color}">
          ${esc(t.phase)} · ${(t.strength).toFixed(2)} (+${(t.pending).toFixed(2)})
        </span>
      </div>
      <div style="height:10px;background:rgba(255,255,255,0.08);border-radius:5px;overflow:hidden;position:relative">
        <div style="height:100%;width:${strPct}%;background:${t.color};transition:width 0.6s ease;position:absolute;left:0"></div>
        <div style="height:100%;left:${strPct}%;width:${pendPct}%;background:rgba(255,255,255,0.4);box-shadow:0 0 8px rgba(255,255,255,0.8);transition:all 0.6s ease;position:absolute"></div>
      </div>
    </div>`;
  }).join('');
}

function startDemoSimulation() {
  if (_demoPlaying) return;
  _demoPlaying = true;
  document.getElementById('demo-play-btn').disabled = true;
  document.getElementById('demo-status-text').innerHTML = '<span class="spinner"></span> 正在演化推演中...';
  
  const stream = document.getElementById('demo-dialogue-stream');
  if (_demoStep === 0) stream.innerHTML = '';

  function nextTurn() {
    if (_demoStep >= DEMO_SCRIPTS.length) {
      _demoPlaying = false;
      document.getElementById('demo-play-btn').disabled = false;
      document.getElementById('demo-status-text').innerHTML = '✅ 演化演示完毕（特质已完成质变跃迁）';
      toast('Demo 推演完成！特质曲线成功跃迁', 'ok');
      return;
    }
    const item = DEMO_SCRIPTS[_demoStep];
    _demoStep++;

    // 渲染对话气泡
    const div = document.createElement('div');
    div.style.padding = '8px 12px';
    div.style.borderRadius = '6px';
    div.style.background = 'var(--bg)';
    div.style.border = '1px solid var(--border)';
    div.style.fontSize = '12px';
    div.innerHTML = `
      <div style="color:var(--accent);margin-bottom:4px"><strong>👤 User:</strong> ${esc(item.user)}</div>
      <div style="color:var(--fg);margin-bottom:6px"><strong>🤖 Character:</strong> ${esc(item.char)}</div>
      <div style="font-size:11px;color:var(--ok);border-top:1px dashed var(--border);padding-top:4px">⚡ 动力学: ${esc(item.note)}</div>
    `;
    stream.appendChild(div);
    stream.scrollTop = stream.scrollHeight;

    // 更新特质数值
    for (const [k, d] of Object.entries(item.delta)) {
      const trait = DEMO_TRAITS.find(t => t.name === k);
      if (trait) {
        trait.pending = Math.max(0, trait.pending + d);
        if (trait.pending > 0.3) {
          trait.strength = Math.min(0.95, trait.strength + 0.25);
          trait.pending = 0.05;
          trait.phase = "growing";
        }
      }
    }
    renderDemoTraits();

    _demoTimer = setTimeout(nextTurn, 2200);
  }

  nextTurn();
}

function resetDemoSimulation() {
  if (_demoTimer) clearTimeout(_demoTimer);
  _demoPlaying = false;
  _demoStep = 0;
  DEMO_TRAITS[0].strength = 0.15; DEMO_TRAITS[0].pending = 0.05; DEMO_TRAITS[0].phase = "sprouting";
  DEMO_TRAITS[1].strength = 0.70; DEMO_TRAITS[1].pending = 0.02; DEMO_TRAITS[1].phase = "hardened";
  DEMO_TRAITS[2].strength = 0.35; DEMO_TRAITS[2].pending = 0.08; DEMO_TRAITS[2].phase = "growing";
  document.getElementById('demo-play-btn').disabled = false;
  document.getElementById('demo-status-text').innerText = '准备就绪，点击开始播放';
  document.getElementById('demo-dialogue-stream').innerHTML = '<div class="muted" style="text-align:center;padding:20px;font-size:12px">点击上方“播放演化推演”观察对话与特质联动</div>';
  renderDemoTraits();
}

// 页面初始化时挂载 demo
window.addEventListener('DOMContentLoaded', () => {
  renderDemoTraits();
});

// ---- DUAL-MODE CONSTANTS & PERSONA KNOBS ----
let _currentConstantsMode = 'macro';

const PRESET_MAP = {
  aloof:   { sensitivity: 0.25, stubbornness: 0.85, resilience: 0.80, vigilance: 0.85, creativity: 0.35 },
  gentle:  { sensitivity: 0.75, stubbornness: 0.30, resilience: 0.70, vigilance: 0.20, creativity: 0.75 },
  cheerful:{ sensitivity: 0.80, stubbornness: 0.20, resilience: 0.90, vigilance: 0.10, creativity: 0.60 },
  fragile: { sensitivity: 0.90, stubbornness: 0.40, resilience: 0.15, vigilance: 0.80, creativity: 0.85 },
};

function switchConstantsMode(mode) {
  _currentConstantsMode = mode;
  const macroView = document.getElementById('constants-macro-view');
  const microView = document.getElementById('constants-micro-view');
  const btnMacro = document.getElementById('tab-btn-macro');
  const btnMicro = document.getElementById('tab-btn-micro');
  
  if (mode === 'macro') {
    macroView.style.display = 'block';
    microView.style.display = 'none';
    btnMacro.className = 'btn btn-sm btn-ok';
    btnMicro.className = 'btn btn-sm btn-outline';
  } else {
    macroView.style.display = 'none';
    microView.style.display = 'block';
    btnMacro.className = 'btn btn-sm btn-outline';
    btnMicro.className = 'btn btn-sm btn-ok';
    loadConstants();
  }
}

function onKnobChange() {
  ['sensitivity', 'stubbornness', 'resilience', 'vigilance', 'creativity'].forEach(k => {
    const val = parseFloat(document.getElementById('knob-' + k).value).toFixed(2);
    document.getElementById('knob-val-' + k).innerText = val;
  });
}

function applyPersonaPreset(name) {
  const p = PRESET_MAP[name];
  if (!p) return;
  for (const [k, v] of Object.entries(p)) {
    const inp = document.getElementById('knob-' + k);
    if (inp) {
      inp.value = v;
      document.getElementById('knob-val-' + k).innerText = v.toFixed(2);
    }
  }
  toast(`已选择预设：${name}，点击下方保存即可持久化生效`, 'ok');
}

function resetPersonaKnobs() {
  ['sensitivity', 'stubbornness', 'resilience', 'vigilance', 'creativity'].forEach(k => {
    const inp = document.getElementById('knob-' + k);
    if (inp) {
      inp.value = 0.5;
      document.getElementById('knob-val-' + k).innerText = '0.50';
    }
  });
  toast('已重置为标准平衡态', 'ok');
}

function computeKnobsToOverrides() {
  const s = parseFloat(document.getElementById('knob-sensitivity').value);
  const st = parseFloat(document.getElementById('knob-stubbornness').value);
  const r = parseFloat(document.getElementById('knob-resilience').value);
  const v = parseFloat(document.getElementById('knob-vigilance').value);
  const c = parseFloat(document.getElementById('knob-creativity').value);

  const overrides = {};
  overrides["PLASTICITY"] = +(0.18 + 0.37 * s).toFixed(4);
  overrides["BREAKTHROUGH"] = +(0.95 - 0.25 * s).toFixed(4);
  overrides["FAST_LIMIT"] = +(0.15 + 0.27 * s).toFixed(4);
  overrides["CEILING"] = +(0.90 + 0.09 * st).toFixed(4);
  overrides["DECAY"] = +(0.995 + 0.0049 * st).toFixed(5);
  overrides["GATE_LEVEL_MULTIPLIER"] = +(1.02 + 0.33 * st).toFixed(3);
  overrides["FAST_DECAY"] = +(0.85 - 0.40 * r).toFixed(4);
  overrides["LEAK"] = +(0.98 - 0.18 * r).toFixed(4);
  overrides["PENDING_RESIDUAL"] = +(0.35 - 0.30 * r).toFixed(4);
  overrides["UNCERTAINTY_GATE"] = +(0.35 + 0.40 * v).toFixed(4);
  overrides["SARCASTIC_AMBIGUITY"] = +(0.88 - 0.38 * v).toFixed(4);
  overrides["SPREAD_DECAY"] = +(0.60 + 0.28 * c).toFixed(4);
  overrides["MAX_HOPS"] = Math.round(2 + 4 * c);
  overrides["EDGE_STRENGTHEN"] = +(0.15 + 0.35 * c).toFixed(4);

  return overrides;
}

async function savePersonaKnobs() {
  const overrides = computeKnobsToOverrides();
  try {
    const r = await call('POST', '/constants', {overrides, persist: true});
    toast(`性格气质已成功映射至 ${Object.keys(overrides).length} 项物理常数并永久落盘！`, 'ok');
  } catch(e) {
    toast('保存失败: ' + e.message, 'err');
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
  const r = await call('POST', '/constants', {overrides, persist: true});
  const n = Object.keys(r.applied||{}).length;
  toast(`${n} constants saved and persisted to disk`, 'ok');
  loadConstants();
}

async function clearConstants() {
  if (!confirm('确定要重置所有常数覆盖并恢复默认值吗？')) return;
  try {
    const r = await call('POST', '/constants/clear', {});
    toast(`已清空所有覆盖 (${r.cleared||0} 项)`, 'ok');
    loadConstants();
  } catch(e) {
    toast('重置失败: ' + e.message, 'err');
  }
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
    // update base URL display with local network addresses
    updateBaseUrlDisplay();
    // upstream model values are fetched from API, no need to restore
  } catch(e) {
    toast('Could not load config: ' + e.message, 'err');
  }
}

async function updateBaseUrlDisplay() {
  const altEl = document.getElementById('client-base-url-alt');
  const errEl = document.getElementById('client-base-url-err');
  try {
    const addrs = await callAdmin('GET', '/admin/addresses');
    if (addrs.local && addrs.local.length) {
      const primary = addrs.local[0];
      altEl.innerHTML = `跨 App 用：http://${primary}:8781/v1`;
      if (errEl) errEl.textContent = '';
    } else {
      altEl.textContent = '未检测到局域网 IP，跨 App 请手动输入本机 IP';
      if (errEl) errEl.textContent = '提示：手机和电脑必须连同一个 WiFi';
    }
  } catch(e) {
    altEl.textContent = '地址检测失败，请刷新重试';
    if (errEl) errEl.textContent = '请确保 proxy 已启动，并且手机和客户端在同一网络';
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
// // check for updates
// checkVersion();
async function saveGrowthSettings() {
  const statusEl = document.getElementById('growth-settings-status');
  const batch = parseInt(document.getElementById('grow-batch').value) || 20;
  const idle = parseInt(document.getElementById('grow-idle').value) || 900;
  const interval = parseInt(document.getElementById('grow-interval').value) || 60;
  statusEl.innerHTML = '<span class="spinner"></span> 正在保存...';
  try {
    const r = await callAdmin('POST', '/admin/growth-settings', {batch_turns: batch, idle_seconds: idle, grow_interval: interval});
    if (r.ok) {
      statusEl.innerHTML = '<span class="ok">✅ 已保存。重启 loam 后生效。</span>';
      document.getElementById('growth-batch').textContent = batch;
      document.getElementById('growth-idle').textContent = Math.round(idle/60);
    } else {
      statusEl.innerHTML = '<span class="err">❌ ' + (r.error||'保存失败') + '</span>';
    }
  } catch(e) {
    statusEl.innerHTML = '<span class="err">❌ ' + e.message + '</span>';
  }
}

async function loadActions() {
  try {
    const data = await callAdmin('GET', '/admin/growth-settings');
    if (data) {
      if (data.batch_turns) { document.getElementById('grow-batch').value = data.batch_turns; document.getElementById('growth-batch').textContent = data.batch_turns; }
      if (data.idle_seconds) { document.getElementById('grow-idle').value = data.idle_seconds; document.getElementById('growth-idle').textContent = Math.round(data.idle_seconds/60); }
      if (data.grow_interval) { document.getElementById('grow-interval').value = data.grow_interval; }
    }
  } catch(e) { /* ignore */ }
}
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
        elif self.path == "/admin/addresses":
            self._json(self._local_addresses())
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
    def _local_addresses(self):
        """Return non-loopback local IPs and loopback for same-machine use.

        Tries socket.gethostbyname first, then falls back to parsing
        ifconfig/ip output so Android/Termux environments can expose
        the LAN IP to other apps (e.g. Operit).
        """
        addrs: Dict[str, Any] = {"loopback": "127.0.0.1", "local": []}
        try:
            # best-effort: get a non-loopback IP via socket
            hostname = socket.gethostname()
            addrs["hostname"] = hostname
            try:
                ip = socket.gethostbyname(hostname)
                if ip and not ip.startswith("127."):
                    addrs["local"].append(ip)
            except Exception:
                pass

            # fallback: parse ifconfig / ip addr
            seen = set(addrs["local"])
            candidates: List[str] = []
            try:
                import subprocess as sp
                try:
                    out = sp.check_output(["ifconfig"], stderr=sp.DEVNULL, timeout=5).decode("utf-8", "ignore")
                except Exception:  # noqa: BLE001
                    out = sp.check_output(["ip", "addr"], stderr=sp.DEVNULL, timeout=5).decode("utf-8", "ignore")
                for m in re.finditer(r"inet\s+(?:addr:)?(\d+\.\d+\.\d+\.\d+)", out):
                    candidates.append(m.group(1))
            except Exception:
                pass

            for ip in candidates:
                if ip and not ip.startswith("127.") and ip not in seen:
                    seen.add(ip)
                    addrs["local"].append(ip)
        except Exception:
            pass
        return addrs

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
            "base_url": (body.get("base_url") or "").strip().rstrip("/v1").rstrip("/"),
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
        """Return local commit hash + fetch remote via curl (not git ls-remote)."""
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
            req = urllib.request.Request(
                "https://api.github.com/repos/lmynszbd-ctrlbe/Loam-A-Runtime-Where-Characters-Grow-a-Self-from-Memory-/commits/main",
                headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "loam-admin"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                remote = data.get("sha", "")[:7]
        except Exception:
            pass  # network failed, silently skip
        has_update = bool(local and remote and local != remote)
        return {"local": local, "remote": remote, "has_update": has_update}
    def _run_update(self):
        """Run git pull and restart loam + proxy.

        Users who tinkered with tracked source files would otherwise get
        blocked by ``git pull --ff-only`` ("local changes would be
        overwritten"). To keep the update button robust we auto-stash any
        local changes, pull, then restore the stash. If restoring conflicts
        we KEEP the stash (never silently drop the user's work) and report it
        so they can resolve it by hand.

        Body option ``{"discard_local": true}`` lets the user opt in to
        throwing away local changes and hard-resetting to the remote — off by
        default so we never destroy work unless explicitly asked.
        """
        body = self._read_body()
        discard_local = bool(body.get("discard_local"))
        # Data-safety net: snapshot the .loam runtime DBs before touching the
        # tree, so even if something goes wrong the user's memory is recoverable.
        skip_snapshot = bool(body.get("skip_snapshot"))
        repo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        def git(*args, timeout=30):
            return subprocess.run(["git", "-C", repo_dir, *args],
                                  capture_output=True, text=True, timeout=timeout)

        def snapshot_data():
            """Copy runtime DBs to ~/.loam/snapshots/pre_update_<stamp>.

            Returns (snapshot_dir, [copied files]) or (None, []) if nothing to
            back up. Best-effort: failures never block the update itself, but we
            surface them so the caller can decide.
            """
            import shutil
            stamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
            snap_dir = SECRETS_HOME / "snapshots" / f"pre_update_{stamp}"
            copied = []
            for name in ("journal.db", "memory.db"):
                src = SECRETS_HOME / name
                if not src.exists():
                    continue
                snap_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, snap_dir / name)
                copied.append(name)
            return (str(snap_dir) if copied else None), copied

        try:
            snapshot_dir = None
            snapshot_files = []
            snapshot_error = None
            if not skip_snapshot:
                try:
                    snapshot_dir, snapshot_files = snapshot_data()
                except Exception as se:
                    snapshot_error = str(se)[:200]
            # Opt-in destructive path: hard reset to remote, dropping local work.
            if discard_local:
                f = git("fetch", "origin")
                if f.returncode != 0:
                    return {"error": "git fetch failed", "detail": (f.stdout + "\n" + f.stderr).strip()[:300]}
                # determine current branch, default to main
                b = git("rev-parse", "--abbrev-ref", "HEAD")
                branch = (b.stdout.strip() or "main") if b.returncode == 0 else "main"
                rs = git("reset", "--hard", f"origin/{branch}")
                if rs.returncode != 0:
                    return {"error": "git reset failed", "detail": (rs.stdout + "\n" + rs.stderr).strip()[:300]}
                git("clean", "-fd")  # remove untracked files the user chose to discard
                out = rs.stdout.strip()
                stash_conflict = None
            else:
                # 1) stash local changes (tracked + untracked) if the tree is dirty
                status = git("status", "--porcelain")
                dirty = bool(status.stdout.strip())
                stashed = False
                if dirty:
                    s = git("stash", "push", "-u", "-m", "loam-auto-update")
                    stashed = s.returncode == 0 and "No local changes" not in (s.stdout or "")

                # 2) fast-forward pull
                r = git("pull", "--ff-only")
                out = r.stdout.strip()
                if r.returncode != 0:
                    # restore the user's work before bailing out
                    if stashed:
                        git("stash", "pop")
                    out = (out + "\n" + r.stderr).strip()
                    return {"error": "git pull failed", "detail": out[:300]}

                # 3) restore the stashed local changes
                stash_conflict = None
                if stashed:
                    p = git("stash", "pop")
                    if p.returncode != 0:
                        # keep the stash for manual resolution — do NOT drop it
                        stash_conflict = (p.stdout + "\n" + p.stderr).strip()[:300]


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
            result = {"ok": True, "detail": out[:200], "restarted": restart}
            if snapshot_dir:
                result["snapshot"] = snapshot_dir
                result["snapshot_files"] = snapshot_files
            if snapshot_error:
                result["snapshot_error"] = snapshot_error
            if stash_conflict:
                result["warning"] = (
                    "本地改动已拉取新代码，但你的本地修改在自动恢复时发生冲突，"
                    "已保留在 git stash 里（未丢失）。请手动 `git stash pop` 解决冲突。"
                )
                result["stash_conflict"] = stash_conflict
            return result
        except Exception as e:
            return {"error": str(e)}

    def _read_constants_local(self):
        """Read constants + descriptions directly from constants.py and state/overrides.json."""
        import importlib
        try:
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            import loam.core.constants as C
            from loam.core.state import load_persisted_overrides
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
        overrides = load_persisted_overrides(home=SECRETS_HOME)
        return {"constants": all_consts, "overrides": overrides, "descriptions": descriptions}

    def _restart_proxy(self):
        """Kill and restart the forced proxy process so it picks up new upstreams.json."""
        repo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # 先确保文件存在
        if not UPSTREAMS_FILE.exists():
            write_json_file(UPSTREAMS_FILE, {"default":"relayA","providers":{"relayA":{"base_url":"","api_key":"","default_model":""}}})
        # 强杀端口占用
        import subprocess as sp
        try:
            sp.run(["fuser", "-k", "8781/tcp"], timeout=5, capture_output=True)
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