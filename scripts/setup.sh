#!/usr/bin/env bash
# ============================================================
# loam — one-command setup for all platforms
# ============================================================
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/.../setup.sh | bash
#   or
#   bash setup.sh
#
# This script:
#   1. Detects your OS (Termux/macOS/Linux/Windows)
#   2. Installs prerequisites if missing
#   3. If ~/loam doesn't exist, clones it; otherwise pulls latest
#   4. Walks you through configuration (API key, model)
#   5. Starts loam + proxy + admin panel
#   6. Opens the admin panel in your browser
# ============================================================

set -e

# ---- colors ----
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'

say()  { echo -e "${GREEN}→${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC}  $1"; }
err()  { echo -e "${RED}✗${NC}  $1"; }
info() { echo -e "${BLUE}ℹ${NC}  $1"; }
heading() { echo -e "\n${BOLD}${BLUE}═══ $1 ═══${NC}\n"; }

# ---- detect OS ----
detect_os() {
    case "$(uname -s)" in
        Darwin)  OS="macos" ;;
        Linux)
            if [ -d /data/data/com.termux ]; then
                OS="termux"
            elif grep -qi microsoft /proc/version 2>/dev/null; then
                OS="wsl"
            else
                OS="linux"
            fi
            ;;
        MINGW*|MSYS*|CYGWIN*) OS="windows" ;;
        *) OS="unknown" ;;
    esac
    say "Detected OS: ${OS}"
}

# ---- install prerequisites ----
install_prereqs() {
    heading "Checking prerequisites"

    # Python 3
    if command -v python3 &>/dev/null; then
        say "python3: $(python3 --version)"
    elif command -v python &>/dev/null; then
        PYTHON="python"
        say "python: $(python --version)"
    else
        warn "python3 not found, installing..."
        case $OS in
            termux) pkg install -y python ;;
            macos)  brew install python3 2>/dev/null || err "Please install python3: https://python.org" ;;
            linux)  sudo apt-get update -qq && sudo apt-get install -y python3 ;;
            *)      err "Please install python3 manually: https://python.org" && exit 1 ;;
        esac
    fi

    # Git
    if ! command -v git &>/dev/null; then
        warn "git not found, installing..."
        case $OS in
            termux) pkg install -y git ;;
            macos)  brew install git 2>/dev/null || err "Please install git: https://git-scm.com" ;;
            linux)  sudo apt-get install -y git ;;
            *)      err "Please install git manually" && exit 1 ;;
        esac
    fi

    # Curl
    if ! command -v curl &>/dev/null; then
        warn "curl not found, installing..."
        case $OS in
            termux) pkg install -y curl ;;
            macos)  ;; # macOS has curl built-in
            linux)  sudo apt-get install -y curl ;;
        esac
    fi

    say "All prerequisites satisfied"
}

# ---- clone repo ----
clone_repo() {
    heading "Cloning loam"
    LOAM_DIR="${HOME}/loam"
    REPO="https://github.com/lmynszbd-ctrlbe/Loam-A-Runtime-Where-Characters-Grow-a-Self-from-Memory-.git"
    RAW="https://raw.githubusercontent.com/lmynszbd-ctrlbe/Loam-A-Runtime-Where-Characters-Grow-a-Self-from-Memory-/main"

    if [ -d "$LOAM_DIR" ]; then
        say "loam already exists at ${LOAM_DIR}"
        cd "$LOAM_DIR"
        if git pull --ff-only 2>/dev/null; then
            say "Pulled latest changes"
        else
            warn "git pull failed (network issue?) — trying curl fallback..."
            for f in scripts/admin.py scripts/setup.sh bridge/forced_flow_proxy.py; do
                curl -fsSL "${RAW}/${f}" -o "${f}" 2>/dev/null && say "  ✓ ${f}" || warn "  ✗ ${f} (skipped)"
            done
            say "Core files updated via curl"
        fi
    else
        say "Cloning into ${LOAM_DIR}..."
        git clone "$REPO" "$LOAM_DIR"
        cd "$LOAM_DIR"
    fi
}

# ---- configure ----
configure() {
    heading "Configuration"

    mkdir -p ~/.loam

    # secrets.json (loam 后台记忆消化用)
    # 优先自动从 upstreams.json 复制，解决用户配了 upstream 但记忆不长的常见问题
    if [ ! -f ~/.loam/secrets.json ]; then
        if [ -f ~/.loam/upstreams.json ]; then
            python3 -c "
import json, sys
try:
    cfg = json.load(open('$HOME/.loam/upstreams.json'))
    providers = cfg.get('providers', {})
    if providers:
        first = list(providers.values())[0]
        secrets = {
            'api_key': first.get('api_key', ''),
            'base_url': (first.get('base_url', 'https://api.openai.com/v1') or 'https://api.openai.com/v1').rstrip('/v1').rstrip('/'),
            'model': first.get('default_model', first.get('model', 'gpt-4o-mini')),
        }
        json.dump(secrets, open('$HOME/.loam/secrets.json', 'w'), indent=2, ensure_ascii=False)
        print('OK')
    else:
        print('NO_PROVIDERS')
except Exception as e:
    print(f'ERR: {e}')
" 2>/dev/null
            if [ -f ~/.loam/secrets.json ]; then
                say "secrets.json auto-generated from upstreams.json (后台记忆消化用)"
            else
                warn "Could not auto-generate secrets.json — run 'python3 -m loam init-secrets' or create manually"
            fi
        else
            info "No upstreams.json yet. You can configure secrets.json later via the admin panel."
            info "Or run: python3 -m loam init-secrets --secrets-home ~/.loam"
        fi
    else
        say "secrets.json already exists"
        # Auto-heal: if base_url ends with /v1, fix it (loam Brain appends /v1/chat/completions)
        python3 -c "
import json, os
p = os.path.expanduser('~/.loam/secrets.json')
try:
    d = json.load(open(p))
    url = d.get('base_url','')
    if url.endswith('/v1'):
        d['base_url'] = url[:-3].rstrip('/')
        json.dump(d, open(p,'w'), indent=2, ensure_ascii=False)
        print('FIXED: stripped trailing /v1 from secrets.json')
    else:
        print('secrets.json base_url OK')
except Exception as e:
    print('secrets.json check skipped:', e)
" 2>/dev/null
    fi

    # upstreams.json
    if [ ! -f ~/.loam/upstreams.json ]; then
        if [ -f bridge/upstreams.example.json ]; then
            cp bridge/upstreams.example.json ~/.loam/upstreams.json
            say "upstreams.json created from example"
        fi
    else
        say "upstreams.json already exists"
    fi
}

# ---- start ----
start_services() {
    heading "Starting loam"

    # Use the dedicated reset helper to free ports and kill old processes.
    # On Android, zombie listeners can block setup.sh; reset.sh is extra aggressive.
    if [ -f scripts/reset.sh ]; then
        bash scripts/reset.sh
    else
        pkill -f "loam.__main__" 2>/dev/null || true
        pkill -f "forced_flow_proxy" 2>/dev/null || true
        pkill -f "scripts/admin.py" 2>/dev/null || true
        pkill -f "dashboard.py" 2>/dev/null || true
        sleep 2
    fi

    # Start the complete stack behind one external port. Internal services bind
    # to loopback only and are reachable through scripts/unified_gateway.py.
    export LOAM_HOME="${HOME}/.loam"
    mkdir -p "${LOAM_HOME}/run" "${LOAM_HOME}/state"
    export UNIFIED_HOST="${UNIFIED_HOST:-127.0.0.1}"
    export UNIFIED_PORT="${UNIFIED_PORT:-8783}"
    export LOAM_PORT="${LOAM_PORT:-8765}"
    export PROXY_PORT="${PROXY_PORT:-8781}"
    export ADMIN_PORT="${ADMIN_PORT:-8900}"
    export LOAM_URL="http://127.0.0.1:${LOAM_PORT}"
    export PROXY_URL="http://127.0.0.1:${PROXY_PORT}"
    export ADMIN_URL="http://127.0.0.1:${ADMIN_PORT}"
    export PROXY_HOST="127.0.0.1"
    export ADMIN_HOST="127.0.0.1"
    export PROXY_NO_AUTH="${PROXY_NO_AUTH:-1}"

    nohup python3 start.py > "${LOAM_HOME}/run/loam-stack.log" 2>&1 &
    echo $! > "${LOAM_HOME}/run/stack.pid"
    say "loam stack started (public port ${UNIFIED_PORT}, pid $(cat "${LOAM_HOME}/run/stack.pid"))"

    sleep 2

    if curl -sf "http://127.0.0.1:${UNIFIED_PORT}/health" > /dev/null 2>&1; then
        say "unified gateway health check: OK"
    else
        warn "unified gateway health check failed — check ${LOAM_HOME}/run/loam-stack.log"
    fi
}

# ---- open browser ----
open_browser() {
    heading "Opening admin panel"

    URL="http://127.0.0.1:${UNIFIED_PORT:-8783}"
    case $OS in
        macos)  open "$URL" ;;
        linux|wsl) xdg-open "$URL" 2>/dev/null || true ;;
        termux) termux-open-url "$URL" 2>/dev/null || true ;;
        windows) start "$URL" 2>/dev/null || true ;;
    esac
    echo ""
    echo -e "${BOLD}${GREEN}✓ loam is running!${NC}"
    echo ""
    echo "  Admin + API:  ${BLUE}http://127.0.0.1:${UNIFIED_PORT:-8783}${NC}"
    echo "  Client base URL: ${BLUE}http://127.0.0.1:${UNIFIED_PORT:-8783}/v1${NC}"
    echo "  Model name:      ${BLUE}relayA/deepseek-chat${NC} (or whatever you configured)"
    echo ""
    echo -e "${BOLD}${YELLOW}⚠  IMPORTANT — Keep these processes running!${NC}"
    echo "  If you close this terminal, loam stops. To keep it alive:"
    echo "    • systemd:  sudo systemctl enable --now loam"
    echo "    • tmux:     tmux new -s loam, run ./setup.sh, Ctrl+B D to detach"
    echo "    • nohup:    nohup bash scripts/setup.sh &"
    echo "    • Docker:   docker compose up -d"
    echo ""
    echo "  To stop:  kill \$(cat "${LOAM_HOME}/run/stack.pid" 2>/dev/null || true)"
    echo ""
}

# ---- main ----
main() {
    echo ""
    echo -e "${BOLD}${BLUE}  ╔══════════════════════════════════╗${NC}"
    echo -e "${BOLD}${BLUE}  ║       loam · one-click setup     ║${NC}"
    echo -e "${BOLD}${BLUE}  ║  memory runtime for AI characters ║${NC}"
    echo -e "${BOLD}${BLUE}  ╚══════════════════════════════════╝${NC}"
    echo ""

    detect_os
    install_prereqs
    clone_repo
    configure
    start_services
    open_browser
}

main