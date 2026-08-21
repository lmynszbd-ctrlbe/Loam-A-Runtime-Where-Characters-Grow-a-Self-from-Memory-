# loam

A memory runtime where identity grows from immutable dialogue history through gated growth dynamics, Hebbian associative networks, and auditable reconstruction.

## What it is

loam is two cooperating processes that run locally:

1. **loam** (port 8765) — stores raw dialogue turns, digests them into structured memory (events, traits, a Hebbian network, and a self-narrative), and serves retrieval via `/context`.
2. **forced proxy** (port 8780) — an OpenAI-compatible gateway that enforces the pipeline `context -> upstream LLM -> ingest` on every turn, so memory writes don't depend on host tool-calling reliability.

Your client connects to `http://127.0.0.1:8780/v1`. The proxy routes to whichever upstream provider you configured, then writes the turn back to loam. The growth model digests accumulated turns asynchronously.

## Why the design decisions are what they are

### Immutable substrate
Raw turns are append-only. Every derived artifact (trait strength, event, edge, narrative) points to a concrete source turn. If the model improves later, replay the same raw journal through the new model and compare.

### Gated growth, not weighted averaging
Traits don't move on every interaction. Evidence accumulates in a `pending` buffer. Only when the buffer crosses a dynamic threshold does a qualitative shift occur — and the threshold itself rises after each commit (marginal diminishing returns). This prevents both random jitter and runaway positive feedback.

### Hebbian network for causal recall
Similarity search alone can't jump from "I'm nervous about tomorrow" to "the last time someone interrupted you in a meeting." The network grows edges between events that co-occur in experience, then spreads activation along those edges. Different characters develop different network topologies from different experiences — the topology *is* the personality.

### Chat model ≠ growth model
The model that generates replies is decoupled from the model that digests memory. You can use a fast model for chat and a more capable model for digestion, or vice versa. They are configured independently in `upstreams.json`.

## Growth mechanics

Trait dynamics follow S-shaped capacity:

```
capacity = max(strength, 0.06) * max(0.97 - strength, 0.06)
delta    = 0.35 * capacity * signal * salience
gate     = max(0.004, 0.5 * capacity) * 1.1^gate_level
```

Key mechanisms:
- **Pending -> commit**: evidence accumulates in a buffer; qualitative change only after crossing the dynamic gate.
- **Expression feedback**: claimed-but-never-expressed traits are pulled down; consistently-expressed-but-unclaimed traits are pushed up.
- **Saturation**: absorption rate decays near boundaries (strength >= 0.88).
- **Rebound**: extreme traits (abs(S - 0.5) > 0.25) slowly soften toward center when not reinforced.
- **Freeze**: after 48 inactive cycles, traits freeze entirely — no decay, no drift, preserved until explicitly woken.
- **Sarcasm reversal**: ambiguity >= 0.65 inverts the literal signal and discounts it.
- **Trait graph**: when one trait shifts, a ripple propagates through the relation network to connected traits.
- **Lifecycle**: warmup -> active -> converging -> dormant -> frozen -> recovering.

Tests: `python tests/test_growth.py` (25/25 pass).

## Memory network

A single Hebbian rule: nodes co-activated together strengthen their edges. The rest follows:

```
strengthen: new = min(w + 0.30 * base * room * force, 0.95)
spread:     energy(dst) = Σ energy(src) * edge_weight * 0.75
```

- **Lived co-occurrence** (same experience) seeds edges at 0.22; recalled co-occurrence at 0.05.
- **Spreading activation** (max 4 hops) enables multi-step causal recall across semantically dissimilar but causally linked events.
- **Edge decay** (0.995/cycle) and pruning (< 0.015) handle forgetting.
- **Anchor nodes** (always-on) and **tiering** (hot/warm/cold) control retrieval scope.

## Quick start

```bash
git clone https://github.com/lmynszbd-ctrlbe/Loam-A-Runtime-Where-Characters-Grow-a-Self-from-Memory-.git loam
cd loam

# 1. Create both config files (required)
mkdir -p ~/.loam
python -m loam init-secrets --secrets-home ~/.loam
nano ~/.loam/secrets.json       # fill in api_key, base_url, model
cp bridge/upstreams.example.json ~/.loam/upstreams.json
nano ~/.loam/upstreams.json     # fill in provider info

# 2. Start loam + proxy
bash scripts/termux/final_start_all.sh

# 3. Verify
curl -s http://127.0.0.1:8765/health
curl -s http://127.0.0.1:8780/health
curl -s http://127.0.0.1:8780/v1/models
```

Client: Base URL `http://127.0.0.1:8780/v1`, model `provider/model` (e.g. `relayA/deepseek-chat`).

## Deployment

See `docs/DEPLOY.md` for all platforms (Termux, Windows, macOS, Linux, Docker) and extras (MCP, systemd).

Additional references: `docs/RELEASE.md` `docs/MIGRATION_RUNBOOK.md` `docs/BACKUP_RESTORE_RUNBOOK.md` `docs/OPS_SOP.md`

## Tech stack

- Python 3 (stdlib-first, no framework dependencies)
- SQLite (WAL mode, FTS5 with custom bigram tokenizer for Chinese)
- ThreadingHTTPServer (process-internal)
- Model-agnostic LLM backend (OpenAI-compatible API)

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
