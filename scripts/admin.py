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



def api(path, method="GET", body=None):
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
  --bg: #070b14;
  --bg-subtle: rgba(15, 23, 42, 0.75);
  --bg-card: rgba(17, 25, 44, 0.72);
  --bg-card-hover: rgba(24, 35, 60, 0.88);
  --bg-card-solid: #0f172a;
  --surface: #0f172a;
  --border: rgba(148, 163, 184, 0.14);
  --border-hover: rgba(96, 165, 250, 0.4);
  --border-strong: rgba(96, 165, 250, 0.55);
  --fg: #f1f5f9;
  --text: #f1f5f9;
  --text-color: #f1f5f9;
  --fg-dim: #94a3b8;
  --muted: #64748b;
  --accent: #60a5fa;
  --accent-rgb: 96, 165, 250;
  --accent-grad: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 55%, #ec4899 100%);
  --accent-soft: rgba(96, 165, 250, 0.12);
  --accent-2: #c084fc;
  --warn: #f59e0b;
  --err: #f43f5e;
  --ok: #10b981;
  --input-bg: rgba(9, 14, 26, 0.75);
  --radius-sm: 10px;
  --radius: 16px;
  --radius-lg: 22px;
  --shadow-sm: 0 2px 10px rgba(0, 0, 0, 0.25);
  --shadow: 0 10px 30px -8px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.05);
  --shadow-lg: 0 20px 45px -12px rgba(0, 0, 0, 0.68), 0 0 28px rgba(96, 165, 250, 0.12);
  --glass: blur(20px) saturate(1.4);
  --sidebar-width: 260px;
  --sidebar-collapsed-width: 74px;
  --glow:
    radial-gradient(900px 480px at 8% -5%, rgba(59, 130, 246, 0.16), transparent 60%),
    radial-gradient(850px 480px at 92% 4%, rgba(168, 85, 247, 0.13), transparent 58%),
    radial-gradient(750px 550px at 50% 108%, rgba(16, 185, 129, 0.08), transparent 60%);
}

.light {
  --bg: #f1f5f9;
  --bg-subtle: rgba(241, 245, 249, 0.9);
  --bg-card: rgba(255, 255, 255, 0.88);
  --bg-card-hover: rgba(255, 255, 255, 0.98);
  --bg-card-solid: #ffffff;
  --surface: #ffffff;
  --border: rgba(148, 163, 184, 0.24);
  --border-hover: rgba(37, 99, 235, 0.4);
  --border-strong: rgba(37, 99, 235, 0.55);
  --fg: #0f172a;
  --text: #0f172a;
  --text-color: #0f172a;
  --fg-dim: #475569;
  --muted: #64748b;
  --accent: #2563eb;
  --accent-rgb: 37, 99, 235;
  --accent-grad: linear-gradient(135deg, #2563eb 0%, #7c3aed 60%, #db2777 100%);
  --accent-soft: rgba(37, 99, 235, 0.1);
  --accent-2: #7c3aed;
  --warn: #d97706;
  --err: #e11d48;
  --ok: #059669;
  --input-bg: #f8fafc;
  --shadow-sm: 0 2px 8px rgba(15, 23, 42, 0.05);
  --shadow: 0 10px 28px -8px rgba(15, 23, 42, 0.08), inset 0 1px 0 rgba(255, 255, 255, 0.8);
  --shadow-lg: 0 18px 38px -10px rgba(15, 23, 42, 0.13);
  --glow:
    radial-gradient(900px 480px at 8% -5%, rgba(37, 99, 235, 0.08), transparent 60%),
    radial-gradient(850px 480px at 92% 4%, rgba(124, 58, 237, 0.06), transparent 58%),
    radial-gradient(750px 550px at 50% 108%, rgba(5, 150, 105, 0.05), transparent 60%);
}

* { margin: 0; padding: 0; box-sizing: border-box; }
::selection { background: rgba(var(--accent-rgb), 0.28); }
html { scroll-behavior: smooth; }

body {
  font: 13.5px/1.65 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
  background-color: var(--bg);
  color: var(--fg);
  display: flex;
  flex-direction: row;
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

/* ---- Typography & Helpers ---- */
h1 {
  font-size: 24px;
  font-weight: 800;
  letter-spacing: -0.025em;
  margin-bottom: 6px;
  color: var(--fg);
  display: flex;
  align-items: center;
  gap: 10px;
}

h2 {
  font-size: 16px;
  font-weight: 700;
  margin: 18px 0 12px;
  color: var(--fg);
}

h3 {
  font-size: 14.5px;
  font-weight: 700;
  margin-bottom: 12px;
  color: var(--fg);
  display: flex;
  align-items: center;
  gap: 8px;
}

.sub {
  font-size: 13px;
  color: var(--fg-dim);
  margin-bottom: 20px;
  line-height: 1.5;
}

.muted { color: var(--muted); }
.ok { color: var(--ok) !important; font-weight: 600; }
.err { color: var(--err) !important; font-weight: 600; }
.warn { color: var(--warn) !important; font-weight: 600; }

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
  color: #ffffff;
  background: var(--accent-grad);
  font-weight: 650;
  border-color: rgba(255, 255, 255, 0.18);
  box-shadow: 0 6px 18px -4px rgba(var(--accent-rgb), 0.45);
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

/* ---- Mobile Responsive ---- */
.mobile-header {
  display: none;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  background: var(--bg-card-solid);
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  z-index: 90;
}
.nav-toggle-btn {
  background: transparent;
  border: none;
  color: var(--fg);
  cursor: pointer;
  padding: 4px;
}
.sidebar-overlay {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  backdrop-filter: blur(4px);
  z-index: 95;
  opacity: 0;
  transition: opacity 0.25s ease;
}

@media (max-width: 900px) {
  .connect-form-row, .upstream-row {
    grid-template-columns: 1fr !important;
  }
  .const-row {
    grid-template-columns: 1fr 100px;
  }
  .const-val, .const-desc {
    grid-column: 1 / -1;
  }
}

@media (max-width: 768px) {
  .mobile-header { display: flex; }
  body { flex-direction: column; }
  nav {
    position: fixed;
    top: 0;
    left: 0;
    height: 100vh;
    transform: translateX(-100%);
    box-shadow: 6px 0 30px rgba(0, 0, 0, 0.45);
  }
  nav.mobile-open { transform: translateX(0); }
  .sidebar-overlay.active { display: block; opacity: 1; }
  .desktop-only { display: none !important; }
  main { padding: 20px 16px 48px; }
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
      <span class="version-badge">v0.8.0</span>
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
      <a href="#" onclick="showPanel('selfhood')" id="nav-selfhood">🌱 自性体系</a>
      <a href="#" onclick="showPanel('memory')" id="nav-memory">🧠 记忆总线</a>
      <a href="#" onclick="showPanel('config')" id="nav-config">⚙️ 系统配置</a>
      <a href="#" onclick="showPanel('constants')" id="nav-constants">🧊 常数环境</a>
      <a href="#" onclick="showPanel('traits')" id="nav-traits">🧬 特质快照</a>
      <a href="#" onclick="showPanel('connect')" id="nav-connections">🔌 外部连接</a>
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
    <h1>✨ 运行状态总览 (Runtime Status)</h1>
    <div class="sub" id="status-time">loading...</div>
    <div class="grid" id="status-grid"></div>
    <div class="card"><h3>🧬 核心性格特质 (Active Traits)</h3><div id="status-traits"></div></div>
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

  <!-- PERSONA -->
  <div id="panel-persona" class="panel">
    <h1>🎭 性格预设与宏观气质 (Persona & Macro Knobs)</h1>
    <div class="sub">将底层 48 个物理动力学参数抽象为 5 维直观气质大旋钮与 4 套经典预设卡（底层微调请前往 <a href="#" onclick="showPanel('constants');return false;" style="color:var(--accent);text-decoration:underline">🧊 常数环境</a>）</div>
    
    <div class="card" style="margin-bottom:16px;">
      <h3>⚡ 快捷性格预设卡 (One-Click Presets)</h3>
      <div id="persona-presets" style="display:grid;grid-template-columns:repeat(auto-fit, minmax(190px, 1fr));gap:12px;margin-top:12px;">
        <!-- 预设卡按钮由 JS 动态生成 -->
      </div>
      <div id="current-preset-badge" style="margin-top:12px;font-size:13px;color:var(--muted);display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
        <span>当前状态：<span id="active-preset-name" style="font-weight:600;color:var(--accent)">自定义参数</span></span>
        <button class="btn btn-sm btn-outline" onclick="showPanel('constants')">🔬 查看受控的底层物理常数</button>
      </div>
    </div>

    <div class="card" style="margin-bottom:16px;">
      <h3>🎛️ 五维气质宏观大旋钮 (Macro Knobs)</h3>
      <div id="persona-knobs-list" style="margin-top:12px;display:flex;flex-direction:column;gap:14px;">
        <!-- 旋钮滑块由 JS 动态生成 -->
      </div>
      <div style="display:flex;gap:10px;margin-top:20px;">
        <button class="btn btn-ok" onclick="savePersonaKnobs()">💾 保存并应用参数</button>
        <button class="btn btn-outline" onclick="resetPersona()">🔄 重置为默认平衡态</button>
      </div>
    </div>

    <div class="card">
      <h3>🌊 当下心境共振与独处自省 (Resonance & Daydream)</h3>
      <div id="persona-resonance-box" style="margin-top:10px;">
        <!-- 心境与情绪共振状态 -->
      </div>
      <div style="display:flex;gap:10px;margin-top:16px;">
        <button class="btn btn-sm btn-outline" onclick="triggerProactiveThought()">💭 触发一次独处心理反思</button>
        <button class="btn btn-sm" onclick="loadPersona()">🔄 刷新心境态</button>
      </div>
    </div>
  </div>

  <!-- SELFHOOD -->
  <div id="panel-selfhood" class="panel">
    <h1>🌱 自性体系 (Selfhood Genesis)</h1>
    <div class="sub">监控角色的内心执念 (Zeigarnik Effect)、潜意识梦境 (Dream Replay) 与他者之镜 (Theory of Mind)。</div>
    <div class="actions">
      <button class="btn btn-sm btn-outline" onclick="loadSelfhood()">🔄 刷新自性状态</button>
      <button class="btn btn-sm" onclick="triggerDream()">💭 触发梦境重构</button>
    </div>
    
    <div class="grid" style="grid-template-columns: 1fr 1fr; gap: 16px;">
      <!-- Drives -->
      <div class="card">
        <h3>🌀 内心执念 (Latent Drives)</h3>
        <div class="sub">随时间发酵的蔡加尼克心理张力。</div>
        <div id="selfhood-drives-list" style="margin-top:12px; display:flex; flex-direction:column; gap:12px;">
          <!-- JS 注入 -->
        </div>
      </div>

      <!-- Mirror & Dream -->
      <div style="display:flex; flex-direction:column; gap:16px;">
        <div class="card">
          <h3>👥 他者之镜 (Mirror of Other)</h3>
          <div class="sub">角色对当前交谈对象的心智揣摩。</div>
          <div id="selfhood-mirror-box" style="margin-top:12px;">
            <!-- JS 注入 -->
          </div>
        </div>

        <div class="card">
          <h3>🌙 潜意识梦境 (Recent Dreams)</h3>
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
    <h1>🧬 特质演化快照 (Trait Plasticity)</h1>
    <div class="sub">实时追踪角色每一条性格特质的沉淀强度、所处生命周期阶段、证据累积量与内核固化状态</div>
    <div class="actions">
      <button class="btn btn-sm" onclick="loadTraits()">🔄 Refresh</button>
    </div>
    <div class="card" id="traits-table"></div>
  </div>

  <!-- MEMORY -->
  <div id="panel-memory" class="panel">
    <h1>🧠 记忆总线与赫布拓扑 (Memory & Neural Graph)</h1>
    <div class="sub">查看情景记忆流、角色自我叙述、特质质变账本，以及动态生长的赫布神经网络拓扑图</div>
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
    <h1>⚙️ 系统运行配置 (Runtime Config)</h1>
    <div class="sub">查看或热更新上下文检索预算、衰减半衰期与流水线并发参数（支持版本化回滚）</div>
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
        <textarea id="config-updates" placeholder='{"context.max_matches": 12}'></textarea>
      </div>
      <button class="btn" onclick="updateConfig()">Apply</button>
    </div>
  </div>

  <!-- CONSTANTS -->
  <div id="panel-constants" class="panel">
    <h1>🧊 底层物理常数环境 (48 Dynamical Constants)</h1>
    <div class="sub">直接检视与微调 Loam 引擎的 48 项底层生物物理动力学常数（半衰期、赫布学习率、情绪惯性、防备阈值等）并持久化落盘</div>

    <div class="banner banner-info" style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;margin-bottom:16px">
      <div>
        💡 <strong>分工说明：</strong>此处为<strong>底层 48 项物理常数专家微调表</strong>。如需使用「4 套一键预设卡」或「5 维宏观气质大旋钮」，请前往性格卡片面板。
        <span id="const-override-summary" style="margin-left:8px;color:var(--accent);font-weight:600"></span>
      </div>
      <button class="btn btn-sm btn-outline" onclick="showPanel('persona')">🎭 前往性格卡片 (宏观调参)</button>
    </div>

    <div class="actions" style="margin-bottom:14px;justify-content:space-between;flex-wrap:wrap;gap:10px">
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
        <button class="btn btn-sm" onclick="loadConstants()">🔄 刷新常数</button>
        <button class="btn btn-sm btn-ok" onclick="applyConstants()">💾 保存并持久化覆盖</button>
        <button class="btn btn-sm btn-outline" onclick="clearConstants()">🗑 恢复全部默认值</button>
      </div>
      <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap">
        <label style="display:flex;align-items:center;gap:6px;font-size:12.5px;color:var(--muted);cursor:pointer;user-select:none">
          <input type="checkbox" id="const-only-overridden" onchange="filterConstantsRows()"> 仅看已覆盖项 (Overridden)
        </label>
        <input type="text" id="const-search-inp" placeholder="🔍 搜索常数名或描述..." oninput="filterConstantsRows()" style="width:220px;padding:6px 10px;font-size:12.5px">
      </div>
    </div>
    <div class="card" id="constants-list"></div>
  </div>

  <!-- CONNECT -->
  <div id="panel-connect" class="panel">
    <h1>🔌 外部模型与客户端连接 (API & Upstreams)</h1>
    <div class="sub">配置 API 密钥。loam 使用两套独立的模型：一套消化记忆，一套生成回复。</div>

    <!-- 顶部三卡片：告诉用户填到聊天客户端的三个值 -->
    <div class="grid" style="grid-template-columns:repeat(3, 1fr); margin-bottom:20px">
      <div class="card">
        <h3>🔗 填到聊天软件的 Base URL</h3>
        <div id="client-base-url" style="font-family:monospace;font-size:14px;text-align:center;padding:6px;background:var(--bg);border-radius:4px">http://127.0.0.1:8783/v1</div>
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
        <button class="btn btn-sm btn-outline btn-fetch" style="height:38px;align-self:end" onclick="fetchModels('sec')" title="从提供商拉取可用模型列表">拉取</button>
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
        <div id="backup_export-result" style="margin-top:8px;font-size:12px"></div>
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

    const presetIcons = { aloof: '🧊', gentle: '🌸', cheerful: '🐶', fragile: '🥀' };
    let presetsHtml = '';
    for (const [key, p] of Object.entries(presets)) {
      const isCur = (key === curPreset);
      const activeClass = isCur ? 'btn-ok' : 'btn-outline';
      const icon = presetIcons[key] || '🎭';
      presetsHtml += `
        <div style="padding:14px;border:1px solid ${isCur ? 'var(--accent)' : 'var(--border)'};border-radius:10px;background:${isCur ? 'rgba(99,102,241,0.08)' : 'var(--bg-subtle)'};transition:all 0.2s">
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
            <span style="font-size:22px">${icon}</span>
            <span style="font-weight:600;font-size:14px;">${esc(p.name)}</span>
          </div>
          <div style="font-size:12px;color:var(--muted);min-height:36px;margin-bottom:12px;line-height:1.45;">${esc(p.desc)}</div>
          <button class="btn btn-sm ${activeClass}" style="width:100%" onclick="applyPersonaPreset('${key}')">${isCur ? '✅ 当前已激活' : '⚡ 一键应用此卡片'}</button>
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
        <div style="font-size:12px;color:var(--muted);margin-bottom:2px;">🎭 当下情绪态 / 主导心境</div>
        <div style="font-size:14px;font-weight:600;color:var(--text);">${esc(moodDesc)}</div>
        ${elemBarsHtml}
      </div>
      <div style="padding:10px 14px;background:var(--bg-subtle);border-radius:6px;border:1px solid var(--border)">
        <div style="font-size:12px;color:var(--muted);margin-bottom:2px;">💭 独处时的自省与惦记 (Daydreaming Thought)</div>
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
  const grid = document.getElementById('status-grid');
  grid.innerHTML = `
    <div class="card"><h3>🎭 角色与引擎状态</h3>
      <div class="stat"><span>当前角色 (Character)</span><span class="val" style="color:var(--accent)">${esc(stats.character||'-')}</span></div>
      <div class="stat"><span>演化周期 (Cycle)</span><span class="val">#${mem['周期']||0}</span></div>
      <div class="stat"><span>后台生长器 (Grower)</span><span class="val ${(stats.grower_alive?'ok':'err')}">${stats.grower_alive?'● 运行中':'● 已暂停'}</span></div>
      <div class="stat"><span>待消化对话 (Pending)</span><span class="val">${stats.pending||0} 条</span></div>
    </div>
    <div class="card"><h3>🧠 记忆与神经沉淀</h3>
      <div class="stat"><span>情景记忆节点 (Events)</span><span class="val">${mem['事件']||0}</span></div>
      <div class="stat"><span>性格特质总数 (Traits)</span><span class="val">${mem['特质']||0}</span></div>
      <div class="stat"><span>已固化内核 (Kernel)</span><span class="val ok">${mem['内核']||0}</span></div>
      <div class="stat"><span>赫布突触连线 (Edges)</span><span class="val">${mem['连线']||0}</span></div>
    </div>
    <div class="card"><h3>🌱 自性与系统健康</h3>
      <div class="stat"><span>活跃执念 (Active Drives)</span><span class="val warn">${stats.active_drives||0}</span></div>
      <div class="stat"><span>自我叙述版本 (Narratives)</span><span class="val">${mem['自述版本']||0}</span></div>
      <div class="stat"><span>演化账本记录 (Changelog)</span><span class="val">${mem['变更记录']||0}</span></div>
      <div class="stat"><span>服务健康探针 (Health)</span><span class="val ${(healthz.ok?'ok':'err')}">${healthz.ok?'✓ 正常':'✗ 异常'}</span></div>
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
    : '<div class="muted" style="padding:16px;text-align:center">🌱 尚未长出显著性格特质。去「🎮 演示大厅」试玩，或通过客户端与角色多聊几句吧！</div>';
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

// ---- CONSTANTS (48 Physical & Dynamical Parameters) ----
async function loadConstants() {
  const data = await callAdmin('GET', '/admin/constants');  // direct from admin, no loam needed
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
      <span class="const-desc" title="${escAttr(desc)}">${isOverridden?`⚡ 已覆盖 · ${esc(desc)}`:esc(desc)}</span>
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
      <button class="btn btn-sm btn-danger" style="height:38px;align-self:end" onclick="removeUpstreamRow('${escAttr(name)}')">✕</button>
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
  if (r.ok) { el.innerHTML = '<span class="ok">✓ 已保存</span>'; toast('记忆生长模型配置已保存', 'ok'); }
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
    el.innerHTML = '<span class="ok">✓ 已保存并热加载生效！</span>';
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
      if (statusEl) statusEl.innerHTML = `<span class="ok">✓ 已加载 ${r.models.length} 个模型，请选择后点击保存</span>`;
    } else {
      toast('拉取失败：' + (r.error||'未返回模型'), 'err');
      if (statusEl) statusEl.innerHTML = `<span class="err">✗ ${esc(r.error||'未返回模型')}</span>`;
    }
  } catch(e) {
    toast('拉取出错：' + e.message, 'err');
    if (statusEl) statusEl.innerHTML = `<span class="err">✗ ${esc(e.message)}</span>`;
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
      statusEl.innerHTML = '<span class="ok">✅ 已保存并立即生效！</span>';
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