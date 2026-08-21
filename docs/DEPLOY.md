# loam Deployment Guide

## One-command setup (recommended)

```bash
bash scripts/setup.sh
```

Detects your OS, installs prerequisites, clones the repo, walks you through configuration, starts everything, and opens the admin panel at `http://127.0.0.1:8899`. Works on Termux, macOS, Linux, WSL, and Windows.

The sections below are for manual setup if you prefer step-by-step control.

## Quick overview

loam runs as two processes plus an optional admin panel:

| Process | Port | What it does |
|---------|------|-------------|
| loam server | 8765 | Stores memories, grows personality, digests conversations |
| forced proxy | 8780 | OpenAI-compatible API gateway, routes to your LLM provider |
| admin panel | 8899 | Web UI for status, traits, memory, config, constants, actions |

You need both loam and proxy. The proxy is what your chat client connects to.

## You need two things before starting

1. **An API key** from an LLM provider (DeepSeek, OpenAI, any OpenAI-compatible service)
2. **A device** — Android phone, Windows/Mac/Linux computer, or server

---

## How config works (read this first)

loam uses **two separate config files**. They are not the same thing.

### File 1: `~/.loam/secrets.json` — for the loam server

This tells loam which model to use for background digestion (extracting events, appraising traits, writing narratives).

Create it:
```bash
mkdir -p ~/.loam
python -m loam init-secrets --secrets-home ~/.loam
```

Then edit `~/.loam/secrets.json`:
```json
{
  "api_key": "sk-your-real-key-here",
  "base_url": "https://api.deepseek.com",
  "model": "deepseek-chat",
  "low_cost_enabled": false,
  "low_cost_api_key": "",
  "low_cost_base_url": "",
  "low_cost_model": ""
}
```

Fill in: `api_key`, `base_url`, `model`. The `low_cost_*` fields are optional — they let you route cheaper extraction phases to a smaller model to save money.

### File 2: `~/.loam/upstreams.json` — for the forced proxy

This tells the proxy which models your chat client can use.

Create it:
```bash
cp bridge/upstreams.example.json ~/.loam/upstreams.json
nano ~/.loam/upstreams.json
```

Replace the placeholders:
```json
{
  "default": "relayA",
  "providers": {
    "relayA": {
      "base_url": "https://api.deepseek.com",
      "api_key": "sk-your-real-key-here",
      "default_model": "deepseek-chat"
    }
  }
}
```

- `base_url`: your provider's API endpoint (must start with `https://`)
- `api_key`: your actual API key
- `default_model`: the model name your provider uses
- `default`: which provider to use when the client doesn't specify one

You can add multiple providers (see "Multi-upstream" section below).

---

## A) Android (Termux)

No computer needed. Everything runs on your phone.

### Step 1: Install Termux

Download from F-Droid (NOT Google Play — the Play version is outdated):
https://f-droid.org/packages/com.termux/

Open the app. You'll see a black screen with a blinking cursor — this is the terminal.

### Step 2: Copy and paste each line, one at a time

```bash
# Allow Termux to access phone storage (a popup will appear)
termux-setup-storage

# Install Python and Git
pkg update -y
pkg install -y python git curl nano

# Download loam
cd ~
git clone https://github.com/lmynszbd-ctrlbe/Loam-A-Runtime-Where-Characters-Grow-a-Self-from-Memory-.git loam
cd ~/loam
```

### Step 3: Create loam config (secrets.json)

```bash
mkdir -p ~/.loam
python -m loam init-secrets --secrets-home ~/.loam
nano ~/.loam/secrets.json
```

Replace `api_key`, `base_url`, and `model` with your actual values. In nano: arrow keys to move, type to edit. Press `Ctrl+X`, then `Y`, then `Enter` to save.

### Step 4: Create proxy config (upstreams.json)

```bash
cp bridge/upstreams.example.json ~/.loam/upstreams.json
nano ~/.loam/upstreams.json
```

Replace the placeholders with your actual provider info. Same nano save procedure.

### Step 5: Start everything

```bash
bash scripts/termux/final_start_all.sh
```

You'll see text scrolling. When it stops, both loam and proxy are running.

### Step 6: Verify

Open a new Termux session (swipe from left edge -> "New session") and run:

```bash
curl -s http://127.0.0.1:8765/health
curl -s http://127.0.0.1:8780/health
```

Both should show `{"status":"ok"}`.

### Step 7: Connect your chat client

Open any AI chat app that supports custom OpenAI-compatible endpoints. Point it to:

- **Address:** `http://127.0.0.1:8780/v1`
- **API Key:** anything (e.g. `local-key`)
- **Model:** `relayA/deepseek-chat` (or whatever you put in upstreams.json)

### Daily commands

```bash
cd ~/loam
bash scripts/termux/final_status_all.sh    # check if running
bash scripts/termux/final_stop_all.sh      # stop
bash scripts/termux/final_start_all.sh     # restart
```

---

## B) Windows

### Step 1: Install Python

Download from https://python.org. During installation, **CHECK the box "Add Python to PATH"** (this is important — if you miss it, the commands below won't work).

### Step 2: Install Git

Download from https://git-scm.com. Use all default settings.

### Step 3: Open Command Prompt

Press `Win+R`, type `cmd`, press Enter. You'll see a black window with white text.

### Step 4: Download loam

```bash
cd %USERPROFILE%
git clone https://github.com/lmynszbd-ctrlbe/Loam-A-Runtime-Where-Characters-Grow-a-Self-from-Memory-.git loam
cd loam
```

### Step 5: Create both config files

```bash
mkdir %USERPROFILE%\.loam
python -m loam init-secrets --secrets-home %USERPROFILE%\.loam
copy bridge\upstreams.example.json %USERPROFILE%\.loam\upstreams.json
```

Now open both files in Notepad and fill in your real API key and model:

- `%USERPROFILE%\.loam\secrets.json` — replace `api_key`, `base_url`, `model`
- `%USERPROFILE%\.loam\upstreams.json` — same replacements

### Step 6: Start loam and proxy (two terminals)

Open **two** Command Prompt windows. In each one:

Terminal 1 — loam server:
```bash
cd %USERPROFILE%\loam
python -m loam run --character default --home %USERPROFILE%\.loam\characters --secrets-home %USERPROFILE%\.loam --host 127.0.0.1 --port 8765
```

Terminal 2 — proxy:
```bash
cd %USERPROFILE%\loam
set UPSTREAMS_CONFIG=%USERPROFILE%\.loam\upstreams.json
set UPSTREAM_DEFAULT=relayA
python bridge\forced_flow_proxy.py
```

### Step 7: Verify

Open a third Command Prompt:
```bash
curl -s http://127.0.0.1:8765/health
```

If you see `{"status":"ok"}`, it's working. If `curl` is not found, open http://127.0.0.1:8765/health in your browser instead.

### Step 8: Connect your chat client

Same as Android — see client settings above.

---

## C) macOS

### Step 1: Install Python and Git

Open Terminal (Applications -> Utilities -> Terminal):
```bash
# If you have Homebrew:
brew install python git curl

# If you don't have Homebrew, download Python from https://python.org
```

### Step 2: Download and configure

```bash
cd ~
git clone https://github.com/lmynszbd-ctrlbe/Loam-A-Runtime-Where-Characters-Grow-a-Self-from-Memory-.git loam
cd ~/loam

# Create configs
mkdir -p ~/.loam
python3 -m loam init-secrets --secrets-home ~/.loam
cp bridge/upstreams.example.json ~/.loam/upstreams.json

# Edit both files with your API key and model
nano ~/.loam/secrets.json
nano ~/.loam/upstreams.json
```

### Step 3: Start (two terminals)

Terminal 1 — loam:
```bash
cd ~/loam
python3 -m loam run --character default --home ~/.loam/characters --secrets-home ~/.loam --host 127.0.0.1 --port 8765
```

Terminal 2 — proxy:
```bash
cd ~/loam
UPSTREAMS_CONFIG="$HOME/.loam/upstreams.json" UPSTREAM_DEFAULT='relayA' python3 bridge/forced_flow_proxy.py
```

### Step 4: Verify

```bash
curl -s http://127.0.0.1:8765/health
```

---

## D) Linux (Ubuntu/Debian)

### Step 1: Install dependencies

```bash
sudo apt update
sudo apt install -y python3 python3-pip git curl nano
```

### Step 2: Download and configure

```bash
cd ~
git clone https://github.com/lmynszbd-ctrlbe/Loam-A-Runtime-Where-Characters-Grow-a-Self-from-Memory-.git loam
cd ~/loam

mkdir -p ~/.loam
python3 -m loam init-secrets --secrets-home ~/.loam
cp bridge/upstreams.example.json ~/.loam/upstreams.json
nano ~/.loam/secrets.json
nano ~/.loam/upstreams.json
```

### Step 3: Start (two terminals)

Terminal 1 — loam:
```bash
cd ~/loam
python3 -m loam run --character default --home ~/.loam/characters --secrets-home ~/.loam --host 127.0.0.1 --port 8765
```

Terminal 2 — proxy:
```bash
cd ~/loam
UPSTREAMS_CONFIG="$HOME/.loam/upstreams.json" UPSTREAM_DEFAULT='relayA' python3 bridge/forced_flow_proxy.py
```

### Step 4: Verify

```bash
curl -s http://127.0.0.1:8765/health
```

### Production (systemd)

For servers that should auto-restart on reboot, create a systemd service:

```ini
# /etc/systemd/system/loam.service
[Unit]
Description=loam memory runtime
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/home/your-username/loam
ExecStart=/usr/bin/python3 -m loam run --character default --home /home/your-username/.loam/characters --secrets-home /home/your-username/.loam --host 127.0.0.1 --port 8765
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Then `sudo systemctl enable --now loam`. Run the proxy similarly in a separate service.

---

## E) Docker

### Build and start

```bash
cd ~/loam
docker compose up -d --build
docker compose logs -f
```

### Verify

```bash
curl -s http://127.0.0.1:8765/health
```

### Important Docker notes

- The docker-compose only starts the **loam server** on port 8765.
- The **proxy** must be run separately outside Docker (or added to docker-compose with port 8780 mapped).
- For secrets, either:
  - Mount `~/.loam` into the container: add `- ~/.loam:/root/.loam` to volumes in docker-compose.yml
  - Or set environment variables in docker-compose.yml

---

## Multi-upstream (use multiple providers)

Add more entries to `~/.loam/upstreams.json`:

```json
{
  "default": "relayA",
  "providers": {
    "relayA": {
      "base_url": "https://api.deepseek.com",
      "api_key": "sk-your-deepseek-key",
      "default_model": "deepseek-chat"
    },
    "relayB": {
      "base_url": "https://api.openai.com",
      "api_key": "sk-your-openai-key",
      "default_model": "gpt-4o-mini"
    }
  }
}
```

Then in your chat client, choose models by prefix:
- `relayA/deepseek-chat` -> uses DeepSeek
- `relayB/gpt-4o-mini` -> uses OpenAI
- No prefix -> uses the `default` provider (relayA in this example)

---

## Using loam as an MCP tool

MCP (Model Context Protocol) lets AI assistants like Claude Desktop or Continue use external tools. Since loam's proxy speaks standard OpenAI API, any MCP client that supports OpenAI-compatible providers can use loam as a memory backend.

### What this gives you

When an MCP client connects to loam, every conversation is automatically logged, digested, and turned into long-term memory — traits, events, narratives — without any extra setup. The AI assistant gets a growing self across sessions.

### Step-by-step: connect loam to your MCP client

**Step 1: Make sure loam is running**

Before configuring any MCP client, loam must be running. Pick your platform from the sections above (A through E), start both loam and proxy, and verify:

```bash
curl -s http://127.0.0.1:8765/health
curl -s http://127.0.0.1:8780/health
```

Both must return `{"status":"ok"}`.

**Step 2: Find your MCP client's config file**

Different clients store their config in different places. Here are the most common ones:

| MCP Client | Config file location |
|------------|---------------------|
| Claude Desktop | `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows) |
| Continue (VS Code) | `~/.continue/config.json` |
| Cursor | `~/.cursor/mcp.json` |
| Cline (VS Code) | `~/.cline/mcp_settings.json` |
| Operit (Android) | Settings -> MCP Servers -> Add Server |

If your client isn't listed, search its documentation for "MCP server configuration" or "OpenAI-compatible provider".

**Step 3: Add loam to the config**

Open the config file and add a `loam` entry under `mcpServers`. Here is the exact JSON to add:

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

What each field means:
- `type`: tells the client this is an OpenAI-compatible API (not a custom MCP server)
- `baseURL`: the address of loam's proxy — always `http://127.0.0.1:8780/v1`
- `apiKey`: anything non-empty works (e.g. `local-key`); authentication is handled by the upstream provider
- `model`: the model name in `provider/model` format. Change `relayA` to match your upstreams.json default, and `deepseek-chat` to your actual model

**Step 4: Restart your MCP client**

Close and reopen the client app. It should pick up the new config. In some clients, you may need to manually enable the loam server in settings.

**Step 5: Verify it works**

Send a message through your MCP client. Then check loam's memory:

```bash
curl -s http://127.0.0.1:8765/context
```

If you see events and traits accumulating, the connection is working. Every conversation is now being digested into long-term memory.

### Multiple MCP clients

You can connect multiple MCP clients to the same loam instance. Each client gets its own character (configured via the `--character` flag when starting loam). This lets different assistants develop different personalities from different conversations, all stored in the same loam database.

---

## Post-deployment: verify everything works

```bash
# 1. Health checks
curl -s http://127.0.0.1:8765/health
curl -s http://127.0.0.1:8780/health

# 2. Check available models
curl -s http://127.0.0.1:8780/v1/models

# 3. Run a test chat completion
curl -s http://127.0.0.1:8780/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"relayA/deepseek-chat","messages":[{"role":"user","content":"Hello"}]}'

# 4. Run unit tests (optional)
python3 -m compileall -q loam tests scripts
python3 tests/test_growth.py
python3 tests/test_context.py
```

---

## Troubleshooting

### "command not found: python" or "pip: command not found"
-> Python isn't installed or not in PATH.
- Windows: reinstall Python and check "Add Python to PATH"
- Mac/Linux: try `python3` instead of `python`

### "git: command not found"
-> Git isn't installed.
- Termux: `pkg install git`
- Windows: download from https://git-scm.com
- Mac: `brew install git`
- Linux: `sudo apt install git`

### "Connection refused" at /health
-> The service isn't running. Check if the terminal is still running and not showing errors. On Termux, run `bash scripts/termux/final_status_all.sh`.

### "401 Unauthorized" in chat client
-> The API key in `upstreams.json` is wrong or expired. Open the file and double-check.

### "Models list is empty" or "no models available"
-> The `base_url` in `upstreams.json` is wrong. It must be the API endpoint (starts with `https://`), not the provider's homepage.

### Proxy exits immediately
-> Check the log: `cat ~/.loam/run/forced_proxy.log`. Usually a typo in `upstreams.json`.

### loam won't start: "启动失败：未检测到 LOAM_API_KEY"
-> `secrets.json` is missing or has an empty `api_key`. Run `python -m loam init-secrets --secrets-home ~/.loam` and edit the file.

### "No module named loam"
-> You're not in the loam directory. Run `cd ~/loam` first.

---

## Security notes

- Both `secrets.json` and `upstreams.json` contain API keys. Never commit them to git.
- The proxy forwards requests directly to your configured providers. No third-party relay is involved.
- Keep `~/.loam/` private (`chmod 700 ~/.loam`).

---

## Still stuck?

Open an issue on GitHub with:
1. Your platform (Android/Windows/Mac/Linux/Docker)
2. Which step you're stuck on
3. The exact command you ran and the full error message
4. Output of `curl -s http://127.0.0.1:8765/health`
5. Structure of your config files (redact the API keys!)