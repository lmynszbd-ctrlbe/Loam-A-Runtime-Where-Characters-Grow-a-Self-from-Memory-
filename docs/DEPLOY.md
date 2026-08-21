# loam Deployment Guide

Covers all platforms. Start from the section that matches your environment.

---

## Before anything: upstream config

All platforms share the same upstream mapping mechanism. You need one upstream provider (or relay) with `base_url`, `api_key`, and `default_model`.

The template file is `bridge/upstreams.example.json` in this repository. Copy it to `~/.loam/upstreams.json`, replace placeholders, and validate:

```bash
mkdir -p ~/.loam
cp bridge/upstreams.example.json ~/.loam/upstreams.json
nano ~/.loam/upstreams.json
python -m json.tool ~/.loam/upstreams.json >/dev/null && echo JSON_OK
```

Template structure:
```json
{
  "default": "relayA",
  "providers": {
    "relayA": {
      "base_url": "https://your-upstream.example.com",
      "api_key": "sk-xxxx",
      "default_model": "gpt-4o-mini"
    }
  }
}
```

- `base_url`: API endpoint (starts with `https://`). Not the provider's homepage.
- `api_key`: from your provider's developer console. Never commit to git.
- `default_model`: exact model ID from your provider.
- `default`: which provider to use when no prefix is specified.

---

## A) Termux on Android

Recommended for first-time deployers. Fastest path to a running instance.

### Prerequisites
- Termux (F-Droid version recommended)
- One upstream provider account

### Steps

```bash
# 1. Grant storage permission
termux-setup-storage

# 2. Install dependencies
pkg update -y
pkg install -y python git curl nano

# 3. Clone repository
cd ~
git clone https://github.com/lmynszbd-ctrlbe/Loam-A-Runtime-Where-Characters-Grow-a-Self-from-Memory-.git loam
cd ~/loam

# 4. Create upstream config (see "Before anything" section above)

# 5. Start everything
LOAM_API_KEY='your_growth_key' \
LOAM_MODEL='deepseek-chat-flash' \
UPSTREAMS_CONFIG="$HOME/.loam/upstreams.json" \
UPSTREAM_DEFAULT='relayA' \
bash scripts/termux/final_start_all.sh

# 6. Verify
curl -s http://127.0.0.1:8765/health
curl -s http://127.0.0.1:8780/health
curl -s http://127.0.0.1:8780/v1/models
```

### Client settings
- Base URL: `http://127.0.0.1:8780/v1`
- API Key: any non-empty string (e.g. `local-key`)
- Model: `provider/model` (e.g. `relayA/gpt-4o-mini`)

### Daily commands
```bash
cd ~/loam
bash scripts/termux/final_status_all.sh   # check status
bash scripts/termux/final_stop_all.sh     # stop
bash scripts/termux/final_start_all.sh    # restart
```

### Troubleshooting
- **Models empty**: `~/.loam/upstreams.json` has wrong `base_url/api_key/default_model`.
- **Proxy exits immediately**: check `~/.loam/run/forced_proxy.log`.
- **Connection refused**: services not running. Run status check first.
- **401 Unauthorized**: API key missing or wrong. Check `upstreams.json`.

---

## B) Linux server / VM

For long-running, managed operation.

### Prerequisites
- Python 3.10+
- git, curl

```bash
# Ubuntu/Debian
sudo apt-get update && sudo apt-get install -y python3 python3-pip git curl nano

# Clone and enter
cd ~
git clone https://github.com/lmynszbd-ctrlbe/Loam-A-Runtime-Where-Characters-Grow-a-Self-from-Memory-.git loam
cd ~/loam
```

### Create upstream config
See "Before anything" section above. Same steps.

### Start (two terminals, or use systemd/supervisord)

Terminal 1 — loam:
```bash
python -m loam init-secrets --secrets-home ~/.loam
python -m loam run --character default --home ~/.loam/characters --secrets-home ~/.loam --host 127.0.0.1 --port 8765
```

Terminal 2 — proxy:
```bash
UPSTREAMS_CONFIG="$HOME/.loam/upstreams.json" UPSTREAM_DEFAULT='relayA' python bridge/forced_flow_proxy.py
```

### Verify
```bash
curl -s http://127.0.0.1:8765/health
curl -s http://127.0.0.1:8780/health
curl -s http://127.0.0.1:8780/v1/models
```

### Production notes
- Use systemd or supervisord for auto-restart on crash.
- Keep loam on 8765, proxy on 8780 unless you have custom port policy.
- Logs: loam logs to stdout; proxy logs to `~/.loam/run/forced_proxy.log`.

---

## C) WSL / macOS

For development and debugging. Same runtime as Linux; install dependencies with your package manager.

```bash
# macOS
brew install python git curl

# Clone and enter
cd ~
git clone https://github.com/lmynszbd-ctrlbe/Loam-A-Runtime-Where-Characters-Grow-a-Self-from-Memory-.git loam
cd ~/loam
```

Follow the Linux section from "Create upstream config" onward. Keep endpoints on `127.0.0.1`.

---

## D) Docker

For reproducible environments.

```bash
cd ~/loam
mkdir -p ./data

# Start
docker compose up -d --build
docker compose logs -f

# Verify loam
curl -s http://127.0.0.1:8765/health
```

Note: the default docker-compose only starts loam. To add the proxy, create upstream config and run proxy separately:

```bash
mkdir -p ~/.loam
cp bridge/upstreams.example.json ~/.loam/upstreams.json
nano ~/.loam/upstreams.json
UPSTREAMS_CONFIG="$HOME/.loam/upstreams.json" UPSTREAM_DEFAULT='relayA' python bridge/forced_flow_proxy.py
```

Keep secrets outside the image — inject at runtime.

---

## Multi-upstream routing

If you use multiple providers, add more entries to `upstreams.json`:

```json
{
  "default": "relayA",
  "providers": {
    "relayA": { "base_url": "https://a.example.com", "api_key": "sk-a", "default_model": "gpt-4o-mini" },
    "relayB": { "base_url": "https://b.example.com", "api_key": "sk-b", "default_model": "claude-3-5-sonnet" }
  }
}
```

Client model naming: `relayA/gpt-4o-mini`, `relayB/claude-3-5-sonnet`. If no prefix, defaults to the `default` provider.

---

## Security

- Provider keys stay in `~/.loam/upstreams.json` (local file).
- Never commit this file to git.
- Proxy forwards requests directly to your configured providers.
- No maintainer-hosted relay is required for normal operation.

---

## Post-deployment checks

1. Snapshot backup:
   ```bash
   python scripts/ops/create_snapshot.py --character-dir ~/.loam/characters/default --out-dir ~/.loam/backups
   ```

2. Run smoke tests:
   ```bash
   python tests/test_growth.py
   python tests/test_context.py
   python tests/test_server.py
   ```

3. One end-to-end chat turn through proxy to verify the full pipeline.

---

## When you're stuck

Provide these 6 items to the maintainer:
1. Platform (Termux / Linux / Docker)
2. Which step you're on
3. The exact command that failed
4. Full terminal error output
5. `curl /health` output
6. Structure of `upstreams.json` (redact keys)