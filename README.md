# loam
A memory runtime where identity grows from immutable dialogue history through gated growth dynamics, Hebbian associative networks, and auditable reconstruction.

## What it is

loam gives AI characters real memory that grows over time. It runs locally — two processes behind any OpenAI-compatible chat client:

1. **loam** (port 8765) — stores dialogue turns, digests them into structured memory, grows traits
2. **forced proxy** (port 8781) — OpenAI-compatible gateway that enforces `context → upstream LLM → ingest` on every turn

Optional extras:
- **admin panel** (port 8900) — 6-tab web UI: Status, Traits, Memory, Config, Constants, Actions
- **watchdog** — keeps both processes alive, auto-restarts on crash

## Getting started

Two steps. Step 1 installs loam (skip it if you already have the folder); Step 2 launches everything.

**Step 1 — Install loam** (skip if already installed)

```bash
cd ~ && git clone https://github.com/lmynszbd-ctrlbe/Loam-A-Runtime-Where-Characters-Grow-a-Self-from-Memory-.git loam
```

> ✅ Already have the `~/loam` folder? Skip Step 1. (A `destination path 'loam' already exists` error just means it's already installed — go to Step 2.)

**Step 2 — Set up & launch**

```bash
cd ~/loam && git pull && bash scripts/setup.sh
```

`setup.sh` auto-detects your OS, installs prerequisites, walks you through the API keys, starts all three processes, and opens the admin panel.

After setup, open `http://127.0.0.1:8900` — the admin panel lets you view traits, browse memory, hot-tune constants, trigger digest, and set both API keys (see the **Connect** tab). Prefer per-platform manual commands? See [docs/DEPLOY.md](docs/DEPLOY.md).

## Why the design decisions are what they are

### Immutable substrate
Raw turns are append-only. Every derived artifact (trait strength, event, edge, narrative) points to a concrete source turn. Replay the same journal through an improved model and compare.

### Gated growth, not weighted averaging
Traits don't move on every interaction. Evidence accumulates in a `pending` buffer. Only when the buffer crosses a dynamic threshold does a qualitative shift occur — and the threshold itself rises after each commit. This prevents random jitter and runaway positive feedback.

### Hebbian network for causal recall
Co-activated events automatically wire together. Spreading activation (max 4 hops) jumps across semantic gaps — from "I'm nervous about tomorrow" to "the last time someone interrupted you in a meeting." Different characters develop different network topologies — the topology *is* the personality.

### Chat model ≠ growth model
The model that generates replies is decoupled from the model that digests memory. Configure independently in `upstreams.json`.

### Audit trail, not black box
Every trait change is logged with the specific events that caused it. Every constant is documented in `loam/core/constants.py` (287 lines, 48 parameters). Trace any trait value back to the exact conversation turns that shaped it.

## Growth mechanics

```
capacity = max(strength, 0.06) * max(0.97 - strength, 0.06)
delta    = 0.35 * capacity * signal * salience
gate     = max(0.004, 0.5 * capacity) * 1.1^gate_level
```

Key mechanisms: pending→commit gating, expression feedback, saturation, rebound, freeze, sarcasm reversal, trait graph, state/trait separation, polarization spiral damping, anti-sycophancy prompt. Tests: `python tests/test_growth.py` (25/25 pass).

## Memory network

```
strengthen: new = min(w + 0.30 * base * room * force, 0.95)
spread:     energy(dst) = Σ energy(src) * edge_weight * 0.75
```

Lived co-occurrence seeds edges at 0.22; recalled at 0.05. Spreading activation (4 hops). Edge decay (0.995/cycle), pruning (< 0.015). Hub penalty: degree > 20 → energy damped by `1/(degree/20)^2`. Star-structured memory consolidation preserves original events. `/network` endpoint returns full topology JSON.

## API endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Liveness check |
| `/healthz` | GET | Health + stats |
| `/stats` | GET | Full statistics |
| `/dashboard` | GET | Time-windowed activity data |
| `/context` | GET/POST | Build memory context (supports `sync_grow=true` for real-time digestion) |
| `/ingest` | POST | Submit raw dialogue turns |
| `/digest` | POST | Trigger one digestion cycle |
| `/drain` | POST | Process all queued turns |
| `/narrative` | GET | Current self-narrative |
| `/network` | GET | Network topology (nodes + edges JSON) |
| `/config` | GET | Runtime configuration |
| `/config/update` | POST | Update runtime config |
| `/config/rollback` | POST | Rollback config to previous version |
| `/constants` | GET | List all 48 tunable parameters |
| `/constants` | POST | Hot-override parameters (in-memory, reset on restart) |
| `/explain` | GET | Explain recent trait changes |

## CLI

```bash
python -m loam run              # Start HTTP server
python -m loam stats            # Print current state
python -m loam digest-once      # Manual digestion
python -m loam context "query"  # Build context
python -m loam snapshot -o ~/my-character  # Export living character card
python -m loam init-secrets     # Generate secrets.json template
```

## Deployment

See [docs/DEPLOY.md](docs/DEPLOY.md) for all platforms and extras (MCP, systemd, Docker) — or just run `bash scripts/setup.sh` for one-click setup.

## Tech stack

Python 3 (stdlib-first), SQLite (WAL mode, FTS5 with Chinese bigram tokenizer), ThreadingHTTPServer, model-agnostic LLM backend. Admin panel: single-file HTML on port 8899.

## Self-benchmark

`scripts/benchmark.py` compares loam's recall against a naive keyword baseline on a synthetic dataset.

## Contributing

1. Fork and create a feature branch.
2. Keep changes minimal: code + tests + docs.
3. Before submitting: `python -m compileall -q loam tests && for f in tests/test_*.py; do python "$f"; done`
4. PR should describe motivation, scope, and verification.

## Attribution

- **@lmynszbd-ctrlbe** — project initiated, designed, and directed.
- **玉槿 (AI co-author)** — implementation, growth mechanics, deployment documentation.
- **all (AI co-author)** — implementation, refactoring, test scaffolding.

---
Don't script a persona. Grow a self from memory.
