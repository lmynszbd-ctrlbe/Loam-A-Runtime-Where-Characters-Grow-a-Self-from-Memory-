#!/usr/bin/env bash
# reset.sh — kill loam, proxy, admin processes and free their ports.
# Run this manually if setup.sh ever complains about ports being in use.

set +e

echo "[reset] Stopping loam / proxy / admin processes..."

pkill -f "loam.__main__" 2>/dev/null || true
pkill -f "forced_flow_proxy" 2>/dev/null || true
pkill -f "scripts/admin.py" 2>/dev/null || true
pkill -f "dashboard.py" 2>/dev/null || true

sleep 1

# Free ports aggressively (Termux/Android friendly)
for port in 8765 8780 8781 8900 8899 8977; do
    fuser -k "${port}/tcp" 2>/dev/null || true
done

sleep 1

# Second pass: if ss can list listeners, kill those PIDs too
if command -v ss >/dev/null 2>&1; then
    for port in 8765 8780 8781 8900 8899 8977; do
        pids=$(ss -tlnp 2>/dev/null | grep ":${port} " | sed -n 's/.*pid=\([0-9]*\).*/\1/p' | sort -u)
        for p in $pids; do
            kill -9 "$p" 2>/dev/null || true
        done
    done
fi

sleep 1

echo "[reset] Done. Ports should now be free."

# Verify
if command -v ss >/dev/null 2>&1; then
    still=$(ss -tln 2>/dev/null | grep -E ':(8765|8780|8781|8900|8899|8977) ' || true)
    if [ -n "$still" ]; then
        echo "[reset] WARNING: some ports are still in use:"
        echo "$still"
        echo "[reset] If setup.sh still fails, force-stop Termux from Android settings and reopen it."
    else
        echo "[reset] All ports are free."
    fi
fi
