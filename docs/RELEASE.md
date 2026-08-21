# loam Release Notes

## v0.3.0 — Growth mechanics complete

### What changed

Growth model now implements eight coordinated mechanisms:

| Mechanism | Constant | Behavior |
|-----------|----------|----------|
| Fast/slow dual gate | `FAST_DECAY=0.72`, `FAST_LIMIT=0.28` | Transient reactions oscillate like an ECG; long-term strength is unaffected |
| Epistemic gating | `UNCERTAINTY_GATE=0.55` | Low-confidence interpretations enter uncertain pool, not long-term pending |
| Sarcasm reversal | `SARCASTIC_AMBIGUITY=0.65` | Ambiguity ≥ threshold inverts literal signal with 0.55× discount |
| Saturation | `SATURATION_START=0.88` | Absorption rate decays near boundaries in both feed and settle phases |
| Rebound | `REBOUND=0.001` | Extreme traits (|S−0.5| > 0.25) soften toward center when unreinforced |
| Freeze | `FREEZE_AFTER=48` | After 48 inactive cycles, traits freeze — no decay, no drift, preserved until woken |
| Autonomous drift | `AUTONOMOUS_DRIFT=0.0002` | Dormant/converging traits experience tiny random drift |
| Trait relation network | `TraitGraph` | When one trait shifts, a ripple propagates to connected traits |

### Growth formula

```
capacity = max(strength, 0.06) × max(0.97 − strength, 0.06)
delta    = plasticity × capacity × force × jitter
gate     = max(0.004, 0.5 × capacity) × 1.1^gate_level
```

Evidence processing path:
```
feed() → epistemic check → uncertain pool (if confidence < gate)
       → sarcasm check → signal reversal (if ambiguity ≥ 0.65)
       → saturation check → absorption discount (if S ≥ 0.88)
       → assimilation (warmup=0.62, dormant=0.35, recovering=0.68)
       → pending buffer
settle() → calibration → gate check → commit (if |pending| ≥ gate)
        → decay + rebound + autonomous drift (if no input)
        → freeze (if inactive_cycles ≥ 48)
```

### Test results

```
test_growth.py: 25/25 PASS
test_store.py:  14/14 PASS
test_network.py, test_context.py, test_server.py, test_integration.py: all pass
```

### Memory network

Hebbian co-activation with spreading activation (max 4 hops, transmit 0.75). Lived co-occurrence seeds edges at 0.22; recalled co-occurrence at 0.05. Edge decay (0.995/cycle) and pruning (< 0.015) handle forgetting.

### Deployment

Single `docs/DEPLOY.md` covers Termux, Linux, WSL, macOS, and Docker. All platforms share the same upstream mapping mechanism via `~/.loam/upstreams.json`.

---

## v0.2.0 — Pipeline enforcement and migration stability

- Forced proxy enforces `context → upstream → ingest` on every turn.
- CI Verify passes: SQLite→Postgres/TiKV migration, MySQL local_infile, Dockerfile CMD.
- Multi-upstream routing with `provider/model` naming.
- Newbie deployment documentation with JSON validation steps.

---

## v0.1.1 — Initial release

- Immutable journal + derived memory (events, traits, network, narrative).
- Gated trait growth with S-shaped capacity and pending→commit dynamics.
- Hebbian memory network with spreading activation.
- Expression feedback calibration.
- Termux scripts for Android deployment.