#!/usr/bin/env bash
# watchdog.sh — keep loam and proxy alive.
#
# Checks both processes every 30 seconds. If either is down, restarts it.
# Gives up after 3 consecutive failures per process.
#
# Usage:
#   bash scripts/watchdog.sh
#
# Or run in background:
#   nohup bash scripts/watchdog.sh > ~/.loam/watchdog.log 2>&1 &
#
# Stop:
#   kill $(cat ~/.loam/watchdog.pid)

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOAM_HOME="${LOAM_HOME:-$HOME/.loam}"
PID_FILE="$LOAM_HOME/watchdog.pid"
LOAM_PORT="${LOAM_PORT:-8765}"
PROXY_PORT="${PROXY_PORT:-8780}"
CHECK_INTERVAL="${WATCHDOG_INTERVAL:-30}"
MAX_FAILURES="${WATCHDOG_MAX_FAIL:-3}"

mkdir -p "$LOAM_HOME"
echo $$ > "$PID_FILE"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

cleanup() {
    log "watchdog stopping"
    rm -f "$PID_FILE"
    exit 0
}
trap cleanup INT TERM

log "watchdog started (pid=$$, interval=${CHECK_INTERVAL}s, max_failures=$MAX_FAILURES)"

loam_fails=0
proxy_fails=0

while true; do
    # --- check loam ---
    if curl -s --max-time 5 "http://127.0.0.1:$LOAM_PORT/health" > /dev/null 2>&1; then
        loam_fails=0
    else
        loam_fails=$((loam_fails + 1))
        log "loam DOWN (fail $loam_fails/$MAX_FAILURES)"
        if [ "$loam_fails" -ge "$MAX_FAILURES" ]; then
            log "loam: restarting after $MAX_FAILURES failures"
            bash "$SCRIPT_DIR/termux/start_loam.sh" 2>&1 | while read -r line; do log "[loam] $line"; done &
            loam_fails=0
            sleep 5  # give it time to start
        fi
    fi

    # --- check proxy ---
    if curl -s --max-time 5 "http://127.0.0.1:$PROXY_PORT/health" > /dev/null 2>&1; then
        proxy_fails=0
    else
        proxy_fails=$((proxy_fails + 1))
        log "proxy DOWN (fail $proxy_fails/$MAX_FAILURES)"
        if [ "$proxy_fails" -ge "$MAX_FAILURES" ]; then
            log "proxy: restarting after $MAX_FAILURES failures"
            bash "$SCRIPT_DIR/termux/start_forced_proxy.sh" 2>&1 | while read -r line; do log "[proxy] $line"; done &
            proxy_fails=0
            sleep 5
        fi
    fi

    sleep "$CHECK_INTERVAL"
done