# Data Flow

This document summarizes how data moves through JIQT_2.

## Sample Creation

Users create and maintain samples through frontend sample pages. The frontend calls backend API endpoints from modules in `SCRmonitor/frontend/src/api/`. The backend validates request data, writes records to SQLite, and returns normalized JSON responses to the frontend.

Sample records are stored in the SQLite database located under the configured runtime data directory.

## Raw Data Upload

Raw Data workflows begin in the frontend Raw Data page. Users create Raw Data records and upload files associated with those records. Uploaded files are written under the runtime upload directory, usually beneath:

```text
SCRmonitor/data/uploads/
```

or the directory configured by `JIQT_DATA_DIR`.

Uploaded files are runtime/business data and must not be committed.

## Parser Processing

Parser modules in `SCRmonitor/parsers/` process supported measurement file formats. The backend calls these modules after upload or when a parse/visualization endpoint is requested.

Current parser responsibilities include:

- reading CD SEM template CSV data
- reading resistance CSV data
- producing normalized parsed records
- generating visualization artifacts such as charts or reports

Generated parser outputs are stored in the runtime output directory. They are reproducible artifacts or local analysis results and must not be committed.

## Normalized Records

After parsing, the backend stores normalized metadata and record summaries in SQLite. This lets frontend pages display parsed data, detail panels, summaries, record tables, and processing status without reading raw uploaded files directly from the browser.

The database is runtime state and must not be uploaded.

## Frontend API Consumption

Frontend API wrappers live in `SCRmonitor/frontend/src/api/`. Page and component code calls these wrappers to load and update:

- samples
- test data
- process records
- raw data
- parsed data
- processing jobs
- characterization collections/files
- performance datasets
- dashboard summaries
- MES route templates and flow records

The frontend consumes JSON from the backend and renders feature-specific pages under `SCRmonitor/frontend/src/pages/`.

## Runtime File Storage

The backend runtime directory is controlled by `JIQT_DATA_DIR` or defaults to `SCRmonitor/data`.

Expected runtime subdirectories include:

- `uploads/` for uploaded user files
- `outputs/` for generated charts, visualizations, reports, and downloads
- `logs/` for runtime logs
- `backups/` for local backups when created

Only placeholder `.gitkeep` files should be committed under `SCRmonitor/data`.

## Generated Files That Must Not Be Committed

Do not commit:

- SQLite databases
- uploaded Raw Data files
- characterization uploads
- generated charts
- generated reports
- generated exports
- generated downloads
- logs
- backups
- packaging output
- frontend build output
- dependency folders
- Python bytecode/cache files
- real experimental or business data

---

# Deletion & Data-Safety Policy

This section is **authoritative**. Every delete path in the backend MUST follow
these rules, and any new deletable entity MUST be added here and implemented to
match. The goal: a deletion is always **preceded by a recoverable checkpoint**,
**consistent across entities**, and **explicitly confirmed** when it removes more
than a single leaf row.

There are two independent axes that a delete touches, and they must not be
confused:

1. **Database rows** — handled by the database via foreign keys.
2. **Files on disk** (`uploads/`, `outputs/`) — handled only by application
   code; the database cascade cannot touch the filesystem.

## Principle 1 — Row cascade is uniform and DB-enforced

Every child table references its parent with `ON DELETE CASCADE`, and
`PRAGMA foreign_keys = ON` is set on every connection (`app/db.py`). Deleting a
parent row deletes all descendant rows automatically, in one transaction.

There are **no exceptions**. In particular, `parsed_records` — which historically
had **no** `ON DELETE` rule and could *block* a parent delete with a foreign-key
violation — is brought into line via a migration so it cascades from
`parsed_data` like every other child. `processing_results.sample_id` remains
`ON DELETE SET NULL` by design (a computed result may outlive its sample), and
this is the single deliberate exception, documented here.

## Principle 2 — File cleanup is centralized in application code

Because the DB cascade cannot delete files, **every** delete routes file removal
through one shared helper rather than ad-hoc code per handler. The helper
collects the entity's file paths (and its descendants' paths) **before** the row
delete, then removes them from the live store **after** the row delete succeeds.

Critically, `delete_sample` MUST call this helper. Previously it ran only
`DELETE FROM samples`, so the cascade removed the child *rows* but the actual
files were **orphaned** on disk forever. That is now closed: deleting a sample
removes its uploaded and generated files too.

Removing files from the live store is safe because of Principle 4 (the archive
already holds an immutable copy).

## Principle 3 — Confirmation tiers by blast radius

| Tier | Applies to | Required UX |
|------|-----------|-------------|
| **Simple** | a leaf row with no children and no files (e.g. one `test_data` point) | a one-line "Delete?" confirm |
| **Strong** | any entity with children or files (`samples`, `raw_data`, `performance_datasets`, `characterization` collections, `parsed_data`) | a dialog that shows the **cascade preview** — counts of child rows and files that will be removed — and requires explicit confirmation |

The cascade preview is provided by a backend **preview endpoint** that reports
the blast radius without deleting anything; the frontend calls it before showing
the Strong-tier dialog.

## Principle 4 — Backup precedes destruction

Before any destructive action the system guarantees a recoverable checkpoint:

- **Files:** every uploaded file is copied into an **append-only,
  content-addressed archive at upload time** (see below) — so file bytes are
  preserved *independently of, and prior to,* any later delete.
- **Database:** a DB snapshot is taken before strong-tier deletes (in addition to
  the rotating startup backups), and the directly-targeted row is snapshotted
  into `deletion_audit` at delete time.

## The upload archive (append-only, content-addressed)

- **What:** every file accepted by an upload endpoint (`upload_raw_data_files`,
  `create_performance_dataset`, `create_characterization_files`) is copied into
  an archive keyed by its **SHA-256** content hash. Identical content is stored
  once (automatic deduplication); the existing `raw_data_files.sha256` is reused.
- **Where:** a configurable directory, `JIQT_ARCHIVE_DIR` (default
  `<data-dir>/archive`). It may live on a larger/separate disk.
- **Lifetime:** **append-only and never auto-pruned.** Uploaded measurement
  files are write-once, so the archive is the durable source of truth for raw
  bytes. The rotating `backups/` directory (DB snapshots) is pruned; the archive
  is not.
- **Caveat (documented intentionally):** because the archive is never pruned, it
  deliberately preserves data even after a "delete." This is appropriate for
  process/measurement data. If a future requirement demands *permanent* purge of
  specific content, the archive is the one place that must be addressed
  explicitly — it will not forget on its own.

## Why not soft-delete

Soft-delete (flagging rows instead of removing them) was evaluated and
**deliberately not adopted**. It would require a `deleted_at` filter on every
read query across all feature modules (large, error-prone surface), and it
collides with the `UNIQUE(sample_display_code)` / `raw_data_code` constraints (a
hidden "deleted" row keeps owning its unique code). The archive + per-delete
backup + `deletion_audit` + confirmation/preview deliver recoverability without
that cost. The one thing given up is one-click in-app *undo*; recovery instead
restores from the archive/backup, guided by `deletion_audit`.

## Per-entity deletion summary

| Entity | Tier | Row cascade | Files removed from live store | Recovery source |
|--------|------|-------------|-------------------------------|-----------------|
| `samples` | Strong | all children cascade | yes (via helper — incl. raw/char/perf files) | archive + DB backup |
| `raw_data` | Strong | files, parsed_data, parsed_records | yes | archive + DB backup |
| `raw_data_files` (one file) | Simple/Strong | the file row | yes | archive |
| `parsed_data` | Strong | parsed_records (after migration) | generated outputs | DB backup |
| `characterization` file/collection | Strong | collection → files | yes | archive |
| `performance_datasets` | Strong | dataset files | yes | archive |
| `test_data` (one point) | Simple | none | none | DB backup / `deletion_audit` |
| `mes_route_step` | Strong | sample steps + events | none | DB backup |

## Backup & restore operations

There are two recovery stores and a restore tool:

- **DB snapshots** — full copies of the database written by `app/backup.py`
  (`backup_database()`) to `<data-dir>/backups/sample_testing_<timestamp>.db`,
  at startup and before strong-tier deletes; the newest 10 are kept.
- **Upload archive** — append-only, content-addressed file store (see above);
  not pruned.

**Restoring the database** (`scripts/restore_db.py`): the server must be stopped
first (the DB must not be in use). The tool lists snapshots, snapshots the
*current* DB to `backups/pre_restore_*.db` (so a restore is itself reversible),
copies the chosen snapshot over the live DB, and **clears the `-wal`/`-shm`
sidecar files** so the restored copy is not merged with stale write-ahead frames.

```text
python3 scripts/restore_db.py --list                 # show available snapshots
python3 scripts/restore_db.py --latest               # restore the most recent
python3 scripts/restore_db.py --file <name> --yes    # restore a specific one
```

Manual equivalent (if not using the script): stop the server, copy the chosen
`backups/*.db` over `sample_testing.db`, delete `sample_testing.db-wal` and
`sample_testing.db-shm`, restart.

