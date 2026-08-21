# loam Release Notes

## v0.4.0 — Robustness & observability

### What changed since v0.3.0

#### Growth model hardening

| Addition | Description |
|----------|-------------|
| **Polarization spiral damping** | Consecutive same-direction pushes on already-extreme traits (>0.85 or <0.15) are progressively damped. Prevents "runaway certainty" without affecting normal S-shaped growth. |
| **Anti-sycophancy prompt** | Digestion LLM instructed to require stronger evidence for same-direction signals when traits are already extreme. |
| **State/Trait separation** | Transient states (tired, excited, hungry) are now marked `is_state` — they fade naturally and don't clog the trait space. |
| **Constants extraction** | All 45+ tunable parameters moved to `loam/core/constants.py` with provenance annotations (intuition source, tuning range, what breaks if changed). |

#### Memory network hardening

| Addition | Description |
|----------|-------------|
| **Hub penalty** | Nodes with degree > 20 get spread energy damped by `1/(degree/20)^2`. Prevents high-frequency concepts from becoming network super-hubs. |
| **Memory consolidation** | After 3 idle cycles, related events about the same entity are merged into higher-level summaries. Reduces fragmentation. |
| **Token budget** | Context hard-capped at 2000 chars in the proxy, with paragraph-priority truncation. |

#### Infrastructure

| Addition | Description |
|----------|-------------|
| **Proxy auth** | Random token at startup, required as `Authorization: Bearer <token>`. Set `PROXY_NO_AUTH=1` to disable for local dev. |
| **Watchdog** | `scripts/watchdog.sh` — health-checks both processes every 30s, auto-restarts after 3 consecutive failures. |
| **Seed narrative** | `secrets.json` now accepts `seed_narrative` — pre-digested on first cycle for cold-start bootstrapping. |
| **Audit logging** | Every `_grow` cycle logs LLM-extracted appraisals alongside trait changes for full traceability. |
| **Write buffer** | `log_change` calls are buffered and batch-committed per cycle — reduces SQLite write amplification. |

#### Observability & tooling

| Addition | Description |
|----------|-------------|
| **Dashboard** | Single-page HTML dashboard on port 8899 with trait evolution, event timeline, and changelog. |
| **`/network` endpoint** | `GET /network?limit=80` returns full node + edge JSON for topology visualization. |
| **`/narrative` endpoint** | `GET /narrative` returns the current self-narrative. |
| **Snapshot CLI** | `python -m loam snapshot -o ~/my-character` exports a living character card (memory.db + JSON). |
| **Benchmark script** | `scripts/benchmark.py` compares loam recall against a naive keyword baseline. |

### Test results

```
test_growth.py:      25/25 PASS
test_store.py:       14/14 PASS
test_digest.py:      33/33 PASS
test_network.py:     16/16 PASS
test_context.py:       5/5 PASS
test_server.py:        9/9 PASS
test_integration.py:   4/4 PASS
test_cli.py:           3/3 PASS
test_adapters.py:      1/1 PASS
test_llm_routing.py:   1/1 PASS
---
Total: 111/111 PASS
```

### Growth formula (unchanged core)

```
capacity = max(strength, 0.06) * max(0.97 - strength, 0.06)
delta    = plasticity * capacity * force * jitter
gate     = max(0.004, 0.5 * capacity) * 1.1^gate_level
```

All constants are documented in `loam/core/constants.py`.

### Deployment

See `docs/DEPLOY.md` for all platforms. Quick start in README covers the watchdog-based launch.

---

## v0.3.0 — Growth mechanics complete

### What changed

Growth model now implements eight coordinated mechanisms:

| Mechanism | Constant | Behavior |
|-----------|----------|----------|
| Fast/slow dual gate | `FAST_DECAY=0.72`, `FAST_LIMIT=0.28` | Transient reactions oscillate like an ECG; long-term strength is unaffected |
| Epistemic gating | `UNCERTAINTY_GATE=0.55` | Low-confidence interpretations enter uncertain pool, not long-term pending |
| Sarcasm reversal | `SARCASTIC_AMBIGUITY=0.65` | Ambiguity >= threshold inverts literal signal with 0.55x discount |
| Saturation | `SATURATION_START=0.88` | Absorption rate decays near boundaries in both feed and settle phases |
| Rebound | `REBOUND=0.001` | Extreme traits soften toward center when unreinforced (abs(S-0.5) > 0.25) |
| Freeze | `FREEZE_AFTER=48` | After 48 inactive cycles, traits freeze — no decay, no drift, preserved until woken |
| Autonomous drift | `AUTONOMOUS_DRIFT=0.0002` | Dormant/converging traits experience tiny random drift |
| Trait relation network | `TraitGraph` | When one trait shifts, a ripple propagates to connected traits |

### Growth formula

```
capacity = max(strength, 0.06) * max(0.97 - strength, 0.06)
delta    = plasticity * capacity * force * jitter
gate     = max(0.004, 0.5 * capacity) * 1.1^gate_level
```

Evidence processing path:

```
feed() -> epistemic check -> uncertain pool (if confidence < gate)
       -> sarcasm check -> signal reversal (if ambiguity >= 0.65)
       -> saturation check -> absorption discount (if S >= 0.88)
       -> assimilation (warmup=0.62, dormant=0.35, recovering=0.68)
       -> pending buffer
settle() -> calibration -> gate check -> commit (if abs(pending) >= gate)
        -> decay + rebound + autonomous drift (if no input)
        -> freeze (if inactive_cycles >= 48)
```

### Memory network

Hebbian co-activation with spreading activation (max 4 hops, transmit 0.75). Lived co-occurrence seeds edges at 0.22; recalled co-occurrence at 0.05. Edge decay (0.995/cycle) and pruning (< 0.015) handle forgetting.

---

## v0.2.0 — Pipeline enforcement and migration stability

- Forced proxy enforces `context -> upstream -> ingest` on every turn.
- CI Verify passes: SQLite->Postgres/TiKV migration, MySQL local_infile, Dockerfile CMD.
- Multi-upstream routing with `provider/model` naming.
- Newbie deployment documentation with JSON validation steps.

---

## v0.1.1 — Initial release

- Immutable journal + derived memory (events, traits, network, narrative).
- Gated trait growth with S-shaped capacity and pending->commit dynamics.
- Hebbian memory network with spreading activation.
- Expression feedback calibration.