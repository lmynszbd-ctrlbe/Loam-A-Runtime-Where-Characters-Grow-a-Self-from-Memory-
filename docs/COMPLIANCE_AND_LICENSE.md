# Compliance & License Checklist

## License
- Project license: `MIT` (`/LICENSE`)
- Copyright holder: `@lmynszbd-ctrlbe`

## Runtime dependencies
- Runtime path is intentionally **stdlib-only**.
- Lock file: `/requirements.lock` (documents Python version and no third-party runtime deps).

## Third-party service usage
- Optional external LLM API providers can be configured by the deployer.
- Operators must ensure their API usage complies with provider ToS and local regulations.

## Data handling
- Raw dialogue is stored immutably in `journal.db`.
- Derived memory is stored in `memory.db`.
- Snapshot/restore tools are provided in `scripts/ops/` and `scripts/migration/`.

## Pre-release compliance checks
1. Confirm LICENSE exists and matches repository policy.
2. Confirm no secrets committed (`~/.loam/secrets.json` must stay local).
3. Run reproducible-build check:
   - `bash scripts/ops/check_reproducible_build.sh`
4. Run migration consistency check for any DB export:
   - `python scripts/migration/verify_migration_consistency.py --manifest <path>`