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
:root{
  --bg:#0b0e14;--bg-2:#121826;--fg:#dbe3f0;--accent:#7aa2ff;--accent-2:#c792ea;
  --warn:#e0a458;--err:#ff6b6b;--ok:#4ade80;--card:rgba(22,28,42,0.72);--card-solid:#161c2a;
  --border:rgba(122,162,255,0.14);--border-strong:rgba(122,162,255,0.28);--muted:#7f8ba3;
  --input-bg:rgba(11,14,20,0.6);
  --glow:radial-gradient(1200px 600px at 12% -10%,rgba(122,162,255,0.16),transparent 60%),radial-gradient(900px 500px at 100% 0%,rgba(199,146,234,0.13),transparent 55%),radial-gradient(700px 700px at 50% 120%,rgba(74,222,128,0.07),transparent 60%);
  --shadow:0 1px 2px rgba(0,0,0,0.3),0 8px 24px -12px rgba(0,0,0,0.6);
  --shadow-lg:0 2px 4px rgba(0,0,0,0.3),0 24px 48px -20px rgba(0,0,0,0.7);
  --radius:14px;
}
.light{
  --bg:#f4f1ea;--bg-2:#fffdf8;--fg:#26303d;--accent:#3563d6;--accent-2:#8b5cd6;
  --warn:#a86a1a;--err:#c33a3a;--ok:#1f8a4c;--card:rgba(255,255,255,0.78);--card-solid:#ffffff;
  --border:rgba(38,48,61,0.12);--border-strong:rgba(38,48,61,0.22);--muted:#6b7686;
  --input-bg:rgba(255,255,255,0.9);
  --glow:radial-gradient(1100px 560px at 10% -12%,rgba(53,99,214,0.10),transparent 60%),radial-gradient(900px 520px at 100% 0%,rgba(139,92,214,0.09),transparent 55%),radial-gradient(700px 700px at 50% 120%,rgba(31,138,76,0.05),transparent 60%);
  --shadow:0 1px 2px rgba(38,48,61,0.06),0 8px 24px -14px rgba(38,48,61,0.22);
  --shadow-lg:0 2px 6px rgba(38,48,61,0.08),0 24px 48px -22px rgba(38,48,61,0.3);
}
*{margin:0;padding:0;box-sizing:border-box}
::selection{background:rgba(122,162,255,0.28)}
html{-webkit-text-size-adjust:100%}
body{
  font:13.5px/1.65 "Inter",-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Noto Sans SC",sans-serif;
  background:var(--bg);color:var(--fg);display:flex;min-height:100vh;
  letter-spacing:0.01em;-webkit-font-smoothing:antialiased;position:relative;
}
body::before{
  content:"";position:fixed;inset:0;background-image:var(--glow);pointer-events:none;z-index:0;
}
body::after{
  content:"";position:fixed;inset:0;pointer-events:none;z-index:0;opacity:0.035;
  background-image:radial-gradient(currentColor 0.5px,transparent 0.5px);background-size:3px 3px;
}
nav,main{position:relative;z-index:1}

/* ─────────── nav ─────────── */
nav{
  width:232px;flex-shrink:0;padding:20px 0 24px;z-index:10;
  background:linear-gradient(180deg,rgba(18,24,38,0.92),rgba(11,14,20,0.86));
  border-right:1px solid var(--border);backdrop-filter:blur(14px) saturate(1.2);
  -webkit-backdrop-filter:blur(14px) saturate(1.2);
}
.light nav{background:linear-gradient(180deg,rgba(255,253,248,0.94),rgba(244,241,234,0.88))}
nav .logo{
  font-size:15px;font-weight:700;padding:0 18px 16px;margin-bottom:12px;
  border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center;
  letter-spacing:0.02em;
  background:linear-gradient(100deg,var(--accent),var(--accent-2));
  -webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;
}
nav .logo .theme-btn{
  background:var(--card-solid);border:1px solid var(--border-strong);color:var(--fg);
  border-radius:9px;padding:3px 8px;cursor:pointer;font-size:12px;line-height:1.2;
  -webkit-text-fill-color:initial;transition:transform .18s cubic-bezier(.34,1.56,.64,1),box-shadow .18s;
}
nav .logo .theme-btn:hover{transform:translateY(-1px) rotate(-12deg);box-shadow:var(--shadow)}
nav a{
  display:block;padding:9px 18px;color:var(--muted);text-decoration:none;font-size:13px;
  position:relative;transition:color .18s,background .18s,padding-left .18s;border-radius:0 10px 10px 0;
}
nav a::before{
  content:"";position:absolute;left:0;top:50%;transform:translateY(-50%);
  width:2px;height:0;border-radius:0 2px 2px 0;
  background:linear-gradient(180deg,var(--accent),var(--accent-2));transition:height .22s ease;
}
nav a:hover{color:var(--fg);background:linear-gradient(90deg,var(--border),transparent)}
nav a:hover::before{height:40%}
nav a.active{
  color:var(--fg);font-weight:600;
  background:linear-gradient(90deg,rgba(122,162,255,0.14),transparent);
}
nav a.active::before{height:62%}

/* ─────────── layout / type ─────────── */
main{flex:1;padding:30px 32px 48px;overflow-y:auto;max-height:100vh;scroll-behavior:smooth}
main::-webkit-scrollbar,.narrative::-webkit-scrollbar,.timeline::-webkit-scrollbar,pre::-webkit-scrollbar,textarea::-webkit-scrollbar{width:9px;height:9px}
main::-webkit-scrollbar-thumb,.narrative::-webkit-scrollbar-thumb,.timeline::-webkit-scrollbar-thumb,pre::-webkit-scrollbar-thumb,textarea::-webkit-scrollbar-thumb{background:var(--border-strong);border-radius:9px}
main::-webkit-scrollbar-track{background:transparent}
h1{
  font-size:25px;line-height:1.25;margin-bottom:6px;font-weight:700;letter-spacing:-0.015em;
  background:linear-gradient(96deg,var(--fg) 20%,var(--accent) 120%);
  -webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;
}
h2{
  font-size:15px;margin:26px 0 12px;color:var(--fg);font-weight:650;letter-spacing:0.01em;
  display:flex;align-items:center;gap:10px;
}
h2::after{content:"";flex:1;height:1px;background:linear-gradient(90deg,var(--border-strong),transparent)}
.sub{color:var(--muted);font-size:12.5px;margin-bottom:24px;max-width:70ch}

/* ─────────── cards ─────────── */
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(268px,1fr));gap:14px;margin-bottom:18px}
.card{
  background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:16px 17px;
  backdrop-filter:blur(12px) saturate(1.15);-webkit-backdrop-filter:blur(12px) saturate(1.15);
  box-shadow:var(--shadow);position:relative;overflow:hidden;
  transition:transform .22s cubic-bezier(.22,.61,.36,1),box-shadow .22s,border-color .22s;
  animation:rise .42s cubic-bezier(.22,.61,.36,1) both;
}
.card::before{
  content:"";position:absolute;top:0;left:0;right:0;height:1px;
  background:linear-gradient(90deg,transparent,var(--border-strong) 30%,var(--border-strong) 70%,transparent);
}
.card:hover{transform:translateY(-2px);box-shadow:var(--shadow-lg);border-color:var(--border-strong)}
.card h3{
  font-size:11px;color:var(--muted);margin-bottom:10px;text-transform:uppercase;
  letter-spacing:0.09em;font-weight:700;
}
.stat{
  display:flex;justify-content:space-between;gap:10px;padding:6px 0;
  border-bottom:1px dashed var(--border);font-size:13px;
}
.stat:last-child{border-bottom:none}
.val{font-weight:650;font-variant-numeric:tabular-nums;letter-spacing:-0.01em}
.ok{color:var(--ok)}.warn{color:var(--warn)}.err{color:var(--err)}.muted{color:var(--muted)}
pre,code{font-family:"JetBrains Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
pre{
  background:var(--input-bg);border:1px solid var(--border);border-radius:10px;padding:12px 14px;
  line-height:1.6;white-space:pre-wrap;word-break:break-word;
}
code{background:var(--input-bg);border:1px solid var(--border);border-radius:5px;padding:1px 5px;font-size:0.92em}

/* ─────────── buttons ─────────── */
.btn{
  background:linear-gradient(140deg,var(--accent),var(--accent-2));color:#fff;border:none;
  padding:7px 16px;border-radius:10px;cursor:pointer;font-size:13px;font-weight:600;
  font-family:inherit;letter-spacing:0.015em;white-space:nowrap;position:relative;overflow:hidden;
  box-shadow:0 1px 2px rgba(0,0,0,0.2),0 6px 16px -10px var(--accent);
  transition:transform .16s cubic-bezier(.34,1.4,.64,1),box-shadow .18s,filter .18s;
}
.btn::after{
  content:"";position:absolute;inset:0;background:linear-gradient(180deg,rgba(255,255,255,0.18),transparent 55%);
  pointer-events:none;
}
.btn:hover{transform:translateY(-1px);filter:saturate(1.15) brightness(1.06);box-shadow:0 2px 4px rgba(0,0,0,0.22),0 12px 22px -12px var(--accent)}
.btn:active{transform:translateY(0) scale(0.985)}
.btn:disabled{opacity:0.45;cursor:not-allowed;transform:none;filter:grayscale(0.4);box-shadow:none}
.btn-sm{font-size:11.5px;padding:5px 11px;border-radius:9px}
.btn-danger{background:linear-gradient(140deg,var(--err),#c0447a);box-shadow:0 1px 2px rgba(0,0,0,0.2),0 6px 16px -10px var(--err)}
.btn-danger:hover{box-shadow:0 2px 4px rgba(0,0,0,0.22),0 12px 22px -12px var(--err)}
.btn-ok{background:linear-gradient(140deg,var(--ok),#22a2a2);box-shadow:0 1px 2px rgba(0,0,0,0.2),0 6px 16px -10px var(--ok)}
.btn-ok:hover{box-shadow:0 2px 4px rgba(0,0,0,0.22),0 12px 22px -12px var(--ok)}
.btn-outline{background:transparent;border:1px solid var(--border-strong);color:var(--fg);box-shadow:none;font-weight:550}
.btn-outline::after{display:none}
.btn-outline:hover{background:var(--border);filter:none;box-shadow:var(--shadow)}
.actions{display:flex;gap:9px;flex-wrap:wrap;margin-bottom:18px;align-items:center}

/* ─────────── forms ─────────── */
input,textarea,select{
  background:var(--input-bg);color:var(--fg);border:1px solid var(--border);border-radius:10px;
  padding:9px 11px;font-size:13px;font-family:inherit;width:100%;
  transition:border-color .18s,box-shadow .18s,background .18s;
}
input:hover,textarea:hover,select:hover{border-color:var(--border-strong)}
input:focus,textarea:focus,select:focus{
  outline:none;border-color:var(--accent);
  box-shadow:0 0 0 3px rgba(122,162,255,0.16);
}
input::placeholder,textarea::placeholder{color:var(--muted);opacity:0.7}
textarea{resize:vertical;min-height:104px;font-family:"JetBrains Mono",ui-monospace,Menlo,monospace;font-size:12px;line-height:1.6}
label{display:block;font-size:11.5px;color:var(--muted);margin-bottom:5px;margin-top:11px;font-weight:550;letter-spacing:0.02em}
.form-group{margin-bottom:11px}

/* ─────────── toast / spinner ─────────── */
.toast{
  position:fixed;bottom:22px;right:22px;padding:11px 18px;border-radius:12px;font-size:13px;
  font-weight:600;z-index:999;animation:fadeIn .34s cubic-bezier(.22,.61,.36,1);
  box-shadow:var(--shadow-lg);backdrop-filter:blur(8px);
}
.toast.ok{background:linear-gradient(140deg,var(--ok),#22a2a2);color:#04180d}
.toast.err{background:linear-gradient(140deg,var(--err),#c0447a);color:#fff}
@keyframes fadeIn{from{opacity:0;transform:translateY(12px) scale(0.97)}to{opacity:1;transform:translateY(0) scale(1)}}
@keyframes rise{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
@keyframes spin{to{transform:rotate(360deg)}}
@keyframes shimmer{0%{background-position:-180% 0}100%{background-position:180% 0}}
.spinner{
  display:inline-block;width:14px;height:14px;border:2px solid var(--border-strong);
  border-top-color:var(--accent);border-radius:50%;animation:spin .62s linear infinite;
  margin-right:7px;vertical-align:middle;
}
.btn-fetching{
  background:var(--border)!important;color:var(--muted)!important;box-shadow:none!important;
  background-image:linear-gradient(90deg,transparent,var(--border-strong),transparent)!important;
  background-size:180% 100%!important;animation:shimmer 1.1s linear infinite;
}

/* ─────────── bars / traits ─────────── */
.bar{height:7px;border-radius:99px;background:var(--border);margin:9px 0;overflow:hidden}
.bar-fill{height:100%;border-radius:99px;transition:width .6s cubic-bezier(.22,.61,.36,1)}
.bar-fill.ok{background:linear-gradient(90deg,var(--ok),#22c2a0)}
.bar-fill.warn{background:linear-gradient(90deg,var(--warn),#e0c458)}
.bar-fill.err{background:linear-gradient(90deg,var(--err),#e0538a)}
.trait{display:flex;align-items:center;gap:10px;padding:5px 0;border-radius:8px;transition:background .18s}
.trait:hover{background:var(--border)}
.trait-name{flex:1;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:200px;font-weight:550}
.trait-bar{flex:2;height:8px;background:var(--border);border-radius:99px;overflow:hidden}
.trait-fill{
  height:100%;border-radius:99px;transition:width .6s cubic-bezier(.22,.61,.36,1);
  background:linear-gradient(90deg,var(--accent),var(--accent-2));
  box-shadow:0 0 10px -2px var(--accent);
}
.trait-val{font-size:11px;color:var(--muted);width:38px;text-align:right;font-variant-numeric:tabular-nums}
.trait-phase{font-size:10px;color:var(--muted);width:52px;text-align:right;letter-spacing:0.03em}

/* ─────────── events / timeline / changelog ─────────── */
.event{
  font-size:12.5px;padding:6px 0;border-bottom:1px dashed var(--border);display:flex;gap:9px;
  transition:background .18s;
}
.event:last-child{border-bottom:none}
.event-dot{
  width:8px;height:8px;border-radius:50%;margin-top:6px;flex-shrink:0;
  box-shadow:0 0 0 3px var(--border);
}
.narrative{
  font-size:13.5px;line-height:1.85;white-space:pre-wrap;max-height:300px;overflow-y:auto;
  padding-left:14px;border-left:2px solid var(--border-strong);
}
.timeline{max-height:400px;overflow-y:auto;padding-right:4px}
.changelog-entry{font-size:12.5px;padding:8px 0;border-bottom:1px dashed var(--border);line-height:1.6}
.changelog-entry:last-child{border-bottom:none}
.changelog-entry .ts{color:var(--muted);margin-right:9px;font-variant-numeric:tabular-nums;font-size:11.5px}

/* ─────────── constants ─────────── */
.const-row{
  display:grid;grid-template-columns:180px 80px 120px;gap:5px 10px;align-items:center;
  padding:7px 0;border-bottom:1px dashed var(--border);font-size:12.5px;transition:background .18s;
}
.const-row:last-child{border-bottom:none}
.const-name{font-weight:650;color:var(--accent);letter-spacing:0.01em}
.const-val{text-align:right;font-variant-numeric:tabular-nums;color:var(--muted)}
.const-desc{grid-column:1/-1;color:var(--muted);font-size:11px;line-height:1.55;padding:2px 0}
.const-input{width:80px;text-align:right;padding:4px 8px;border-radius:8px;font-size:12px}

/* ─────────── panels / banner / modal ─────────── */
.panel{display:none}
.panel.active{display:block;animation:rise .34s cubic-bezier(.22,.61,.36,1) both}
.banner{
  background:linear-gradient(100deg,rgba(224,164,88,0.14),rgba(224,164,88,0.05));
  border:1px solid rgba(224,164,88,0.4);border-radius:var(--radius);padding:12px 15px;
  margin-bottom:20px;font-size:12.5px;color:var(--warn);display:flex;align-items:center;gap:10px;
  box-shadow:var(--shadow);line-height:1.6;
}
.banner strong{color:#f0c878}
.light .banner strong{color:#8a5410}
.banner a{color:var(--accent);text-decoration:none;border-bottom:1px solid transparent;transition:border-color .18s}
.banner a:hover{border-bottom-color:var(--accent)}
.banner .banner-dismiss{
  background:none;border:none;color:var(--muted);cursor:pointer;font-size:18px;line-height:1;
  padding:0 4px;margin-left:auto;flex-shrink:0;border-radius:6px;transition:color .18s,transform .18s;
}
.banner .banner-dismiss:hover{color:var(--fg);transform:rotate(90deg)}
.modal-overlay{
  position:fixed;inset:0;background:rgba(4,6,12,0.62);display:flex;align-items:center;
  justify-content:center;z-index:9999;backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);
  animation:fadeIn .24s ease both;
}
.modal-box{
  background:var(--card-solid);border:1px solid var(--border-strong);border-radius:18px;
  padding:28px 26px;max-width:430px;width:90%;text-align:center;box-shadow:var(--shadow-lg);
  animation:rise .3s cubic-bezier(.22,.61,.36,1) both;
}
.modal-box h2{font-size:18px;margin:0 0 10px;display:block;font-weight:700}
.modal-box h2::after{display:none}
.modal-box p{color:var(--muted);font-size:13px;margin-bottom:18px;line-height:1.7}
.modal-box .modal-actions{display:flex;gap:10px;justify-content:center}

/* ─────────── upstream rows ─────────── */
.upstream-row{align-items:end}
.up-name-inp,.up-url-inp,.up-key-inp{font-size:12.5px}

/* ─────────── mobile ─────────── */
#menu-toggle{
  display:none;background:var(--card-solid);border:1px solid var(--border-strong);color:var(--fg);
  font-size:18px;cursor:pointer;padding:3px 9px;border-radius:9px;line-height:1.3;
}
@media(max-width:768px){
  body{flex-direction:column}
  nav{
    width:100%;padding:10px 12px;display:flex;flex-wrap:wrap;align-items:center;gap:5px;
    border-right:none;border-bottom:1px solid var(--border);position:sticky;top:0;z-index:100;
    box-shadow:0 6px 20px -14px rgba(0,0,0,0.7);
  }
  nav .logo{width:auto;flex:1;border:none;margin:0;padding:0;font-size:14px}
  nav a{font-size:11.5px;padding:6px 10px;border-radius:9px}
  nav a::before{display:none}
  nav a.active{background:linear-gradient(120deg,rgba(122,162,255,0.2),rgba(199,146,234,0.12))}
  #menu-toggle{display:block}
  nav .nav-links{display:none;width:100%;flex-direction:column;gap:2px;margin-top:6px}
  nav .nav-links.open{display:flex;animation:rise .26s ease both}
  main{padding:14px 12px 32px;max-height:none;overflow-x:hidden}
  h1{font-size:19px}
  h2{font-size:14px;margin:20px 0 10px}
  .sub{margin-bottom:16px}
  .grid{grid-template-columns:1fr!important}
  .card{padding:13px;border-radius:12px}
  .card h3{font-size:10.5px}
  .const-row{grid-template-columns:130px 55px 1fr;font-size:11.5px}
  .const-input{width:55px}
  /* Connect: form rows stack vertically */
  .connect-form-row{grid-template-columns:1fr!important}
  .upstream-row{grid-template-columns:1fr 1fr!important;gap:5px;font-size:11.5px}
  .upstream-row .form-group{margin-bottom:5px}
  .upstream-row label{font-size:10px}
  .btn{font-size:11.5px;padding:6px 11px}
  .btn-sm{font-size:10.5px;padding:4px 9px}
  .actions{gap:5px}
  .banner{font-size:11.5px;padding:10px 11px;border-radius:12px}
  .toast{left:14px;right:14px;bottom:14px;text-align:center}
}
@media(prefers-reduced-motion:reduce){
  *{animation-duration:.001s!important;transition-duration:.001s!important}
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

    <!-- 手动操作 -->
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
        <h3>📸 导出角色卡</h3>
        <p class="muted" style="font-size:12px;margin-bottom:8px">导出当前所有记忆和特质</p>
        <button class="btn" onclick="doAction('snapshot')">📦 导出</button>
        <div id="snapshot-result" style="margin-top:8px;font-size:12px"></div>
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