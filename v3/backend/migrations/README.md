# Migration Scripts

This directory provides explicit up/down SQL migrations for Phase 1 sprint schema.

## Files

- `001_phase1_up.sql`: Applies phase-1 policy, indexing, lesson-card, artifact, and audit tables.
- `001_phase1_down.sql`: Rolls back phase-1 tables.
- `run_migration.py`: Applies or rolls back migrations with an automatic SQLite backup.

## Usage

Run from `v3/backend`:

```powershell
python migrations/run_migration.py up --db ../data/app.db
python migrations/run_migration.py down --db ../data/app.db
```

A timestamped backup file is written before each action.
