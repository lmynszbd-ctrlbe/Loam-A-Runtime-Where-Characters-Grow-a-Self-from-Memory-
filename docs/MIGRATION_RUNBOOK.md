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

## B. Consistency verification (source side)
```bash
python scripts/migration/verify_migration_consistency.py \
  --manifest /tmp/loam_migration/migration_manifest.json
```

## C. Load to target databases
```bash
python scripts/migration/load_to_postgres_tikv.py \
  --manifest /tmp/loam_migration/migration_manifest.json \
  --postgres-dsn postgresql://<user>:<pass>@<host>:5432/<db> \
  --tikv-dsn mysql://<user>:<pass>@<host>:4000/<db>
```

> 如只迁移单一目标，可用 `--skip-postgres` 或 `--skip-tikv`。

## D. Consistency verification (target side)
Postgres:
```bash
python scripts/migration/verify_loaded_target_consistency.py \
  --manifest /tmp/loam_migration/migration_manifest.json \
  --target postgres \
  --postgres-dsn postgresql://<user>:<pass>@<host>:5432/<db>
```

TiKV:
```bash
python scripts/migration/verify_loaded_target_consistency.py \
  --manifest /tmp/loam_migration/migration_manifest.json \
  --target tikv \
  --tikv-dsn mysql://<user>:<pass>@<host>:4000/<db>
```

## E. Rollback plan
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

## F. Migration rehearsal (pressure drill)
```bash
python scripts/migration/rehearse_migration_load.py \
  --journal-db ~/.loam/characters/<character>/journal.db \
  --memory-db ~/.loam/characters/<character>/memory.db \
  --rounds 5
```

Use duration distribution to estimate cutover window and rollback budget.