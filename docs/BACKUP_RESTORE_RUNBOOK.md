# Backup & Restore Runbook

## 1) Create snapshot
```bash
python scripts/ops/create_snapshot.py \
  --character-dir ~/.loam/characters/<character> \
  --out-dir ~/.loam/backups
```

Output: `snapshot_<timestamp>/` with `journal.db`, `memory.db`, `snapshot_manifest.json`.

## 2) Verify snapshot integrity
- Check manifest hashes and file existence.
- Optional deep check with migration verifier (for exported manifests).

## 3) Restore snapshot
```bash
python scripts/ops/restore_snapshot.py \
  --snapshot-dir ~/.loam/backups/snapshot_<timestamp> \
  --character-dir ~/.loam/characters/<character>
```

## 4) Rollback during migration
If migration fails after cutover:
```bash
python scripts/migration/rollback_from_snapshot.py \
  --snapshot-dir ~/.loam/backups/snapshot_<timestamp> \
  --target-dir ~/.loam/characters/<character>
```

## 5) Post-restore verification
1. `python -m loam stats --character <character> --home ~/.loam/characters`
2. `curl http://127.0.0.1:8765/healthz`
3. Optional: run `scripts/verify_three_dialogues_trait_shift.py` for functional sanity.

## 6) Safety notes
- Keep at least one recent and one weekly snapshot.
- Snapshot before any schema/data migration.
- Restore writes files in place; stop running loam service before restore.