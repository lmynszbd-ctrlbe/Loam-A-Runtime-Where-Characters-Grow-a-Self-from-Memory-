"""Start Loam's internal services behind one externally visible port."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import List


PUBLIC_HOST = os.environ.get("UNIFIED_HOST", "127.0.0.1")
PUBLIC_PORT = os.environ.get("UNIFIED_PORT", "8783")
CORE_PORT = os.environ.get("LOAM_PORT", "8765")
PROXY_PORT = os.environ.get("PROXY_PORT", "8781")
ADMIN_PORT = os.environ.get("ADMIN_PORT", "8900")


def _terminate(processes: List[subprocess.Popen[object]]) -> None:
    """Stop children in reverse startup order and avoid hanging on shutdown."""
    for process in reversed(processes):
        if process.poll() is None:
            process.terminate()
    deadline = time.monotonic() + 5
    for process in reversed(processes):
        if process.poll() is None:
            remaining = max(0.0, deadline - time.monotonic())
            try:
                process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)


def main() -> int:
    root = Path(__file__).resolve().parent
    python_exe = sys.executable
    env = os.environ.copy()
    loam_home = Path(env.get("LOAM_HOME", "~/.loam")).expanduser()
    env.update(
        {
            "LOAM_HOST": "127.0.0.1",
            "LOAM_PORT": CORE_PORT,
            "PROXY_HOST": "127.0.0.1",
            "PROXY_PORT": PROXY_PORT,
            "ADMIN_HOST": "127.0.0.1",
            "ADMIN_PORT": ADMIN_PORT,
            "UNIFIED_HOST": PUBLIC_HOST,
            "UNIFIED_PORT": PUBLIC_PORT,
            "LOAM_URL": f"http://127.0.0.1:{CORE_PORT}",
            "ADMIN_URL": f"http://127.0.0.1:{ADMIN_PORT}",
            "PROXY_URL": f"http://127.0.0.1:{PROXY_PORT}",
            # Preserve the existing local setup behavior. Set PROXY_NO_AUTH=0
            # and provide PROXY_TOKEN when the public gateway needs auth.
            "PROXY_NO_AUTH": env.get("PROXY_NO_AUTH", "1"),
        }
    )
    commands = [
        [
            python_exe,
            "-m",
            "loam",
            "run",
            "--host",
            "127.0.0.1",
            "--port",
            CORE_PORT,
            "--home",
            str(loam_home / "characters"),
            "--secrets-home",
            str(loam_home),
        ],
        [python_exe, "bridge/forced_flow_proxy.py"],
        [python_exe, "scripts/admin.py"],
        [python_exe, "scripts/unified_gateway.py"],
    ]
    processes: List[subprocess.Popen[object]] = []

    print(f"Starting Loam behind http://{PUBLIC_HOST}:{PUBLIC_PORT}")
    try:
        for command in commands:
            process = subprocess.Popen(command, cwd=root, env=env)
            processes.append(process)
            time.sleep(0.5)
            if process.poll() is not None:
                raise RuntimeError(f"service exited with code {process.returncode}: {' '.join(command)}")

        print("\nLoam is running with one external port:")
        print(f"  Admin UI: http://{PUBLIC_HOST}:{PUBLIC_PORT}/")
        print(f"  OpenAI API: http://{PUBLIC_HOST}:{PUBLIC_PORT}/v1")
        print("  Press Ctrl+C to stop all services.\n")

        while True:
            time.sleep(1)
            exited = [p for p in processes if p.poll() is not None]
            if exited:
                raise RuntimeError(f"a backend service exited with code {exited[0].returncode}")
    except KeyboardInterrupt:
        print("\nShutting down Loam...")
        return 0
    except (OSError, RuntimeError) as exc:
        print(f"Startup failed: {exc}", file=sys.stderr)
        return 1
    finally:
        _terminate(processes)
        print("All services stopped.")


if __name__ == "__main__":
    raise SystemExit(main())
