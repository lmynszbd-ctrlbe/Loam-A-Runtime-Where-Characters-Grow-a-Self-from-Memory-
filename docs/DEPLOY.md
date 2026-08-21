# loam Deployment Guide

> 🚀 **Fastest path — two steps.** Step 1 installs loam (skip it if you already have the folder), Step 2 launches everything.

### Step 1 — Install loam (skip if already installed)

If you have **not** downloaded loam yet, run this once:

```bash
cd ~ && git clone https://github.com/lmynszbd-ctrlbe/Loam-A-Runtime-Where-Characters-Grow-a-Self-from-Memory-.git loam
```

> ✅ **Already have the `~/loam` folder?** Skip Step 1 and go straight to Step 2.
> (If a clone fails with `destination path 'loam' already exists`, that just means loam is already installed — jump to Step 2.)

### Step 2 — Set up & launch

```bash
cd ~/loam && git pull && bash scripts/setup.sh
```

`setup.sh` auto-detects your OS, installs prerequisites, walks you through the API keys, starts all three processes, and opens the admin panel at `http://127.0.0.1:8900`.

> 📖 Prefer to do it by hand? See **Manual setup** below for per-platform commands.

---

## Quick overview

| Process | Port | Purpose |
|---------|------|---------|
| loam server | 8765 | Memory storage, digestion, trait growth |
| forced proxy | 8781 | OpenAI-compatible gateway, routes to your LLM provider |
| admin panel | 8900 | Web UI: Status, Traits, Memory, Config, Constants, Connect, Actions |

Client connects to `http://127.0.0.1:8781/v1`
Model name: `provider/model` (e.g. `relayA/deepseek-chat`, configured in the Connect tab)

> ⚠️ **ALL THREE processes must keep running.**
> Closing the terminal kills them. `setup.sh` backgrounds them, but for long-term use see [Keeping processes running](#keeping-processes-running) below.

---

## Keeping processes running

loam is **not a static website** — it's three live processes. If you close the terminal, they all stop.

| Method | Best for | Command |
|--------|----------|---------|
| **systemd** | Linux servers | `sudo systemctl enable --now loam` (see [systemd section](#systemd-server-auto-restart)) |
| **tmux / screen** | Any platform | `tmux new -s loam` then run `bash scripts/setup.sh` inside, detach with `Ctrl+B D` |
| **Docker** | Containers | `docker compose up -d` |
| **Termux** | Android | `termux-wake-lock` + keep Termux app open |
| **nohup** | Quick & dirty | `nohup bash scripts/setup.sh &` (won't survive reboot) |

> 💡 The admin panel itself (port 8899) is also a process — it must stay running too. It's not a static HTML file. `setup.sh` starts it automatically.

---

## Manual setup (per platform)

Only needed if you skipped `scripts/setup.sh` and want to run each step yourself.
For every platform: if you already cloned loam, skip the Clone step and start from Configure.

### Android (Termux)

```bash
# Prerequisites
pkg update -y && pkg install -y python git curl

# Clone
cd ~ && git clone https://github.com/lmynszbd-ctrlbe/Loam-A-Runtime-Where-Characters-Grow-a-Self-from-Memory-.git loam
cd ~/loam

# Configure
mkdir -p ~/.loam
python -m loam init-secrets --secrets-home ~/.loam
cp bridge/upstreams.example.json ~/.loam/upstreams.json
# Edit ~/.loam/secrets.json and ~/.loam/upstreams.json

# Start
bash scripts/termux/final_start_all.sh

# Stop / status
bash scripts/termux/final_stop_all.sh
bash scripts/termux/final_status_all.sh
```

### Windows

```bash
# Prerequisites: install Python (check "Add to PATH") + Git from https://git-scm.com

# Clone
cd %USERPROFILE%
git clone https://github.com/lmynszbd-ctrlbe/Loam-A-Runtime-Where-Characters-Grow-a-Self-from-Memory-.git loam
cd loam

# Configure
mkdir %USERPROFILE%\.loam
python -m loam init-secrets --secrets-home %USERPROFILE%\.loam
copy bridge\upstreams.example.json %USERPROFILE%\.loam\upstreams.json
# Edit %USERPROFILE%\.loam\secrets.json and upstreams.json in Notepad

# Start (two terminals)
# Terminal 1:
python -m loam run --home %USERPROFILE%\.loam\characters --secrets-home %USERPROFILE%\.loam

# Terminal 2:
set UPSTREAMS_CONFIG=%USERPROFILE%\.loam\upstreams.json
set UPSTREAM_DEFAULT=relayA
python bridge\forced_flow_proxy.py
```

### macOS

```bash
# Prerequisites
brew install python git

# Clone & configure
cd ~ && git clone https://github.com/lmynszbd-ctrlbe/Loam-A-Runtime-Where-Characters-Grow-a-Self-from-Memory-.git loam
cd ~/loam
mkdir -p ~/.loam
python3 -m loam init-secrets --secrets-home ~/.loam
cp bridge/upstreams.example.json ~/.loam/upstreams.json
# Edit ~/.loam/secrets.json and ~/.loam/upstreams.json

# Start (two terminals)
# Terminal 1:
python3 -m loam run

# Terminal 2:
UPSTREAMS_CONFIG="$HOME/.loam/upstreams.json" UPSTREAM_DEFAULT=relayA python3 bridge/forced_flow_proxy.py
```

### Linux (Ubuntu/Debian)

```bash
# Prerequisites
sudo apt install -y python3 git curl

# Clone & configure
cd ~ && git clone https://github.com/lmynszbd-ctrlbe/Loam-A-Runtime-Where-Characters-Grow-a-Self-from-Memory-.git loam
cd ~/loam
mkdir -p ~/.loam
python3 -m loam init-secrets --secrets-home ~/.loam
cp bridge/upstreams.example.json ~/.loam/upstreams.json
# Edit ~/.loam/secrets.json and ~/.loam/upstreams.json

# Start (two terminals)
# Terminal 1:
python3 -m loam run

# Terminal 2:
UPSTREAMS_CONFIG="$HOME/.loam/upstreams.json" UPSTREAM_DEFAULT=relayA python3 bridge/forced_flow_proxy.py
```

### systemd (server auto-restart)

```ini
# /etc/systemd/system/loam.service
[Unit]
Description=loam memory runtime
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/home/your-username/loam
ExecStart=/usr/bin/python3 -m loam run
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now loam
```

### Docker

```bash
cd ~/loam && docker compose up -d --build
```

Note: docker-compose only starts loam server (8765). Run proxy separately or add a second service to docker-compose.yml with port 8780.

---

## Configuration reference

You can set both API keys **visually in the admin panel** (open `http://127.0.0.1:8899` → **Connect** tab → *Set Your API Keys*), or edit these two files in `~/.loam/` by hand.

loam uses **two** separate keys, one per file:

### `secrets.json` — loam memory model (digestion)

```json
{
  "api_key": "sk-your-key",
  "base_url": "https://api.deepseek.com",
  "model": "deepseek-chat"
}
```

Optional `low_cost_*` fields route cheaper extraction phases to a smaller model.

### `upstreams.json` — forced proxy (chat models)

```json
{
  "default": "relayA",
  "providers": {
    "relayA": {
      "base_url": "https://api.deepseek.com",
      "api_key": "sk-your-key",
      "default_model": "deepseek-chat"
    }
  }
}
```

---

## Multi-upstream

```json
{
  "default": "relayA",
  "providers": {
    "relayA": { "base_url": "https://api.deepseek.com", "api_key": "sk-...", "default_model": "deepseek-chat" },
    "relayB": { "base_url": "https://api.openai.com", "api_key": "sk-...", "default_model": "gpt-4o-mini" }
  }
}
```

Model format: `provider/model` (e.g. `relayA/deepseek-chat`, `relayB/gpt-4o-mini`).

---

## MCP integration

Add to your MCP client config:

```json
{
  "mcpServers": {
    "loam": {
      "type": "openai-compatible",
      "baseURL": "http://127.0.0.1:8780/v1",
      "apiKey": "local-key",
      "model": "relayA/deepseek-chat"
    }
  }
}
```

Client config locations:

| Client | Config path |
|--------|-------------|
| Claude Desktop | `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) |
| Continue (VS Code) | `~/.continue/config.json` |
| Cursor | `~/.cursor/mcp.json` |
| Cline (VS Code) | `~/.cline/mcp_settings.json` |

---

## Verify

```bash
curl -s http://127.0.0.1:8765/health
curl -s http://127.0.0.1:8780/health
curl -s http://127.0.0.1:8780/v1/models
```

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `command not found: python` | Try `python3`, or reinstall Python |
| `Connection refused` | Service not running — check terminals |
| `401 Unauthorized` | Wrong API key in `upstreams.json` |
| `Models list empty` | `base_url` in `upstreams.json` must be API endpoint, not homepage |
| Proxy exits immediately | Check `~/.loam/run/forced_proxy.log` for typos in `upstreams.json` |
| `No module named loam` | `cd ~/loam` first |
| Client app can't fetch models | Client and proxy are in different sandboxes; use the phone's LAN IP instead of `127.0.0.1` |
| Base URL with `/v1` gives errors | Supported since v0.x; proxy now tolerates `https://host/v1` and `https://host` |

## Security

- Never commit `secrets.json` or `upstreams.json` to git
- Proxy forwards directly to your providers — no third-party relay
- `chmod 700 ~/.loam`
