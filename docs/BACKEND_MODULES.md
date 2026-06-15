# Backend Modules

A per-module reference for the SCRmonitor backend so a developer can understand
each module without reading source. Backend root:
`SCRmonitor/SCRmonitor/`.

For the layered design and request lifecycle see
[`ARCHITECTURE.md`](ARCHITECTURE.md). For the deletion/data-safety policy see
[`Data_Flow.md`](Data_Flow.md). To add an endpoint or migration see
[`../CONTRIBUTING.md`](../CONTRIBUTING.md).

**Layering (dependency direction):** low-level ← features ← http.
`http/handler.py` imports features; features import db / validation / storage /
errors / backup / deletion; everything reads `app.config` for paths at call
time.

---

## Entry: `server.py`

**Responsibility:** Thin entrypoint. Parses CLI args / environment and runs the
startup sequence before serving; contains no business logic.

**Startup sequence (in order):**
`configure_paths(data_dir)` → make data/upload/output/log dirs →
`setup_logging()` → `init_db()` → `run_migrations()` → `backup_database()` →
start `ThreadingHTTPServer(AppHandler)` → write `<data-dir>/server.pid` →
`serve_forever()`. On shutdown the pidfile is removed (a lingering pidfile after
a crash is acceptable — `restore_db.py` verifies the PID is alive).

**CLI / env:** `--host` (`JIQT_HOST`, default `0.0.0.0`), `--port` (`PORT`,
default `8000`), `--data-dir` (`JIQT_DATA_DIR`).

**Depends on:** `app.config`, `app.logging_setup`, `app.migrations`,
`app.backup`, `app.http.handler`.

---

## Low-level / data layer

### `app/config.py`
**Responsibility:** Runtime paths and shared constants. `configure_paths()`
reassigns the path globals at startup, so other modules must reference these as
attributes at call time (`config.DB_PATH`, never bind at import).
**Key:** `configure_paths(data_dir)` → set `DATA_DIR`, `DB_PATH`, `UPLOAD_DIR`,
`OUTPUT_DIR`, `LOG_DIR`, `ARCHIVE_DIR`. Constants: `STATIC_DIR`, `TEMPLATE_DIR`,
`MIGRATIONS_DIR`, `RAW_DATA_TYPES`, `ALLOWED_TEMPLATE_FILES`, `GARBLED_TEXT_MARKERS`,
`PARSED_RECORD_INSERT_COLUMNS`, `PARSED_RECORD_MAPPED_KEYS`.
**Used by:** every module.

### `app/errors.py`
**Responsibility:** Domain exceptions and the exception→HTTP status convention.
Feature code raises; the handler maps centrally.
**Key:** `ConflictError`, `AuthenticationError`, `AuthorizationError`.
**Status map:** `ValueError`→400, `AuthenticationError`→401,
`AuthorizationError`→403, `LookupError`→404, `ConflictError`→409, else→500.
**Used by:** features, http, auth.

### `app/validation.py`
**Responsibility:** Input coercion/validation, JSON helpers, safe-path helpers,
and timestamps. No DB or HTTP.
**Key functions:** `now_iso()` → UTC ISO timestamp; `row_dict`/`rows_dict` →
sqlite Row→dict; `require_text`/`optional_text` → required/optional field;
`parse_float`/`finite_float_or_none`/`to_float_or_none`/`int_or_none` → numeric
coercion; `has_garbled_text` → detect mojibake markers; `json_text`/`json_object`
→ validate/normalize JSON fields; `safe_path_parts`/`safe_path_part`/
`safe_download_name` → sanitize untrusted filenames; `parse_positive_int_param`/
`parse_optional_bool_param` → query-string coercion.
**Used by:** features, storage, archive, migrations.

### `app/db.py`
**Responsibility:** SQLite connections and shared DB helpers.
**Key functions:** `connect_db()` → open SQLite with `Row` factory + PRAGMAs
(`foreign_keys = ON`, `journal_mode = WAL`, `synchronous = NORMAL`);
`record_deletion(conn, table, row, pk_field)` → write a JSON row snapshot into
`deletion_audit`; `ensure_schema_migrations` / `table_columns` /
`add_column_if_missing` / `unique_index_columns` / `samples_has_legacy_code_unique`
/ `process_records_has_legacy_unique` → schema introspection used by migrations.
**Used by:** features, migrations, deletion, backup.

### `app/migrations.py`
**Responsibility:** Create the baseline schema and apply forward-only,
checksum-guarded SQL migrations.
**Key functions:** `init_db()` → create baseline tables/indexes, then run
`migrate_db()` compatibility fixups; `run_migrations()` → apply pending
`migrations/NNN_*.sql` in order, recording each file's SHA-256 in
`schema_migrations`; aborts if a previously-applied file's checksum changed.
Helpers: `migration_version`, `migration_checksum`, `iter_sql_statements`,
`migrate_db`, `ensure_samples_composite_unique`,
`ensure_process_records_instance_unique`, `ensure_characterization_collections`.
**Used by:** `server.py`. **Depends on:** `db`, `config`, `validation`.

### `app/storage.py`
**Responsibility:** Filesystem path resolution and safe storage of
uploaded/generated files under the data directory.
**Key functions:** `storage_path_for(path)` → relative storage key;
`resolve_data_path(storage_path)` → absolute path under the data dir;
`save_uploaded_file(...)` → write an upload (sanitized name + uuid prefix) and
return its metadata; `file_sha256(path)` → content hash; `remove_stored_path` →
delete a stored file/dir confined to the upload root;
`raw_data_upload_file_path`/`raw_data_file_path` → resolve+confine a raw-data
file path; `output_paths_from_job_output(output_json)` → extract chart/report
paths from a `processing_jobs` output blob; `relative_output_path`/
`output_url_for` → output path/URL helpers.
**Used by:** features, deletion, archive, handler.

---

## Infra layer

### `app/logging_setup.py`
**Responsibility:** Configure the `scrmonitor` logger (rotating file + stderr).
Idempotent; must run after `configure_paths()`.
**Key:** `setup_logging(level)` → install handlers (`data/logs/app.log`, 5 MB × 5);
`get_logger(name)` → package/child logger.
**Used by:** `server.py`, handler, backup, archive.

### `app/backup.py`
**Responsibility:** SQLite snapshots via the online-backup API. Never raises out
of startup or a delete.
**Key:** `backup_database(keep=10)` → copy live DB to
`data/backups/sample_testing_<timestamp>.db`, retain newest `keep`, prune rest.
**Used by:** `server.py` (startup) and strong-tier deletes in features.

### `app/archive.py`
**Responsibility:** Append-only, content-addressed upload archive. Every
uploaded file is copied in, keyed by SHA-256 (deduplicated). Best-effort —
failures are logged and never break an upload.
**Key:** `archive_file(src_path, sha256, original_filename, source)` → copy into
`ARCHIVE_DIR/<sha[:2]>/<sha><ext>`, append a record to `manifest.jsonl`.
**Used by:** the three upload endpoints (raw-data, performance, characterization).

### `app/auth.py`
**Responsibility:** Optional token auth + RBAC. **OFF by default** — `authorize`
is a no-op unless explicitly enabled; only `/api/` paths are guarded.
**Key functions:** `auth_enabled()` → read `JIQT_AUTH_ENABLED` /
`JIQT_AUTH_DISABLED` at call time; `token_store()` → parse `JIQT_API_TOKENS`
(`token:role,...`) into `{token: role}`; `authenticate(headers)` → role for the
request's bearer / `X-API-Key` token; `authorize(method, path, headers)` →
enforce per-method RBAC (GET≤viewer, POST/PUT/PATCH≤operator, DELETE=admin),
raising `AuthenticationError`/`AuthorizationError`.
**Used by:** `http/handler.route()`.
> The frontend sends no token and has no login UI, so enabling auth breaks the
> app today (every `/api/` call → 401). Keep it OFF until a login layer exists.

### `app/deletion.py`
**Responsibility:** Centralized file cleanup (the DB cascade can't touch files)
plus read-only cascade-preview helpers. Collect an entity's file paths **before**
the row delete, remove them **after** it succeeds; all removals are confined to
the upload/output roots.
**Key functions:**
- `collect_sample_file_paths(conn, sample_id)` → live-store paths owned by a
  sample (raw-data files, characterization files, performance files, parsed-data
  outputs).
- `collect_job_output_paths(job_rows)` → visualization output paths from
  `processing_jobs.output_json`.
- `collect_sample_job_output_paths(conn, sample_id)` → the sample's
  `processing_jobs` output paths.
- `remove_files(paths)` → unlink each existing path under the upload/output roots.
- `sample_delete_preview(sample_id)` → counts of child rows + total files.
- `raw_data_delete_preview(raw_data_id)` → files / parsed_data / parsed_records counts.
- `raw_data_file_delete_preview(file_id)` → what the single-file delete cascades.
- `performance_dataset_delete_preview(dataset_id)` → dataset file count.

**Used by:** features (`samples`, `raw_data`) for cleanup; preview helpers are
imported directly by `http/handler.py`.

---

## HTTP layer: `app/http/handler.py`

**Responsibility:** `AppHandler` (subclass of `BaseHTTPRequestHandler`) is the
single entry point for every request. Transport only — no business logic.

**Request lifecycle (`route(method)`):**
parse URL + query, start timer →
`authorize(method, path, headers)` (no-op unless auth enabled) →
if path starts with `/api/` call `handle_api(...)` (a large dispatch table → the
feature handler), else `serve_static(path)` (SPA fallback to `index.html`) →
`send_json(payload, status)` → **`finally`:** access-log
`METHOD PATH status=… duration_ms=…`.

**Exception → status:** a `try/except` chain maps `ValueError`→400,
`AuthenticationError`→401, `AuthorizationError`→403, `LookupError`→404,
`ConflictError`→409, and any other `Exception`→500 (logged with full traceback
via `logger.exception`).

**Key methods:** `handle_api` (route table), `read_json` / `read_multipart`
(parse bodies), `path_id` (extract numeric id), `send_json`, `serve_static`,
`serve_output`, `serve_template`, `send_raw_data_file`,
`send_characterization_file`, `send_visualization_chart_archive`,
`guess_content_type`.

**Depends on:** every feature module + `app.deletion` (preview endpoints) +
`storage`, `db`, `auth`, `errors`, `logging_setup`, `config`.

---

## Feature layer: `app/features/*.py`

One module per domain area. Each owns its HTTP-facing handlers and the SQL behind
them. The handler dispatches to the functions named below.

| Module | Domain | Main endpoints (→ handler) |
|--------|--------|----------------------------|
| `samples.py` | Samples (LIMS root): CRUD, UID generation, identity validation. | `GET /api/samples`→`get_samples`; `POST /api/samples`→`create_sample`; `PUT /api/samples/{id}`→`update_sample`; `DELETE /api/samples/{id}`→`delete_sample` |
| `test_data.py` | Numeric test-data records (single + bulk). | `GET /api/test-data`→`get_test_data`; `POST /api/test-data`→`create_test_data`; `POST /api/test-data/bulk`→`bulk_create_test_data`; `DELETE /api/test-data/{id}`→`delete_test_data` |
| `process_records.py` | Per-sample/layer process records; sample/field/layer lookups; auto-advances MES on submit. | `GET /api/process-records/sample-lookup`→`lookup_process_sample`; `…/sample-suggestions`→`search_process_samples`; `…/field-suggestions`→`search_process_field_suggestions`; `…/layers`→`search_process_layers`; `POST`/`PUT /api/process-records`→`save_process_record` |
| `mes.py` | MES route templates (layers, steps) and per-sample routes/steps/events. | `GET`/`POST /api/mes-route-templates`→`get_mes_route_templates`/`create_mes_route_template`; `…/by-project`→`get_mes_route_template_by_project`; `GET /api/mes-route-templates/{id}`→`get_mes_route_template_detail`; `POST …/{id}/layers`→`create_mes_route_layer`; `POST /api/mes-route-layers/{id}/steps`→`create_mes_route_step`; `PATCH`/`DELETE /api/mes-route-steps/{id}`→`update_mes_route_step`/`delete_mes_route_step`; `POST /api/mes-sample-routes`→`create_mes_sample_route`; `POST …/{id}/advance`→`advance_mes_sample_route`; `GET /api/samples/{id}/mes-route`→`get_mes_sample_route_by_sample` |
| `raw_data.py` | Raw-data records, multipart upload, file download/delete, cascade deletes. | `GET`/`POST /api/raw-data`→`get_raw_data_list`/`create_raw_data`; `GET`/`DELETE /api/raw-data/{id}`→`get_raw_data_detail`/`delete_raw_data`; `POST …/{id}/files`→`upload_raw_data_files`; `DELETE /api/raw-data-files/{id}`→`delete_raw_data_file`; `GET …/{id}/download`→handler. Helper `raw_data_file_row` |
| `parsing.py` | Parse raw files into `parsed_data`/`parsed_records`; list/detail/records/options; test-only mock. | `GET /api/parsed-data`→`get_parsed_data_list`; `GET …/{id}`→`get_parsed_data_detail`; `GET …/{id}/records`→`get_parsed_data_records`; `GET …/{id}/record-options`→`get_parsed_record_options`; `POST /api/raw-data/{id}/parse`→`parse_raw_data`; `POST /api/parsed-data/mock`→`create_mock_parsed_data` (gated, see note) |
| `visualization.py` | Resistance summary, parsed-data visualization, chart-archive download, processing jobs. | `POST /api/parsed-data/{id}/visualize`→`visualize_parsed_data`; `POST …/{id}/resistance-summary`→`get_resistance_summary`; `GET /api/processing-jobs`→`get_processing_jobs`; `GET /api/processing-jobs/{id}/charts/download`→handler. Helper `delete_output_files_for_jobs` |
| `characterization.py` | Characterization collections + files; preview/download; tree. | `GET`/`POST /api/characterization-files`→`get_characterization_files`/`create_characterization_files`; `GET`/`DELETE /api/characterization-files/{id}`→`get_characterization_file`/`delete_characterization_file`; `…/{id}/preview`,`…/{id}/download`→handler; `POST`/`GET /api/characterization-collections[/{id}]`→`create_characterization_collection`/`get_characterization_collection`; `GET /api/characterization/samples`→`get_characterization_samples`; `GET /api/samples/{id}/characterization-tree`→`get_characterization_tree` |
| `performance.py` | Performance datasets and their files. | `GET`/`POST /api/performance-datasets`→`get_performance_datasets`/`create_performance_dataset`; `GET …/{id}/files`→`get_performance_dataset_files`; `DELETE …/{id}`→`delete_performance_dataset` |
| `processing.py` | Generic processing jobs over test_data (stats/qc/normalize). | `POST /api/process`→`run_processing`; `GET /api/process-results`→`get_processing_results` |
| `summary.py` | Dashboard summary counts. | `GET /api/summary`→`get_summary` |

### Delete-preview endpoints (handler → `app/deletion.py`)
- `GET /api/samples/{id}/delete-preview` → `sample_delete_preview`
- `GET /api/raw-data/{id}/delete-preview` → `raw_data_delete_preview`
- `GET /api/raw-data-files/{id}/delete-preview` → `raw_data_file_delete_preview`
- `GET /api/performance-datasets/{id}/delete-preview` → `performance_dataset_delete_preview`

### Deletion behavior (exact)
- **`delete_sample`** — calls `backup_database()`, collects file paths
  (`collect_sample_file_paths` + `collect_sample_job_output_paths`) **before**
  the row delete, then `DELETE FROM processing_jobs WHERE sample_id = ?` and
  `DELETE FROM samples …` (children cascade), then `remove_files(...)` for both
  the entity files **and** the `processing_jobs` visualization outputs.
- **`delete_raw_data`** — calls `backup_database()`, collects `processing_jobs`
  output paths, then explicitly deletes `processing_jobs`, `parsed_records`,
  `parsed_data`, `raw_data` rows, then `remove_files(...)` incl. visualization
  outputs.
- **`delete_raw_data_file`** — takes a **per-delete `backup_database()`**;
  raises `ConflictError` (409) if the parent has more than one file; otherwise
  cascades the parent raw_data (`processing_jobs`/`parsed_records`/`parsed_data`)
  and removes the file plus visualization outputs via
  `delete_output_files_for_jobs`.

### Mock endpoint gating
`POST /api/parsed-data/mock` (`create_mock_parsed_data`) writes real
`parsed_data` rows from arbitrary client JSON. The handler **returns 404 unless
`JIQT_ENABLE_MOCK` is truthy** (`1`/`true`/`yes`/`on`). Keep it off in
production; it is for tests/fixtures only.

---

## Parsers: `parsers/`

Standalone parser/visualizer modules invoked by `parsing`/`visualization`. They
convert raw files to records and produce chart artifacts under the outputs dir.

| Module | Name / version | Does |
|--------|----------------|------|
| `resistance_csv_parser.py` | `resistance_csv_parser` 0.4.0 | Parse resistance CSV/XLSX into die/area/value `parsed_records` (die_id, area, row/col indices, numeric values). |
| `resistance_heatmap_visualizer.py` | `resistance_wafer_heatmap` 0.1.0 | Render a wafer heatmap PNG from resistance die summaries. |
| `cd_template_parser.py` | `cd_template_parser` 0.1.0 | Parse CD/SEM template CSV (row_group/side/direction/die_no/dose/cd_value) into `parsed_records`. |
| `cd_violin_visualizer.py` | `cd_violin_visualizer` 0.1.0 | Generate multi-chart CD/SEM violin plots (PNG) with parameterized x/y/hue/facet. |

---

## Scripts and tests

### `scripts/restore_db.py`
Restore the SQLite DB from a `backups/sample_testing_*.db` snapshot.
**Flags:** `--data-dir`, `--list`, `--latest`, `--file <name>`, `--yes`.
**Hardened:** refuses to run if a live server is detected via
`<data-dir>/server.pid` (verifies the PID is alive); always snapshots the
current non-empty live DB to `backups/pre_restore_<timestamp>.db` first
(aborts if that snapshot fails); copies the chosen snapshot over the live DB and
clears the `-wal`/`-shm` sidecars.

### `scripts/restore_file.py`
Recover an uploaded file from the content-addressed archive. Reads the
append-only `manifest.jsonl`; never modifies the archive.
**Flags:** `--data-dir`, `--list` (optionally `--name <substr>`),
`--sha <hash>`, `--name <filename>`, `--out <path|dir>`, `--force`.

### `scripts/cleanup_dev_orphans.py`
Dev maintenance: report (and with `--apply` delete) orphaned `raw_data`/upload
folders and dangling rows. Dry-run by default.

### `tests/smoke_test.py`
Regression smoke test. Boots the server against a throwaway temp data dir, waits
for `/api/summary`, exercises the key read endpoints plus a sample
create → delete-preview → delete round-trip, and exits non-zero on any
regression. Keep it green.

---

## How to extend

- **Add an endpoint:** implement the handler in the right `app/features/*.py`
  (validation + parameterized SQL via `connect_db()`), register a `method`/`path`
  branch in `handle_api()`, signal errors with exceptions, extend
  `tests/smoke_test.py`. See [`../CONTRIBUTING.md`](../CONTRIBUTING.md).
- **Add a migration:** create the next-numbered `migrations/NNN_*.sql` (plain
  SQL, no `BEGIN`/`COMMIT`); never edit an applied migration. See
  [`../CONTRIBUTING.md`](../CONTRIBUTING.md) and `migrations/README.md`.

---

## Environment variables

Matches the [`README.md`](../README.md) configuration table.

| Env var | Meaning | Default |
|---------|---------|---------|
| `JIQT_HOST` | bind host | `0.0.0.0` |
| `PORT` | bind port | `8000` |
| `JIQT_DATA_DIR` | runtime data directory | `SCRmonitor/data` |
| `JIQT_ARCHIVE_DIR` | append-only upload archive directory | `<data-dir>/archive` |
| `JIQT_AUTH_ENABLED` | turn token auth ON (truthy) | off |
| `JIQT_AUTH_DISABLED` | hard-override that keeps auth OFF | off |
| `JIQT_API_TOKENS` | `token:role,...` (roles: viewer/operator/admin) | empty |
| `JIQT_ENABLE_MOCK` | enable `POST /api/parsed-data/mock` (404 otherwise) | off |

> ⚠️ Do not enable `JIQT_AUTH_ENABLED` yet — the frontend sends no token and has
> no login UI, so auth makes every `/api/` call fail with 401.
