# Implementation Plan: Raw Data Upload, Parsing & Visualization

> As-built plan describing **HOW** the feature in [`spec.md`](./spec.md) is
> built. It passes the **Constitution Check** below
> ([constitution](../../.specify/memory/constitution.md)).

## Parent Spec

- **Spec:** [`./spec.md`](./spec.md)
- **Feature number:** 002
- **Status of spec:** Implemented (this is a retroactive as-built record)

## Constitution Check

| Article | Verdict | Notes |
|---------|---------|-------|
| I — Zero runtime dependencies (stdlib backend) | PASS | Backend record/upload/parse/serve path is pure stdlib (`http.server`, `sqlite3`, `csv`, `cgi`, `hashlib`, `zipfile`). The **only** third-party use is chart rendering (matplotlib) and optional XLSX reading (openpyxl), both confined to `parsers/` and treated as the approved, vetted exception; openpyxl is optional and absence degrades gracefully (clear error asking for CSV). No web framework, ORM, or chart lib in `app/`. |
| II — Layered architecture, one-way dependencies | PASS | `handler.py` (HTTP) imports `app/features/*`; the feature modules import only infra/domain (`db`, `validation`, `storage`, `archive`, `deletion`, `backup`, `errors`, `config`) and `parsers/*`. `visualization.py` and `parsing.py` import helpers from each other / `raw_data.py` within the same Features layer (no cross-layer reversal); the one Features→Features call from `raw_data.delete_raw_data_file` into `visualization.delete_output_files_for_jobs` is a **function-local import** to avoid a cycle. No infra module imports a feature or HTTP. |
| III — One feature owns its domain | PASS (with note) | This feature is split across three modules — `raw_data.py` (record + file lifecycle), `parsing.py` (parse → parsed_data/parsed_records), `visualization.py` (summary, charts, jobs) — rather than one. This honors the *spirit* of Article III: the split is by **distinct lifecycle stage of one cohesive domain** (the raw-data lifecycle), each module is a single owner of its stage with its own handler functions + parameterized SQL, and `handler.py` stays thin (pure parse/route/dispatch/serialize, no business logic). The boundary that Article III guards — logic leaking into the router, or unclear ownership — is not crossed: each stage has exactly one owning module. A single 1,000-line module would be *less* legible and would violate Article X (simplicity). See note below. |
| IV — Data safety is non-negotiable | PASS | Every delete is Strong-tier: `delete-preview` endpoints report blast radius without deleting; `backup_database()` precedes each destructive op; `record_deletion()` snapshots the removed row into `deletion_audit`; child rows cascade (`ON DELETE CASCADE`), `processing_jobs` (`ON DELETE SET NULL`) are deleted explicitly; file cleanup is centralized in `app/deletion.py` / `visualization.delete_output_files_for_jobs`, root-confined to the upload/output dirs. Uploads are archived append-only at write time. Matches [`docs/Data_Flow.md`](../../docs/Data_Flow.md). |
| V — Forward-only checksummed migrations | PASS (N/A for new SQL) | These tables (`raw_data`, `raw_data_files`, `parsed_data`, `parsed_records`, `processing_jobs`) are part of the **historical baseline** in `init_db()`; `migrate_db()` adds the later columns (`parsed_data.record_count`, `parsed_data.updated_at`) idempotently via `add_column_if_missing`. No applied migration file is edited. Any *future* schema change to this feature MUST be a new `migrations/NNN_*.sql` (checksum-guarded), never an edit to `init_db()`. |
| VI — Errors via exception convention | PASS | Feature code raises `ValueError` (bad input / unsupported type / parse failure), `LookupError` (missing record/file/job), `ConflictError` (multi-file single-file delete). `handler.route()` maps them to 400/404/409. No hand-built status codes in features. |
| VII — Parameterized SQL only | PASS | All queries use `?` / named params; the only interpolation is trusted, code-built identifiers (e.g. `config.PARSED_RECORD_INSERT_COLUMNS` column lists, fixed WHERE-clause fragments) — never request data. Filter values are always bound. |
| VIII — Runtime config read at call time | PASS | Modules `import app.config as config` and read `config.UPLOAD_DIR` / `config.OUTPUT_DIR` / `config.DATA_DIR` / `config.RAW_DATA_TYPES` at call time, honoring `configure_paths()`. No import-time path binding. |
| IX — Smoke test is the green-light oracle | PASS | `tests/smoke_test.py` exercises the create → upload → parse → records/options → resistance-summary → visualize → download → delete path against a temp DB; it is the authoritative signal and must stay green. |
| X — Simplicity over cleverness | PASS | Synchronous parse/visualize (no queue), points exploded into rows rather than a clever inline blob, summary computed on demand. Deferred items (multi-file precise delete, soft delete, async jobs) stay deferred and are called out in the spec's Out of Scope. |
| XI — Optional-but-real auth & RBAC | PASS | `authorize()` gates all `/api/` paths uniformly; when auth is disabled it is a true no-op. When enabled: GET reads ≤ operator writes (create/upload/parse/visualize) ≤ admin deletes. No half-built auth in this feature. |

> **Article III note (accepted, not a deviation).** "One feature = one module" is
> satisfied *per lifecycle stage*. The raw-data domain is one cohesive lifecycle
> with three clear stages (ingest, parse, visualize), each owned by exactly one
> module; ownership is unambiguous and no logic lives in the router. Collapsing
> them into a single module would harm legibility and simplicity (Article X)
> without improving ownership clarity. This is the intended reading of Article III
> for a multi-stage domain, so it is recorded as PASS, not DEVIATION.

## Technical Context

- **Backend:** Python 3 stdlib HTTP server (`app/http/handler.py`) + `sqlite3`
  (single file under the data dir). Feature logic in `app/features/`.
- **Parsers/visualizers:** plain functions in `parsers/` invoked by the feature
  layer; visualizers use matplotlib (`Agg` backend) — the approved chart-lib
  exception to Article I.
- **Storage:** uploads under `config.UPLOAD_DIR/raw_data/<raw_data_code>/`;
  generated charts under `config.OUTPUT_DIR/visualizations/...`; append-only
  content-addressed archive under `config.ARCHIVE_DIR`.
- **Frontend:** React/TypeScript SPA (`frontend/src/pages/RawDataPage.tsx` +
  `frontend/src/api/rawDataApi.ts` + `frontend/src/types/rawData.ts` + rawData
  components) consuming the JSON/multipart API.

## Architecture & Approach

End-to-end flow:

1. **Create record** — `create_raw_data` validates the data type against
   `config.RAW_DATA_TYPES`, derives the category, generates a unique
   `raw_data_code` (`RD-<uid>-<TYPE>-<date>-<seq>`), inserts the `raw_data` row.
2. **Upload + store + checksum + archive** — `upload_raw_data_files` reads the
   multipart parts (`handler.read_multipart` via `cgi.FieldStorage`), writes each
   file under the record's directory with a UUID-prefixed name, computes SHA-256,
   copies the bytes into the append-only archive (`archive.archive_file`), inserts
   a `raw_data_files` row, and updates `file_count`/`total_size`.
3. **Parse** — `parse_raw_data` selects the parser by data type
   (`resistance_csv_parser` for resistance, `cd_template_parser` for cd_sem),
   picks the highest-priority parseable file (xlsx>csv for resistance), records a
   `processing_jobs` row, runs the parser, and on success calls
   `insert_parsed_data` → one `parsed_data` row + bulk `parsed_records` (exploded
   via `insert_parsed_records`, columns from `config.PARSED_RECORD_INSERT_COLUMNS`).
   Parser status transitions are persisted at each step; failures mark
   `parse_failed` and the job `failed`.
4. **Browse normalized records** — `get_parsed_data_records` /
   `get_parsed_record_options` build parameterized WHERE clauses from query
   filters and page the results.
5. **Summary + visualize** — `get_resistance_summary` cleans/classifies points and
   computes per-die/per-area/overall stats on demand;
   `create_resistance_visualization_job` and `visualize_parsed_data` (CD violin)
   write artifacts under `OUTPUT_DIR`, record a `processing_jobs` row, and return
   it with chart/report URLs.
6. **Download** — the **thin handler** streams files: `send_raw_data_file`
   (original upload), `serve_output` (generated artifacts),
   `send_visualization_chart_archive` (selected charts zipped via
   `get_visualization_chart_archive`).
7. **Delete (preview → cascade)** — preview endpoints
   (`raw_data_delete_preview`, `raw_data_file_delete_preview`) report blast
   radius; `delete_raw_data` / `delete_raw_data_file` back up, audit-snapshot,
   cascade rows, and centrally remove files + outputs.

## Data Model Changes

No new schema for this as-built record — the tables are the historical baseline
in `init_db()` (`raw_data`, `raw_data_files`, `parsed_data`, `parsed_records`,
`processing_jobs`), with `migrate_db()` having backfilled `parsed_data.record_count`
and `parsed_data.updated_at` idempotently. Full column/relationship/cascade
detail: [`./data-model.md`](./data-model.md).

## API Contracts

Full per-endpoint detail: [`./contracts/raw-data-api.md`](./contracts/raw-data-api.md).

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/raw-data` | list/filter records |
| POST | `/api/raw-data` | create record |
| GET | `/api/raw-data/{id}` | record detail + files |
| DELETE | `/api/raw-data/{id}` | Strong cascade delete |
| GET | `/api/raw-data/{id}/delete-preview` | delete blast radius |
| POST | `/api/raw-data/{id}/files` | upload files (multipart) |
| POST | `/api/raw-data/{id}/parse` | parse record |
| GET | `/api/raw-data-files/{id}/download` | download original file |
| DELETE | `/api/raw-data-files/{id}` | delete single file (Strong) |
| GET | `/api/raw-data-files/{id}/delete-preview` | single-file blast radius |
| GET | `/api/parsed-data` | list parsed datasets |
| GET | `/api/parsed-data/{id}` | parsed dataset detail |
| GET | `/api/parsed-data/{id}/records` | paged/filtered normalized records |
| GET | `/api/parsed-data/{id}/record-options` | distinct filter options |
| POST | `/api/parsed-data/{id}/resistance-summary` | compute resistance summary |
| POST | `/api/parsed-data/{id}/visualize` | render heatmap / violin |
| GET | `/api/processing-jobs` | list parse/viz jobs |
| GET | `/api/processing-jobs/{id}/charts/download` | zip of selected charts |
| GET | `/api/outputs/{path}` | stream a generated artifact |

## Affected Modules & Files

This feature spans **three** Features-layer modules plus parsers (see Article III
note above):

- [`app/features/raw_data.py`](../../app/features/raw_data.py) — record + file
  lifecycle, multipart upload, Strong-tier deletes.
- [`app/features/parsing.py`](../../app/features/parsing.py) — parse orchestration,
  parsed_data/parsed_records insertion, record paging/options.
- [`app/features/visualization.py`](../../app/features/visualization.py) —
  resistance summary, heatmap/violin jobs, chart-archive download, job listing,
  output-file cleanup.
- [`parsers/resistance_csv_parser.py`](../../parsers/resistance_csv_parser.py),
  [`parsers/resistance_heatmap_visualizer.py`](../../parsers/resistance_heatmap_visualizer.py),
  [`parsers/cd_template_parser.py`](../../parsers/cd_template_parser.py),
  [`parsers/cd_violin_visualizer.py`](../../parsers/cd_violin_visualizer.py).
- Infra used: [`app/storage.py`](../../app/storage.py),
  [`app/archive.py`](../../app/archive.py),
  [`app/deletion.py`](../../app/deletion.py),
  [`app/backup.py`](../../app/backup.py),
  [`app/db.py`](../../app/db.py),
  [`app/validation.py`](../../app/validation.py),
  [`app/config.py`](../../app/config.py).
- HTTP: [`app/http/handler.py`](../../app/http/handler.py) (dispatch + streaming).
- Frontend: `frontend/src/pages/RawDataPage.tsx`,
  `frontend/src/api/rawDataApi.ts`, `frontend/src/types/rawData.ts`, and the
  `ParsedDataRecordsTable` / `ResistanceSummaryPanel` /
  `ResistanceVisualizationPanel` / `ResistanceWaferHeatmap` /
  `VisualizationPreviewPanel` components.

## Sequence / Flow

**Upload.** `POST /files` → `read_multipart` → per file: `save_raw_data_file`
(write + sha256) → `archive_file` (append-only copy) → insert `raw_data_files` →
recompute `file_count`/`total_size`.

**Parse.** `POST /parse` → set `parsing` → insert running `processing_jobs` →
pick parseable file → run parser → `insert_parsed_data` (+ exploded
`parsed_records`) → update job `success` + record `parsed`. On any failure: job
`failed`, record `parse_failed`, raise.

**Visualize.** `POST /visualize` → insert running job → write artifacts under
`OUTPUT_DIR` → update job `success` with chart/report URLs (or `failed`). Charts
streamed via `/api/outputs/...` or zipped via `/charts/download`.

**Delete (preview → cascade).** `GET /delete-preview` → count children + files,
delete nothing. `DELETE` → `backup_database()` → collect file/output paths →
`record_deletion()` audit → delete `processing_jobs`/`parsed_records`/
`parsed_data`/record (or single file's cascade) → remove on-disk files, storage
dir, and outputs (root-confined).

## Risks & Trade-offs

- **Large files / memory.** Multipart parsing reads file content into memory
  (`cgi.FieldStorage` → `item.file.read()`); very large uploads pressure memory.
  Acceptable at lab volume; streaming upload is a future option.
- **Parser failures.** Strict validation rejects malformed matrices/templates
  with row-precise messages and marks the record `parse_failed` rather than
  inserting partial records — safer, but requires the user to fix and re-parse.
- **Synchronous visualization.** Chart rendering (matplotlib) runs inside the
  request; a heavy render blocks that request. Acceptable for single-workstation
  use; no job queue by design (Article X).
- **Disk growth.** The append-only archive plus generated outputs accumulate;
  deletes remove live files but the archive is immutable by design
  (recoverability over space). Disk hygiene is operational.
- **XLSX dependency.** Resistance XLSX parsing needs openpyxl; if absent the
  parser errors clearly and asks for CSV — no hard failure, but a capability gap.

## Testing Approach

`tests/smoke_test.py` is the oracle (Article IX): boot against a temp DB, create
a sample + raw_data record, upload a fixture file, parse it, page the normalized
records and options, compute a resistance summary, render a visualization,
download artifacts, and delete with preview — asserting status codes and that the
cascade leaves no orphaned rows or files. Any endpoint change here extends the
smoke test before it is considered done.
