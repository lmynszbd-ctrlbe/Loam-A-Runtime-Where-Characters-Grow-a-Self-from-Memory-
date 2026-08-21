#!/usr/bin/env python3
"""loam dashboard — 单页 HTML 仪表盘，纯标准库，不依赖任何前端框架。

用法:
  python scripts/dashboard.py
  # 然后浏览器打开 http://127.0.0.1:8899
"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import urllib.request
import urllib.error
import os
import time

LOAM_URL = os.environ.get("LOAM_URL", "http://127.0.0.1:8765").rstrip("/")
DASH_PORT = int(os.environ.get("DASH_PORT", "8899"))


def _fetch(path: str) -> dict:
    try:
        with urllib.request.urlopen(f"{LOAM_URL}{path}", timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}


HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>loam · 仪表盘</title>
<style>
  :root{--bg:#0d1117;--fg:#c9d1d9;--accent:#58a6ff;--warn:#d29922;--err:#f85149;--ok:#3fb950;--card:#161b22;--border:#30363d;--muted:#8b949e}
  *{margin:0;padding:0;box-sizing:border-box}
  body{font:14px/1.6 -apple-system,BlinkMacSystemFont,sans-serif;background:var(--bg);color:var(--fg);padding:20px;max-width:960px;margin:auto}
  h1{color:var(--accent);font-size:22px;margin-bottom:4px}
  .sub{color:var(--muted);font-size:12px;margin-bottom:20px}
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px;margin-bottom:16px}
  .card{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:14px}
  .card h3{font-size:14px;color:var(--muted);margin-bottom:8px;text-transform:uppercase;letter-spacing:0.5px}
  .stat{display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid var(--border)}
  .stat:last-child{border-bottom:none}
  .val{font-weight:600;font-variant-numeric:tabular-nums}
  .ok{color:var(--ok)} .warn{color:var(--warn)} .err{color:var(--err)} .muted{color:var(--muted)}
  .bar{height:6px;border-radius:3px;background:var(--border);margin:8px 0;overflow:hidden}
  .bar-fill{height:100%;border-radius:3px;transition:width 0.5s}
  .bar-fill.ok{background:var(--ok)} .bar-fill.warn{background:var(--warn)} .bar-fill.err{background:var(--err)}
  .trait{display:flex;align-items:center;gap:8px;padding:3px 0}
  .trait-name{flex:1;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .trait-bar{flex:2;height:8px;background:var(--border);border-radius:4px;overflow:hidden}
  .trait-fill{height:100%;background:var(--accent);border-radius:4px;transition:width 0.5s}
  .trait-val{font-size:11px;color:var(--muted);width:36px;text-align:right}
  .event{font-size:12px;padding:3px 0;border-bottom:1px solid var(--border);display:flex;gap:6px}
  .event-dot{width:8px;height:8px;border-radius:50%;margin-top:4px;flex-shrink:0}
  button{background:var(--accent);color:#fff;border:none;padding:6px 14px;border-radius:6px;cursor:pointer;font-size:13px}
  button:hover{opacity:0.85}
  .refresh{display:flex;align-items:center;gap:8px;margin-bottom:16px}
  .error-box{background:var(--err);color:#fff;padding:10px;border-radius:6px;margin-bottom:12px}
  .narrative{font-size:13px;line-height:1.7;color:var(--fg);white-space:pre-wrap}
  .timeline{max-height:300px;overflow-y:auto}
</style>
</head>
<body>
<h1>🧠 loam</h1>
<div class="sub">人格生长仪表盘 · <span id="status">加载中...</span></div>
<div class="refresh">
  <button onclick="load()">刷新</button>
  <span class="muted" id="updated"></span>
</div>
<div id="errors"></div>

<div class="grid">
  <div class="card">
    <h3>📊 概览</h3>
    <div class="stat"><span>周期</span><span class="val" id="cycle">-</span></div>
    <div class="stat"><span>Grower</span><span class="val" id="grower">-</span></div>
    <div class="stat"><span>待处理</span><span class="val" id="pending">-</span></div>
    <div class="stat"><span>健康状态</span><span class="val" id="health">-</span></div>
  </div>

  <div class="card">
    <h3>📈 流水线</h3>
    <div class="stat"><span>ingest 请求</span><span class="val" id="ingest">-</span></div>
    <div class="stat"><span>digest 请求</span><span class="val" id="digest">-</span></div>
    <div class="stat"><span>队列完成</span><span class="val" id="jobs_done">-</span></div>
    <div class="stat"><span>队列失败</span><span class="val" id="jobs_fail">-</span></div>
  </div>

  <div class="card">
    <h3>🧬 特质</h3>
    <div id="traits" style="max-height:220px;overflow-y:auto">
      <span class="muted">加载中...</span>
    </div>
  </div>

  <div class="card">
    <h3>📝 自述</h3>
    <div class="narrative" id="narrative">
      <span class="muted">加载中...</span>
    </div>
  </div>
</div>

<div class="card" style="margin-bottom:16px">
  <h3>📅 最近事件</h3>
  <div class="timeline" id="events">
    <span class="muted">加载中...</span>
  </div>
</div>

<script>
async function load(){
  document.getElementById('updated').textContent = '加载中...';
  try{
    const [dash, ctx, mem] = await Promise.all([
      fetch('/api/dashboard').then(r=>r.json()),
      fetch('/api/context?q=status').then(r=>r.json()).catch(()=>null),
      fetch('/api/narrative').then(r=>r.json()).catch(()=>null)
    ]);

    // 概览
    const t = dash.tasks||{};
    document.getElementById('cycle').textContent = (t.digest||{}).cycle||'-';
    document.getElementById('grower').innerHTML = (t.grower||{}).alive ? '<span class="ok">● 运行中</span>' : '<span class="err">● 已停止</span>';
    document.getElementById('pending').textContent = (dash.backlog||{}).pending||0;
    const alerts = dash.alerts||{};
    const h = alerts.level==='info'?'ok':alerts.level==='warn'?'warn':'err';
    document.getElementById('health').innerHTML = `<span class="${h}">${alerts.level||'?'}</span>`;

    // 流水线
    const m = (dash.metrics||{}).growth||{};
    document.getElementById('ingest').textContent = m.ingest_requests||0;
    document.getElementById('digest').textContent = m.digest_requests||0;
    document.getElementById('jobs_done').textContent = m.queue_jobs_done||0;
    document.getElementById('jobs_fail').textContent = m.queue_jobs_failed||0;

    // 特质
    const traitsDiv = document.getElementById('traits');
    const traits = (ctx||{}).traits||[];
    if(traits.length){
      traitsDiv.innerHTML = traits.map(t=>{
        const s = (t.strength||0)*100;
        const c = s>80?'ok':s>50?'warn':'';
        return `<div class="trait"><span class="trait-name">${esc(t.text||'?')}</span>
          <div class="trait-bar"><div class="trait-fill" style="width:${s}%"></div></div>
          <span class="trait-val">${s.toFixed(0)}%</span></div>`;
      }).join('');
    }else{
      traitsDiv.innerHTML = '<span class="muted">还没有特质</span>';
    }

    // 自述
    const narr = (mem||{}).text||'';
    document.getElementById('narrative').textContent = narr || '还没有自述。多聊几轮就会长出来。';

    // 事件
    const eventsDiv = document.getElementById('events');
    const events = (ctx||{}).events||[];
    if(events.length){
      eventsDiv.innerHTML = events.slice(0,20).map(e=>{
        const v = (e.valence||0);
        const color = v>0.2?'#3fb950':v<-0.2?'#f85149':'#8b949e';
        return `<div class="event"><div class="event-dot" style="background:${color}"></div>
          <span>${esc(e.summary||'?')}</span></div>`;
      }).join('');
    }else{
      eventsDiv.innerHTML = '<span class="muted">还没有事件</span>';
    }

    document.getElementById('updated').textContent = new Date().toLocaleTimeString();
    document.getElementById('errors').innerHTML = '';
  }catch(e){
    document.getElementById('errors').innerHTML = `<div class="error-box">${esc(e.toString())}</div>`;
  }
}
function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}
load();
setInterval(load,30000);
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self._html(HTML)
        elif self.path == "/api/dashboard":
            self._json(_fetch("/dashboard"))
        elif self.path.startswith("/api/context"):
            q = self.path.split("?q=")[-1] if "?q=" in self.path else "status"
            import urllib.parse
            q = urllib.parse.unquote(q)
            self._json(_fetch(f"/context?query={q}"))
        elif self.path == "/api/narrative":
            self._json(_fetch("/narrative"))
        else:
            self._send(404, "not found")

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
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, *a): pass


def main():
    print(f"loam dashboard on http://127.0.0.1:{DASH_PORT}")
    print(f"loam backend: {LOAM_URL}")
    srv = ThreadingHTTPServer(("127.0.0.1", DASH_PORT), Handler)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()