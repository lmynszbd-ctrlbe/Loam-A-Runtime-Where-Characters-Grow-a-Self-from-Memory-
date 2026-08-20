# SQLite -> Postgres/TiKV Migration Runbook

## A. Export migration artifacts
```bash
python scripts/migration/sqlite_to_postgres_tikv.py \
  --journal-db ~/.loam/characters/<character>/journal.db \
  --memory-db ~/.loam/characters/<character>/memory.db \
  --out-dir /tmp/loam_migration \
  --label pre_cutover
```

Artifacts:
- `migration_manifest.json`
- `<db>/postgres_load.sql`
- `<db>/tikv_load.sql`
- table CSV files + sha256

## B. Consistency verification (pre-cutover)
```bash
python scripts/migration/verify_migration_consistency.py \
  --manifest /tmp/loam_migration/migration_manifest.json
```

## C. Load to target database
- Postgres: execute generated `postgres_load.sql` via `psql`.
- TiKV/MySQL protocol: execute generated `tikv_load.sql` via `mysql --local-infile=1`.

## D. Rollback plan
Before cutover, snapshot current SQLite files:
```bash
python scripts/ops/create_snapshot.py \
  --character-dir ~/.loam/characters/<character> \
  --out-dir ~/.loam/backups
```
If target validation fails:
```bash
python scripts/migration/rollback_from_snapshot.py \
  --snapshot-dir ~/.loam/backups/snapshot_<ts> \
  --target-dir ~/.loam/characters/<character>
```

## E. Migration rehearsal (pressure drill)
```bash
python scripts/migration/rehearse_migration_load.py \
  --journal-db ~/.loam/characters/<character>/journal.db \
  --memory-db ~/.loam/characters/<character>/memory.db \
  --rounds 5
```

Use the duration distribution to estimate cutover window and rollback budget.