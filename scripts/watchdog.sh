#!/usr/bin/env bash
# watchdog.sh — keep the single-port Loam stack alive.
#
# Checks the unified gateway every 30 seconds and restarts the stack if it is down.
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
UNIFIED_PORT="${UNIFIED_PORT:-8783}"
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

gateway_fails=0

while true; do
    if curl -s --max-time 5 "http://127.0.0.1:$UNIFIED_PORT/health" > /dev/null 2>&1; then
        gateway_fails=0
    else
        gateway_fails=$((gateway_fails + 1))
        log "unified gateway DOWN (fail $gateway_fails/$MAX_FAILURES)"
        if [ "$gateway_fails" -ge "$MAX_FAILURES" ]; then
            log "stack: restarting after $MAX_FAILURES failures"
            nohup python3 "$REPO_DIR/start.py" >> "$LOAM_HOME/loam-stack.log" 2>&1 &
            gateway_fails=0
            sleep 5
        fi
    fi

    sleep "$CHECK_INTERVAL"
done