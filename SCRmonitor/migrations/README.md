# SQLite Migration Rules

This project uses a lightweight SQLite migration mechanism managed by `server.py`.

The migration directory is:

```text
migrations/
```

## Current Startup Flow

Database startup is intentionally low risk:

```text
init_db()
run_migrations()
start_server()
```

`init_db()` still creates the historical baseline schema and keeps existing compatibility logic. New database changes after Phase 11 should be added through SQL migration files instead of being appended to `init_db()`.

## Migration Tracking Table

`run_migrations()` ensures this table exists:

```sql
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    checksum TEXT NOT NULL,
    applied_at TEXT NOT NULL
);
```

The table records:

- `version`: migration number, for example `001`
- `filename`: SQL migration file name
- `checksum`: SHA-256 checksum of the UTF-8 SQL file contents
- `applied_at`: timestamp when the migration was applied

## File Naming

Migration files must be named with a monotonic numeric prefix:

```text
001_baseline_marker.sql
002_add_example_table.sql
003_add_example_index.sql
```

Rules:

- Numbers only increase.
- Do not rename an applied migration.
- Do not edit an applied migration.
- If a change is needed, create the next migration file.
- Do not use untraceable names such as `update.sql`, `fix.sql`, or `new.sql`.

## Writing SQL Migrations

Migration files should contain plain SQL statements only:

```sql
CREATE TABLE ...
ALTER TABLE ...
CREATE INDEX ...
UPDATE ...
```

Do not write transaction wrappers inside SQL migration files:

```sql
BEGIN;
COMMIT;
```

`run_migrations()` owns the transaction for each file.

## Checksum Policy

`run_migrations()` computes a SHA-256 checksum from each SQL file using UTF-8.

For already applied migrations:

- The current file checksum is compared with `schema_migrations.checksum`.
- If the checksum differs, startup must stop.
- The error must explain the file name, database checksum, current checksum, and that applied migrations must not be modified.

This protects different developer machines from silently drifting to incompatible database versions.

## Baseline Migration

`001_baseline_marker.sql` marks the existing `init_db()` schema as migration baseline.

It creates a harmless marker table:

```sql
CREATE TABLE IF NOT EXISTS migration_baseline_marker (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO migration_baseline_marker (id) VALUES (1);
```

It does not rebuild business tables and does not delete data.

## Development Rule

For future features:

- New tables must be added through `migrations/*.sql`.
- New columns must be added through `migrations/*.sql`.
- New indexes must be added through `migrations/*.sql`.
- Data repair/backfill steps must be added through `migrations/*.sql`.
- Avoid adding new schema changes directly to `init_db()`.

`init_db()` may still keep historical compatibility logic until the project intentionally refactors it, but it should not be the default place for new schema changes.

## Safety Rules

Migration work must not:

- Clear business data.
- Delete `data/sample_testing.db`.
- Delete `data/uploads`.
- Delete `data/outputs`.
- Restore large `records_json` storage as the primary record store.
- Introduce heavyweight migration frameworks such as Alembic.
- Rewrite `server.py` broadly when a small migration is enough.

## Encoding Rules

Read and write project files as UTF-8.

On Windows PowerShell, Chinese text may display incorrectly because of console encoding or font settings. Do not treat PowerShell mojibake as proof that source files are corrupt. Confirm encoding through actual file content, browser rendering, frontend build, backend API output, or another UTF-8 aware reader before changing Chinese text.

## Verification Checklist

After adding a migration:

```powershell
python -m py_compile server.py parsers\resistance_csv_parser.py parsers\cd_violin_visualizer.py
python server.py
```

Then verify:

- `schema_migrations` exists.
- The new migration version is recorded.
- `checksum` is non-empty.
- `applied_at` is non-empty.
- Restarting does not re-run the same migration.
- Raw Data list/detail still work.
- Resistance summary and heatmap still work if touched by the change.
- CD/SEM records and violin visualization still work if touched by the change.

For frontend changes:

```powershell
cd frontend
npm run build
```
