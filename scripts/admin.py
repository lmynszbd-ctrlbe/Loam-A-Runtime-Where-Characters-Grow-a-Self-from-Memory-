#!/usr/bin/env python3
"""loam admin panel — 可视化管理面板，纯标准库。

Usage:
  python scripts/admin.py
  → http://127.0.0.1:8900 (internal; use the unified gateway externally)
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
ADMIN_HOST = os.environ.get("ADMIN_HOST", "127.0.0.1")
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



def api(path, method="GET", body=None, character=None):
    try:
        secrets = read_json_file(SECRETS_FILE)
        api_key = os.environ.get("LOAM_API_KEY") or (secrets.get("api_key") if isinstance(secrets, dict) else "")
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(f"{LOAM}{path}", data=data, method=method)
            req.add_header("Content-Type", "application/json")
        else:
            req = urllib.request.Request(f"{LOAM}{path}", method=method)
        if api_key:
            req.add_header("X-API-Key", str(api_key).strip())
        if character:
            req.add_header("X-Loam-Character", str(character).strip())
        with urllib.request.urlopen(req, timeout=90) as r:
            raw = r.read().decode("utf-8")
            return json.loads(raw) if raw else {}
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
  --bg: #0c0d10;
  --bg-subtle: rgba(22, 24, 30, 0.78);
  --bg-card: rgba(18, 20, 25, 0.86);
  --bg-card-hover: rgba(25, 28, 35, 0.94);
  --bg-card-solid: #121419;
  --surface: #121419;
  --border: rgba(226, 218, 203, 0.10);
  --border-hover: rgba(212, 163, 115, 0.42);
  --border-strong: rgba(212, 163, 115, 0.62);
  --fg: #ebe6dc;
  --text: #ebe6dc;
  --text-color: #ebe6dc;
  --fg-dim: #a8a298;
  --muted: #78736a;
  --accent: #d4a373;
  --accent-rgb: 212, 163, 115;
  --accent-grad: linear-gradient(135deg, #d4a373 0%, #b5835a 100%);
  --accent-soft: rgba(212, 163, 115, 0.12);
  --accent-2: #8a9bb5;
  --warn: #d99b52;
  --err: #c96d63;
  --ok: #7fa08e;
  --input-bg: rgba(10, 11, 14, 0.82);
  --radius-sm: 6px;
  --radius: 10px;
  --radius-lg: 14px;
  --shadow-sm: 0 2px 8px rgba(0, 0, 0, 0.32);
  --shadow: 0 12px 32px -10px rgba(0, 0, 0, 0.62), inset 0 1px 0 rgba(255, 250, 240, 0.03);
  --shadow-lg: 0 20px 44px -12px rgba(0, 0, 0, 0.75);
  --glass: blur(16px);
  --sidebar-width: 256px;
  --sidebar-collapsed-width: 68px;
  --font-serif: 'Songti SC', 'Noto Serif SC', 'Source Han Serif SC', 'STSong', 'Newsreader', 'Georgia', serif;
  --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
  --font-mono: 'JetBrains Mono', 'SF Mono', 'Consolas', monospace;
  --glow:
    radial-gradient(950px 520px at 10% -8%, rgba(212, 163, 115, 0.09), transparent 62%),
    radial-gradient(850px 500px at 92% 6%, rgba(127, 160, 142, 0.07), transparent 60%),
    radial-gradient(750px 550px at 50% 108%, rgba(138, 155, 181, 0.05), transparent 62%);
}

.light {
  --bg: #f4f0e8;
  --bg-subtle: rgba(236, 230, 219, 0.85);
  --bg-card: rgba(251, 249, 244, 0.92);
  --bg-card-hover: #ffffff;
  --bg-card-solid: #fbf9f4;
  --surface: #fbf9f4;
  --border: rgba(32, 29, 24, 0.11);
  --border-hover: rgba(156, 102, 68, 0.45);
  --border-strong: rgba(156, 102, 68, 0.65);
  --fg: #1c1a17;
  --text: #1c1a17;
  --text-color: #1c1a17;
  --fg-dim: #57524a;
  --muted: #857f75;
  --accent: #9c6644;
  --accent-rgb: 156, 102, 68;
  --accent-grad: linear-gradient(135deg, #9c6644 0%, #7f5539 100%);
  --accent-soft: rgba(156, 102, 68, 0.10);
  --accent-2: #5c6f84;
  --warn: #b5651d;
  --err: #a8423b;
  --ok: #4a7c59;
  --input-bg: #f7f4ed;
  --shadow-sm: 0 2px 6px rgba(28, 26, 23, 0.04);
  --shadow: 0 10px 26px -8px rgba(28, 26, 23, 0.07), inset 0 1px 0 rgba(255, 255, 255, 0.8);
  --shadow-lg: 0 16px 34px -10px rgba(28, 26, 23, 0.11);
  --glow:
    radial-gradient(900px 480px at 8% -5%, rgba(156, 102, 68, 0.06), transparent 60%),
    radial-gradient(850px 480px at 92% 4%, rgba(74, 124, 89, 0.05), transparent 58%);
}

* { margin: 0; padding: 0; box-sizing: border-box; }
::selection { background: rgba(var(--accent-rgb), 0.25); }
html { scroll-behavior: smooth; }

body {
  font: 13.5px/1.68 var(--font-sans);
  background-color: var(--bg);
  color: var(--fg);
  display: flex;
  flex-direction: row;
  min-height: 100vh;
  letter-spacing: 0.01em;
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

/* ---- Editorial Typography ---- */
h1 {
  font-family: var(--font-serif);
  font-size: 25px;
  font-weight: 600;
  letter-spacing: 0.02em;
  margin-bottom: 6px;
  color: var(--fg);
  display: flex;
  align-items: baseline;
  gap: 12px;
}

h2 {
  font-family: var(--font-serif);
  font-size: 16.5px;
  font-weight: 600;
  letter-spacing: 0.02em;
  margin: 20px 0 12px;
  color: var(--fg);
}

h3 {
  font-size: 13.5px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  margin-bottom: 12px;
  color: var(--fg);
  display: flex;
  align-items: center;
  gap: 8px;
}

.sub {
  font-size: 13px;
  color: var(--fg-dim);
  margin-bottom: 22px;
  line-height: 1.58;
  border-left: 2px solid rgba(var(--accent-rgb), 0.35);
  padding-left: 12px;
}

.muted { color: var(--muted); }
.ok { color: var(--ok) !important; font-weight: 600; }
.err { color: var(--err) !important; font-weight: 600; }
.warn { color: var(--warn) !important; font-weight: 600; }
.nav-idx {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--muted);
  letter-spacing: 0.05em;
  min-width: 20px;
}
nav .nav-links a.active .nav-idx {
  color: var(--accent);
}

/* ---- Sidebar Navigation ---- */
nav {
  width: var(--sidebar-width);
  flex-shrink: 0;
  padding: 20px 14px 24px;
  z-index: 100;
  background: var(--bg-card);
  backdrop-filter: var(--glass);
  -webkit-backdrop-filter: var(--glass);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 14px;
  position: sticky;
  top: 0;
  height: 100vh;
  overflow-y: auto;
  transition: width 0.28s cubic-bezier(0.4, 0, 0.2, 1), transform 0.28s cubic-bezier(0.4, 0, 0.2, 1);
}

nav .logo {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 8px 16px;
  border-bottom: 1px solid var(--border);
}

.logo-text {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 20px;
  font-weight: 800;
}

.gradient-text {
  background: var(--accent-grad);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  letter-spacing: -0.03em;
}

.version-badge {
  font-size: 10.5px;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 999px;
  background: rgba(var(--accent-rgb), 0.14);
  color: var(--accent);
  border: 1px solid rgba(var(--accent-rgb), 0.28);
  letter-spacing: 0.02em;
}

nav .logo .theme-btn {
  background: rgba(var(--accent-rgb), 0.06);
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
  padding: 0;
  transition: all 0.2s ease;
}

nav .logo .theme-btn:hover {
  background: rgba(var(--accent-rgb), 0.15);
  border-color: var(--accent);
  color: var(--fg);
  transform: translateY(-1px);
}

.nav-content {
  display: flex;
  flex-direction: column;
  flex: 1;
}

.nav-links {
  display: flex;
  flex-direction: column;
  gap: 5px;
  margin-top: 6px;
  flex: 1;
}

nav a.nav-link, nav .nav-links a {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  color: var(--fg-dim);
  text-decoration: none;
  font-size: 13.5px;
  font-weight: 550;
  border-radius: 12px;
  border: 1px solid transparent;
  transition: all 0.18s ease;
  white-space: nowrap;
  overflow: hidden;
}

nav .nav-links a:hover {
  color: var(--fg);
  background: rgba(var(--accent-rgb), 0.09);
  border-color: rgba(var(--accent-rgb), 0.18);
  transform: translateX(3px);
}

nav .nav-links a.active {
  color: var(--fg);
  background: rgba(var(--accent-rgb), 0.11);
  font-weight: 600;
  border-color: rgba(var(--accent-rgb), 0.25);
  border-left: 3px solid var(--accent);
  border-radius: 4px 10px 10px 4px;
}

/* Sidebar Collapsed State */
body.sidebar-collapsed nav {
  width: var(--sidebar-collapsed-width);
  padding: 20px 10px;
}
body.sidebar-collapsed .logo-text .gradient-text,
body.sidebar-collapsed .logo-text .version-badge,
body.sidebar-collapsed .nav-content > div:first-child {
  display: none;
}
body.sidebar-collapsed nav .logo {
  flex-direction: column;
  gap: 8px;
  padding: 4px 0 12px;
}
body.sidebar-collapsed .nav-links a {
  justify-content: center;
  padding: 10px 0;
  font-size: 0;
}
body.sidebar-collapsed .nav-links a::first-letter {
  font-size: 18px;
}
body.sidebar-collapsed #collapse-icon {
  transform: rotate(180deg);
}

/* ---- Main Layout & Panels ---- */
main {
  flex: 1;
  padding: 28px 38px 64px;
  max-width: 1360px;
  margin: 0 auto;
  z-index: 10;
  width: 100%;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.panel {
  display: none;
  animation: fadeIn 0.24s cubic-bezier(0.16, 1, 0.3, 1);
}
.panel.active {
  display: block;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}

/* ---- Grid & Cards ---- */
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(275px, 1fr));
  gap: 16px;
  margin-bottom: 18px;
}

.card, section {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px 22px;
  backdrop-filter: var(--glass);
  -webkit-backdrop-filter: var(--glass);
  box-shadow: var(--shadow);
  transition: border-color 0.22s ease, box-shadow 0.22s ease, transform 0.22s ease;
  position: relative;
}

.card:hover {
  border-color: var(--border-hover);
  box-shadow: var(--shadow-lg);
}

.preset-card:hover {
  border-color: var(--accent) !important;
  background: rgba(var(--accent-rgb), 0.1) !important;
  transform: translateY(-3px);
}

/* ---- Stats & Overview Rows ---- */
.stat {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8.5px 0;
  border-bottom: 1px dashed var(--border);
  font-size: 13px;
  color: var(--fg-dim);
}
.stat:last-child {
  border-bottom: none;
  padding-bottom: 2px;
}
.stat .val, .val {
  font-family: 'JetBrains Mono', 'Fira Code', ui-monospace, monospace;
  font-weight: 700;
  font-size: 14px;
  color: var(--fg);
}
.card > .val {
  font-size: 28px;
  margin-top: 4px;
}

/* ---- Trait Progress Bars ---- */
.trait {
  display: grid;
  grid-template-columns: minmax(140px, 1.2fr) 2fr 52px;
  align-items: center;
  gap: 14px;
  padding: 9px 12px;
  border-radius: 10px;
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  margin-bottom: 8px;
}
.trait:last-child { margin-bottom: 0; }
.trait-name {
  font-weight: 600;
  font-size: 13px;
  color: var(--fg);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.trait-bar {
  width: 100%;
  height: 8px;
  background: rgba(148, 163, 184, 0.16);
  border-radius: 999px;
  overflow: hidden;
  display: inline-block;
  vertical-align: middle;
}
.trait-fill {
  height: 100%;
  background: var(--accent-grad);
  border-radius: 999px;
  box-shadow: 0 0 10px rgba(var(--accent-rgb), 0.5);
  transition: width 0.5s cubic-bezier(0.22, 1, 0.36, 1);
}
.trait-val {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  font-weight: 700;
  color: var(--accent);
  text-align: right;
}

/* ---- Action Bar & Buttons ---- */
.actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-bottom: 18px;
}

button, .btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  font-family: inherit;
  font-size: 13px;
  font-weight: 600;
  padding: 8.5px 16px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: rgba(var(--accent-rgb), 0.1);
  color: var(--fg);
  cursor: pointer;
  transition: all 0.18s cubic-bezier(0.4, 0, 0.2, 1);
  outline: none;
  text-decoration: none;
  white-space: nowrap;
}

button:hover, .btn:hover {
  border-color: var(--accent);
  background: rgba(var(--accent-rgb), 0.2);
  color: #fff;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(var(--accent-rgb), 0.22);
}
.light button:hover, .light .btn:hover {
  color: var(--accent);
}

button:disabled, .btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

.btn-sm {
  padding: 6px 13px;
  font-size: 12.5px;
  border-radius: 8px;
}

.btn-outline {
  background: transparent;
  border-color: var(--border-strong);
  color: var(--fg-dim);
}
.btn-outline:hover {
  color: var(--fg);
  background: rgba(var(--accent-rgb), 0.12);
}

.btn-ok {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  color: #ffffff !important;
  border-color: rgba(255, 255, 255, 0.15);
  box-shadow: 0 4px 14px rgba(16, 185, 129, 0.3);
}
.btn-ok:hover {
  background: linear-gradient(135deg, #34d399 0%, #10b981 100%);
  border-color: rgba(255, 255, 255, 0.3);
  box-shadow: 0 6px 18px rgba(16, 185, 129, 0.45);
}

.btn-err, .btn-danger {
  background: linear-gradient(135deg, #f43f5e 0%, #e11d48 100%);
  color: #ffffff !important;
  border-color: rgba(255, 255, 255, 0.15);
  box-shadow: 0 4px 14px rgba(244, 63, 94, 0.28);
}
.btn-err:hover, .btn-danger:hover {
  box-shadow: 0 6px 18px rgba(244, 63, 94, 0.45);
}

.btn-warn {
  background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
  color: #ffffff !important;
  border-color: transparent;
}

/* ---- Forms & Inputs ---- */
.form-group {
  display: flex;
  flex-direction: column;
  gap: 5px;
  margin-bottom: 12px;
}

.form-group label, label {
  font-size: 12px;
  font-weight: 600;
  color: var(--fg-dim);
}

input, textarea, select {
  font-family: inherit;
  font-size: 13px;
  background: var(--input-bg);
  color: var(--fg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 8.5px 12px;
  width: 100%;
  outline: none;
  transition: border-color 0.18s ease, box-shadow 0.18s ease;
}

textarea {
  min-height: 90px;
  font-family: 'JetBrains Mono', monospace;
  resize: vertical;
}

input:focus, textarea:focus, select:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(var(--accent-rgb), 0.18);
}

input[type="range"] {
  -webkit-appearance: none;
  appearance: none;
  height: 6px;
  background: rgba(148, 163, 184, 0.22);
  border-radius: 999px;
  padding: 0;
  border: none;
  cursor: pointer;
}
input[type="range"]::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--accent);
  border: 2px solid #ffffff;
  box-shadow: 0 2px 8px rgba(var(--accent-rgb), 0.55);
  cursor: pointer;
  transition: transform 0.15s ease;
}
input[type="range"]::-webkit-slider-thumb:hover {
  transform: scale(1.15);
}

/* ---- Constants Micro Table ---- */
.const-row {
  display: grid;
  grid-template-columns: 220px 110px 120px 1fr;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
  border-radius: 8px;
  font-size: 12.5px;
}
.const-row:hover {
  background: rgba(var(--accent-rgb), 0.05);
}
.const-name {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 600;
  color: var(--fg);
}
.const-input {
  font-family: 'JetBrains Mono', monospace;
  padding: 5px 8px;
  text-align: right;
}
.const-val {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: var(--muted);
}
.const-desc {
  color: var(--fg-dim);
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ---- Timeline, Events & Narrative ---- */
.timeline {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 8px;
}
.event {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 11px 14px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  font-size: 13.5px;
  line-height: 1.55;
}
.event-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  margin-top: 6px;
  flex-shrink: 0;
  box-shadow: 0 0 8px currentColor;
}
.narrative {
  font-size: 14px;
  line-height: 1.75;
  color: var(--fg);
  white-space: pre-wrap;
}

/* ---- Banner & Toast & Modal ---- */
.banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 11px 16px;
  margin-bottom: 22px;
  border-radius: 12px;
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid rgba(245, 158, 11, 0.3);
  color: var(--fg);
  font-size: 12.5px;
}
.banner-dismiss {
  background: transparent;
  border: none;
  color: var(--fg-dim);
  font-size: 18px;
  padding: 0 6px;
  cursor: pointer;
}
.banner-dismiss:hover {
  background: transparent;
  color: var(--fg);
  transform: none;
  box-shadow: none;
}

#toast-container {
  position: fixed;
  top: 20px;
  right: 24px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 8px;
  pointer-events: none;
}
.toast {
  pointer-events: auto;
  padding: 11px 18px;
  border-radius: 12px;
  background: var(--bg-card-solid);
  border: 1px solid var(--border-strong);
  color: var(--fg) !important;
  font-size: 13px;
  font-weight: 600;
  box-shadow: var(--shadow-lg);
  backdrop-filter: var(--glass);
  animation: fadeIn 0.2s ease;
}
.toast.ok { border-left: 4px solid var(--ok); }
.toast.err { border-left: 4px solid var(--err); }
.toast.warn { border-left: 4px solid var(--warn); }

.spinner {
  display: inline-block;
  width: 13px;
  height: 13px;
  border: 2px solid rgba(var(--accent-rgb), 0.3);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  vertical-align: -2px;
  margin-right: 4px;
}
@keyframes spin { to { transform: rotate(360deg); } }

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.65);
  backdrop-filter: blur(6px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.modal-box {
  background: var(--bg-card-solid);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius);
  padding: 24px;
  max-width: 440px;
  width: 90%;
  box-shadow: var(--shadow-lg);
}
.modal-actions {
  display: flex;
  gap: 10px;
  margin-top: 18px;
  justify-content: flex-end;
}

pre, code {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 12.5px;
}
pre {
  background: rgba(5, 8, 15, 0.82);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 14px;
  color: #cbd5e1;
  overflow-x: auto;
  line-height: 1.55;
}
.light pre { background: #1e293b; color: #f8fafc; }

::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(148, 163, 184, 0.22); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: rgba(148, 163, 184, 0.4); }

/* ---- Adaptive & Responsive Layout (Desktop / Tablet / Mobile) ---- */
.mobile-header {
  display: none;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  background: var(--bg-card-solid);
  backdrop-filter: var(--glass);
  -webkit-backdrop-filter: var(--glass);
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  z-index: 90;
}
.nav-toggle-btn {
  background: rgba(var(--accent-rgb), 0.08);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--fg);
  cursor: pointer;
  width: 34px;
  height: 34px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
}
.sidebar-overlay {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.58);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  z-index: 95;
  opacity: 0;
  transition: opacity 0.25s ease;
}

#traits-table {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

canvas {
  display: block;
  max-width: 100%;
}

#demo-hebb-canvas {
  width: 100% !important;
  height: auto !important;
  aspect-ratio: 540 / 215;
}

#neural-canvas {
  width: 100% !important;
  height: auto !important;
  aspect-ratio: 800 / 460;
}

/* Tablet & Small Laptop (<= 1024px) */
@media (max-width: 1024px) {
  main {
    padding: 24px 24px 56px;
  }
  .grid {
    grid-template-columns: 1fr !important;
  }
  #characters-grid {
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)) !important;
  }
  .connect-form-row, .upstream-row {
    grid-template-columns: 1fr 1fr !important;
  }
  .const-row {
    grid-template-columns: 1fr 110px;
  }
  .const-val, .const-desc {
    grid-column: 1 / -1;
  }
}

/* Mobile & Phablet (<= 768px) */
@media (max-width: 768px) {
  .mobile-header { display: flex; }
  body { flex-direction: column; }

  /* Ensure mobile slide-out drawer is always full width even if desktop sidebar was collapsed */
  nav,
  body.sidebar-collapsed nav {
    position: fixed;
    top: 0;
    left: 0;
    width: min(82vw, 280px) !important;
    height: 100vh;
    height: 100dvh;
    padding: 18px 14px 28px !important;
    transform: translateX(-105%);
    box-shadow: 8px 0 32px rgba(0, 0, 0, 0.55);
    z-index: 100;
  }
  nav.mobile-open,
  body.sidebar-collapsed nav.mobile-open {
    transform: translateX(0);
  }
  body.sidebar-collapsed .logo-text .gradient-text,
  body.sidebar-collapsed .logo-text .version-badge,
  body.sidebar-collapsed .nav-content > div:first-child {
    display: flex !important;
  }
  body.sidebar-collapsed .nav-links a {
    justify-content: flex-start !important;
    padding: 10px 14px !important;
    font-size: 13.5px !important;
  }

  .sidebar-overlay.active { display: block; opacity: 1; }
  .desktop-only { display: none !important; }

  main {
    padding: 16px 14px calc(48px + env(safe-area-inset-bottom, 0px));
    max-width: 100vw;
    overflow-x: hidden;
  }

  h1 { font-size: 20px; line-height: 1.35; flex-wrap: wrap; }
  h2 { font-size: 15.5px; }
  .sub { font-size: 12.5px; margin-bottom: 16px; padding-left: 10px; }
  .card, section { padding: 14px 15px; border-radius: 8px; }

  .connect-form-row, .upstream-row, #characters-grid {
    grid-template-columns: 1fr !important;
  }
  .connect-form-row .btn, .upstream-row .btn {
    width: 100%;
    justify-content: center;
  }

  #demo-scenario-select,
  #const-search-inp,
  #up-default {
    width: 100% !important;
    min-width: 0 !important;
    max-width: 100% !important;
  }

  #demo-act-scrubber {
    grid-template-columns: repeat(2, 1fr) !important;
  }

  .trait {
    flex-wrap: wrap;
    gap: 6px;
  }
  .trait-name {
    width: 100%;
    flex: 1 1 100%;
  }
  .trait-bar {
    flex: 1;
  }

  /* Prevent iOS Safari auto-zoom on input focus */
  input, select, textarea {
    font-size: 16px !important;
  }
}

/* Small Phones (<= 420px) */
@media (max-width: 420px) {
  .mobile-header { padding: 8px 12px; }
  main { padding: 12px 10px 40px; }
  .card, section { padding: 12px; }
  .actions { gap: 6px; }
  .actions .btn { flex: 1 1 auto; justify-content: center; }
  .const-row { grid-template-columns: 1fr; gap: 6px; }
  .const-input { width: 100% !important; }
}
</style>
</head>
<body>
<!-- 移动端顶部标题栏 -->
<header class="mobile-header">
  <div style="display:flex;align-items:baseline;gap:6px;min-width:0">
    <span style="font-family:var(--font-serif);font-size:19px;font-weight:700;letter-spacing:0.05em;color:var(--fg)">LOAM</span>
    <span style="font-family:var(--font-mono);font-size:9.5px;color:var(--accent);white-space:nowrap">RUNTIME</span>
  </div>
  <div style="display:flex;align-items:center;gap:6px;flex:1;justify-content:flex-end;min-width:0">
    <select id="mobile-char-select" onchange="onSidebarCharacterChange(this.value)" title="切换当前角色" style="width:auto;max-width:145px;padding:4px 8px;font-size:12.5px !important;font-weight:600;border-radius:6px;background:var(--input-bg);color:var(--fg);border:1px solid var(--border-hover)">
      <option value="default">default</option>
    </select>
    <button class="nav-toggle-btn" onclick="toggleTheme()" title="切换昼夜主题" style="font-family:var(--font-mono);font-size:13px">◐</button>
    <button id="menu-btn" class="nav-toggle-btn" onclick="toggleSidebar()" title="打开导航菜单">
      <svg viewBox="0 0 24 24" width="19" height="19" stroke="currentColor" stroke-width="1.8" fill="none" stroke-linecap="round"><line x1="4" y1="7" x2="20" y2="7"></line><line x1="4" y1="12" x2="20" y2="12"></line><line x1="4" y1="17" x2="20" y2="17"></line></svg>
    </button>
  </div>
</header>
<div id="sidebar-overlay" class="sidebar-overlay" onclick="toggleSidebar()"></div>

<nav id="sidebar">
  <div class="logo">
    <div class="logo-text" style="display:flex;flex-direction:column;align-items:flex-start;gap:2px">
      <div style="display:flex;align-items:baseline;gap:8px">
        <span class="gradient-text" style="font-family:var(--font-serif);font-size:22px;font-weight:700;letter-spacing:0.06em">LOAM</span>
        <span class="version-badge" style="font-family:var(--font-mono);font-size:10px">v0.8</span>
      </div>
      <span style="font-size:10.5px;color:var(--muted);letter-spacing:0.08em;text-transform:uppercase">Selfhood Runtime</span>
    </div>
    <div style="display:flex;gap:4px;">
      <button class="theme-btn" onclick="toggleTheme()" title="切换昼夜主题" style="font-family:var(--font-mono);font-size:11px">◐</button>
      <button id="collapse-btn" class="theme-btn desktop-only" onclick="toggleCollapse()" title="收起/展开导航栏">
        <svg id="collapse-icon" viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="1.8" fill="none" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"></polyline></svg>
      </button>
    </div>
  </div>
  <div class="nav-content">
    <div style="padding:4px 6px 14px;margin-bottom:10px;border-bottom:1px solid var(--border)">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
        <label style="margin:0;font-family:var(--font-mono);font-size:10.5px;font-weight:600;letter-spacing:0.08em;color:var(--muted);text-transform:uppercase">Active Character</label>
        <div style="display:flex;gap:4px">
          <button class="btn btn-sm btn-outline" style="padding:2px 8px;font-size:11px;border-radius:4px" onclick="showPanel('characters');setTimeout(()=>document.getElementById('new-char-name')?.focus(),80)">+ 新建</button>
          <button class="btn btn-sm btn-outline" style="padding:2px 8px;font-size:11px;border-radius:4px" onclick="showPanel('characters')">档案库</button>
        </div>
      </div>
      <select id="sidebar-char-select" onchange="onSidebarCharacterChange(this.value)" style="width:100%;padding:7px 10px;font-size:13px;font-weight:600;border-radius:6px;background:var(--input-bg);color:var(--fg);border:1px solid var(--border-hover)">
        <option value="default">default</option>
      </select>
      <div style="font-size:11.5px;color:var(--muted);margin-top:6px;display:flex;justify-content:space-between;align-items:center">
        <span>当前气质预设</span>
        <strong id="current-persona-display" style="color:var(--accent);font-weight:500">-</strong>
      </div>
    </div>
    <div class="nav-links">
      <a href="#" onclick="showPanel('status')" id="nav-status" class="active"><span class="nav-idx">01</span><span>运行总览</span></a>
      <a href="#" onclick="showPanel('characters')" id="nav-characters"><span class="nav-idx">02</span><span>角色档案</span></a>
      <a href="#" onclick="showPanel('demo')" id="nav-demo"><span class="nav-idx">03</span><span>演化剧场</span></a>
      <a href="#" onclick="showPanel('persona')" id="nav-persona"><span class="nav-idx">04</span><span>气质塑形</span></a>
      <a href="#" onclick="showPanel('selfhood')" id="nav-selfhood"><span class="nav-idx">05</span><span>自性发生</span></a>
      <a href="#" onclick="showPanel('memory')" id="nav-memory"><span class="nav-idx">06</span><span>记忆拓扑</span></a>
      <a href="#" onclick="showPanel('traits')" id="nav-traits"><span class="nav-idx">07</span><span>特质账本</span></a>
      <a href="#" onclick="showPanel('constants')" id="nav-constants"><span class="nav-idx">08</span><span>物理常数</span></a>
      <a href="#" onclick="showPanel('config')" id="nav-config"><span class="nav-idx">09</span><span>运行参数</span></a>
      <a href="#" onclick="showPanel('connect')" id="nav-connections"><span class="nav-idx">10</span><span>外部连接</span></a>
      <a href="#" onclick="showPanel('actions')" id="nav-actions"><span class="nav-idx">11</span><span>维护动作</span></a>
    </div>
  </div>
</nav>
<main>
  <div id="toast-container"></div>
  <div class="banner" id="keep-running-banner" style="display:none">
    <span>注意 · <strong>Keep these processes running!</strong> Closing the terminal kills loam, proxy, and admin panel. <a href="https://github.com/lmynszbd-ctrlbe/Loam-A-Runtime-Where-Characters-Grow-a-Self-from-Memory-/blob/main/docs/DEPLOY.md#keeping-processes-running" target="_blank" style="color:var(--accent)">Learn how →</a></span>
    <button class="banner-dismiss" onclick="this.parentElement.style.display='none'" title="Dismiss">×</button>
  </div>

  <!-- STATUS -->
  <div id="panel-status" class="panel active">
    <h1>运行状态总览 (Runtime Status)</h1>
    <div class="sub" id="status-time">loading...</div>
    <div id="status-api-alert"></div>
    <div class="grid" id="status-grid"></div>
    <div class="card"><h3>核心性格特质 (Active Traits)</h3><div id="status-traits"></div></div>
  </div>

  <!-- CHARACTERS (Multi-Character Manager) -->
  <div id="panel-characters" class="panel">
    <h1>多角色管理中心 (Multi-Character Hub)</h1>
    <div class="sub">每个角色拥有完全独立的 SQLite 记忆库 (journal.db / memory.db)、性格特质曲线、情绪共振状态与初始人设。支持无限扩展角色！</div>

    <div class="grid" style="grid-template-columns: 1.15fr 1fr; gap: 16px; margin-bottom: 18px;">
      <!-- 新建角色卡片 -->
      <div class="card">
        <h3>+ 创建新角色 (Create New Character)</h3>
        <div class="form-group" style="margin-top:10px">
          <label>角色名称 / 唯一标识 (支持中文、英文、数字，如：爱丽丝、星野、苏格拉底)</label>
          <input type="text" id="new-char-name" placeholder="例如：爱丽丝">
        </div>
        <div class="form-group">
          <label>初始性格气质预设 (可在创建后随时微调)</label>
          <select id="new-char-preset">
            <option value="">标准平衡态 (0.50 初始均衡)</option>
            <option value="gentle">温柔包容 (高共情 · 敏锐包容)</option>
            <option value="aloof">高冷孤傲 (慢热防备 · 极强内核)</option>
            <option value="cheerful">乐天小狗 (极度易感 · 快速回血)</option>
            <option value="fragile">敏感易碎 (多疑内耗 · 联想丰富)</option>
          </select>
        </div>
        <div class="form-group">
          <label>初始人设 / 核心背景自述 (Seed Narrative，可选)</label>
          <textarea id="new-char-seed" style="min-height:82px" placeholder="例如：我是爱丽丝，表面说话有些傲娇毒舌，但实际上非常在意身边人的情绪变化，在熟人面前会展现护短的一面..."></textarea>
        </div>
        <div style="display:flex;gap:10px;align-items:center;margin-top:12px">
          <button class="btn btn-ok" onclick="createCharacterFromUI()">创建并激活此角色</button>
          <button class="btn btn-outline btn-sm" onclick="loadCharacters()">刷新列表</button>
        </div>
      </div>

      <!-- 多角色客户端接入指南 -->
      <div class="card" style="display:flex;flex-direction:column;justify-content:space-between">
        <div>
          <h3>客户端如何同时使用多个角色？</h3>
          <p class="muted" style="font-size:12.5px;margin-bottom:12px">无论你使用 SillyTavern (酒馆)、Operit、RisuAI 还是 NextChat，都可以通过以下 <strong>3 种方式</strong>切换或并发隔离不同角色的记忆：</p>
          <div style="display:flex;flex-direction:column;gap:10px;font-size:12.5px">
            <div style="padding:10px 12px;background:var(--bg-subtle);border:1px solid var(--border);border-radius:8px">
              <strong style="color:var(--accent)">方式一：左侧边栏一键切换（零配置，最省心）</strong>
              <div class="muted" style="margin-top:3px">直接在面板左上角下拉框选择角色（或下方卡片点击「设为当前激活」），所有不带标记的客户端对话都会自动路由给该角色。</div>
            </div>
            <div style="padding:10px 12px;background:var(--bg-subtle);border:1px solid var(--border);border-radius:8px">
              <strong style="color:var(--ok)">方式二：角色卡人设内嵌标签（多角色并发推荐 CORE）</strong>
              <div class="muted" style="margin-top:3px">在酒馆/客户端的角色卡 System Prompt 任意位置写上 <code>[loam:角色名]</code>（例如 <code>[loam:爱丽丝]</code> 或 <code>【角色:爱丽丝】</code>），代理会自动按角色分流记忆！</div>
            </div>
            <div style="padding:10px 12px;background:var(--bg-subtle);border:1px solid var(--border);border-radius:8px">
              <strong style="color:var(--accent-2)">方式三：模型名称后缀法</strong>
              <div class="muted" style="margin-top:3px">在客户端填模型名时加上 <code>@角色名</code>（例如 <code>relayA/deepseek-chat@爱丽丝</code>），代理会自动剥离后缀并将记忆归档到对应角色。</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 角色编辑弹窗/内嵌面板 -->
    <div id="char-seed-editor-card" class="card" style="display:none;margin-bottom:18px;border-color:var(--accent)">
      <h3 id="char-seed-editor-title">编辑角色初始人设 / 核心背景自述</h3>
      <input type="hidden" id="char-seed-editor-name">
      <div class="form-group">
        <label>初始人设自述 (Seed Narrative) —— 当角色尚未积累足够长对话时作为基底自述生效</label>
        <textarea id="char-seed-editor-text" style="min-height:100px"></textarea>
      </div>
      <div style="display:flex;gap:10px">
        <button class="btn btn-ok btn-sm" onclick="saveCharacterSeed()">保存初始人设</button>
        <button class="btn btn-outline btn-sm" onclick="document.getElementById('char-seed-editor-card').style.display='none'">取消</button>
      </div>
    </div>

    <h2>已创建的角色列表 (<span id="char-total-count">1</span>)</h2>
    <div id="characters-grid" class="grid" style="grid-template-columns:repeat(auto-fill, minmax(310px, 1fr));gap:16px">
      <!-- JS 动态渲染 -->
    </div>
  </div>

  <!-- DEMO: EVOLUTION THEATER -->
  <div id="panel-demo" class="panel">
    <h1>演化剧场 · 记忆与自性动力学沙盒</h1>
    <div class="sub">零 Token 消耗的完整内核解剖剧场。全景式呈现 Loam 如何从「原始对话分轨」出发，经由「情景记忆蒸馏」、「赫布突触扩散激活」、「蔡加尼克执念发酵」、「潜意识梦境桥接」，最终跨越「双时间尺度相变门限」并改写「第一人称自我叙述」。</div>

    <!-- 剧场控制栏 -->
    <div class="card" style="margin-bottom:16px;padding:16px 20px">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;margin-bottom:14px">
        <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
          <span style="font-family:var(--font-mono);font-size:11px;color:var(--muted);letter-spacing:0.06em">SCENARIO</span>
          <select id="demo-scenario-select" onchange="switchDemoScenario(this.value)" style="width:auto;min-width:270px;padding:6px 12px;font-weight:600">
            <option value="clockmaker">剧本 I ·《雨夜旧钟表店：从戒备到托付》(6 幕全链路推演)</option>
            <option value="observatory">剧本 II ·《深空监听站：执念发酵与跨周期唤醒》(5 幕推演)</option>
          </select>
        </div>
        <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
          <button class="btn btn-sm btn-outline" onclick="stepDemoAct(-1)">← 上一幕</button>
          <button class="btn btn-sm btn-ok" id="demo-play-btn" onclick="startDemoSimulation()">▶ 自动推演全剧</button>
          <button class="btn btn-sm" onclick="stepDemoAct(1)">下一幕 (单步解剖) →</button>
          <button class="btn btn-sm btn-outline" onclick="resetDemoSimulation()">重置剧场</button>
        </div>
      </div>

      <!-- 幕次时间轴进度器 -->
      <div id="demo-act-scrubber" style="display:grid;grid-template-columns:repeat(auto-fit, minmax(120px, 1fr));gap:8px"></div>
      <div id="demo-status-text" style="margin-top:10px;font-family:var(--font-mono);font-size:11.5px;color:var(--accent)"></div>
    </div>

    <!-- 主剧场五维联动工作台 -->
    <div class="grid" style="grid-template-columns: 1.15fr 1fr; gap:16px; margin-bottom:16px">
      <!-- 维度 1：对话三通道剥离 + 情景记忆事件蒸馏 -->
      <div class="card" style="display:flex;flex-direction:column;justify-content:space-between">
        <div>
          <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:10px">
            <h3>I · 对话三通道分轨与情景记忆蒸馏</h3>
            <span style="font-family:var(--font-mono);font-size:11px;color:var(--muted)">CHANNEL PARSER → EPISODIC EVENT</span>
          </div>
          <div id="demo-dialogue-stream" style="display:flex;flex-direction:column;gap:10px;max-height:430px;overflow-y:auto;padding-right:4px"></div>
        </div>
        <div id="demo-distilled-event" style="margin-top:12px;padding-top:12px;border-top:1px solid var(--border)"></div>
      </div>

      <!-- 维度 2 & 3：双时间尺度特质相变仪 + 赫布神经拓扑画布 -->
      <div style="display:flex;flex-direction:column;gap:16px">
        <div class="card">
          <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:6px">
            <h3>II · 双时间尺度特质动力学与相变阈值</h3>
            <span style="font-family:var(--font-mono);font-size:11px;color:var(--muted)">STRENGTH + TRANSIENT vs GATE (0.55)</span>
          </div>
          <div style="font-size:11.5px;color:var(--muted);margin-bottom:10px">实色条为已固化的慢态结构强度 (Strength)，琥珀色光斑为快态瞬态动量 (Momentum)，竖线为相变固化门限。</div>
          <div id="demo-traits-monitor" style="display:flex;flex-direction:column;gap:10px"></div>
        </div>

        <div class="card">
          <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:6px">
            <h3>III · 赫布突触共振与扩散激活拓扑</h3>
            <span style="font-family:var(--font-mono);font-size:11px;color:var(--muted)">HEBBIAN GRAPH & SPREADING RECALL</span>
          </div>
          <canvas id="demo-hebb-canvas" width="540" height="215" style="width:100%;height:215px;background:var(--input-bg);border-radius:6px;border:1px solid var(--border)"></canvas>
          <div id="demo-hebb-caption" style="font-family:var(--font-mono);font-size:11px;color:var(--fg-dim);margin-top:6px"></div>
        </div>
      </div>
    </div>

    <!-- 底部维度 4 & 5：自性三支柱 (执念/他者之镜/潜意识梦境) + 自我叙述重写与溯源账本 -->
    <div class="grid" style="grid-template-columns: 1fr 1.15fr; gap:16px">
      <div class="card">
        <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:10px">
          <h3>IV · 自性内景：蔡加尼克执念 · 他者之镜 · 潜意识梦境</h3>
          <span style="font-family:var(--font-mono);font-size:11px;color:var(--muted)">SELFHOOD GENESIS</span>
        </div>
        <div id="demo-selfhood-box" style="display:flex;flex-direction:column;gap:10px"></div>
      </div>

      <div class="card">
        <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:10px">
          <h3>V · 第一人称自我叙述演化与可溯源账本</h3>
          <span style="font-family:var(--font-mono);font-size:11px;color:var(--muted)">SELF-NARRATIVE & AUDITABLE CHANGELOG</span>
        </div>
        <div id="demo-narrative-box" style="display:flex;flex-direction:column;gap:10px"></div>
      </div>
    </div>
  </div>

  <!-- PERSONA -->
  <div id="panel-persona" class="panel">
    <h1>性格预设与宏观气质 (Persona & Macro Knobs)</h1>
    <div class="sub">将底层 48 个物理动力学参数抽象为 5 维直观气质大旋钮与 4 套经典预设卡（底层微调请前往 <a href="#" onclick="showPanel('constants');return false;" style="color:var(--accent);text-decoration:underline">常数环境</a>）</div>
    
    <div class="card" style="margin-bottom:16px;">
      <h3>快捷性格预设卡 (One-Click Presets)</h3>
      <div id="persona-presets" style="display:grid;grid-template-columns:repeat(auto-fit, minmax(190px, 1fr));gap:12px;margin-top:12px;">
        <!-- 预设卡按钮由 JS 动态生成 -->
      </div>
      <div id="current-preset-badge" style="margin-top:12px;font-size:13px;color:var(--muted);display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
        <span>当前状态：<span id="active-preset-name" style="font-weight:600;color:var(--accent)">自定义参数</span></span>
        <button class="btn btn-sm btn-outline" onclick="showPanel('constants')">查看受控的底层物理常数</button>
      </div>
    </div>

    <div class="card" style="margin-bottom:16px;">
      <h3>五维气质宏观大旋钮 (Macro Knobs)</h3>
      <div id="persona-knobs-list" style="margin-top:12px;display:flex;flex-direction:column;gap:14px;">
        <!-- 旋钮滑块由 JS 动态生成 -->
      </div>
      <div style="display:flex;gap:10px;margin-top:20px;">
        <button class="btn btn-ok" onclick="savePersonaKnobs()">保存并应用参数</button>
        <button class="btn btn-outline" onclick="resetPersona()">重置为默认平衡态</button>
      </div>
    </div>

    <div class="card">
      <h3>当下心境共振与独处自省 (Resonance & Daydream)</h3>
      <div id="persona-resonance-box" style="margin-top:10px;">
        <!-- 心境与情绪共振状态 -->
      </div>
      <div style="display:flex;gap:10px;margin-top:16px;">
        <button class="btn btn-sm btn-outline" onclick="triggerProactiveThought()">触发一次独处心理反思</button>
        <button class="btn btn-sm" onclick="loadPersona()">刷新心境态</button>
      </div>
    </div>
  </div>

  <!-- SELFHOOD -->
  <div id="panel-selfhood" class="panel">
    <h1>自性体系 (Selfhood Genesis)</h1>
    <div class="sub">监控角色的内心执念 (Zeigarnik Effect)、潜意识梦境 (Dream Replay) 与他者之镜 (Theory of Mind)。</div>
    <div class="actions">
      <button class="btn btn-sm btn-outline" onclick="loadSelfhood()">刷新自性状态</button>
      <button class="btn btn-sm" onclick="triggerDream()">触发梦境重构</button>
    </div>
    
    <div class="grid" style="grid-template-columns: 1fr 1fr; gap: 16px;">
      <!-- Drives -->
      <div class="card">
        <h3>内心执念 (Latent Drives)</h3>
        <div class="sub">随时间发酵的蔡加尼克心理张力。</div>
        <div id="selfhood-drives-list" style="margin-top:12px; display:flex; flex-direction:column; gap:12px;">
          <!-- JS 注入 -->
        </div>
      </div>

      <!-- Mirror & Dream -->
      <div style="display:flex; flex-direction:column; gap:16px;">
        <div class="card">
          <h3>他者之镜 (Mirror of Other)</h3>
          <div class="sub">角色对当前交谈对象的心智揣摩。</div>
          <div id="selfhood-mirror-box" style="margin-top:12px;">
            <!-- JS 注入 -->
          </div>
        </div>

        <div class="card">
          <h3>◑ 潜意识梦境 (Recent Dreams)</h3>
          <div class="sub">闲置时潜意识在远距离记忆间建立的隐喻桥梁。</div>
          <div id="selfhood-dream-box" style="margin-top:12px;">
            <!-- JS 注入 -->
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- TRAITS -->
  <div id="panel-traits" class="panel">
    <h1>特质演化快照 (Trait Plasticity)</h1>
    <div class="sub">实时追踪角色每一条性格特质的沉淀强度、所处生命周期阶段、证据累积量与内核固化状态</div>
    <div class="actions">
      <button class="btn btn-sm" onclick="loadTraits()">Refresh</button>
    </div>
    <div class="card" id="traits-table"></div>
  </div>

  <!-- MEMORY -->
  <div id="panel-memory" class="panel">
    <h1>记忆总线与赫布拓扑 (Memory & Neural Graph)</h1>
    <div class="sub">查看情景记忆流、角色自我叙述、特质质变账本，以及动态生长的赫布神经网络拓扑图</div>
    <div class="actions">
      <button class="btn btn-sm" onclick="loadMemory()">Refresh Events</button>
      <button class="btn btn-sm btn-outline" onclick="loadNarrative()">Narrative</button>
      <button class="btn btn-sm btn-outline" onclick="loadChangelog()">Changelog</button>
      <button class="btn btn-sm btn-ok" onclick="loadNetworkGraph()">动态神经拓扑图</button>
    </div>
    <div id="memory-content"></div>
  </div>

  <!-- CONFIG -->
  <div id="panel-config" class="panel">
    <h1>系统运行配置 (Runtime Config)</h1>
    <div class="sub">查看或热更新上下文检索预算、衰减半衰期与流水线并发参数（支持版本化回滚）</div>
    <div class="actions">
      <button class="btn btn-sm" onclick="loadConfig()">Refresh</button>
    </div>
    <div class="card">
      <h3>Runtime Config</h3>
      <pre id="config-display" style="font-size:12px;max-height:400px;overflow-y:auto"></pre>
    </div>
    <div class="card" style="margin-top:12px">
      <h3>Update Config</h3>
      <div class="form-group">
        <label>JSON updates (merge)</label>
        <textarea id="config-updates" placeholder='{"context.max_matches": 12}'></textarea>
      </div>
      <button class="btn" onclick="updateConfig()">Apply</button>
    </div>
  </div>

  <!-- CONSTANTS -->
  <div id="panel-constants" class="panel">
    <h1>底层物理常数环境 (48 Dynamical Constants)</h1>
    <div class="sub">直接检视与微调 Loam 引擎的 48 项底层生物物理动力学常数（半衰期、赫布学习率、情绪惯性、防备阈值等）并持久化落盘</div>

    <div class="banner banner-info" style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;margin-bottom:16px">
      <div>
        <strong>分工说明：</strong>此处为<strong>底层 48 项物理常数专家微调表</strong>。如需使用「4 套一键预设卡」或「5 维宏观气质大旋钮」，请前往性格卡片面板。
        <span id="const-override-summary" style="margin-left:8px;color:var(--accent);font-weight:600"></span>
      </div>
      <button class="btn btn-sm btn-outline" onclick="showPanel('persona')">前往性格卡片 (宏观调参)</button>
    </div>

    <div class="actions" style="margin-bottom:14px;justify-content:space-between;flex-wrap:wrap;gap:10px">
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
        <button class="btn btn-sm" onclick="loadConstants()">刷新常数</button>
        <button class="btn btn-sm btn-ok" onclick="applyConstants()">保存并持久化覆盖</button>
        <button class="btn btn-sm btn-outline" onclick="clearConstants()">恢复全部默认值</button>
      </div>
      <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap">
        <label style="display:flex;align-items:center;gap:6px;font-size:12.5px;color:var(--muted);cursor:pointer;user-select:none">
          <input type="checkbox" id="const-only-overridden" onchange="filterConstantsRows()"> 仅看已覆盖项 (Overridden)
        </label>
        <input type="text" id="const-search-inp" placeholder="搜索常数名或描述..." oninput="filterConstantsRows()" style="width:220px;padding:6px 10px;font-size:12.5px">
      </div>
    </div>
    <div class="card" id="constants-list"></div>
  </div>

  <!-- CONNECT -->
  <div id="panel-connect" class="panel">
    <h1>外部模型与客户端连接 (API & Upstreams)</h1>
    <div class="sub">配置 API 密钥。loam 使用两套独立的模型：一套消化记忆，一套生成回复。</div>

    <!-- 顶部三卡片：告诉用户填到聊天客户端的三个值 -->
    <div class="grid" style="grid-template-columns:repeat(3, 1fr); margin-bottom:20px">
      <div class="card">
        <h3>填到聊天软件的 Base URL</h3>
        <div id="client-base-url" style="font-family:monospace;font-size:14px;text-align:center;padding:6px;background:var(--bg);border-radius:4px">http://127.0.0.1:8783/v1</div>
        <div id="client-base-url-alt" style="font-family:monospace;font-size:12px;text-align:center;padding:4px;background:var(--bg);border-radius:4px;margin-top:4px;color:var(--accent);min-height:1.5em"><span class="spinner"></span> 正在检测可用地址...</div>
        <div id="client-base-url-err" style="color:var(--err);font-size:11px;text-align:center;margin-top:4px;min-height:1.5em"></div>
        <p class="muted" style="font-size:11px;margin-top:4px"><b>同一设备：</b>用 127.0.0.1。<b>不同 App（如 Operit）：</b>用下方带 IP 的地址。<b>不同设备：</b>手机和电脑必须连同一个 WiFi。</b></p>
      </div>
      <div class="card">
        <h3>填到聊天软件的 API Key</h3>
        <div style="font-family:monospace;font-size:14px;text-align:center;padding:6px;background:var(--bg);border-radius:4px">local-key</div>
        <p class="muted" style="font-size:11px;margin-top:4px">填什么都行。loam 跑在你本地，不需要真正鉴权——真正的密钥在下面配置。</p>
      </div>
      <div class="card">
        <h3>聊天软件选什么供应商？</h3>
        <div style="font-family:monospace;font-size:14px;text-align:center;padding:6px;background:var(--bg);border-radius:4px">OpenAI 兼容</div>
        <p class="muted" style="font-size:11px;margin-top:4px">loam 的 proxy 是 OpenAI 兼容接口。聊天软件里选 <b>OpenAI / OpenAI 兼容</b> 即可，模型列表会自动从下面配置的上游 API 拉取。</p>
      </div>
    </div>

    <div class="actions" style="margin-bottom:16px">
      <button class="btn btn-sm" onclick="loadApiConfig()">从磁盘重新加载</button>
      <span class="muted" style="font-size:11px;margin-left:8px">保存位置：<code id="cfg-home">~/.loam</code> · proxy 热加载，保存后立即生效</span>
    </div>

    <!-- SECTION 1: loam memory API — 用于消化记忆，生成角色特质 -->
    <div class="card" style="margin-bottom:16px; border-left:3px solid var(--accent)">
      <h3>记忆生长模型 <span class="muted" style="font-weight:400;font-size:11px">— loam 用它来消化对话、提炼特质、让角色「生长」</span></h3>
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
        <button class="btn btn-sm btn-outline btn-fetch" style="height:38px;align-self:end" onclick="fetchModels('sec')" title="从提供商拉取可用模型列表">拉取</button>
        <button class="btn btn-ok" style="height:38px;align-self:end" onclick="saveSecrets()">保存</button>
      </div>
      <div id="sec-status" style="margin-top:8px;font-size:12px" class="muted"></div>
    </div>

    <!-- SECTION 2: chat upstream APIs — 用于生成聊天回复 -->
    <div class="card" style="border-left:3px solid var(--ok)">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
        <h3 style="margin:0">聊天回复模型 API <span class="muted" style="font-weight:400;font-size:11px">— 你聊天时实际生成回复的模型，可以配多个随时切换</span></h3>
        <button class="btn btn-sm btn-outline" onclick="addUpstreamRow()">+ 添加提供商</button>
      </div>
      <p class="muted" style="font-size:11px;margin-bottom:10px">填 Base URL 和 API Key，点「拉取」获取完整模型列表，然后点「保存全部」。</p>
      <div id="upstream-rows"></div>
      <div style="display:flex;align-items:end;gap:12px;margin-top:10px">
        <div class="form-group" style="margin:0">
          <label>默认提供商</label>
          <select id="up-default" style="width:auto;min-width:200px"></select>
        </div>
        <button class="btn btn-ok" style="height:38px" onclick="saveUpstreams()">保存全部</button>
      </div>
      <div id="up-status" style="margin-top:8px;font-size:12px" class="muted"></div>
    </div>
  </div>

  <!-- ACTIONS → GROWTH -->
  <div id="panel-actions" class="panel">
    <h1>记忆生长</h1>
    <div class="sub">loam 后台自动消化对话，提炼特质和记忆。你也可以手动触发。</div>

    <!-- 机制说明 -->
    <div class="card" style="margin-bottom:16px; border-left:3px solid var(--accent)">
      <h3>生长机制（不费钱）</h3>
      <div class="grid" style="grid-template-columns:repeat(3,1fr);gap:12px">
        <div style="text-align:center;padding:8px">
          <div style="font-family:var(--font-mono);font-size:11px;color:var(--accent);letter-spacing:0.1em;margin-bottom:4px">BATCH THRESHOLD</div>
          <div style="font-weight:600;font-size:14px">攒够 <span id="growth-batch">20</span> 轮对话</div>
          <div class="muted" style="font-size:11px">才消化一次，不是每轮都消化</div>
        </div>
        <div style="text-align:center;padding:8px">
          <div style="font-family:var(--font-mono);font-size:11px;color:var(--accent);letter-spacing:0.1em;margin-bottom:4px">IDLE WINDOW</div>
          <div style="font-weight:600;font-size:14px">或 <span id="growth-idle">15</span> 分钟无新对话</div>
          <div class="muted" style="font-size:11px">聊完一段就自动消化</div>
        </div>
        <div style="text-align:center;padding:8px">
          <div style="font-family:var(--font-mono);font-size:11px;color:var(--accent);letter-spacing:0.1em;margin-bottom:4px">TOKEN ECONOMY</div>
          <div style="font-weight:600;font-size:14px">每 20 轮 ≈ 1~3 次 API</div>
          <div class="muted" style="font-size:11px">比你聊天消耗的 API 少得多</div>
        </div>
      </div>
      <p class="muted" style="font-size:11px;margin-top:8px">loam 每 <b>60 秒</b> 检查一次是否满足条件，不是每 60 秒调一次 API。</p>
    </div>

    <!-- 可调参数 -->
    <div class="card" style="margin-bottom:16px">
      <h3>消化参数</h3>
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
        <button class="btn btn-ok" onclick="saveGrowthSettings()">保存设置</button>
        <span class="muted" style="font-size:11px">注意 · 建议使用默认值，修改后需重启 loam 生效</span>
      </div>
      <div id="growth-settings-status" style="margin-top:8px;font-size:12px"></div>
    </div>

    <!-- 手动操作与备份迁移 -->
    <div class="grid">
      <div class="card">
        <h3>手动消化</h3>
        <p class="muted" style="font-size:12px;margin-bottom:8px">立即消化当前攒下的所有对话</p>
        <button class="btn" onclick="doAction('digest')">立即消化</button>
        <div id="digest-result" style="margin-top:8px;font-size:12px"></div>
      </div>
      <div class="card">
        <h3>全部清空</h3>
        <p class="muted" style="font-size:12px;margin-bottom:8px">处理所有队列中的对话（可能较慢）</p>
        <button class="btn" onclick="doAction('drain')">全部处理</button>
        <div id="drain-result" style="margin-top:8px;font-size:12px"></div>
      </div>
      <div class="card">
        <h3>一键数据备份迁移</h3>
        <p class="muted" style="font-size:12px;margin-bottom:8px">打包全套 SQLite + 状态文件为 tar.gz</p>
        <button class="btn btn-ok" onclick="doAction('backup_export')">导出完整备份包</button>
        <div id="backup_export-result" style="margin-top:8px;font-size:12px"></div>
      </div>
      <div class="card">
        <h3>重建记忆</h3>
        <p class="muted" style="font-size:12px;margin-bottom:8px">从原始对话重新构建所有记忆</p>
        <button class="btn btn-danger" onclick="doAction('recompute')">注意 · 重建</button>
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
let _activeCharacter = localStorage.getItem('loam-active-char') || '';
let _charactersCache = [];

async function call(method, path, body) {
  const headers = {};
  if (_activeCharacter) {
    headers['X-Loam-Character'] = _activeCharacter;
  }
  const opts = {method, headers};
  if (body) {
    headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  const r = await fetch(API + path, opts);
  return r.json();
}

async function syncCharactersList(quiet) {
  try {
    const res = await fetch(API + '/characters');
    const data = await res.json();
    if (!data || !Array.isArray(data.characters)) return null;
    _charactersCache = data.characters;
    const backendDefault = data.default_character || 'default';
    if (!_activeCharacter || !_charactersCache.some(c => c.character === _activeCharacter)) {
      _activeCharacter = backendDefault;
      localStorage.setItem('loam-active-char', _activeCharacter);
    }
    const optsHtml = _charactersCache.map(c => {
      const star = c.is_default ? '● ' : '○ ';
      const tag = c.is_default ? ' (默认)' : '';
      return `<option value="${escAttr(c.character)}" ${c.character === _activeCharacter ? 'selected' : ''}>${star}${esc(c.character)}${tag}</option>`;
    }).join('');
    const sel = document.getElementById('sidebar-char-select');
    if (sel) sel.innerHTML = optsHtml;
    const mobSel = document.getElementById('mobile-char-select');
    if (mobSel) mobSel.innerHTML = optsHtml;
    const curObj = _charactersCache.find(c => c.character === _activeCharacter);
    const sideDisplay = document.getElementById('current-persona-display');
    if (sideDisplay && curObj) {
      sideDisplay.textContent = curObj.persona_label || '自定义 / 平衡态';
    }
    return data;
  } catch (e) {
    if (!quiet) console.warn('syncCharactersList error:', e);
    return null;
  }
}

async function onSidebarCharacterChange(charName) {
  if (!charName) return;
  _activeCharacter = charName;
  localStorage.setItem('loam-active-char', charName);
  try {
    await call('POST', '/characters/default', { character: charName });
    toast(`已切换至角色「${charName}」并设为当前默认对话角色`, 'ok');
  } catch (e) {
    toast(`已切换查看角色「${charName}」`, 'ok');
  }
  await syncCharactersList(true);
  // 刷新当前激活的面板
  const activePanel = document.querySelector('.panel.active');
  if (activePanel && activePanel.id) {
    const pName = activePanel.id.replace('panel-', '');
    showPanel(pName);
  }
}

async function loadCharacters() {
  const data = await syncCharactersList(false);
  const grid = document.getElementById('characters-grid');
  const countEl = document.getElementById('char-total-count');
  if (!grid) return;
  if (!data || !Array.isArray(data.characters)) {
    grid.innerHTML = '<div class="card"><span class="err">无法连接 Loam 后端获取角色列表，请确认服务正在运行。</span></div>';
    return;
  }
  if (countEl) countEl.textContent = data.characters.length;
  const presetIcons = { aloof: '', gentle: '', cheerful: '', fragile: '', '': '' };
  grid.innerHTML = data.characters.map(c => {
    const isAct = (c.character === _activeCharacter);
    const isDef = !!c.is_default;
    const icon = presetIcons[c.persona_preset || ''] || '';
    const preview = c.narrative_preview || '（暂无自述，可通过对话自然生长，或点击下方「编辑初始人设」赋予初始背景）';
    return `
      <div class="card" style="border-color:${isAct ? 'var(--accent)' : 'var(--border)'};display:flex;flex-direction:column;justify-content:space-between;gap:12px">
        <div>
          <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:10px">
            <div style="display:flex;align-items:center;gap:8px">
              <span style="font-family:var(--font-mono);font-size:11px;padding:2px 6px;border:1px solid var(--border);border-radius:4px;color:var(--accent)">${icon}</span>
              <span style="font-size:16px;font-weight:800;color:var(--fg)">${esc(c.character)}</span>
            </div>
            <div style="display:flex;gap:6px;flex-wrap:wrap">
              ${isDef ? '<span style="font-size:11px;padding:2px 8px;border-radius:999px;background:rgba(16,185,129,0.15);color:var(--ok);font-weight:700">● 默认对话角色</span>' : ''}
              ${isAct && !isDef ? '<span style="font-size:11px;padding:2px 8px;border-radius:999px;background:rgba(96,165,250,0.15);color:var(--accent);font-weight:700">◎ 当前查看</span>' : ''}
            </div>
          </div>

          <div style="font-size:12px;color:var(--muted);margin-bottom:10px;padding:8px 10px;background:var(--bg-subtle);border-radius:8px;border:1px solid var(--border);min-height:52px;line-height:1.5">
            ${esc(preview)}
          </div>

          <div class="stat"><span>性格气质预设</span><span class="val" style="font-size:12.5px">${icon} ${esc(c.persona_label || '自定义 / 平衡态')}</span></div>
          <div class="stat"><span>已长出性格特质</span><span class="val ok">${c.traits_count || 0} 条</span></div>
          <div class="stat"><span>情景记忆事件</span><span class="val">${c.events_count || 0} 条</span></div>
          <div class="stat"><span>待消化对话 / 执念</span><span class="val ${(c.pending||0)>0?'warn':''}">${c.pending || 0} 轮 / ${c.active_drives || 0} 个</span></div>
          <div class="stat"><span>当下主导心境</span><span class="val" style="font-size:12px">${esc(c.mood || '心绪平稳')}</span></div>
        </div>

        <div style="display:flex;gap:8px;flex-wrap:wrap;padding-top:8px;border-top:1px solid var(--border)">
          <button class="btn btn-sm ${isDef ? 'btn-ok' : ''}" onclick="switchAndActivateCharacter('${escAttr(c.character)}')">
            ${isDef ? '当前默认激活中' : '切换并设为默认'}
          </button>
          <button class="btn btn-sm btn-outline" onclick="openCharacterPanel('${escAttr(c.character)}', 'persona')">性格卡</button>
          <button class="btn btn-sm btn-outline" onclick="openCharacterPanel('${escAttr(c.character)}', 'memory')">记忆</button>
          <button class="btn btn-sm btn-outline" onclick="openSeedEditor('${escAttr(c.character)}')">初始人设</button>
          ${data.characters.length > 1 ? `<button class="btn btn-sm btn-danger" onclick="deleteCharacterFromUI('${escAttr(c.character)}')" title="移入回收站">移除</button>` : ''}
        </div>
      </div>
    `;
  }).join('');
}

async function switchAndActivateCharacter(charName) {
  await onSidebarCharacterChange(charName);
  await loadCharacters();
}

async function openCharacterPanel(charName, panelName) {
  _activeCharacter = charName;
  localStorage.setItem('loam-active-char', charName);
  try {
    await call('POST', '/characters/default', { character: charName });
  } catch (e) {}
  await syncCharactersList(true);
  showPanel(panelName);
}

async function createCharacterFromUI() {
  const nameInp = document.getElementById('new-char-name');
  const presetSel = document.getElementById('new-char-preset');
  const seedInp = document.getElementById('new-char-seed');
  const charName = (nameInp?.value || '').trim();
  if (!charName) {
    toast('请输入新角色的名称！', 'err');
    nameInp?.focus();
    return;
  }
  try {
    const res = await call('POST', '/characters/create', {
      character: charName,
      preset: presetSel?.value || '',
      seed_narrative: seedInp?.value || '',
      set_default: true,
    });
    if (res && res.ok) {
      _activeCharacter = charName;
      localStorage.setItem('loam-active-char', charName);
      if (nameInp) nameInp.value = '';
      if (seedInp) seedInp.value = '';
      toast(`角色「${charName}」创建成功并已激活！`, 'ok');
      await loadCharacters();
    } else {
      toast((res && res.error) || '创建角色失败', 'err');
    }
  } catch (e) {
    toast('创建角色出错: ' + e.message, 'err');
  }
}

function openSeedEditor(charName) {
  const c = _charactersCache.find(x => x.character === charName);
  const card = document.getElementById('char-seed-editor-card');
  if (!card) return;
  document.getElementById('char-seed-editor-name').value = charName;
  document.getElementById('char-seed-editor-title').textContent = `编辑角色「${charName}」的初始人设 / 背景自述`;
  document.getElementById('char-seed-editor-text').value = (c && (c.seed_narrative || c.narrative_preview)) || '';
  card.style.display = 'block';
  document.getElementById('char-seed-editor-text').focus();
}

async function saveCharacterSeed() {
  const charName = document.getElementById('char-seed-editor-name').value;
  const seedText = document.getElementById('char-seed-editor-text').value;
  if (!charName) return;
  try {
    const res = await call('POST', '/characters/seed', { character: charName, seed_narrative: seedText });
    if (res && res.ok) {
      toast(`已更新角色「${charName}」的初始人设！`, 'ok');
      document.getElementById('char-seed-editor-card').style.display = 'none';
      await loadCharacters();
    } else {
      toast((res && res.error) || '保存失败', 'err');
    }
  } catch (e) {
    toast('保存出错: ' + e.message, 'err');
  }
}

async function deleteCharacterFromUI(charName) {
  if (!confirm(`确定要移除角色「${charName}」吗？\n（数据不会彻底销毁，将安全归档至 ~/.loam/trash 目录）`)) return;
  try {
    const res = await call('POST', '/characters/delete', { character: charName });
    if (res && res.ok) {
      if (_activeCharacter === charName) {
        _activeCharacter = res.default_character || 'default';
        localStorage.setItem('loam-active-char', _activeCharacter);
      }
      toast(`角色「${charName}」已移入回收站`, 'ok');
      await loadCharacters();
    } else {
      toast((res && res.error) || '删除失败', 'err');
    }
  } catch (e) {
    toast('删除出错: ' + e.message, 'err');
  }
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
function showPanel(name) {
  let target = name;
  if (target === 'connections') target = 'connect';
  document.querySelectorAll('.nav-links a').forEach(x => x.classList.remove('active'));
  const navEl = document.getElementById('nav-' + name) || document.getElementById('nav-' + target);
  if (navEl) navEl.classList.add('active');
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  const panelEl = document.getElementById('panel-' + target);
  if (panelEl) panelEl.classList.add('active');
  if (target === 'demo') {
    renderDemoTraits();
    return;
  }
  const fn = 'load' + target.charAt(0).toUpperCase() + target.slice(1);
  if (typeof window[fn] === 'function') window[fn]();
}

document.querySelectorAll('.nav-link').forEach(a => {
  a.addEventListener('click', e => {
    e.preventDefault();
    if (a.dataset.panel) showPanel(a.dataset.panel);
  });
});

// ---- PERSONA & VITALITY ----
let currentPersonaData = null;

async function loadPersona() {
  try {
    const [pData, resData, proData] = await Promise.all([
      call('GET', '/persona'),
      call('GET', '/resonance'),
      call('GET', '/proactive'),
    ]);
    currentPersonaData = pData;

    // 1. Presets
    const presetsDiv = document.getElementById('persona-presets');
    const presets = pData.presets || {};
    const curPreset = pData.current_preset;
    const presetLabel = curPreset ? (presets[curPreset]?.name || curPreset) : '自定义参数模式';
    document.getElementById('active-preset-name').textContent = presetLabel;
    const sideDisplay = document.getElementById('current-persona-display');
    if (sideDisplay) sideDisplay.textContent = presetLabel;

    const presetIcons = { aloof: 'I', gentle: 'II', cheerful: 'III', fragile: 'IV' };
    let presetsHtml = '';
    for (const [key, p] of Object.entries(presets)) {
      const isCur = (key === curPreset);
      const activeClass = isCur ? 'btn-ok' : 'btn-outline';
      const icon = presetIcons[key] || '0';
      presetsHtml += `
        <div style="padding:14px;border:1px solid ${isCur ? 'var(--accent)' : 'var(--border)'};border-radius:10px;background:${isCur ? 'rgba(99,102,241,0.08)' : 'var(--bg-subtle)'};transition:all 0.2s">
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
            <span style="font-family:var(--font-mono);font-size:11px;padding:2px 6px;border:1px solid var(--border);border-radius:4px;color:var(--accent)">${icon}</span>
            <span style="font-weight:600;font-size:14px;">${esc(p.name)}</span>
          </div>
          <div style="font-size:12px;color:var(--muted);min-height:36px;margin-bottom:12px;line-height:1.45;">${esc(p.desc)}</div>
          <button class="btn btn-sm ${activeClass}" style="width:100%" onclick="applyPersonaPreset('${key}')">${isCur ? '当前已激活' : '一键应用此卡片'}</button>
        </div>
      `;
    }
    presetsDiv.innerHTML = presetsHtml;

    // 2. Knobs
    const schema = pData.schema || {};
    const currentKnobs = pData.current_knobs || {};
    const knobsDiv = document.getElementById('persona-knobs-list');
    let knobsHtml = '';
    for (const [key, meta] of Object.entries(schema)) {
      const val = (currentKnobs[key] !== undefined) ? currentKnobs[key] : (meta.default || 0.5);
      knobsHtml += `
        <div style="display:flex;flex-direction:column;gap:4px;padding:8px 12px;background:var(--bg-subtle);border-radius:6px;border:1px solid var(--border)">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <span style="font-weight:600;font-size:13.5px;">${esc(meta.name)}</span>
            <span id="p-knob-val-${key}" style="font-family:monospace;font-weight:bold;color:var(--accent);">${Number(val).toFixed(2)}</span>
          </div>
          <div style="font-size:11.5px;color:var(--muted);">${esc(meta.desc)}</div>
          <input type="range" id="p-knob-slider-${key}" min="0" max="1" step="0.01" value="${val}"
            oninput="document.getElementById('p-knob-val-${key}').textContent = Number(this.value).toFixed(2)"
            style="width:100%;margin-top:6px;cursor:pointer;">
        </div>
      `;
    }
    knobsDiv.innerHTML = knobsHtml;

    // 3. Resonance & Daydream
    const resBox = document.getElementById('persona-resonance-box');
    const moodDesc = resData.description || '心绪平稳均衡';
    const elems = resData.elements || {};
    const thought = (proData && proData.thought) ? proData.thought : '（暂无独处自省，角色正在静静观察外界）';
    
    let elemBarsHtml = '<div style="display:flex;gap:8px;margin-top:8px;margin-bottom:12px;flex-wrap:wrap;">';
    const elemNames = { wood: '木·进取', fire: '火·热情', earth: '土·深思', metal: '金·清醒', water: '水·警惕' };
    for (const [e, v] of Object.entries(elems)) {
      const pct = Math.max(5, Math.min(100, Math.round((Math.abs(v)) * 100)));
      elemBarsHtml += `
        <div style="flex:1;min-width:90px;background:var(--bg);border:1px solid var(--border);border-radius:4px;padding:6px 8px;text-align:center;">
          <div style="font-size:11px;color:var(--muted)">${elemNames[e]||e}</div>
          <div style="font-weight:bold;font-size:12px;margin:2px 0;color:${v>=0?'var(--ok)':'var(--err)'}">${v>0?'+':''}${Number(v).toFixed(2)}</div>
          <div style="background:var(--border);height:4px;border-radius:2px;overflow:hidden;">
            <div style="width:${pct}%;height:100%;background:${v>=0?'var(--ok)':'var(--err)'}"></div>
          </div>
        </div>
      `;
    }
    elemBarsHtml += '</div>';

    resBox.innerHTML = `
      <div style="padding:10px 14px;background:var(--bg-subtle);border-radius:6px;border:1px solid var(--border);margin-bottom:10px;">
        <div style="font-size:12px;color:var(--muted);margin-bottom:2px;">当下情绪态 / 主导心境</div>
        <div style="font-size:14px;font-weight:600;color:var(--text);">${esc(moodDesc)}</div>
        ${elemBarsHtml}
      </div>
      <div style="padding:10px 14px;background:var(--bg-subtle);border-radius:6px;border:1px solid var(--border)">
        <div style="font-size:12px;color:var(--muted);margin-bottom:2px;">独处时的自省与惦记 (Daydreaming Thought)</div>
        <div style="font-size:13.5px;color:var(--text);line-height:1.5;font-style:italic;">"${esc(thought)}"</div>
      </div>
    `;
  } catch (e) {
    toast('加载性格与心境数据失败: ' + e, 'err');
  }
}

async function applyPersonaPreset(name) {
  try {
    const res = await call('POST', '/persona/apply', { preset: name });
    if (res.ok) {
      toast('成功应用预设: ' + name, 'ok');
      await loadPersona();
    } else {
      toast(res.error || '应用预设失败', 'err');
    }
  } catch (e) {
    toast('应用预设出错: ' + e, 'err');
  }
}

async function savePersonaKnobs() {
  if (!currentPersonaData || !currentPersonaData.schema) return;
  const knobs = {};
  for (const k of Object.keys(currentPersonaData.schema)) {
    const el = document.getElementById('p-knob-slider-' + k);
    if (el) knobs[k] = parseFloat(el.value);
  }
  try {
    const res = await call('POST', '/persona/apply', { knobs });
    if (res.ok) {
      toast('性格大旋钮保存成功并已联动更新物理动力学常数！', 'ok');
      await loadPersona();
    } else {
      toast(res.error || '保存失败', 'err');
    }
  } catch (e) {
    toast('保存出错: ' + e, 'err');
  }
}

async function resetPersona() {
  if (!confirm('确定将角色性格大旋钮恢复为默认平衡态 (0.5) 并清空常数覆盖吗？')) return;
  try {
    const res = await call('POST', '/persona/reset');
    if (res.ok) {
      toast('已重置为默认平衡态', 'ok');
      await loadPersona();
    } else {
      toast(res.error || '重置失败', 'err');
    }
  } catch (e) {
    toast('重置出错: ' + e, 'err');
  }
}

async function triggerProactiveThought() {
  try {
    toast('正在触发独处自省思考...', 'ok');
    const res = await call('POST', '/proactive', { force: true });
    if (res.ok) {
      toast('独处自省思考已生成！', 'ok');
      await loadPersona();
    } else {
      toast(res.error || '生成失败', 'err');
    }
  } catch (e) {
    toast('生成出错: ' + e, 'err');
  }
}

// ---- SELFHOOD ----
async function loadSelfhood() {
  try {
    const [drivesRes, mirrorRes, statsRes] = await Promise.all([
      call('GET', '/drives?limit=10'),
      call('GET', '/mirror'),
      call('GET', '/stats')
    ]);
    
    // 1. Drives
    const drivesBox = document.getElementById('selfhood-drives-list');
    const drives = drivesRes.drives || [];
    let dHtml = '';
    if (drives.length === 0) {
      dHtml = '<div style="color:var(--muted); font-size:13px; text-align:center; padding: 20px;">当前角色心中毫无波澜，没有未解的悬念与执念。</div>';
    } else {
      for (const d of drives) {
        const pct = Math.min(100, Math.round((d.tension || 0) * 100));
        let qsHtml = '';
        if (d.questions && d.questions.length > 0) {
          qsHtml = `<div style="font-size:12px; color:var(--muted); margin-top:6px; padding-left:8px; border-left:2px solid var(--border);">萦绕疑问：${esc(d.questions.join(' / '))}</div>`;
        }
        dHtml += `
          <div style="padding:12px; background:var(--bg-subtle); border-radius:6px; border:1px solid var(--border);">
            <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
              <span style="font-weight:600; font-size:14px; color:var(--text);">${esc(d.theme)}</span>
              <span style="font-family:monospace; font-size:12px; color:var(--accent); font-weight:bold;">${pct}%</span>
            </div>
            <div style="background:var(--bg); height:6px; border-radius:3px; overflow:hidden; border:1px solid var(--border);">
              <div style="width:${pct}%; height:100%; background:linear-gradient(90deg, #7aa2ff, #c792ea);"></div>
            </div>
            ${qsHtml}
          </div>
        `;
      }
    }
    drivesBox.innerHTML = dHtml;

    // 2. Mirror
    const mirrorBox = document.getElementById('selfhood-mirror-box');
    const m = mirrorRes.mirror;
    if (!m) {
      mirrorBox.innerHTML = '<div style="color:var(--muted); font-size:13px; text-align:center; padding: 20px;">还在静静观察，未形成明显心智画像。</div>';
    } else {
      let traitsHtml = '';
      if (m.perceived_traits && m.perceived_traits.length > 0) {
        traitsHtml = `<div style="font-size:13px; margin-top:8px;"><strong>揣摩特质：</strong>${esc(m.perceived_traits.join('、'))}</div>`;
      }
      let vulnsHtml = '';
      if (m.vulnerabilities && m.vulnerabilities.length > 0) {
        vulnsHtml = `<div style="font-size:13px; margin-top:4px;"><strong>感知软肋：</strong>${esc(m.vulnerabilities.join('、'))}</div>`;
      }
      mirrorBox.innerHTML = `
        <div style="padding:12px; background:var(--bg-subtle); border-radius:6px; border:1px solid var(--border);">
          <div style="font-size:14px; font-weight:600; color:var(--accent); margin-bottom:8px;">总体印象：${esc(m.summary || '-')}</div>
          ${traitsHtml}
          ${vulnsHtml}
          <div style="font-size:13px; margin-top:8px; padding-top:8px; border-top:1px dashed var(--border);">
            <strong>相处分寸建议：</strong> ${esc(m.interaction_advice || '-')}
          </div>
        </div>
      `;
    }

    // 3. Dream
    const dreamBox = document.getElementById('selfhood-dream-box');
    const lastDream = (statsRes.memory && statsRes.memory['上次梦境隐喻']) || '暂无梦境记忆';
    dreamBox.innerHTML = `
      <div style="padding:16px; background:var(--bg-subtle); border-radius:6px; border:1px solid var(--border); font-style:italic; color:var(--text); line-height:1.6; font-size:13.5px;">
        "${esc(lastDream)}"
      </div>
    `;
  } catch (e) {
    toast('加载自性体系数据失败: ' + e, 'err');
  }
}

async function triggerDream() {
  try {
    toast('正在触发潜意识梦境重构...', 'ok');
    const res = await call('POST', '/dream');
    if (res.ok) {
      toast('梦境重构已产生隐喻！', 'ok');
      await loadSelfhood();
    } else {
      toast(res.error || '重构失败，可能是因为记忆节点不足。', 'err');
    }
  } catch (e) {
    toast('重构出错: ' + e, 'err');
  }
}

// ---- STATUS ----
async function loadStatus() {
  const [stats, healthz, pData] = await Promise.all([
    call('GET', '/stats'), call('GET', '/healthz'), call('GET', '/persona').catch(() => ({}))
  ]);
  document.getElementById('status-time').textContent = new Date().toLocaleString();
  const sideDisplay = document.getElementById('current-persona-display');
  if (sideDisplay) {
    const charName = stats.character || 'default';
    const curPre = pData && pData.current_preset && pData.presets && pData.presets[pData.current_preset]
      ? pData.presets[pData.current_preset].name
      : '';
    sideDisplay.textContent = curPre ? `${charName} (${curPre})` : charName;
  }

  const mem = stats.memory || {};
  const api = stats.api_status || healthz.api_status || {};
  const brainReady = !!api.brain_ready;
  const upstreamsReady = !!api.upstreams_configured;
  const apiReady = !!(brainReady || upstreamsReady);

  const alertBox = document.getElementById('status-api-alert');
  if (alertBox) {
    if (!apiReady) {
      alertBox.innerHTML = `
        <div class="card" style="border-color:rgba(217,119,87,0.55);background:linear-gradient(135deg, rgba(217,119,87,0.12), rgba(212,163,115,0.06));margin-bottom:18px;padding:16px 20px">
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px">
            <div>
              <div style="font-family:var(--font-serif);font-size:15px;font-weight:600;color:var(--err);margin-bottom:4px">
                尚未连接外部模型 API — 记忆生长与对话代理处于待机状态
              </div>
              <div style="font-size:12.5px;color:var(--muted);line-height:1.6">
                当前未检测到有效的 API Key（<code>secrets.json</code> 与 <code>upstreams.json</code> 均为空）。本地记忆库与控制台已就绪，但后台生长器无法提炼记忆，对话网关也无法转发请求。
              </div>
            </div>
            <button class="btn btn-primary btn-sm" onclick="showPanel('connect')" style="white-space:nowrap">
              前往「10 外部连接」配置 API →
            </button>
          </div>
        </div>
      `;
    } else if (!brainReady) {
      alertBox.innerHTML = `
        <div class="card" style="border-color:rgba(212,163,115,0.45);background:rgba(212,163,115,0.07);margin-bottom:18px;padding:14px 18px">
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px">
            <div style="font-size:12.5px;color:var(--fg)">
              <strong style="color:var(--warn)">后台记忆生长模型未配置密钥：</strong>请前往「10 外部连接」填写后台记忆生长模型的 API Key，否则后台生长器将保持待机。
            </div>
            <button class="btn btn-outline btn-sm" onclick="showPanel('connect')">去配置 →</button>
          </div>
        </div>
      `;
    } else {
      alertBox.innerHTML = '';
    }
  }

  let growerStatusText = '● 已暂停';
  let growerStatusCls = 'err';
  if (stats.grower_alive) {
    if (brainReady) {
      growerStatusText = '● 运行中';
      growerStatusCls = 'ok';
    } else {
      growerStatusText = '● 待机 (未配置 API)';
      growerStatusCls = 'warn';
    }
  }

  let healthStatusText = '正常';
  let healthStatusCls = 'ok';
  if (!healthz.ok || stats.last_error) {
    healthStatusText = '异常';
    healthStatusCls = 'err';
  } else if (!apiReady) {
    healthStatusText = '待配置 API 密钥';
    healthStatusCls = 'warn';
  } else if (!brainReady) {
    healthStatusText = '记忆 API 未配置';
    healthStatusCls = 'warn';
  }

  const brainStatusHtml = brainReady
    ? `<span class="val ok" title="${esc(api.brain_base_url||'')}">已连接 (${esc(api.brain_model||'default')})</span>`
    : `<span class="val err" style="cursor:pointer;text-decoration:underline" onclick="showPanel('connect')">未配置 API Key</span>`;

  const upstreamStatusHtml = upstreamsReady
    ? `<span class="val ok">已配置 (${api.upstreams_count||1} 节点)</span>`
    : (brainReady
        ? `<span class="val muted" style="font-size:12px;cursor:pointer" onclick="showPanel('connect')">未独立配置 (共用记忆模型)</span>`
        : `<span class="val err" style="cursor:pointer;text-decoration:underline" onclick="showPanel('connect')">未配置节点</span>`);

  const grid = document.getElementById('status-grid');
  grid.innerHTML = `
    <div class="card"><h3>角色与引擎状态</h3>
      <div class="stat"><span>当前角色 (Character)</span><span class="val" style="color:var(--accent)">${esc(stats.character||'-')}</span></div>
      <div class="stat"><span>记忆生长 API (Brain)</span>${brainStatusHtml}</div>
      <div class="stat"><span>对话代理节点 (Upstream)</span>${upstreamStatusHtml}</div>
      <div class="stat"><span>后台生长器 (Grower)</span><span class="val ${growerStatusCls}">${growerStatusText}</span></div>
      <div class="stat"><span>待消化对话 (Pending)</span><span class="val">${stats.pending||0} 条</span></div>
    </div>
    <div class="card"><h3>记忆与神经沉淀</h3>
      <div class="stat"><span>演化周期 (Cycle)</span><span class="val">#${mem['周期']||0}</span></div>
      <div class="stat"><span>情景记忆节点 (Events)</span><span class="val">${mem['事件']||0}</span></div>
      <div class="stat"><span>性格特质总数 (Traits)</span><span class="val">${mem['特质']||0}</span></div>
      <div class="stat"><span>已固化内核 (Kernel)</span><span class="val ok">${mem['内核']||0}</span></div>
      <div class="stat"><span>赫布突触连线 (Edges)</span><span class="val">${mem['连线']||0}</span></div>
    </div>
    <div class="card"><h3>自性与系统健康</h3>
      <div class="stat"><span>活跃执念 (Active Drives)</span><span class="val warn">${stats.active_drives||0}</span></div>
      <div class="stat"><span>自我叙述版本 (Narratives)</span><span class="val">${mem['自述版本']||0}</span></div>
      <div class="stat"><span>演化账本记录 (Changelog)</span><span class="val">${mem['变更记录']||0}</span></div>
      <div class="stat"><span>最近错误 (Last Error)</span><span class="val ${stats.last_error?'err':'muted'}" style="font-size:11.5px;max-width:150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(stats.last_error||'无')}">${esc(stats.last_error||'无')}</span></div>
      <div class="stat"><span>系统综合状态 (Health)</span><span class="val ${healthStatusCls}">${healthStatusText}</span></div>
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
    : '<div class="muted" style="padding:16px;text-align:center">尚未长出显著性格特质。去「演示大厅」试玩，或通过客户端与角色多聊几句吧！</div>';
}

// ---- TRAITS ----
async function loadTraits() {
  const ctx = await call('GET', '/context?q=status');
  const traits = (ctx.context||{}).traits||[];
  const explain = await call('GET', '/explain?kind=trait&limit=50');
  const changes = explain.items||explain.changes||[];

  document.getElementById('traits-table').innerHTML = traits.length
    ? `<table style="width:100%;border-collapse:collapse;font-size:12px">
      <tr style="border-bottom:1px solid var(--border);color:var(--muted);text-align:left">
        <th style="padding:6px">Trait</th><th>Strength</th><th>Phase</th><th>Evidence</th><th>Kernel</th>
      </tr>
      ${traits.map(t => {
        const s = (t.strength||0)*100;
        const phase = t.phase||'?';
        const ev = t.evidence_count||0;
        const kernel = t.is_kernel ? 'CORE' : '';
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
  const explain = await call('GET', '/explain?limit=50');
  const changes = explain.items||explain.changes||[];
  document.getElementById('memory-content').innerHTML = changes.length
    ? `<h2>Changelog (${changes.length})</h2>
      <div class="timeline">${changes.map(c => `
        <div class="changelog-entry" style="padding:8px 0;border-bottom:1px solid var(--border)">
          <span class="ts" style="font-family:monospace;font-size:11px;color:var(--muted);margin-right:8px">${esc(c.when||'?')}</span>
          <strong style="color:var(--accent);margin-right:8px">[${esc(c.kind||'change')}] ${esc(c.target||'?')}</strong>
          <span class="muted">${esc(c.reason||'')}</span>
          ${(c.before !== null && c.before !== undefined && c.before !== '') ? `<span class="muted"> | ${esc(c.before)} → ${esc(c.after)}</span>` : ''}
        </div>`).join('')}</div>`
    : '<span class="muted">No changelog entries yet.</span>';
}
async function loadNetworkGraph() {
  const net = await call('GET', '/network?limit=80');
  const nodes = net.nodes || [];
  const edges = net.edges || [];

  document.getElementById('memory-content').innerHTML = `
    <h2>动态神经拓扑图 (Neural Topology)</h2>
    <div class="grid" style="margin-bottom:12px">
      <div class="card"><h3>神经元节点数 (Nodes)</h3><div class="val ok">${net.total_nodes || nodes.length}</div></div>
      <div class="card"><h3>赫布突触连线 (Edges)</h3><div class="val">${net.total_edges || edges.length}</div></div>
    </div>
    <div class="card" style="padding:10px;text-align:center">
      <canvas id="neural-canvas" width="800" height="460" style="width:100%;max-width:800px;height:460px;background:#080c14;border-radius:6px;border:1px solid var(--border)"></canvas>
      <div class="muted" style="font-size:11px;margin-top:8px">节点大小代表回忆显著性，连线粗细代表赫布突触强度（共同激活越多连线越深）</div>
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

// ---- EVOLUTION THEATER (Deep 5-Dimension Principle Sandbox) ----
const DEMO_SCENARIOS = {
  clockmaker: {
    title: "雨夜旧钟表店：从戒备到托付",
    acts: [
      {
        act: "ACT I",
        label: "初遇试探",
        cycle: 1,
        user: "这么晚还在修表？把你柜台最底层那只停摆的银怀表卖给我，我出双倍价钱。",
        thought: "（眼神微凛，这只表是旧友遗物，绝不可售。先不动声色试探来意。）",
        action: "放下手中的黄铜镊子，缓步合上玻璃展柜并锁好。",
        speech: "抱歉，底层那只怀表不卖。如果是修表，请放上台面；如果是猎奇，外面雨大，慢走不送。",
        mechNote: "三通道解析器自动剥离 [潜台词 Thought]（仅用于评估当前心境，不混入客观事实库），将外显言语与动作蒸馏为第一条情景记忆。",
        event: { id: "ev_01", summary: "来访者深夜欲高价收购旧友遗留的银怀表，严词回绝并锁柜", salience: 0.78, valence: -0.35, stood_firm: true, entities: ["银怀表", "深夜来客", "底线"], questions: ["对方为何偏偏认出那只停摆的银怀表？"] },
        traits: [
          { name: "边界感与戒备", strength: 0.68, pending: 0.14, phase: "HARDENED", kernel: true },
          { name: "原则底线坚守", strength: 0.52, pending: 0.18, phase: "GROWING", kernel: false },
          { name: "共情与托付感", strength: 0.16, pending: 0.02, phase: "DORMANT", kernel: false },
          { name: "叙事隐喻敏感度", strength: 0.30, pending: 0.06, phase: "SPROUTING", kernel: false }
        ],
        nodes: [
          { id: "银怀表", w: 0.85, x: 140, y: 65, active: true },
          { id: "底线坚守", w: 0.75, x: 270, y: 55, active: true },
          { id: "深夜来客", w: 0.65, x: 190, y: 145, active: true }
        ],
        edges: [
          { s: "银怀表", t: "底线坚守", w: 0.65, active: true },
          { s: "银怀表", t: "深夜来客", w: 0.55, active: true }
        ],
        recallPath: "新节点入网：[银怀表] ──(0.65)──> [底线坚守] (stood_firm=true 赋予防衰减保底权重 0.55)",
        drive: { theme: "来访者与旧友银怀表的隐秘关联", tension: 0.48, status: "ACTIVE · 初生悬念", q: "对方为何指名要那只停在 3:15 的银怀表？" },
        mirror: { summary: "目的不明的深夜造访者，出手阔绰但带有试探性压迫感", traits: ["敏锐", "目标明确", "带有隐情"], advice: "保持距离，守住核心旧物，观察其后续解释" },
        dream: "（清醒交互期 · 潜意识梦境尚未触发）",
        narrativeVer: "v0 · 初始种子自述 (Cycle 0)",
        narrative: "我守着旧街尽头的钟表铺，替人修补走偏的齿轮，但从不向陌生人敞开自己的过去。",
        changelog: [
          { tag: "EVENT_EXTRACT", ref: "ev_01", desc: "检测到 stood_firm=true（面对双倍出价坚守立场），该记忆获得永久抗衰减保护。" }
        ]
      },
      {
        act: "ACT II",
        label: "旧物信物",
        cycle: 2,
        user: "别紧张，我不是来夺人所爱的。你看表盖内侧是不是刻着『致北极星，于暴雨夜』？我是替当年送表的人带话来的。",
        thought: "（呼吸骤停——这句铭文从未对外人提起过！防备心瞬间被巨大的震动撕开一道口子。）",
        action: "手指微微发颤地扶住柜台边缘，重新打开台灯照向对方。",
        speech: "……你怎么会知道表盖内侧的刻字？他现在人在哪里？",
        mechNote: "输入出现高显著性锚点词 [暴雨夜] 与 [银怀表]，赫布网络发生强共同激活（Δw = +0.28），蔡加尼克执念张力急剧攀升。",
        event: { id: "ev_02", summary: "对方准确道出怀表内侧私密铭文『致北极星，于暴雨夜』，自称受故人所托", salience: 0.94, valence: 0.25, stood_firm: false, entities: ["银怀表", "暴雨夜", "北极星", "故人信物"], questions: ["故人如今身在何处？为何委托他人前来？"] },
        traits: [
          { name: "边界感与戒备", strength: 0.64, pending: -0.12, phase: "HARDENED", kernel: true },
          { name: "原则底线坚守", strength: 0.55, pending: 0.08, phase: "GROWING", kernel: false },
          { name: "共情与托付感", strength: 0.22, pending: 0.26, phase: "SPROUTING", kernel: false },
          { name: "叙事隐喻敏感度", strength: 0.34, pending: 0.14, phase: "SPROUTING", kernel: false }
        ],
        nodes: [
          { id: "银怀表", w: 0.95, x: 140, y: 65, active: true },
          { id: "底线坚守", w: 0.72, x: 270, y: 55, active: false },
          { id: "深夜来客", w: 0.70, x: 190, y: 145, active: true },
          { id: "暴雨夜铭文", w: 0.90, x: 340, y: 120, active: true },
          { id: "北极星故人", w: 0.88, x: 430, y: 65, active: true }
        ],
        edges: [
          { s: "银怀表", t: "底线坚守", w: 0.62, active: false },
          { s: "银怀表", t: "深夜来客", w: 0.68, active: true },
          { s: "银怀表", t: "暴雨夜铭文", w: 0.86, active: true },
          { s: "暴雨夜铭文", t: "北极星故人", w: 0.82, active: true }
        ],
        recallPath: "赫布突触强化：[银怀表] ══(0.86)══> [暴雨夜铭文] ══(0.82)══> [北极星故人]",
        drive: { theme: "追问故人下落与当年失约的真相", tension: 0.82, status: "FERMENTING · 高张力悬念", q: "当年暴雨夜他为何不辞而别？如今是否安好？" },
        mirror: { summary: "握有故人核心信物的知情者，并非恶意收购商，言辞诚恳", traits: ["守信", "知晓内情", "沉稳"], advice: "放下敌意，倾听对方带来的故人讯息" },
        dream: "（清醒交互期 · 蔡加尼克张力已达 82%，等待闲置整合）",
        narrativeVer: "v1 · 局部修正自述 (Cycle 2)",
        narrative: "我守着旧街尽头的钟表铺。今夜有人念出了银怀表内侧唯有故人才懂的铭文，我紧锁多年的防备第一次出现了裂痕。",
        changelog: [
          { tag: "TRAIT_MOMENTUM", ref: "ev_02", desc: "「共情与托付感」快态蓄水池注入 +0.26 动量，由 DORMANT 唤醒至 SPROUTING（萌芽态）。" },
          { tag: "MIRROR_UPDATE", ref: "ev_02", desc: "他者之镜修正：将对话者从「可疑收购者」重构为「故人信使」。" }
        ]
      },
      {
        act: "ACT III",
        label: "闲置梦境",
        cycle: 3,
        user: "【系统模拟：对话闲置 3 小时 · 后台 Grower 自动触发潜意识梦境重放与蔡加尼克发酵】",
        thought: "（夜深雨歇，独自坐在滴答作响的钟摆声里，白天的铭文与三年前的远航信件在脑海中交织。）",
        action: "在无人打扰的静默期，潜意识算子自动检索远距离孤立记忆节点并建立隐喻桥接。",
        speech: "（独处低语）原来停在三点十五分的不是齿轮，是我一直没敢拆开的那封旧信……",
        mechNote: "核心机制展示：当空闲时间超过 idle_seconds，Loam 无需外部提问即可自发进行【蔡加尼克张力发酵 (+0.09)】与【潜意识梦境跨簇桥接】。",
        event: { id: "ev_03_dream", summary: "【潜意识梦境桥接】将『停摆的银怀表』与三年前『未寄出的灯塔航行日志』建立跨簇神经连线", salience: 0.84, valence: 0.10, stood_firm: false, entities: ["银怀表", "北极星故人", "灯塔航行日志"], questions: ["我是否准备好直面当年的告别？"] },
        traits: [
          { name: "边界感与戒备", strength: 0.60, pending: -0.05, phase: "HARDENED", kernel: true },
          { name: "原则底线坚守", strength: 0.56, pending: 0.04, phase: "GROWING", kernel: false },
          { name: "共情与托付感", strength: 0.36, pending: 0.24, phase: "SPROUTING", kernel: false },
          { name: "叙事隐喻敏感度", strength: 0.58, pending: 0.06, phase: "GROWING", kernel: false }
        ],
        nodes: [
          { id: "银怀表", w: 0.95, x: 140, y: 65, active: true },
          { id: "底线坚守", w: 0.68, x: 270, y: 55, active: false },
          { id: "深夜来客", w: 0.66, x: 190, y: 145, active: false },
          { id: "暴雨夜铭文", w: 0.88, x: 340, y: 120, active: false },
          { id: "北极星故人", w: 0.90, x: 430, y: 65, active: true },
          { id: "灯塔旧日志", w: 0.82, x: 420, y: 165, active: true }
        ],
        edges: [
          { s: "银怀表", t: "底线坚守", w: 0.58, active: false },
          { s: "银怀表", t: "深夜来客", w: 0.64, active: false },
          { s: "银怀表", t: "暴雨夜铭文", w: 0.84, active: false },
          { s: "暴雨夜铭文", t: "北极星故人", w: 0.82, active: false },
          { s: "银怀表", t: "灯塔航行日志", w: 0.74, active: true },
          { s: "北极星故人", t: "灯塔旧日志", w: 0.79, active: true }
        ],
        recallPath: "梦境隐喻桥接：[银怀表] ──(Dream Bridge 0.79)──> [北极星故人] ──> [灯塔旧日志]",
        drive: { theme: "追问故人下落与当年失约的真相", tension: 0.91, status: "CRITICAL · 蔡加尼克峰值 (91%)", q: "下次见面时必须主动询问灯塔观测站的结局" },
        mirror: { summary: "握有故人核心信物的知情者，激发了自身深层回忆", traits: ["守信", "知晓内情", "值得深谈"], advice: "下次对话主动提及灯塔旧日志，坦诚交流" },
        dream: "「梦见雨水倒流回怀表的发条盒里，三点十五分的指针化作远方灯塔的旋转光束，照亮了那页未签名的航行日志。」",
        narrativeVer: "v1 · 静默自省态 (Cycle 3)",
        narrative: "我守着旧街尽头的钟表铺。今夜有人念出了银怀表内侧唯有故人才懂的铭文，那些被我尘封在灯塔日志里的旧事正在重新苏醒。",
        changelog: [
          { tag: "DREAM_SYNAPSE", ref: "ev_03_dream", desc: "闲置期潜意识做梦：在远距离节点 [银怀表] 与 [灯塔旧日志] 之间建立隐喻突触。" },
          { tag: "PHASE_GATE", ref: "ev_03_dream", desc: "「叙事隐喻敏感度」跨越 0.55 相变门限（0.34 → 0.58），正式跃迁至 GROWING（成形态）。" }
        ]
      },
      {
        act: "ACT IV",
        label: "二跳召回",
        cycle: 4,
        user: "他当年没能赶回来，是因为北极星号观测船在返航途中遭遇磁暴，他把最后的航行日志封存在了海岸灯塔。",
        thought: "（心头剧震——昨夜梦里浮现的『灯塔旧日志』竟然在这一刻与现实严丝合缝地印证了！）",
        action: "从内室木匣中取出一本边缘泛黄的册子，轻轻推到对方手边。",
        speech: "你说的是那座断崖上的灯塔吧……其实那本日志的下半册，三年前就已经辗转寄到我手里了。",
        mechNote: "赫布二跳扩散激活 (2-Hop Spreading Activation)：用户输入 [灯塔] → 激活 [北极星故人] → 跨跳唤醒昨夜桥接的 [银怀表] 与 [暴雨夜铭文]，上下文精准注入！",
        event: { id: "ev_04", summary: "得知故人因磁暴滞留并封存日志于海岸灯塔，主动取出珍藏的下半册日志相认", salience: 0.96, valence: 0.68, stood_firm: false, entities: ["灯塔旧日志", "北极星故人", "银怀表", "托付"], questions: [] },
        traits: [
          { name: "边界感与戒备", strength: 0.46, pending: -0.08, phase: "GROWING", kernel: false },
          { name: "原则底线坚守", strength: 0.62, pending: 0.06, phase: "HARDENED", kernel: true },
          { name: "共情与托付感", strength: 0.64, pending: 0.08, phase: "GROWING", kernel: false },
          { name: "叙事隐喻敏感度", strength: 0.66, pending: 0.05, phase: "GROWING", kernel: false }
        ],
        nodes: [
          { id: "银怀表", w: 0.96, x: 140, y: 65, active: true },
          { id: "底线坚守", w: 0.70, x: 270, y: 55, active: false },
          { id: "深夜来客", w: 0.78, x: 190, y: 145, active: true },
          { id: "暴雨夜铭文", w: 0.90, x: 340, y: 120, active: true },
          { id: "北极星故人", w: 0.95, x: 430, y: 65, active: true },
          { id: "灯塔旧日志", w: 0.94, x: 420, y: 165, active: true }
        ],
        edges: [
          { s: "银怀表", t: "底线坚守", w: 0.58, active: false },
          { s: "银怀表", t: "深夜来客", w: 0.75, active: true },
          { s: "银怀表", t: "暴雨夜铭文", w: 0.88, active: true },
          { s: "暴雨夜铭文", t: "北极星故人", w: 0.91, active: true },
          { s: "北极星故人", t: "灯塔旧日志", w: 0.93, active: true }
        ],
        recallPath: "二跳扩散召回命中：[灯塔旧日志] ══(0.93)══> [北极星故人] ══(0.91)══> [暴雨夜铭文] ══(0.88)══> [银怀表]",
        drive: { theme: "追问故人下落与当年失约的真相", tension: 0.0, status: "RESOLVED · 执念释怀消解", q: "已得知磁暴真相，长达三年的未解心结圆满闭合。" },
        mirror: { summary: "跨越风浪送达故人真相的同行者，值得交付深层信任", traits: ["重诺", "坚韧", "同路人"], advice: "坦诚相待，共同拼合完整的航行记忆" },
        dream: "「梦境隐喻已在现实对话中完成印证与闭环。」",
        narrativeVer: "v2 · 相变重写自述 (Cycle 4 · 重大人格演进)",
        narrative: "我曾在旧街尽头的钟表铺里独自守着停摆的银怀表，用冷漠防备外界。直到今夜故人的信使带来海岸灯塔的真相，我明白守住底线并非为了封闭自己，而是为了把珍贵的记忆托付给真正值得信任的同行者。",
        changelog: [
          { tag: "PHASE_TRANSITION", ref: "ev_02, ev_04", desc: "【核心质变】「共情与托付感」慢态强度突破 0.55 门限（0.36 → 0.64），正式跃迁为 GROWING 主导特质！" },
          { tag: "DRIVE_RESOLVED", ref: "ev_04", desc: "蔡加尼克执念「故人失约真相」获得完整解答，张力从 91% 释放归零，转化为正向情感共振。" },
          { tag: "NARRATIVE_REWRITE", ref: "ev_01..ev_04", desc: "触发第一人称自我叙述 v2 重写：从「孤立防御者」演进为「有原则的守望与托付者」。" }
        ]
      }
    ]
  },
  observatory: {
    title: "深空监听站：执念发酵与跨周期唤醒",
    acts: [
      {
        act: "ACT I",
        label: "异常脉冲",
        cycle: 1,
        user: "第 14 扇区刚才收到一段窄带脉冲，频率是 1420.4 MHz，但只持续了四秒就消失了。",
        thought: "（1420.4 MHz 是中性氢谱线……难道是三年前失联的『远行者七号』？但证据还太单薄，不能贸然下结论。）",
        action: "迅速调出频谱瀑布图，将那四秒波形锁定在副屏第 01 号采样槽。",
        speech: "我已经锁定了这段波形。先别上报中心，单次四秒脉冲可能是反射杂波，我们需要等待二次谐波确认。",
        mechNote: "首次特征事件入库：形成未解疑问与蔡加尼克初始驱动力，理性审慎特质处于主导地位。",
        event: { id: "ev_101", summary: "捕获 1420.4 MHz 短暂四秒脉冲，克制冲动并锁定波形等待二次验证", salience: 0.80, valence: 0.15, stood_firm: true, entities: ["1420MHz脉冲", "第14扇区", "远行者七号"], questions: ["这段脉冲究竟是自然杂波还是远行者七号的回音？"] },
        traits: [
          { name: "实证审慎态度", strength: 0.72, pending: 0.10, phase: "HARDENED", kernel: true },
          { name: "探索执念张力", strength: 0.32, pending: 0.18, phase: "SPROUTING", kernel: false },
          { name: "协同默契信任", strength: 0.28, pending: 0.08, phase: "SPROUTING", kernel: false }
        ],
        nodes: [
          { id: "1420MHz脉冲", w: 0.84, x: 150, y: 80, active: true },
          { id: "第14扇区", w: 0.70, x: 290, y: 65, active: true },
          { id: "远行者七号", w: 0.65, x: 240, y: 155, active: true }
        ],
        edges: [
          { s: "1420MHz脉冲", t: "第14扇区", w: 0.72, active: true },
          { s: "1420MHz脉冲", t: "远行者七号", w: 0.58, active: true }
        ],
        recallPath: "初始拓扑建立：[1420MHz脉冲] ──(0.72)──> [第14扇区]",
        drive: { theme: "验证 1420.4 MHz 脉冲的真实信源", tension: 0.52, status: "ACTIVE · 悬念生成", q: "是否还会出现第二次规律脉冲？" },
        mirror: { summary: "敏锐但略显急切的值班观测搭档", traits: ["敏锐", "直觉强"], advice: "用严谨数据引导搭档，共同守候第二轮信号" },
        dream: "（清醒值守期 · 尚未进入梦境重放）",
        narrativeVer: "v0 · 初始种子自述 (Cycle 1)",
        narrative: "我是深空监听站的记录员，只相信经过交叉验证的频谱数据，从不被未经证实的猜想左右。",
        changelog: [
          { tag: "DRIVE_SPAWN", ref: "ev_101", desc: "未解问题自动转化为蔡加尼克执念（初始张力 52%）。" }
        ]
      },
      {
        act: "ACT II",
        label: "静默发酵",
        cycle: 2,
        user: "【系统模拟：连续 12 小时无新信号 · 后台 Grower 执行执念发酵与独处自省】",
        thought: "（耳机里只有宇宙背景辐射的白噪音，但那四秒脉冲的包络线一直在脑海里挥之不去……）",
        action: "独自比对三年前『远行者七号』失联前的遥测帧头校验码。",
        speech: "（独白）如果把时间轴拉长十倍，那四秒脉冲的间隔，恰好对应着当年航天器自旋稳定的周期……",
        mechNote: "在无外部对话输入时，蔡加尼克执念随时间自动发酵（52% → 86%），并在后台触发潜意识梦境与独处顿悟。",
        event: { id: "ev_102_idle", summary: "【闲置期自省与梦境】发现四秒脉冲间隔与三年前『自旋周期校验码』存在数学同构", salience: 0.88, valence: 0.30, stood_firm: false, entities: ["1420MHz脉冲", "自旋校验码", "远行者七号"], questions: ["搭档是否保存着当年的原始遥测密钥？"] },
        traits: [
          { name: "实证审慎态度", strength: 0.72, pending: 0.04, phase: "HARDENED", kernel: true },
          { name: "探索执念张力", strength: 0.57, pending: 0.12, phase: "GROWING", kernel: false },
          { name: "协同默契信任", strength: 0.32, pending: 0.10, phase: "SPROUTING", kernel: false }
        ],
        nodes: [
          { id: "1420MHz脉冲", w: 0.88, x: 150, y: 80, active: true },
          { id: "第14扇区", w: 0.66, x: 290, y: 65, active: false },
          { id: "远行者七号", w: 0.85, x: 240, y: 155, active: true },
          { id: "自旋校验码", w: 0.86, x: 410, y: 115, active: true }
        ],
        edges: [
          { s: "1420MHz脉冲", t: "第14扇区", w: 0.68, active: false },
          { s: "1420MHz脉冲", t: "远行者七号", w: 0.78, active: true },
          { s: "远行者七号", t: "自旋校验码", w: 0.84, active: true }
        ],
        recallPath: "潜意识跨簇桥接：[1420MHz脉冲] ══(0.78)══> [远行者七号] ══(0.84)══> [自旋校验码]",
        drive: { theme: "验证 1420.4 MHz 脉冲的真实信源", tension: 0.86, status: "CRITICAL · 执念发酵至 86%", q: "亟需用旧遥测密钥解码脉冲包络！" },
        mirror: { summary: "并肩守候深空信号的可靠搭档", traits: ["敏锐", "坚持"], advice: "主动分享自旋周期发现，请求协助解码" },
        dream: "「梦见射电望远镜的抛物面化作寂静的海湾，四秒一次的灯塔闪光在星图上连成了远行者七号的轨道。」",
        narrativeVer: "v1 · 执念觉醒自述 (Cycle 2)",
        narrative: "我依然坚守实证原则，但那段四秒脉冲已在心底发酵成无法忽视的执念。在漫长的静默比对中，我看见了远行者七号跨越三年的回音。",
        changelog: [
          { tag: "ZEIGARNIK_FERMENT", ref: "ev_102_idle", desc: "蔡加尼克张力随静默时长攀升至 86%，推动「探索执念张力」跨越 0.55 相变门限进入 GROWING。" }
        ]
      },
      {
        act: "ACT III",
        label: "破译闭环",
        cycle: 3,
        user: "我把三年前归档室的旧遥测密钥带来了！按自旋周期解调后，屏幕跳出了一行字：『已完成木卫二冰层掠飞，正在返航』！",
        thought: "（三年的漫长等待终于落地！审慎的克制与炽热的守望在这一刻合二为一。）",
        action: "与搭档同时站起身，将解码成功的完整遥测帧正式签发至主星际通讯网。",
        speech: "确认无误，信噪比 18dB，校验完全匹配。谢谢你一直没有放弃第 14 扇区——我们终于把它接回家了。",
        mechNote: "闭环达成：赫布全链路高能激活，蔡加尼克张力释放归零，「协同默契信任」突破门限完成人格质变。",
        event: { id: "ev_103", summary: "与搭档用旧遥测密钥成功破译远行者七号返航报文，三年守望圆满闭环", salience: 0.98, valence: 0.85, stood_firm: false, entities: ["远行者七号", "自旋校验码", "1420MHz脉冲", "第14扇区"], questions: [] },
        traits: [
          { name: "实证审慎态度", strength: 0.78, pending: 0.05, phase: "KERNEL", kernel: true },
          { name: "探索执念张力", strength: 0.68, pending: 0.04, phase: "HARDENED", kernel: true },
          { name: "协同默契信任", strength: 0.62, pending: 0.08, phase: "GROWING", kernel: false }
        ],
        nodes: [
          { id: "1420MHz脉冲", w: 0.94, x: 150, y: 80, active: true },
          { id: "第14扇区", w: 0.82, x: 290, y: 65, active: true },
          { id: "远行者七号", w: 0.98, x: 240, y: 155, active: true },
          { id: "自旋校验码", w: 0.92, x: 410, y: 115, active: true }
        ],
        edges: [
          { s: "1420MHz脉冲", t: "第14扇区", w: 0.85, active: true },
          { s: "1420MHz脉冲", t: "远行者七号", w: 0.94, active: true },
          { s: "远行者七号", t: "自旋校验码", w: 0.92, active: true },
          { s: "第14扇区", t: "自旋校验码", w: 0.80, active: true }
        ],
        recallPath: "全网共振闭环：[第14扇区] ══> [1420MHz脉冲] ══> [远行者七号] ══> [自旋校验码]",
        drive: { theme: "验证 1420.4 MHz 脉冲的真实信源", tension: 0.0, status: "RESOLVED · 执念圆满达成", q: "远行者七号返航信号已确认。" },
        mirror: { summary: "共同见证深空奇迹的生死挚友与默契搭档", traits: ["敏锐", "执着", "高度默契"], advice: "完全信赖，共享最高权限观测资料" },
        dream: "「深空的海湾归于澄澈，所有散落的脉冲星点都已汇入返航的航迹。」",
        narrativeVer: "v2 · 终章重写自述 (Cycle 3)",
        narrative: "我是深空监听站的守望者。我依然敬畏每一份严谨的实证数据，但我更学会了在漫长的宇宙静默中与同伴并肩守候那些跨越岁月的微弱回音。",
        changelog: [
          { tag: "KERNEL_LOCK", ref: "ev_101..ev_103", desc: "「实证审慎态度」经多周期验证正式固化为 KERNEL（核心不灭特质）。" },
          { tag: "PHASE_TRANSITION", ref: "ev_103", desc: "「协同默契信任」突破 0.55 相变门限（0.32 → 0.62），自我叙述完成 v2 重写。" }
        ]
      }
    ]
  }
};

let _demoScenarioKey = 'clockmaker';
let _demoPlaying = false;
let _demoStep = 0;
let _demoTimer = null;

function switchDemoScenario(key) {
  if (!DEMO_SCENARIOS[key]) return;
  _demoScenarioKey = key;
  resetDemoSimulation();
}

function jumpDemoAct(idx) {
  const acts = DEMO_SCENARIOS[_demoScenarioKey].acts;
  if (idx < 0 || idx >= acts.length) return;
  if (_demoTimer) clearTimeout(_demoTimer);
  _demoPlaying = false;
  const playBtn = document.getElementById('demo-play-btn');
  if (playBtn) playBtn.textContent = '▶ 自动推演全剧';
  _demoStep = idx;
  renderDemoTheater();
}

function stepDemoAct(delta) {
  const acts = DEMO_SCENARIOS[_demoScenarioKey].acts;
  const next = Math.max(0, Math.min(acts.length - 1, _demoStep + delta));
  jumpDemoAct(next);
}

function drawDemoHebbianCanvas(actData) {
  const canvas = document.getElementById('demo-hebb-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const w = canvas.width, h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  const isLight = document.documentElement.classList.contains('light');
  const accentColor = isLight ? '#9c6644' : '#d4a373';
  const mutedColor = isLight ? 'rgba(87, 82, 74, 0.28)' : 'rgba(168, 162, 152, 0.24)';
  const textColor = isLight ? '#1c1a17' : '#ebe6dc';

  const nodeMap = {};
  (actData.nodes || []).forEach(n => { nodeMap[n.id] = n; });

  // Draw edges
  (actData.edges || []).forEach(e => {
    const s = nodeMap[e.s], t = nodeMap[e.t];
    if (!s || !t) return;
    ctx.beginPath();
    ctx.moveTo(s.x, s.y);
    ctx.lineTo(t.x, t.y);
    ctx.strokeStyle = e.active ? accentColor : mutedColor;
    ctx.lineWidth = e.active ? Math.max(2, e.w * 3.4) : 1.2;
    ctx.stroke();

    // Weight label on midpoint
    const mx = (s.x + t.x) / 2, my = (s.y + t.y) / 2;
    ctx.fillStyle = e.active ? accentColor : 'rgba(140,135,125,0.65)';
    ctx.font = '10px monospace';
    ctx.textAlign = 'center';
    ctx.fillText(e.w.toFixed(2), mx, my - 4);
  });

  // Draw nodes
  (actData.nodes || []).forEach(n => {
    const r = 7 + n.w * 7;
    if (n.active) {
      ctx.beginPath();
      ctx.arc(n.x, n.y, r + 6, 0, Math.PI * 2);
      ctx.fillStyle = isLight ? 'rgba(156, 102, 68, 0.14)' : 'rgba(212, 163, 115, 0.16)';
      ctx.fill();
    }
    ctx.beginPath();
    ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
    ctx.fillStyle = n.active ? accentColor : (isLight ? '#b8b0a4' : '#4a4742');
    ctx.fill();

    ctx.fillStyle = textColor;
    ctx.font = (n.active ? '600 ' : '') + '11.5px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(n.id, n.x, n.y + r + 15);
  });
}

function renderDemoTraits() {
  renderDemoTheater();
}

function renderDemoTheater() {
  const scen = DEMO_SCENARIOS[_demoScenarioKey] || DEMO_SCENARIOS.clockmaker;
  const acts = scen.acts;
  if (_demoStep >= acts.length) _demoStep = acts.length - 1;
  const cur = acts[_demoStep];

  // 1. Scrubber
  const scrubber = document.getElementById('demo-act-scrubber');
  if (scrubber) {
    scrubber.innerHTML = acts.map((a, i) => {
      const isCur = (i === _demoStep);
      const isDone = (i < _demoStep);
      return `<div onclick="jumpDemoAct(${i})" style="cursor:pointer;padding:8px 12px;border-radius:6px;border:1px solid ${isCur ? 'var(--accent)' : 'var(--border)'};background:${isCur ? 'var(--accent-soft)' : 'var(--bg-subtle)'};transition:all 0.2s">
        <div style="display:flex;justify-content:space-between;align-items:center;font-family:var(--font-mono);font-size:10.5px;color:${isCur ? 'var(--accent)' : (isDone ? 'var(--ok)' : 'var(--muted)')}">
          <span>${esc(a.act)}</span>
          <span>CYCLE #${a.cycle}</span>
        </div>
        <div style="font-weight:600;font-size:12.5px;margin-top:2px;color:var(--fg)">${esc(a.label)}</div>
      </div>`;
    }).join('');
  }

  const statusEl = document.getElementById('demo-status-text');
  if (statusEl) {
    statusEl.textContent = `[${cur.act} · ${cur.label}]  ${cur.mechNote}`;
  }

  // 2. Dialogue stream (cumulative up to _demoStep)
  const stream = document.getElementById('demo-dialogue-stream');
  if (stream) {
    stream.innerHTML = acts.slice(0, _demoStep + 1).map((a, idx) => {
      const isLatest = (idx === _demoStep);
      return `<div style="padding:12px 14px;border-radius:6px;background:${isLatest ? 'var(--bg-subtle)' : 'transparent'};border:1px solid ${isLatest ? 'var(--border-hover)' : 'var(--border)'}">
        <div style="display:flex;justify-content:space-between;font-family:var(--font-mono);font-size:10.5px;color:var(--muted);margin-bottom:6px">
          <span>${esc(a.act)} · ${esc(a.label)}</span>
          <span>EVENT: ${esc(a.event.id)}</span>
        </div>
        <div style="margin-bottom:8px;font-size:13px;color:var(--fg)">
          <span style="font-family:var(--font-mono);font-size:11px;color:var(--accent);margin-right:6px">[USER]</span>${esc(a.user)}
        </div>
        <div style="padding-left:10px;border-left:2px solid var(--border);display:flex;flex-direction:column;gap:4px;font-size:12.5px">
          <div style="color:var(--muted);font-style:italic"><span style="font-family:var(--font-mono);font-size:10.5px;font-style:normal;color:var(--accent-2)">[THOUGHT 潜台词·不落事实库]</span> ${esc(a.thought)}</div>
          <div style="color:var(--fg-dim)"><span style="font-family:var(--font-mono);font-size:10.5px;color:var(--ok)">[ACTION 动作轨]</span> ${esc(a.action)}</div>
          <div style="color:var(--fg);font-weight:500"><span style="font-family:var(--font-mono);font-size:10.5px;color:var(--accent)">[SPEECH 言语轨]</span> ${esc(a.speech)}</div>
        </div>
      </div>`;
    }).join('');
    stream.scrollTop = stream.scrollHeight;
  }

  // 3. Distilled Episodic Event Card
  const evBox = document.getElementById('demo-distilled-event');
  if (evBox && cur.event) {
    const ev = cur.event;
    evBox.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
        <span style="font-family:var(--font-mono);font-size:11.5px;font-weight:700;color:var(--accent)">DISTILLED EVENT · ${esc(ev.id)}</span>
        <div style="display:flex;gap:8px;font-family:var(--font-mono);font-size:11px">
          <span>Salience: <strong>${ev.salience.toFixed(2)}</strong></span>
          <span>Valence: <strong class="${ev.valence >= 0 ? 'ok' : 'err'}">${ev.valence >= 0 ? '+' : ''}${ev.valence.toFixed(2)}</strong></span>
          ${ev.stood_firm ? '<span style="padding:1px 6px;border-radius:3px;background:var(--accent-soft);color:var(--accent)">STOOD_FIRM (抗衰减保底)</span>' : ''}
        </div>
      </div>
      <div style="font-size:13px;font-weight:600;color:var(--fg);margin-bottom:6px">${esc(ev.summary)}</div>
      <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;font-size:11.5px;color:var(--muted)">
        <span>锚定实体：${ev.entities.map(x => `<code style="margin-right:4px">${esc(x)}</code>`).join('')}</span>
        <span>${ev.questions.length ? '生成未解悬念：' + esc(ev.questions[0]) : '悬念状态：无新增未解悬念'}</span>
      </div>
    `;
  }

  // 4. Dual-Timescale Traits Monitor
  const traitsBox = document.getElementById('demo-traits-monitor');
  if (traitsBox) {
    traitsBox.innerHTML = cur.traits.map(t => {
      const strPct = Math.round(t.strength * 100);
      const pendPct = Math.round(Math.max(0, t.pending) * 100);
      const negPend = t.pending < 0;
      return `<div style="padding:9px 12px;background:var(--bg-subtle);border-radius:6px;border:1px solid var(--border)">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px">
          <div style="display:flex;align-items:center;gap:8px">
            <span style="font-weight:600;font-size:13px">${esc(t.name)}</span>
            ${t.kernel ? '<span style="font-family:var(--font-mono);font-size:10px;padding:1px 5px;border:1px solid var(--accent);color:var(--accent);border-radius:3px">KERNEL</span>' : ''}
          </div>
          <span style="font-family:var(--font-mono);font-size:11px;color:var(--fg-dim)">
            ${esc(t.phase)} · <strong>${t.strength.toFixed(2)}</strong> <span style="color:${negPend ? 'var(--err)' : 'var(--accent)'}">(${t.pending >= 0 ? '+' : ''}${t.pending.toFixed(2)})</span>
          </span>
        </div>
        <div style="height:8px;background:var(--input-bg);border-radius:4px;overflow:hidden;position:relative;border:1px solid var(--border)">
          <div style="height:100%;width:${strPct}%;background:var(--ok);transition:width 0.45s ease;position:absolute;left:0"></div>
          <div style="height:100%;left:${strPct}%;width:${pendPct}%;background:var(--accent);opacity:0.75;transition:all 0.45s ease;position:absolute"></div>
          <div title="相变固化门限 Gate = 0.55" style="position:absolute;left:55%;top:0;bottom:0;width:2px;background:var(--fg);opacity:0.65"></div>
        </div>
      </div>`;
    }).join('');
  }

  // 5. Hebbian Canvas & Caption
  drawDemoHebbianCanvas(cur);
  const cap = document.getElementById('demo-hebb-caption');
  if (cap) cap.textContent = cur.recallPath || '';

  // 6. Selfhood Box (Zeigarnik Drive + Mirror + Dream)
  const selfBox = document.getElementById('demo-selfhood-box');
  if (selfBox) {
    const d = cur.drive;
    const m = cur.mirror;
    const tPct = Math.round((d.tension || 0) * 100);
    selfBox.innerHTML = `
      <div style="padding:10px 12px;background:var(--bg-subtle);border-radius:6px;border:1px solid var(--border)">
        <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:4px">
          <span style="font-weight:600">蔡加尼克内心执念：${esc(d.theme)}</span>
          <span style="font-family:var(--font-mono);color:var(--accent)">${esc(d.status)} (${tPct}%)</span>
        </div>
        <div style="height:5px;background:var(--input-bg);border-radius:3px;overflow:hidden;margin-bottom:6px">
          <div style="height:100%;width:${tPct}%;background:var(--accent);transition:width 0.45s ease"></div>
        </div>
        <div style="font-size:11.5px;color:var(--muted)">核心心结：${esc(d.q)}</div>
      </div>

      <div style="padding:10px 12px;background:var(--bg-subtle);border-radius:6px;border:1px solid var(--border)">
        <div style="font-family:var(--font-mono);font-size:10.5px;color:var(--muted);margin-bottom:3px">MIRROR OF OTHER · 他者之镜心智画像</div>
        <div style="font-size:12.5px;font-weight:600;color:var(--fg);margin-bottom:4px">${esc(m.summary)}</div>
        <div style="font-size:11.5px;color:var(--fg-dim)">感知特质：${esc(m.traits.join(' · '))} ｜ 相处策略：${esc(m.advice)}</div>
      </div>

      <div style="padding:10px 12px;background:var(--bg-subtle);border-radius:6px;border:1px solid var(--border)">
        <div style="font-family:var(--font-mono);font-size:10.5px;color:var(--muted);margin-bottom:3px">SUBCONSCIOUS DREAM · 潜意识梦境重放</div>
        <div style="font-family:var(--font-serif);font-size:13px;font-style:italic;color:var(--fg);line-height:1.55">${esc(cur.dream)}</div>
      </div>
    `;
  }

  // 7. Narrative & Auditable Changelog
  const narBox = document.getElementById('demo-narrative-box');
  if (narBox) {
    narBox.innerHTML = `
      <div style="padding:12px 14px;background:var(--bg-subtle);border-radius:6px;border:1px solid var(--border-hover)">
        <div style="display:flex;justify-content:space-between;font-family:var(--font-mono);font-size:10.5px;color:var(--accent);margin-bottom:6px">
          <span>FIRST-PERSON SELF-NARRATIVE</span>
          <span>${esc(cur.narrativeVer)}</span>
        </div>
        <div style="font-family:var(--font-serif);font-size:14.5px;line-height:1.7;color:var(--fg)">「${esc(cur.narrative)}」</div>
      </div>

      <div style="padding:10px 12px;background:var(--bg-subtle);border-radius:6px;border:1px solid var(--border)">
        <div style="font-family:var(--font-mono);font-size:10.5px;color:var(--muted);margin-bottom:6px">AUDITABLE CHANGELOG · 可溯源演化账本（每一笔变更均锚定原始证据）</div>
        <div style="display:flex;flex-direction:column;gap:6px">
          ${cur.changelog.map(c => `
            <div style="font-size:12px;line-height:1.45;padding-left:8px;border-left:2px solid var(--accent)">
              <span style="font-family:var(--font-mono);font-size:10.5px;color:var(--accent);margin-right:6px">[${esc(c.tag)}]</span>
              <span style="font-family:var(--font-mono);font-size:10.5px;color:var(--ok);margin-right:6px">ref:${esc(c.ref)}</span>
              <span style="color:var(--fg-dim)">${esc(c.desc)}</span>
            </div>
          `).join('')}
        </div>
      </div>
    `;
  }
}

function startDemoSimulation() {
  const scen = DEMO_SCENARIOS[_demoScenarioKey] || DEMO_SCENARIOS.clockmaker;
  const acts = scen.acts;
  const playBtn = document.getElementById('demo-play-btn');

  if (_demoPlaying) {
    if (_demoTimer) clearTimeout(_demoTimer);
    _demoPlaying = false;
    if (playBtn) playBtn.textContent = '▶ 继续自动推演';
    return;
  }

  _demoPlaying = true;
  if (_demoStep >= acts.length - 1) _demoStep = 0;
  if (playBtn) playBtn.textContent = '⏸ 暂停推演';
  renderDemoTheater();

  function tick() {
    if (!_demoPlaying) return;
    if (_demoStep < acts.length - 1) {
      _demoStep++;
      renderDemoTheater();
      _demoTimer = setTimeout(tick, 3200);
    } else {
      _demoPlaying = false;
      if (playBtn) playBtn.textContent = '▶ 重新自动推演';
      toast('全剧演化推演完成：角色已完成跨周期特质相变与自我叙述重写', 'ok');
    }
  }

  _demoTimer = setTimeout(tick, 3200);
}

function resetDemoSimulation() {
  if (_demoTimer) clearTimeout(_demoTimer);
  _demoPlaying = false;
  _demoStep = 0;
  const playBtn = document.getElementById('demo-play-btn');
  if (playBtn) playBtn.textContent = '▶ 自动推演全剧';
  renderDemoTheater();
}

window.addEventListener('DOMContentLoaded', () => {
  renderDemoTheater();
});

// ---- CONSTANTS (48 Physical & Dynamical Parameters) ----
async function loadConstants() {
  let data = null;
  try {
    const remote = await call('GET', '/constants');
    if (remote && remote.constants && Object.keys(remote.constants).length > 0) {
      data = remote;
    }
  } catch (e) {}
  if (!data) {
    data = await callAdmin('GET', '/admin/constants');  // fallback when loam backend is offline
  }
  const consts = data.constants||{};
  const overrides = data.overrides||{};
  const descs = data.descriptions||{};
  const keys = Object.keys(consts).sort();
  const ovCount = Object.keys(overrides).length;
  const summaryEl = document.getElementById('const-override-summary');
  if (summaryEl) {
    summaryEl.textContent = ovCount > 0 ? `(当前已有 ${ovCount} / ${keys.length} 项常数被覆盖)` : `(当前全部 ${keys.length} 项均为系统默认值)`;
  }
  document.getElementById('constants-list').innerHTML = keys.map(k => {
    const v = consts[k];
    const ov = overrides[k];
    const isOverridden = !!ov;
    const desc = descs[k] || '';
    return `<div class="const-row" data-key="${escAttr(k.toLowerCase())}" data-desc="${escAttr(desc.toLowerCase())}" data-overridden="${isOverridden ? '1' : '0'}" style="${isOverridden?'background:rgba(99,102,241,0.10)':''}">
      <span class="const-name" title="${escAttr(desc)}">${esc(k)}</span>
      <input class="const-input" data-name="${k}" value="${isOverridden?ov.override:v}" style="${isOverridden?'border-color:var(--accent)':''}">
      <span class="const-val">${isOverridden?`<span class="warn">${ov.original} → ${ov.override}</span>`:v}</span>
      <span class="const-desc" title="${escAttr(desc)}">${isOverridden?`已覆盖 · ${esc(desc)}`:esc(desc)}</span>
    </div>`;
  }).join('');
  filterConstantsRows();
}

function filterConstantsRows() {
  const q = (document.getElementById('const-search-inp')?.value || '').trim().toLowerCase();
  const onlyOv = !!document.getElementById('const-only-overridden')?.checked;
  document.querySelectorAll('#constants-list .const-row').forEach(row => {
    const k = row.dataset.key || '';
    const d = row.dataset.desc || '';
    const isOv = row.dataset.overridden === '1';
    const matchText = !q || k.includes(q) || d.includes(q);
    const matchOv = !onlyOv || isOv;
    row.style.display = (matchText && matchOv) ? '' : 'none';
  });
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
      altEl.innerHTML = `跨 App 用：http://${primary}:8783/v1`;
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
    const dmodel = p.default_model || p.model || '';
    const dlId = `up-models-list-${escAttr(name)}`;
    return `<div class="upstream-row" id="up-row-${escAttr(name)}" style="display:grid;grid-template-columns:0.8fr 1.2fr 1.2fr 1fr auto auto;gap:8px;align-items:end;padding:8px 0;border-bottom:1px solid var(--border)">
      <div class="form-group" style="margin:0">
        <label>提供商名称</label>
        <input class="up-name-inp" value="${escAttr(name)}" placeholder="如 relay1" style="font-weight:600">
      </div>
      <div class="form-group" style="margin:0">
        <label>Base URL（如 https://api.deepseek.com）</label>
        <input class="up-url-inp" value="${escAttr(p.base_url||'')}" placeholder="请填写 API 地址">
      </div>
      <div class="form-group" style="margin:0">
        <label>API Key（sk-...）</label>
        <input class="up-key-inp" type="password" value="${escAttr(p.api_key||'')}" placeholder="请填写密钥">
      </div>
      <div class="form-group" style="margin:0">
        <label>默认模型（Default Model）</label>
        <input class="up-model-inp" value="${escAttr(dmodel)}" list="${dlId}" placeholder="如 deepseek-chat">
        <datalist id="${dlId}"></datalist>
      </div>
      <button class="btn btn-sm btn-outline btn-fetch" style="height:38px;align-self:end" onclick="fetchModels('${escAttr(name)}')" title="拉取模型列表">拉取</button>
      <button class="btn btn-sm btn-danger" style="height:38px;align-self:end" onclick="removeUpstreamRow('${escAttr(name)}')">删除</button>
    </div>`;
  }).join('');

  // default select
  select.innerHTML = sorted.map(n => `<option value="${escAttr(n)}" ${n===defName?'selected':''}>${esc(n)}</option>`).join('');
  if (!sorted.length) select.innerHTML = '<option value="">— no providers —</option>';
}

function addUpstreamRow(name) {
  _upstreamData = collectUpstreamFromDOM();
  name = (name || '').trim();
  if (!name) {
    let i = 1;
    while (_upstreamData['relay'+i]) i++;
    name = 'relay'+i;
  }
  if (!_upstreamData[name]) _upstreamData[name] = {base_url:'', api_key:'', default_model:''};
  renderUpstreamRows(document.getElementById('up-default').value || name);
}

function removeUpstreamRow(name) {
  _upstreamData = collectUpstreamFromDOM();
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
    const modelInp = row.querySelector('.up-model-inp');
    const modelVal = (modelInp ? modelInp.value : (existing.default_model || '')).trim();
    data[name] = {
      base_url: (row.querySelector('.up-url-inp')?.value || '').trim(),
      api_key: (row.querySelector('.up-key-inp')?.value || '').trim(),
      default_model: modelVal,
    };
  });
  return data;
}

async function saveSecrets() {
  const modelEl = document.getElementById('sec-model');
  const modelVal = (modelEl.value || '').trim();
  const body = {
    api_key: document.getElementById('sec-key').value.trim(),
    base_url: document.getElementById('sec-url').value.trim(),
    model: modelVal,
  };
  if (!body.api_key || !body.base_url || !body.model) {
    toast('请完整填写记忆生长模型的 Base URL、API Key 和 Model', 'err'); return;
  }
  const r = await callAdmin('POST', '/admin/secrets', body);
  const el = document.getElementById('sec-status');
  if (r.ok) { el.innerHTML = '<span class="ok">已保存</span>'; toast('记忆生长模型配置已保存', 'ok'); }
  else { el.innerHTML = '<span class="err">'+esc(r.error||'failed')+'</span>'; toast('保存失败', 'err'); }
}

async function saveUpstreams() {
  const providers = collectUpstreamFromDOM();
  if (!Object.keys(providers).length) { toast('请至少添加一个提供商', 'err'); return; }
  for (const [name, p] of Object.entries(providers)) {
    if (!p.base_url || !p.api_key || !p.default_model) {
      toast('提供商 "' + name + '": 请完整填写 Base URL、API Key 和默认模型', 'err'); return;
    }
  }
  const defName = document.getElementById('up-default').value;
  const body = {providers};
  if (defName && providers[defName]) body.default = defName;
  const el = document.getElementById('up-status');
  el.innerHTML = '<span class="spinner"></span> 正在保存配置...';
  const r = await callAdmin('POST', '/admin/upstreams', body);
  if (r.ok) {
    _upstreamData = providers;
    el.innerHTML = '<span class="ok">已保存并热加载生效！</span>';
    toast('聊天回复模型 API 已保存并热生效', 'ok');
  } else { el.innerHTML = '<span class="err">'+esc(r.error||'保存失败')+'</span>'; toast('保存失败', 'err'); }
}

function loadConnect() { loadApiConfig(); }

// ---- FETCH MODELS ----
async function fetchModels(section) {
  let url, key, btnId;
  if (section === 'sec') {
    url = document.getElementById('sec-url').value.trim();
    key = document.getElementById('sec-key').value.trim();
    btnId = 'sec-status';
  } else {
    const row = document.getElementById('up-row-'+section);
    if (!row) { toast('找不到该提供商行', 'err'); return; }
    url = row.querySelector('.up-url-inp')?.value.trim() || '';
    key = row.querySelector('.up-key-inp')?.value.trim() || '';
    btnId = 'up-status';
  }
  if (!url || !key) { toast('请先填写 Base URL 和 API Key', 'err'); return; }
  const statusEl = document.getElementById(btnId);
  if (statusEl) statusEl.innerHTML = '<span class="spinner"></span> 正在拉取模型列表...';
  document.querySelectorAll('.btn-fetch').forEach(b => { b.disabled = true; b.classList.add('btn-fetching'); });
  try {
    const r = await callAdmin('POST', '/admin/fetch-models', {base_url: url, api_key: key});
    if (r.models && r.models.length) {
      if (section === 'sec') {
        const dl = document.getElementById('sec-models-list');
        if (dl) dl.innerHTML = r.models.map(m => `<option value="${escAttr(m)}">`).join('');
        const inp = document.getElementById('sec-model');
        if (inp) {
          const sel = document.createElement('select');
          sel.id = 'sec-model';
          sel.style.cssText = inp.style.cssText;
          const cur = inp.value;
          sel.innerHTML = r.models.map(m => `<option value="${escAttr(m)}" ${m===cur?'selected':''}>${esc(m)}</option>`).join('');
          inp.parentNode.replaceChild(sel, inp);
        }
      } else {
        const row = document.getElementById('up-row-'+section);
        if (row) {
          const inp = row.querySelector('.up-model-inp');
          if (inp) {
            const cur = inp.value;
            const sel = document.createElement('select');
            sel.className = 'up-model-inp';
            sel.style.cssText = inp.style.cssText;
            sel.innerHTML = r.models.map(m => `<option value="${escAttr(m)}" ${m===cur?'selected':''}>${esc(m)}</option>`).join('');
            inp.parentNode.replaceChild(sel, inp);
          }
        }
      }
      toast(`${r.models.length} 个模型已加载`, 'ok');
      if (statusEl) statusEl.innerHTML = `<span class="ok">已加载 ${r.models.length} 个模型，请选择后点击保存</span>`;
    } else {
      toast('拉取失败：' + (r.error||'未返回模型'), 'err');
      if (statusEl) statusEl.innerHTML = `<span class="err">${esc(r.error||'未返回模型')}</span>`;
    }
  } catch(e) {
    toast('拉取出错：' + e.message, 'err');
    if (statusEl) statusEl.innerHTML = `<span class="err">${esc(e.message)}</span>`;
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
      <h2>Update Available</h2>
      <p>Your loam is at <code>${esc(v.local)}</code> — latest is <code style="color:var(--ok)">${esc(v.remote)}</code>.<br>Update now? (loam + proxy will restart)</p>
      <div class="modal-actions">
        <button class="btn btn-ok" id="update-btn-confirm">Update & Restart</button>
        <button class="btn btn-outline" id="update-btn-cancel">Later</button>
      </div>
    </div>`;
    document.body.appendChild(overlay);
    document.getElementById('update-btn-cancel').onclick = () => overlay.remove();
    document.getElementById('update-btn-confirm').onclick = async () => {
      const btn = document.getElementById('update-btn-confirm');
      btn.disabled = true; btn.textContent = 'Updating...';
      const r = await callAdmin('POST', '/admin/update');
      if (r.ok) {
        overlay.querySelector('h2').textContent = 'Updated';
        overlay.querySelector('p').innerHTML = 'loam updated to <code>'+esc(v.remote)+'</code>. Restarting...<br>Page will reload in 5 seconds.';
        overlay.querySelector('.modal-actions').innerHTML = '';
        setTimeout(() => { location.reload(); }, 5000);
      } else {
        overlay.querySelector('p').innerHTML = '<span class="err">Update failed:</span> ' + esc(r.error||'unknown');
        btn.disabled = false; btn.textContent = 'Retry';
      }
    };
    // auto-close after 60s if ignored
    setTimeout(() => { if (overlay.parentNode) overlay.remove(); }, 60000);
  } catch(e) { /* network error — silently ignore */ }
}

// ---- ACTIONS ----
async function doAction(action) {
  const el = document.getElementById(action+'-result') || document.getElementById('backup-result');
  if (el) el.innerHTML = '<span class="spinner"></span> 正在执行...';
  try {
    let r;
    switch(action) {
      case 'digest': r = await call('POST', '/digest', {limit: 20}); break;
      case 'drain': r = await call('POST', '/drain', {max_rounds: 50}); break;
      case 'backup_export': r = await call('POST', '/backup/export', {}); break;
      case 'recompute':
        if (!confirm('确定要从原始对话重新整理与索引记忆吗？')) {
          if (el) el.innerHTML = '';
          return;
        }
        r = await call('POST', '/recompute', {mode: 'incremental', note: 'admin panel'});
        break;
      default:
        r = {error: '未知动作: ' + action};
    }
    if (el) el.innerHTML = `<pre style="font-size:11px;max-height:200px;overflow-y:auto">${esc(JSON.stringify(r,null,2))}</pre>`;
    toast(action + ' 执行完成', 'ok');
  } catch(e) {
    if (el) el.innerHTML = `<span class="err">${esc(e.message)}</span>`;
    toast(action + ' 失败: ' + e.message, 'err');
  }
}

function esc(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function escAttr(s) { return String(s).replace(/&/g,'&amp;').replace(/"/g,'"').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

// ---- theme ----
(function(){ if(localStorage.getItem('loam-theme')==='light') document.documentElement.classList.add('light'); })();
function toggleTheme(){
  const isLight = document.documentElement.classList.toggle('light');
  localStorage.setItem('loam-theme', isLight?'light':'dark');
  document.querySelector('.theme-btn').textContent = isLight?'◑':'◐';
}
(function(){ document.querySelector('.theme-btn').textContent = document.documentElement.classList.contains('light')?'◑':'◐'; })();

// ---- init ----
syncCharactersList(true).then(() => loadStatus());
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
      statusEl.innerHTML = '<span class="ok">已保存并立即生效！</span>';
      document.getElementById('growth-batch').textContent = batch;
      document.getElementById('growth-idle').textContent = Math.round(idle/60);
    } else {
      statusEl.innerHTML = '<span class="err">' + (r.error||'保存失败') + '</span>';
    }
  } catch(e) {
    statusEl.innerHTML = '<span class="err">' + e.message + '</span>';
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
        elif self.path == "/admin/growth-settings":
            self._json(self._get_growth_settings())
        elif self.path.startswith("/api/proxy"):
            self._proxy("GET")
        else:
            self._json({"error": "not found"})

    def do_POST(self):
        if self.path == "/admin/secrets":
            self._json(self._save_secrets())
        elif self.path == "/admin/upstreams":
            self._json(self._save_upstreams())
        elif self.path == "/admin/fetch-models":
            self._json(self._fetch_models())
        elif self.path == "/admin/restart-proxy":
            self._json(self._restart_proxy())
        elif self.path == "/admin/growth-settings":
            self._json(self._save_growth_settings())
        elif self.path == "/admin/update":
            self._json(self._run_update())
        elif self.path.startswith("/api/proxy"):
            self._proxy("POST")
        else:
            self._json({"error": "not found"})

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
                for item in socket.getaddrinfo(hostname, None, socket.AF_INET):
                    ip_cand = item[4][0]
                    if ip_cand and not ip_cand.startswith("127.") and ip_cand not in addrs["local"]:
                        addrs["local"].append(ip_cand)
            except Exception:
                try:
                    ip = socket.gethostbyname(hostname)
                    if ip and not ip.startswith("127.") and ip not in addrs["local"]:
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
        base_url = (body.get("base_url") or "").strip().rstrip("/")
        if base_url.endswith("/v1"):
            base_url = base_url[:-3].rstrip("/")
        data = {
            "api_key": (body.get("api_key") or "").strip(),
            "base_url": base_url,
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
            chars_root = SECRETS_HOME / "characters"
            if chars_root.exists():
                for char_dir in chars_root.iterdir():
                    if not char_dir.is_dir():
                        continue
                    for name in ("journal.db", "memory.db"):
                        src = char_dir / name
                        if not src.exists():
                            continue
                        dst = snap_dir / char_dir.name
                        dst.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src, dst / name)
                        copied.append(f"{char_dir.name}/{name}")
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
            if sys.platform != "win32":
                for proc_name in ["loam.__main__", "forced_flow_proxy", "scripts/admin.py", "scripts/dashboard.py"]:
                    try:
                        subprocess.run(["pkill", "-f", proc_name], timeout=5)
                        restart.append(proc_name)
                    except Exception:
                        pass
            try:
                subprocess.Popen([sys.executable, "-m", "loam", "run", "--grow-interval", "60"],
                                cwd=repo_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                restart.append("loam-restarted")
            except Exception:
                pass
            try:
                subprocess.Popen([sys.executable, "bridge/forced_flow_proxy.py"],
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

    def _get_growth_settings(self):
        res = api("/growth-settings", "GET")
        if isinstance(res, dict) and "batch_turns" in res:
            return res
        local_cfg = read_json_file(SECRETS_HOME / "growth_settings.json")
        return {
            "batch_turns": int(local_cfg.get("batch_turns", 20)) if isinstance(local_cfg, dict) else 20,
            "idle_seconds": float(local_cfg.get("idle_seconds", 900)) if isinstance(local_cfg, dict) else 900,
            "grow_interval": float(local_cfg.get("grow_interval", 60)) if isinstance(local_cfg, dict) else 60,
        }

    def _save_growth_settings(self):
        body = self._read_body()
        batch = max(1, min(200, int(body.get("batch_turns") or 20)))
        idle = max(10, min(86400, int(body.get("idle_seconds") or 900)))
        interval = max(5, min(3600, int(body.get("grow_interval") or 60)))
        payload = {"batch_turns": batch, "idle_seconds": idle, "grow_interval": interval}
        write_json_file(SECRETS_HOME / "growth_settings.json", payload)
        res = api("/growth-settings", "POST", payload)
        if isinstance(res, dict) and res.get("ok"):
            return res
        return {"ok": True, **payload}

    def _restart_proxy(self):
        """forced_flow_proxy.py auto-reloads upstreams.json on mtime change.
        Avoid killing the child process when managed by start.py, which would
        bring down the entire stack.
        """
        if not UPSTREAMS_FILE.exists():
            write_json_file(UPSTREAMS_FILE, {"default":"relayA","providers":{"relayA":{"base_url":"","api_key":"","default_model":""}}})
        else:
            os.utime(UPSTREAMS_FILE, None)
        return {"ok": True, "message": "upstreams hot-reloaded"}

    def _fetch_models(self):
        """Proxy a /v1/models call to a provider. Body: {base_url, api_key}."""
        body = self._read_body()
        url = (body.get("base_url") or "").strip()
        key = (body.get("api_key") or "").strip()
        if not url or not key:
            return {"error": "base_url and api_key are required"}
        url = url.rstrip("/")
        models_url = f"{url}/models" if url.endswith("/v1") else f"{url}/v1/models"
        try:
            req = urllib.request.Request(models_url)
            req.add_header("Authorization", f"Bearer {key}")
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=15) as r:
                raw = r.read().decode("utf-8")
                data = json.loads(raw) if raw else {}
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
        char_hdr = self.headers.get("X-Loam-Character") or self.headers.get("x-loam-character")
        result = api(path, method, body, character=char_hdr)
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
    print(f"loam admin panel (internal) → http://{ADMIN_HOST}:{PORT}")
    print(f"loam backend → {LOAM}")
    srv = ThreadingHTTPServer((ADMIN_HOST, PORT), Handler)
    srv.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()