# Implementation Plan: Domain Model Reform — Sample-Rooted Two-Axis Model

> **HOW** the reform in [`spec.md`](./spec.md) is built: the target architecture,
> the phased non-destructive roadmap, per-phase migrations, back-compat, and
> testing. This plan MUST pass the Constitution Check below before any task is
> executed.
>
> **This plan is a Draft blueprint.** It documents *how* the reform would be
> built if approved; it does not authorize writing code. Every phase is
> independently shippable, forward-only, and leaves the smoke test green.

## Parent Spec

- **Spec:** [`./spec.md`](./spec.md)
- **Feature number:** 004
- **Status of spec:** **Draft** — human approval required before any phase
  begins. (Approved is required before implementation of any phase.)
- **Companion review (north-star):** [`../../docs/DOMAIN_MODEL.md`](../../docs/DOMAIN_MODEL.md)

## Constitution Check

> Compliance with all 11 Articles of the
> [constitution](../../.specify/memory/constitution.md).

| Article | Verdict | Notes |
|---------|---------|-------|
| I — Standard-library backend core, one sanctioned dependency boundary | **PASS** | The `measurements` and `artifacts` views are pure `sqlite3`; the legacy-route redirects are frontend-only (React Router). No third-party import enters `app/**` or `server.py`. Visualization keeps its existing matplotlib use confined to `parsers/`; this reform does not add any dependency. |
| II — Layered architecture, one-way dependencies | **PASS** | The views are read inside feature modules (`processing.py` for `measurements`; `raw_data.py`'s list query for `artifacts`); `handler.py` gains no new logic (legacy-route redirects are frontend-only). No infra module imports a feature; no new cycles. |
| III — One feature owns its domain | **PASS (with justification)** | The reform *consolidates* how features are grouped in the UI, but the backend keeps one module per domain (`raw_data`, `test_data`, `processing`, `performance`, `parsing`). Performance is *surfaced* alongside `raw_data` via the shared `artifacts` read model — its own module still owns writes/deletes — so this is improved UI cohesion, **not** spreading a feature across modules. The `measurements` and `artifacts` views are shared read infrastructure consumed by existing feature modules, not new competing owners. See "Article III note" below. |
| IV — Data safety is non-negotiable | **PASS** | **No phase moves or deletes data** — both Measurements (Phase 1) and Artifacts (Phase 2) are additive read-model views over existing tables, so no pre-migration snapshot is needed. No new deletable entity is introduced: performance-origin artifacts keep deleting via the existing `delete_performance_dataset` path, raw_data-origin via `delete_raw_data` (both already do `backup_database()` + `ON DELETE CASCADE` + `deletion_audit`). Because nothing is copied, there is **no shared-file / double-delete hazard**. |
| V — Forward-only, checksum-guarded migrations | **PASS** | Every schema change is a **new** `migrations/NNN_*.sql`, and each is a single additive `CREATE VIEW` (the `measurements` view in Phase 1; the `artifacts` view in Phase 2). No applied file is edited; `init_db()` baseline is untouched. Migration SQL contains no `BEGIN`/`COMMIT`. |
| VI — Errors via the exception convention | **PASS** | No new hand-built status codes. Feature code reading the view continues to raise `ValueError` / `LookupError`; redirects are transport-level and do not bypass the central mapping. |
| VII — Parameterized SQL only | **PASS** | The view definition uses only fixed, code-authored column lists — including the parsed-row `metric_name` `CASE` derivation (per-`data_type` composition of `side`/`direction`/`row_group`) — with **no request data** interpolated. Feature queries against the view continue to use `?`/named parameters exactly as today. |
| VIII — Runtime config read at call time | **PASS** | No path binding changes; any new code reads `config.<NAME>` at call time. The view migrations reference no runtime path (pure SQL). |
| IX — The smoke test is the green-light oracle | **PASS** | Each phase records a baseline `python3 tests/smoke_test.py`, then extends it: Phase 1 asserts view-backed Analysis sees both sources; Phase 2 asserts performance is queryable via the `artifacts` view and the frontend legacy route resolves; Phase 3 asserts the Analysis nav grouping and the `/processing` redirect. |
| X — Simplicity over cleverness | **PASS (honest transitional cost)** | The end state is *simpler* (one Measurements concept, one Artifact concept). Transitionally the system carries a dual-read (each view UNIONs two tables) and, for Artifacts, delete/write must route to the correct backing table by `source`. This is real added complexity, deliberately **bounded by phasing**. We do **not** copy performance rows/files or build a physical unified table speculatively (both deferred), so there is no dual-store to reconcile. |
| XI — Optional-but-real auth & RBAC | **PASS** | Relabelled and redirected routes preserve the existing `GET ≤ operator-write ≤ admin-delete` policy and remain a true no-op when auth is disabled. No auth code changes. |

**Article III note (justification, not deviation).** Article III forbids a single
*feature* being spread across multiple modules. This reform does the opposite: it
*increases* cohesion by presenting all file Artifacts (raw-data + performance)
under one concept and all measurements under one concept. The two read models
(`measurements`, `artifacts`) are **not** feature modules — they are shared read
infrastructure (like an index), consumed by existing feature owners; the backing
tables and their write/delete owners (`raw_data`, `performance`, `test_data`,
`parsing`) are unchanged. No feature's logic is scattered. Recorded here so
reviewers see it was considered.

> No row is a DEVIATION. Two rows carry explicit justifications (III, X) that a
> human reviewer must accept as part of approving this Draft.

## Technical Context

- **Backend layer(s) touched:**
  - **Migrations** — one new file for the `measurements` view (Phase 1); one new
    file for the `artifacts` view (Phase 2). Both migrations are additive
    `CREATE VIEW`; no data moves.
  - **Feature modules** — `app/features/processing.py` (repoint its source query
    from `test_data` to the `measurements` view, and emit `source` +
    `source_row_id` in QC/normalize output instead of the now-ambiguous `id`);
    `app/features/raw_data.py` (Artifact **list** query reads the `artifacts`
    view; detail/files/delete stay per-source) / `app/features/performance.py`
    (the standalone performance create path is reframed to write `raw_data`
    going forward). `visualization.py` is **untouched** (FR-007 deferred).
  - **HTTP** — `app/http/handler.py` is **unchanged** for routing; legacy-route
    redirects are frontend-only (React Router). No business logic added.
  - **db / validation / storage / deletion** — unchanged; performance-origin
    artifacts keep their existing `delete_performance_dataset` path and
    raw_data-origin their `delete_raw_data` path (routed by `source`). Nothing is
    copied, so no shared-file cleanup change.
- **Frontend area(s):**
  - `frontend/src/utils/constants.ts` — `NAV_ITEMS` + `VIEW_META` relabel and
    regroup (Phases 0/3).
  - `frontend/src/router/index.tsx` — keep legacy paths as redirects/aliases.
  - `frontend/src/pages/*` — Measurements label, Analysis grouping, performance
    presented as an artifact type.
- **Relevant references:**
  [`../../docs/DOMAIN_MODEL.md`](../../docs/DOMAIN_MODEL.md) (north-star review),
  [`../../docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md),
  [`../../docs/BACKEND_MODULES.md`](../../docs/BACKEND_MODULES.md),
  [`../../docs/Data_Flow.md`](../../docs/Data_Flow.md),
  [`../../docs/Code_Structure.md`](../../docs/Code_Structure.md).

## Architecture & Approach

**Root = Sample. Two orthogonal axes replace the flat block list.**

**Axis A — Storage entities (two kinds).**
- **Artifacts** = files attached to a sample, discriminated by `type`. `raw_data`
  already *is* the general Artifact store: it has `data_type`, a files child
  (`raw_data_files`), and an optional parse pipeline (`parsed_data` /
  `parsed_records`). The reform introduces an **`artifacts` read model first**: a
  SQL VIEW `artifacts` that UNIONs `raw_data` and `performance_datasets` (mapped
  to `data_type='performance'`, files-only, no parser), so performance shows up in
  the unified Artifacts **list** with **no data migration**. The view backs the
  list only; detail/files/delete stay on the existing per-source endpoints,
  routed by `source`. New performance uploads are reframed to write `raw_data`
  going forward; a physical consolidation is a later, optional step (out of
  scope). Characterization stays a separate store (deferred).
- **Measurements** = numeric points about a sample, discriminated by `source`.
  The reform introduces a **read model first**: a SQL VIEW `measurements` that
  UNIONs `test_data` (`source='manual'`) and `parsed_records`
  (`source='parsed'`) exposing common columns (sample identity, metric name,
  numeric value, unit, measured-at, source). This lets transforms operate over
  *all* measurements with **no data migration**. A physical unified table is a
  later, optional step (out of scope).

**Axis B — Transforms as capabilities (apply across Measurements).**
- `parse`: Artifact file → parsed Measurements (exists, unchanged).
- `analyze`/`process`: Measurements → stats/QC/normalize. Target (Phase 1): read
  the `measurements` view (both sources), not only `test_data`.
- `visualize`: Measurements → charts. **Deferred (FR-007)** — its charts need
  per-record layout columns the scalar view omits, so it keeps sourcing
  `parsed_records` in this reform.

**Thin-handler contract preserved.** `handler.py` continues to parse/route/
serialize only. The source-of-truth change (read `measurements` instead of
`test_data`) happens inside `processing.py`'s `fetch_processing_source()`; the
handler is unaware. Legacy-route redirects live entirely in the frontend router,
so `handler.py` needs no change at all.

**Data flow (unchanged in shape) for Analysis after Phase 1:**
`POST /api/process` → `run_processing()` → `fetch_processing_source(conn)`
(now `SELECT … FROM measurements …`) → stats/QC/normalize → `processing_results`.

## The Phased, Non-Destructive Roadmap

Each phase is independently shippable, forward-only, and smoke-green.

### Phase 0 — Naming / clarity (ZERO schema)

- Relabel "Data Base" → **"Measurements / 测试结果"** in
  `frontend/src/utils/constants.ts` (`NAV_ITEMS` label for `/test-data`, and the
  `VIEW_META["/test-data"]` / `["/data"]` `eyebrow`/`title`).
- **Reframe the manual test-data entry form as "Add a measurement"** under the
  Measurements / 测试结果 area (FR-002b). This is a **frontend/UX/label change
  only**: the backend write path is untouched — `create_test_data` and the bulk
  create still write to `test_data` as `source='manual'`, and no physical unified
  table is introduced. Non-destructive. (The label/framing lands here in Phase 0;
  the full Measurements grouping is completed with the nav regroup in Phase 3.)
- Disambiguate the three "processing" meanings in UI copy + docs:
  - present `processing_jobs` as the **"parse / visualization job log"** of Raw
    Data (it already only logs `parse` and `visualization` job types — see
    `parsing.py` / `visualization.py`);
  - present the Analysis block (route `/processing`, endpoint `/api/process`) as
    **"Analysis"**;
  - leave `process_records` as **工艺记录 / MES traveller**.
- **Migration:** none. **Back-compat:** trivially reversible (copy only).
- **Testing:** run the smoke test; assert `schema_migrations` is unchanged.

### Phase 1 — Measurements read model

- Add the `measurements` SQL VIEW via a **new** forward-only migration (additive,
  non-destructive). See [`data-model.md`](./data-model.md) for the exact SQL. The
  view derives the parsed-row `metric_name` per `data_type` via a pure-SQL `CASE`
  (composing `side`/`direction`/`row_group` for `cd_sem`; literal `'resistance'`;
  else `data_type`) and keeps `data_type` as its own column (RC-2). This adds a
  little view complexity but remains code-authored SQL with no request data
  (Article VII PASS).
- Repoint `processing.py`'s `fetch_processing_source()` to `SELECT … FROM
  measurements` so Analysis also sees parsed data. `run_stats` is unchanged
  (reads `metric_name`/`unit`/`numeric_value`). `run_qc` and `run_normalize`
  currently emit `row["id"]`, which the view does **not** expose (it exposes
  `source_row_id` + `source`, because `test_data.id` and `parsed_records.id`
  overlap); repoint those two to emit `source` + `source_row_id` instead. The
  frontend `ProcessingResultViewer` ignores that field today, so this is
  consumer-invisible; the added `source` also appears in the API contract.
- Extend the smoke test: seed a sample with one manual `test_data` row and one
  parsed record; assert Analysis `source_count` covers both.
- **Migration:** `migrations/NNN_measurements_view.sql` (view only).
- **Back-compat:** the view is read-only and additive; `test_data` writes are
  untouched. **No data moves.**

### Phase 2 — Artifacts read model

- Add one `artifacts` VIEW via a **new** forward-only migration, mirroring
  Phase 1. `artifacts` UNIONs `raw_data` with `performance_datasets` mapped to
  `raw_data`'s shape (`data_type='performance'`, synthesized `artifact_code`,
  `total_bytes→total_size`, `storage_dir→storage_path`, `collected_at→
  measured_at`, and `aliquot_code`/`test_type`/`data_format`/`source_folder_name`
  folded into `metadata_json` via `json_object`); it carries `source` +
  `source_row_id` (since `raw_data.id` and `performance_datasets.id` overlap).
  Exact SQL and mappings in [`data-model.md`](./data-model.md). **No data moves.**
- **No backup needed** (Article IV): the view reads the source tables in place;
  nothing is copied, moved, or deleted, so no shared-file / double-delete hazard.
- Repoint the Artifact **list** read (`get_raw_data_list`) at the `artifacts`
  view; leave detail / files / download / delete on the existing per-source
  endpoints unchanged (the frontend routes by `source`). Reframe the performance
  **create** path to write `raw_data` (`data_type='performance'`) going forward.
  The existing performance API endpoints stay live over the retained tables (see
  [`contracts/routes-and-api.md`](./contracts/routes-and-api.md)).
- Legacy-route redirects (`/performance-datasets`, `/performance`) are
  **frontend-only** (React Router), following the existing `/data`, `/performance`
  alias precedent. No backend redirect.
- Frontend shows performance as an artifact type under Raw Data / Artifacts.
- **Migration:** `migrations/NNN_artifacts_view.sql`.
- **Testing:** assert performance rows are queryable via the `artifacts` view
  with `data_type='performance'`; assert `/performance-datasets` resolves via the
  frontend redirect; smoke-green.

### Phase 3 — Transforms unification (nav only)

- Reposition Processing as a general **Analysis** transform and unify the nav
  "Analysis" area (Analyze/Process, with Visualization as a navigational grouping
  only). **Visualization-over-the-read-model is deferred (FR-007)** — its charts
  need layout columns the scalar view omits, so it keeps sourcing `parsed_records`
  and its behavior is unchanged.
- Add the `/processing` → Analysis **frontend** redirect/alias (see
  [`contracts/routes-and-api.md`](./contracts/routes-and-api.md)).
- **Migration:** none.
- **Testing:** assert the Analysis nav grouping + the `/processing` frontend
  redirect resolve; smoke-green.

## Data Model Changes

- **Phase 1 migration** — `migrations/NNN_measurements_view.sql`: `CREATE VIEW
  measurements AS SELECT … FROM test_data UNION ALL SELECT … FROM parsed_records`.
  Read-only; no tables/rows altered.
- **Phase 2 migration** — `migrations/NNN_artifacts_view.sql`: `CREATE VIEW
  artifacts AS SELECT … FROM raw_data UNION ALL SELECT …(mapped)… FROM
  performance_datasets JOIN samples`. Read-only; no tables/rows/files altered.
  (No `artifact_files` view — file listing stays per-source.)
- **Data-safety note:** neither view introduces a deletable entity. Nothing is
  copied, so a physical file is referenced by exactly one row/owner as today:
  raw_data-origin artifacts delete via `delete_raw_data`, performance-origin via
  `delete_performance_dataset` (both `backup_database()` + `ON DELETE CASCADE` +
  archive/audit). The existing `performance_datasets` deletion row in
  `docs/Data_Flow.md` stays valid unchanged.
- Full column mappings and the exact view SQL: [`./data-model.md`](./data-model.md).

## API / Route Contracts

The reform is primarily a **behavioral / navigational** contract, not a set of
brand-new endpoints. Key behavior changes:

| Aspect | Current | Target |
|--------|---------|--------|
| Analysis source | `run_processing` reads `test_data` only | reads `measurements` view (both sources) |
| Visualization source | `parsed_records` only | **unchanged** — `parsed_records` (FR-007 deferred) |
| Performance nav | top-level block + `/api/performance-datasets` | artifact type `data_type='performance'` via `artifacts` view; frontend redirect. API endpoints stay live over retained tables |
| "Data Base" nav | `/test-data` labelled "Data Base" | relabelled "Measurements / 测试结果" (same route) |
| Legacy routes | `/raw-data`, `/test-data`, `/performance-datasets`, `/processing`, `/data`, `/performance` | all still resolve (frontend redirect/alias) |

Full current→target route mapping, redirect notes, and endpoint behavior:
[`./contracts/routes-and-api.md`](./contracts/routes-and-api.md).

## Affected Modules & Files (per phase)

> **These lists are a non-exhaustive starting point, not the full blast radius.**
> Phase 0 proved it: the plan implied ~3 targets (`constants.ts` + `pages/*` +
> docs) but a copy/label change that crosses feature boundaries actually touched
> **15 files** — nav, the manual-entry form, the Analysis page *and its
> components*, the dashboard, raw-data views, the processing store, and the
> glossary. **Before implementing any phase, `grep` the whole repo for the
> affected terms/symbols and scope from the results** — do not trust this list
> alone. The risk is highest for **UI copy/label changes** (a term recurs across
> many components); it is lowest for backend-localized changes.

- **Phase 0 (as-built):** `frontend/src/utils/constants.ts`; the manual-entry form
  (`components/testData/MetricInputForm.tsx`); the Analysis page + its components
  (`pages/ProcessingPage.tsx`, `components/processing/*`); dashboard + raw-data
  copy (`pages/DashboardPage.tsx`, `pages/RawDataPage.tsx`,
  `components/rawData/{ProcessingJobsTable,RawDataDetailPanel,ResistanceVisualizationPanel}.tsx`);
  `stores/processingStore.ts`; `pages/TestDataPage.tsx`; `docs/GLOSSARY.md`.
- **Phase 1:** `migrations/NNN_measurements_view.sql`;
  `app/features/processing.py` (`fetch_processing_source` + `source`/
  `source_row_id` in QC/normalize output); `tests/smoke_test.py`.
  *Backend-localized — the output change is invisible to the frontend (it ignores
  the row `id`), so no UI files; this list is expected to hold as-is.*
- **Phase 2:** `migrations/NNN_artifacts_view.sql`;
  `app/features/raw_data.py` (Artifact **list** read via the `artifacts` view) /
  `app/features/performance.py` (create-path reframe); **no** `handler.py`
  change; `frontend/src/router/index.tsx`, `frontend/src/pages/*`;
  `tests/smoke_test.py`. *Re-grep first: the frontend "route by source" likely
  reaches the raw-data / performance list + detail components beyond `pages/*`.*
- **Phase 3:** `frontend/src/utils/constants.ts` +
  `frontend/src/router/index.tsx` (Analysis grouping + `/processing` redirect);
  `tests/smoke_test.py`; `docs/ARCHITECTURE.md` / `docs/BACKEND_MODULES.md`.
  (`visualization.py` untouched — FR-007 deferred.) ***Highest re-scoping risk*** —
  like Phase 0, an Analysis nav regroup will touch more UI copy than listed
  (breadcrumbs, any component naming the grouping). Grep before scoping.

## Sequence / Flow (Phase 1 Analysis, the representative path)

1. `POST /api/process` arrives at `route()` → `run_processing(payload)`.
2. Validation via `validation.*`; `sample_exists` check; raise `ValueError`.
3. `fetch_processing_source(conn, …)` runs parameterized SQL against the
   **`measurements` view** (both sources) instead of `test_data`.
4. `run_stats` / `run_qc` / `run_normalize` operate over the combined rows.
5. Result persisted to `processing_results`; serialized JSON response out.

## Risks & Trade-offs

- **Artifacts-view mapping & identity (Phase 2).** The `artifacts` view must
  project `performance_datasets` into `raw_data`'s shape: synthesize a
  `raw_data_code`-shaped label (performance has none), map `total_bytes→
  total_size` / `storage_dir→storage_path` / `collected_at→measured_at`, and
  fold `aliquot_code`/`test_type`/`data_format`/`source_folder_name` (no
  `raw_data` home) into a JSON `metadata_json` expression. `raw_data.id` and
  `performance_datasets.id` overlap, so the view exposes `source` +
  `source_row_id`; **any consumer that reads, links to, or deletes an artifact
  must key off `(source, source_row_id)`**, not a bare `id`. Mitigation: since
  nothing is copied, a bad projection is fixable by editing the (not-yet-applied)
  view migration — no data to unwind. Detail in [`data-model.md`](./data-model.md).
- **Artifact detail stays per-source (Phase 2).** The `artifacts` view backs the
  **list** only; detail, file listing, download, and delete keep using the
  existing `/api/raw-data` and `/api/performance-datasets` endpoints, routed from
  the frontend by `source`. This avoids a cross-source `artifact_files` view and
  any `handler.py` change, at the cost of two detail shapes behind one list — an
  accepted trade (a unified detail is deferred; Article X). Detail in
  [`data-model.md`](./data-model.md).
- **View column-mapping gaps (Phase 1).** `parsed_records` has **no
  `metric_name`** (derived per `data_type` via `CASE` — RC-2), **no `unit`**
  (emit `''` — RC-3), and **no `measured_at`** (use `created_at`); and the view's
  identity is `source_row_id` + `source`, not `id` — so `run_qc`/`run_normalize`
  must emit those (they currently emit `row["id"]`, which would `KeyError` on the
  view). This is an honest projection for the read model — acceptable because the
  view is additive and Analysis groups by metric name + unit. Resolved in the
  spec's Resolved Clarifications (RC-1..RC-4).
- **Metric-grouping usefulness (Phase 1, validation).** The parsed `metric_name`
  `CASE` composes a per-type label (`cd_sem` from `side`/`direction`/`row_group`;
  `resistance` literal; else `data_type`). This is a **design choice, not a
  proven grouping** — operators should confirm the resulting metric buckets are
  actually useful for Analysis before the derivation is considered final; the
  per-type composition is cheap to adjust in the view migration if not.
- **Route/URL breakage → frontend redirects.** Legacy routes are kept as
  **client-side** redirects/aliases — the router already aliases
  `/data`→TestData and `/performance`→Performance, so the pattern exists there.
  The backend performance API is left untouched (no new redirect pattern). Risk
  is low but must be covered by smoke assertions.
- **Delete/write routing for the `artifacts` view (Phase 2).** Because the view
  spans two backing tables, a performance-origin artifact must be
  created/deleted against `performance_datasets` and a raw_data-origin one
  against `raw_data`. This routing (keyed on `source`) is the one net-new bit of
  feature logic; both delete paths already exist, so it is dispatch, not new
  deletion machinery.
- **Frontend rework.** Regrouping nav (Phase 3) is the largest UI change; bounded
  by keeping page components intact and only re-labeling/re-grouping.
- **Transitional dual-read.** Each view reads a UNION of two tables; slightly
  more work per query than a single-table scan. At lab data volume this is
  negligible; indexes on `test_data(metric_name)`, `parsed_records(data_type)`,
  and the `sample_id` / dataset indexes already exist.
- **Scope discipline.** Characterization fold, physical unified tables (both
  measurements and artifacts), visualization-over-view (FR-007), and deleting
  deprecated performance tables are all explicitly deferred to prevent scope
  creep (Article X).

## Testing Approach

- **Baseline:** run `python3 tests/smoke_test.py` before each phase.
- **Phase 0:** assert no migration added (`schema_migrations` unchanged); smoke green — covers AC-001..AC-003.
- **Phase 1:** seed manual + parsed numeric data; assert view returns both and
  Analysis `source_count` reflects both — covers AC-004..AC-006.
- **Phase 2:** apply the `artifacts` view migration; assert performance rows are
  queryable via the `artifacts` list view (`data_type='performance'`, tagged
  `source='performance'`); assert no source row/file was altered; assert
  `/performance-datasets` resolves via the frontend redirect — covers
  AC-007..AC-009.
- **Phase 3:** assert the Analysis nav grouping + the `/processing` frontend
  redirect resolve — covers AC-011..AC-012 (AC-010 deferred with FR-007).
- **Manual checks:** click each relabelled nav entry and each legacy URL to
  confirm the frontend redirects resolve.
