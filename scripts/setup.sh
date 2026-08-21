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

    # secrets.json
    if [ ! -f ~/.loam/secrets.json ]; then
        python3 -m loam init-secrets --secrets-home ~/.loam 2>/dev/null || true
        echo ""
        info "You need an API key for the LLM provider (OpenAI, DeepSeek, etc.)"
        echo -n "  API key (or press Enter to skip): "
        read -r API_KEY
        if [ -n "$API_KEY" ]; then
            echo -n "  API base URL [https://api.openai.com/v1]: "
            read -r BASE_URL
            BASE_URL=${BASE_URL:-https://api.openai.com/v1}
            echo -n "  Model name [gpt-4o-mini]: "
            read -r MODEL
            MODEL=${MODEL:-gpt-4o-mini}

            cat > ~/.loam/secrets.json << EOF
{
  "api_key": "${API_KEY}",
  "base_url": "${BASE_URL}",
  "model": "${MODEL}"
}
EOF
            say "secrets.json configured"
        else
            say "Skipped — edit ~/.loam/secrets.json later"
        fi
    else
        say "secrets.json already exists"
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

    # Kill any existing instances — aggressive port-based kill for Android
    say "Stopping old processes..."
    pkill -f "loam.__main__" 2>/dev/null || true
    pkill -f "forced_flow_proxy" 2>/dev/null || true
    pkill -f "scripts/admin.py" 2>/dev/null || true
    pkill -f "dashboard.py" 2>/dev/null || true
    # Aggressive: kill anything on loam ports (Android stubborn processes)
    fuser -k 8765/tcp 2>/dev/null || true
    fuser -k 8781/tcp 2>/dev/null || true
    fuser -k 8900/tcp 2>/dev/null || true
    sleep 2

    # Start loam
    nohup python3 -m loam run --grow-interval 60 > /dev/null 2>&1 &
    say "loam started (port 8765)"

    # Start proxy
    if [ -f bridge/forced_flow_proxy.py ]; then
        PROXY_NO_AUTH=1 nohup python3 bridge/forced_flow_proxy.py > /dev/null 2>&1 &
        say "proxy started (port 8781)"
    fi

    # Start admin panel
    if [ -f scripts/admin.py ]; then
        nohup python3 scripts/admin.py > /dev/null 2>&1 &
        say "admin panel started (port 8900)"
    elif [ -f scripts/dashboard.py ]; then
        nohup python3 scripts/dashboard.py > /dev/null 2>&1 &
        say "dashboard started (port 8900)"
    fi

    sleep 2

    # Verify
    if curl -sf http://127.0.0.1:8765/health > /dev/null 2>&1; then
        say "loam health check: OK"
    else
        warn "loam health check failed — check the logs"
    fi
}

# ---- open browser ----
open_browser() {
    heading "Opening admin panel"

    URL="http://127.0.0.1:8900"
    case $OS in
        macos)  open "$URL" ;;
        linux|wsl) xdg-open "$URL" 2>/dev/null || true ;;
        termux) termux-open-url "$URL" 2>/dev/null || true ;;
        windows) start "$URL" 2>/dev/null || true ;;
    esac
    echo ""
    echo -e "${BOLD}${GREEN}✓ loam is running!${NC}"
    echo ""
    echo "  Admin panel:  ${BLUE}http://127.0.0.1:8900${NC}"
    echo "  API:          ${BLUE}http://127.0.0.1:8765${NC}"
    echo "  Proxy:        ${BLUE}http://127.0.0.1:8781/v1${NC}"
    echo ""
    echo "  Client base URL: ${BLUE}http://127.0.0.1:8781/v1${NC}"
    echo "  Model name:      ${BLUE}relayA/deepseek-chat${NC} (or whatever you configured)"
    echo ""
    echo -e "${BOLD}${YELLOW}⚠  IMPORTANT — Keep these processes running!${NC}"
    echo "  If you close this terminal, loam stops. To keep it alive:"
    echo "    • systemd:  sudo systemctl enable --now loam"
    echo "    • tmux:     tmux new -s loam, run ./setup.sh, Ctrl+B D to detach"
    echo "    • nohup:    nohup bash scripts/setup.sh &"
    echo "    • Docker:   docker compose up -d"
    echo ""
    echo "  To stop:  kill \$(pgrep -f 'loam.__main__\|forced_flow_proxy\|dashboard\|admin')"
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