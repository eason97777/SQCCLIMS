# Architecture

SQCCLIMS's backend is a small, dependency-free Python application organized into clear layers. This document describes those layers, the request lifecycle, the data model, and the cross-cutting infrastructure.

> For a per-module reference (responsibility, key functions, endpoints) see
> [`BACKEND_MODULES.md`](BACKEND_MODULES.md). For the deletion/data-safety policy
> see [`Data_Flow.md`](Data_Flow.md).

## Layered overview

```
        ┌─────────────────────────────────────────────┐
        │  HTTP layer        app/http/handler.py        │   AppHandler: parse, route, dispatch, respond
        └───────────────┬─────────────────────────────┘
                        │ calls feature handlers
        ┌───────────────▼─────────────────────────────┐
        │  Features          app/features/*.py          │   one module per domain area (API + service logic)
        └───────────────┬─────────────────────────────┘
                        │ calls data access + domain helpers
        ┌───────────────▼─────────────────────────────┐
        │  Domain / data     app/db.py, validation.py,  │   connections, parameterized SQL, validation,
        │                    errors.py, storage.py       │   filesystem storage, deletion audit
        └───────────────┬─────────────────────────────┘
                        │
        ┌───────────────▼─────────────────────────────┐
        │  Infra             config, migrations,        │   paths, schema, migrations, logging, backups, auth
        │                    logging_setup, backup, auth │
        └─────────────────────────────────────────────┘
```

**Dependency direction:** low-level ← features ← http. The HTTP layer imports features; features import db/validation/storage/errors; everything reads `app.config` for paths. There are no import cycles. Where a cycle would otherwise be needed (e.g. `db.record_deletion` needing `validation.now_iso`), it is broken with a **function-local import**.

### HTTP layer — `app/http/handler.py`

`AppHandler` (subclass of `http.server.BaseHTTPRequestHandler`) is the single entry point for every request. It parses the request, runs authorization, routes `/api/` paths to feature handlers and everything else to the static SPA, serializes JSON responses, streams file downloads (raw-data files, characterization files, outputs, templates, chart archives), and emits the access log. It contains **no business logic** — only transport concerns.

### Feature layer — `app/features/`

One module per domain area. Each module owns both its HTTP-facing handler functions and the service logic / SQL behind them. For the full module reference (domain + main endpoints) see [`BACKEND_MODULES.md`](BACKEND_MODULES.md#feature-layer-appfeaturespy).

### Domain / data-access layer

- `db.py` — `connect_db()` (opens SQLite with `Row` factory and PRAGMAs), `record_deletion()` (deletion-audit snapshots), schema-introspection helpers used by migrations.
- `validation.py` — input coercion/validation helpers (`require_text`, `optional_text`, `parse_float`, garbled-text detection), `now_iso()`, row-to-dict helpers, safe-path helpers.
- `errors.py` — domain exceptions (`ConflictError`, `AuthenticationError`, `AuthorizationError`) and the documented exception→status convention.
- `storage.py` — filesystem path resolution and safe storage of uploaded/generated files under the data directory.

### Infra layer

- `config.py` — runtime paths and shared constants; `configure_paths()` reassigns path globals at startup.
- `migrations.py` — `init_db()` (baseline schema) and `run_migrations()` (forward-only, checksum-guarded).
- `logging_setup.py` — rotating file + stderr logging on the `sqcclims` logger.
- `backup.py` — startup SQLite backup using the online-backup API, with retention pruning.
- `auth.py` — optional token auth + RBAC, off by default.

### Parsers — `parsers/`

Standalone parser/visualizer modules (`resistance_csv_parser.py`, `resistance_heatmap_visualizer.py`, `cd_template_parser.py`, `cd_violin_visualizer.py`) invoked by the `parsing`/`visualization` features. They convert raw files to records and produce chart artifacts under the outputs directory.

## Request lifecycle

Every request flows through `AppHandler.route()`: parse URL + query, run `authorize()` (a no-op unless auth is enabled), dispatch `/api/` paths through `handle_api()` to a feature handler (validation + parameterized SQL) and everything else to the static SPA, then serialize the JSON response. For the step-by-step lifecycle see [`BACKEND_MODULES.md`](BACKEND_MODULES.md#http-layer-apphttphandlerpy).

Two cross-cutting behaviors wrap the dispatch:

- **Access logging** — the `finally` block logs `METHOD PATH status=… duration_ms=…` for every request, regardless of outcome.
- **500 stack-trace logging** — the catch-all `except Exception` logs a full traceback via `logger.exception(...)` before returning a sanitized 500.

### Exception → HTTP status map

Feature code signals failures by raising exceptions; the handler maps them centrally (so handlers never build status codes by hand). For the canonical mapping table see [`CODE_PRINCIPLES.md#exception--http-status-mapping`](CODE_PRINCIPLES.md#exception--http-status-mapping).

## Data model

The schema is created in `init_db()` (`app/migrations.py`) and extended by the SQL files in `migrations/`. Core flow:

```
samples ─┬─ test_data
         ├─ process_records
         ├─ characterization_collections ── characterization_files
         ├─ performance_datasets ── performance_dataset_files
         └─ raw_data ── raw_data_files
                  └─ parsed_data ── parsed_records
                          └─ processing_jobs  (visualization / chart jobs)
```

- **samples** — the root entity. Identity is the composite (`sample_code`, `name`, `category`, `batch`) plus a generated, **unique** `sample_uid` (`SMP-YYYY-NNNNNN`; partial unique index `idx_samples_uid_unique`) and a unique `sample_display_code`.
- **test_data** — numeric metric records per sample.
- **process_records** — per (sample, stage, layer, record_no) process detail; unique on that tuple.
- **raw_data / raw_data_files** — a raw-data record and its uploaded files; `parser_status` tracks parse state.
- **parsed_data / parsed_records** — normalized parse output: `parsed_data` is the summary row, `parsed_records` are the per-measurement rows (resistance map cells / CD-SEM measurements), indexed for filtering by die/area and CD/SEM dimensions.
- **processing_jobs** — visualization/processing job rows linking raw/parsed/sample and recording inputs, outputs, status, and output artifacts.
- **characterization_collections / characterization_files** — grouped characterization uploads (images, spectra, reports).
- **performance_datasets / performance_dataset_files** — performance test datasets and their files.

### MES model (`migrations/002`, seeded by `003`)

- **mes_route_templates → mes_route_layers → mes_route_steps** — reusable route definitions (project → layers → steps).
- **mes_sample_routes → mes_sample_steps → mes_step_events** — a route instantiated for a sample, its per-step state, and an append-only event history as the sample advances.

### Audit

- **deletion_audit** (`migrations/004`) — every delete that goes through `record_deletion()` writes a JSON snapshot of the row plus table name, primary key, and timestamp, giving lightweight recoverability and an audit trail.
- **schema_migrations** — tracks applied migrations (version, filename, checksum, applied_at).

## Infrastructure details

- **SQLite WAL mode.** `connect_db()` opens each connection with `PRAGMA foreign_keys = ON`, `journal_mode = WAL`, `synchronous = NORMAL`, `busy_timeout = 5000` — concurrent reads during writes, with foreign keys enforced.
- **Startup backups.** `backup_database()` runs once at startup, copying the live DB into `data/backups/sample_testing_<timestamp>.db` via SQLite's online-backup API, retaining the **10** most recent and pruning the rest. Backup failure is logged and never blocks startup.
- **Deletion-audit snapshots.** Deletes capture a full row snapshot into `deletion_audit` before removal (see above).
- **Optional auth.** `auth.py` enforces token auth + RBAC only when `LIMS_AUTH_ENABLED` is truthy (and `LIMS_AUTH_DISABLED` is not). Default is OFF — `authorize()` is a no-op and the API behaves as if auth did not exist. Tokens come from `LIMS_API_TOKENS`; roles are admin/operator/viewer with GET≤operator-write≤admin-delete policy. All env vars are read at call time.
- **Logging.** `logging_setup.setup_logging()` configures the `sqcclims` logger with a rotating file handler (`data/logs/app.log`, 5 MB × 5) plus stderr; it is idempotent and must run after `configure_paths()`.

## Migration system

Forward-only and checksum-guarded (`app/migrations.py`, files in `migrations/`):

- Files are named `NNN_description.sql` with a monotonic numeric prefix and applied in order.
- Each applied file's SHA-256 is stored in `schema_migrations`. On startup, if a previously-applied file's checksum no longer matches, startup **aborts** — applied migrations must never be edited; add a new one instead.
- `run_migrations()` owns the transaction per file (statements split by `sqlite3.complete_statement`); don't put `BEGIN`/`COMMIT` in migration SQL.
- New schema changes belong in migration files, not in `init_db()` (which holds the historical baseline and compatibility logic).

See `migrations/README.md` for the full migration rulebook.
