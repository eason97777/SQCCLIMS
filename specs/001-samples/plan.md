# Implementation Plan: Samples

> As-built plan for the Samples feature. It documents **HOW** the feature in
> [`./spec.md`](./spec.md) is built — layer placement, the (baseline) data model,
> the API contracts, and the request flows — and proves constitutional
> compliance article-by-article. Because the feature already exists, this plan is
> a faithful description of the current implementation, not a forward proposal.

## Parent Spec

- **Spec:** [`./spec.md`](./spec.md)
- **Feature number:** 001
- **Status of spec:** Implemented (Approved baseline)

## Constitution Check

> Compliance with each Article of the
> [constitution](../../.specify/memory/constitution.md). Verdicts reflect the
> shipped code.

| Article | Verdict | Notes |
|---------|---------|-------|
| I — Zero runtime dependencies (stdlib backend) | PASS | Feature uses only `sqlite3` + stdlib; no backend deps added. |
| II — Layered architecture, one-way dependencies | PASS | `handler.py` (HTTP) → `features/samples.py` → `db`/`validation`/`deletion`/`backup`; no cycles. |
| III — One feature owns its domain | PASS | All sample logic + SQL lives in `app/features/samples.py`; `handler.py` only parses/routes/serializes. |
| IV — Data safety is non-negotiable | PASS | `delete_sample` calls `backup_database()` first, snapshots the row via `record_deletion`, cascades by DB FKs, and cleans files via centralized `app/deletion.py`. |
| V — Forward-only checksummed migrations | PASS | `samples` is part of the historical `init_db()` baseline; later identity changes (`sample_uid`, `sample_display_code`, composite/display unique indexes) are applied via the migration system, not by editing the baseline. |
| VI — Errors via exception convention | PASS | Raises `ValueError` (400) for invalid/duplicate input and `LookupError` (404) for missing samples; `route()` maps centrally. |
| VII — Parameterized SQL only | PASS | Every query uses `?`/named params; the only interpolation (`{where_sql}`) is a code-built clause with values still bound as params. |
| VIII — Runtime config read at call time | PASS | Paths resolved via `connect_db()` / `app.config` at call time; no import-time path binding in the feature. |
| IX — Smoke test is the green-light oracle | PASS | `tests/smoke_test.py` exercises create/list/update/delete-preview/delete for samples. |
| X — Simplicity over cleverness | PASS | No speculative abstraction; pagination, soft-delete, and a detail endpoint are deferred (documented). |
| XI — Optional-but-real auth & RBAC | PASS | Auth is a global no-op when disabled; when enabled, `authorize()` enforces `GET ≤ operator-write ≤ admin-delete` uniformly on `/api/` before dispatch. |

> No deviations. All rows PASS.

## Technical Context

- **Backend layer(s) touched:** HTTP (`app/http/handler.py`), Feature
  (`app/features/samples.py`), Domain/Data (`app/db.py`, `app/validation.py`,
  `app/deletion.py`, `app/backup.py`), Infra/Schema (`app/migrations.py`).
- **Frontend area(s):** `frontend/src/api/samplesApi.ts`,
  `frontend/src/types/sample.ts`, `frontend/src/pages/SamplesPage.tsx`.
- **Relevant references:** [`docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md),
  [`docs/BACKEND_MODULES.md`](../../docs/BACKEND_MODULES.md),
  [`docs/Data_Flow.md`](../../docs/Data_Flow.md),
  [`docs/Code_Structure.md`](../../docs/Code_Structure.md),
  [`docs/GLOSSARY.md`](../../docs/GLOSSARY.md).

## Architecture & Approach

The feature follows the project's thin-handler contract. `AppHandler.route()`
runs `authorize()`, then `handle_api()` matches the request to one of the sample
routes and calls a single function in `app/features/samples.py`, passing parsed
query params or JSON body. The feature module owns **all** business logic and
parameterized SQL:

- **Identity is server-owned.** `generate_sample_uid()` scans existing
  `SMP-{year}-` UIDs, takes the max numeric suffix, and returns the next
  zero-padded value (`{seq:06d}`) — gap-tolerant and year-scoped.
  `build_sample_display_code()` joins normalized `sample_code`, `name`,
  `category`, `batch` with `-` (empty parts become `-`).
- **Validation is layered.** `validate_sample_payload()` normalizes text, checks
  required fields, rejects garbled text / malformed sequence, builds the display
  code, and checks display-code uniqueness via SQL. `validate_sample_hierarchy()`
  additionally enforces name consistency across the same project number and the
  same project+process type. Both create and update run
  `validate_sample_hierarchy()`.
- **Reads are enriched.** `get_samples()` LEFT JOINs `test_data` to attach
  `data_count` and `last_measured_at`, builds an optional `WHERE` from query and
  status, and orders `created_at DESC, id DESC`.
- **Delete is Strong-tier.** `delete_sample()` snapshots the DB
  (`backup_database()`), collects descendant file paths and job-output paths
  *before* the row delete, records the sample row to `deletion_audit`, explicitly
  deletes `processing_jobs` (whose FK is `ON DELETE SET NULL`), deletes the
  sample row (DB cascades the rest), then removes the collected live-store files
  after commit. `sample_delete_preview()` is the read-only counterpart.

`handler.py` contains no sample business logic — only path matching, id
extraction, and `send_json` serialization.

## Data Model Changes

> The `samples` table is part of the **baseline** schema (in `init_db()`), not a
> new migration introduced by this plan. The identity columns and constraints
> that make the feature work were layered on via the migration system. No schema
> change is introduced *by this plan*; it documents the as-built model.

- **Baseline table:** `samples` (in `app/migrations.py` `init_db()`):
  `id`, `sample_uid`, `sample_display_code`, `sample_code`, `name`, `category`,
  `batch`, `owner`, `status` (default `待测试`), `received_at`, `notes`,
  `created_at`, `updated_at`, with `UNIQUE(sample_display_code)`.
- **Indexes / constraints (applied via migration helpers):**
  `idx_samples_identity_unique` on `(sample_code, name, category, batch)` and
  `idx_samples_display_code_unique` on `(sample_display_code)`; the legacy
  single-column `UNIQUE(sample_code)` is dropped/rebuilt by
  `ensure_samples_composite_unique()`.
- **Child FKs:** every child table references `samples(id)`; almost all are
  `ON DELETE CASCADE`. The two `ON DELETE SET NULL` exceptions
  (`processing_results.sample_id`, `processing_jobs.sample_id`) are handled
  explicitly by `delete_sample()` so nothing orphans.
- **Data-safety note:** sample delete = backup → audit snapshot → DB cascade →
  centralized live-file removal. See [`./data-model.md`](./data-model.md) and
  the per-entity table in [`docs/Data_Flow.md`](../../docs/Data_Flow.md).

## API Contracts

> Full request/response shapes in [`./contracts/samples-api.md`](./contracts/samples-api.md).
> Each relies on the exception→status mapping (Article VI).

| Method | Path | Purpose | Min role (if auth on) |
|--------|------|---------|-----------------------|
| GET | `/api/samples` | List samples (filter by `query`, `status`) | viewer |
| POST | `/api/samples` | Create a sample (201) | operator |
| PUT | `/api/samples/{id}` | Update a sample | operator |
| DELETE | `/api/samples/{id}` | Cascade-delete a sample (Strong tier) | admin |
| GET | `/api/samples/{id}/delete-preview` | Read-only cascade preview | viewer |
| GET | `/api/samples/{id}/mes-route` | Latest MES route for the sample | viewer |
| GET | `/api/samples/{id}/characterization-tree` | Characterization collections+files tree | viewer |

- Detailed contracts: [`./contracts/`](./contracts/)

## Affected Modules & Files

- **Feature:** `app/features/samples.py` — UID/display-code generation,
  validation, create/list/update, Strong-tier delete (handlers + SQL).
- **HTTP:** `app/http/handler.py` — dispatch entries for the 7 routes; id
  extraction; no business logic. (`/delete-preview`, `/mes-route`,
  `/characterization-tree` are matched before the generic `/api/samples/`
  PUT/DELETE branch.)
- **Domain/Infra:** `app/deletion.py` (`collect_sample_file_paths`,
  `collect_sample_job_output_paths`, `remove_files`, `sample_delete_preview`),
  `app/db.py` (`connect_db`, `record_deletion`), `app/validation.py`
  (text/normalization helpers), `app/backup.py` (`backup_database`).
- **Schema:** `app/migrations.py` — baseline `samples` table + identity index
  migrations.
- **Frontend:** `frontend/src/api/samplesApi.ts`,
  `frontend/src/types/sample.ts`, `frontend/src/pages/SamplesPage.tsx`.
- **Tests:** `tests/smoke_test.py` — sample CRUD + delete-preview + delete.

## Sequence / Flow

**Create (`POST /api/samples`):**

1. `route("POST")` → `authorize()` → `handle_api()` matches `/api/samples` →
   `create_sample(read_json())`.
2. `create_sample` builds the field dict (defaults: `status="待测试"`,
   timestamps via `now_iso()`).
3. `connect_db()` opens the connection; `validate_sample_hierarchy()` normalizes,
   checks required fields, garbled text, sequence format, builds + uniqueness-
   checks the display code, and enforces name consistency.
4. `generate_sample_uid(conn)` assigns the UID; parameterized `INSERT` runs (a
   DB `IntegrityError` on the unique display code is re-raised as `ValueError`).
5. The inserted row is re-selected and returned as JSON with status **201**.

**Strong-tier delete (preview-then-confirm):**

1. **Preview** — `GET /api/samples/{id}/delete-preview` →
   `sample_delete_preview(id)`: read-only; 404 if missing; returns per-category
   counts + `files_total`. Nothing is modified.
2. **Confirm** — `DELETE /api/samples/{id}` → `delete_sample(id)`:
   a. `backup_database()` snapshots the DB before the delete transaction.
   b. Open `connect_db()`; 404 (`LookupError`) if the sample is missing.
   c. Collect descendant file paths and `processing_jobs` output paths *before*
      deleting (the cascade would otherwise drop the rows pointing at them).
   d. `record_deletion(conn, "samples", row)` snapshots the row to
      `deletion_audit`.
   e. Explicitly `DELETE FROM processing_jobs WHERE sample_id = ?` (its FK is
      `SET NULL`), then `DELETE FROM samples WHERE id = ?` — the DB cascades all
      other children.
   f. After commit, `remove_files(...)` unlinks the collected live-store files
      (archive copies remain for recovery).
   g. Return `{"deleted": id}`.

## Risks & Trade-offs

- **No single-sample detail endpoint.** The frontend reads detail from the list
  response; a `GET /api/samples/{id}` is a known gap (frontend TODO). Low risk at
  current data volumes; revisit if the list grows or pagination lands.
- **No pagination.** `get_samples` returns the full filtered set. Acceptable for
  single-workstation lab volumes (Article X); a future risk at large scale.
- **`SET NULL` children need manual handling.** `processing_jobs` /
  `processing_results` are not cascaded by the DB; `delete_sample` deletes
  `processing_jobs` explicitly and collects its outputs. Any *new* `SET NULL`
  child of `samples` MUST be added to this delete path or it will orphan — this
  is a maintenance hazard called out in `app/deletion.py`.
- **Backup-before-delete cost.** `backup_database()` runs on every sample delete;
  acceptable given data-safety priority (Article IV) and expected delete cadence.

## Testing Approach

- **Baseline:** run `python3 tests/smoke_test.py` before any change to capture a
  green baseline (Article IX).
- **Coverage:** the smoke test creates a sample (asserts `sample_uid` shape and
  `sample_display_code`), lists with `query`/`status` filters, updates it,
  requests the delete-preview (asserts counts), and performs the cascade delete
  (asserts children/files gone and a `deletion_audit` row exists) — covering
  AC-001…AC-009.
- **Manual checks:** verify the delete-preview dialog in `SamplesPage.tsx` shows
  counts before the confirm, and that auth-enabled mode rejects a viewer DELETE
  with 403.
