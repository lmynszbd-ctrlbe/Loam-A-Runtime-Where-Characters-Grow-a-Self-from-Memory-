# loam Deployment Guide

<<<<<<< HEAD
> 🚀 **One-click**: `git clone <repo> && cd loam && bash scripts/setup.sh` — auto-detects OS, installs everything, opens admin panel.
=======
> 🚀 **One-click**: `git clone https://github.com/lmynszbd-ctrlbe/Loam-A-Runtime-Where-Characters-Grow-a-Self-from-Memory-.git && cd loam && bash scripts/setup.sh` — auto-detects OS, installs everything, opens admin panel.
> 📖 **Manual**: pick your platform below for step-by-step commands.

---

## Quick overview

| Process | Port | Purpose |
|---------|------|---------|
| loam server | 8765 | Memory storage, digestion, trait growth |
| forced proxy | 8780 | OpenAI-compatible gateway, routes to your LLM provider |
| admin panel | 8899 | Web UI: Status, Traits, Memory, Config, Constants, Actions |

Client connects to `http://127.0.0.1:8780/v1`
Model name: `relayA/deepseek-chat` (or whatever you configured in upstreams.json)

---

## Manual setup (per platform)

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

Two files in `~/.loam/`:

### `secrets.json` — loam server (digestion model)

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

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `command not found: python` | Try `python3`, or reinstall Python |
| `Connection refused` | Service not running — check terminals |
| `401 Unauthorized` | Wrong API key in `upstreams.json` |
| `Models list empty` | `base_url` in `upstreams.json` must be API endpoint, not homepage |
| Proxy exits immediately | Check `~/.loam/run/forced_proxy.log` for typos in `upstreams.json` |
| `No module named loam` | `cd ~/loam` first |

## Security

- Never commit `secrets.json` or `upstreams.json` to git
- Proxy forwards directly to your providers — no third-party relay
- `chmod 700 ~/.loam`
