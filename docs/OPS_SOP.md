# Ops Manual & Alert SOP

## Health endpoints
- `GET /health` : liveness
- `GET /healthz` : runtime health (pending/open_gaps/grower)
- `GET /dashboard` : alert levels + backlog + task state

## Alert levels
- `info`: normal operation
- `warn`: recoverable backlog or partial degradation
- `error`: grower down / queue failed

## First-response SOP
1. **error** level:
   - Check `/dashboard.tasks.grower.alive`
   - Check `/dashboard.backlog.queue.jobs_failed`
   - Restart grower: `POST /grower/start`
   - Re-run drain: `POST /drain {"max_rounds": 100}`
2. **warn** level:
   - Inspect `/dashboard.tasks.ingest_queue.sessions`
   - If pending accumulates, run `POST /drain`
   - Verify decay and recompute history for anomalies.

## Routine checks (daily)
1. `GET /dashboard` and archive JSON snapshots.
2. Run load/fault drill (staging):
   - `python scripts/ops/load_and_fault_drill.py --base-url http://127.0.0.1:8765 --sessions 3 --turns 20 --fault-check`
3. Create snapshot backup:
   - `python scripts/ops/create_snapshot.py --character-dir <dir> --out-dir <backup_dir>`

## Weekly checks
1. Cold archive old snapshots:
   - `python scripts/ops/archive_cold_snapshots.py --snapshot-root <backup_dir> --days-old 7`
2. Migration rehearsal:
   - `python scripts/migration/rehearse_migration_load.py --journal-db <...> --memory-db <...> --rounds 3`

## Escalation criteria
- `jobs_failed > 0` for > 10 minutes
- `pending` continuously increasing for > 30 minutes
- `grower_alive=false` and restart unsuccessful

When any criterion holds, escalate to on-call maintainer and prepare rollback snapshot restore.