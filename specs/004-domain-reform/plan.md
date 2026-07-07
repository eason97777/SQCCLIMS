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
| I — Standard-library backend core, one sanctioned dependency boundary | **PASS** | The `measurements` view, the performance-fold `INSERT…SELECT`, and route redirects are all pure `sqlite3` + `http.server`. No third-party import enters `app/**` or `server.py`. Visualization keeps its existing matplotlib use confined to `parsers/`; this reform does not add any dependency. |
| II — Layered architecture, one-way dependencies | **PASS** | Reading the view is done inside feature modules (`processing.py`, `visualization.py`); `handler.py` only gains redirect/alias dispatch entries (transport concern). No infra module imports a feature; no new cycles. |
| III — One feature owns its domain | **PASS (with justification)** | The reform *consolidates* how features are grouped in the UI, but the backend keeps one module per domain (`raw_data`, `test_data`, `processing`, `visualization`, `parsing`). Performance folds **into** `raw_data`'s store — that is improved domain cohesion (one Artifact owner), **not** spreading a feature across modules. The `measurements` view is shared read infrastructure consumed by existing feature modules, not a new competing owner. See "Article III note" below. |
| IV — Data safety is non-negotiable | **PASS** | Only Phase 2 moves data; it takes a DB snapshot before the fold (as `performance` delete already does via `backup_database()`), copies with `INSERT…SELECT`, and **keeps the source tables until verified**. The view (Phase 1) touches no rows. No new deletable entity is introduced by the view; folded performance artifacts inherit `raw_data`'s existing Strong-tier deletion + `ON DELETE CASCADE` + archive/audit path. |
| V — Forward-only, checksum-guarded migrations | **PASS** | Every schema change is a **new** `migrations/NNN_*.sql`: the view is one migration; the performance fold is another (`INSERT…SELECT`). No applied file is edited; `init_db()` baseline is untouched. Migration SQL contains no `BEGIN`/`COMMIT`. |
| VI — Errors via the exception convention | **PASS** | No new hand-built status codes. Feature code reading the view continues to raise `ValueError` / `LookupError`; redirects are transport-level and do not bypass the central mapping. |
| VII — Parameterized SQL only | **PASS** | The view definition uses only fixed, code-authored column lists — including the parsed-row `metric_name` `CASE` derivation (per-`data_type` composition of `side`/`direction`/`row_group`) — with **no request data** interpolated. Feature queries against the view continue to use `?`/named parameters exactly as today. |
| VIII — Runtime config read at call time | **PASS** | No path binding changes; any new code reads `config.<NAME>` at call time. The fold migration references no runtime path (pure SQL). |
| IX — The smoke test is the green-light oracle | **PASS** | Each phase records a baseline `python3 tests/smoke_test.py`, then extends it: Phase 1 asserts view-backed Analysis sees both sources; Phase 2 asserts the folded performance artifact is queryable and old routes redirect; Phase 3 asserts visualization-over-view and the Analysis nav. |
| X — Simplicity over cleverness | **PASS (honest transitional cost)** | The end state is *simpler* (one Measurements concept, one Artifact concept). Transitionally the system carries a dual-read (view UNION over two tables) and, in Phase 2, two copies of performance data until verified. This is real added complexity, deliberately **bounded by phasing** and removed as each phase lands. We do **not** build the physical unified table speculatively (deferred). |
| XI — Optional-but-real auth & RBAC | **PASS** | Relabelled and redirected routes preserve the existing `GET ≤ operator-write ≤ admin-delete` policy and remain a true no-op when auth is disabled. No auth code changes. |

**Article III note (justification, not deviation).** Article III forbids a single
*feature* being spread across multiple modules. This reform does the opposite: it
*increases* cohesion by making `raw_data` the one owner of file Artifacts
(absorbing performance) and by giving all transforms one shared read model. The
`measurements` view is not a feature module — it is shared read infrastructure
(like an index), consumed by the existing `processing`/`visualization` owners.
No feature's logic is scattered. Recorded here so reviewers see it was considered.

> No row is a DEVIATION. Two rows carry explicit justifications (III, X) that a
> human reviewer must accept as part of approving this Draft.

## Technical Context

- **Backend layer(s) touched:**
  - **Migrations** — one new file for the `measurements` view (Phase 1); one new
    file for the performance→`raw_data` fold (Phase 2).
  - **Feature modules** — `app/features/processing.py` (repoint its source query
    from `test_data` to the `measurements` view); `app/features/visualization.py`
    (allow sourcing from the view); `app/features/raw_data.py` /
    `app/features/performance.py` (performance becomes an artifact type; the
    standalone create path is redirected/reframed).
  - **HTTP** — `app/http/handler.py` gains redirect/alias dispatch entries for
    legacy routes; no business logic added.
  - **db / validation / storage / deletion** — unchanged in shape; folded
    performance artifacts reuse `raw_data`'s existing deletion path.
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
  `parsed_records`). The reform makes this explicit and **folds
  `performance_datasets`/`performance_dataset_files` into
  `raw_data`/`raw_data_files` as `data_type='performance'`** (files-only, no
  parser). Characterization stays a separate store (deferred).
- **Measurements** = numeric points about a sample, discriminated by `source`.
  The reform introduces a **read model first**: a SQL VIEW `measurements` that
  UNIONs `test_data` (`source='manual'`) and `parsed_records`
  (`source='parsed'`) exposing common columns (sample identity, metric name,
  numeric value, unit, measured-at, source). This lets transforms operate over
  *all* measurements with **no data migration**. A physical unified table is a
  later, optional step (out of scope).

**Axis B — Transforms as capabilities (apply across Measurements).**
- `parse`: Artifact file → parsed Measurements (exists, unchanged).
- `visualize`: Measurements → charts. Target: able to operate over the
  `measurements` view (both sources), not only `parsed_records`.
- `analyze`/`process`: Measurements → stats/QC/normalize. Target: read the
  `measurements` view (both sources), not only `test_data`.

**Thin-handler contract preserved.** `handler.py` continues to parse/route/
serialize only. The source-of-truth change (read `measurements` instead of
`test_data`) happens inside `processing.py`'s `fetch_processing_source()`; the
handler is unaware. Redirects are pure dispatch entries.

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
  measurements` so Analysis also sees parsed data. Keep the same output shape
  (`metric_name`, `unit`, `numeric_value`, sample identity columns) so
  `run_stats` / `run_qc` / `run_normalize` are unchanged.
- Extend the smoke test: seed a sample with one manual `test_data` row and one
  parsed record; assert Analysis `source_count` covers both.
- **Migration:** `migrations/NNN_measurements_view.sql` (view only).
- **Back-compat:** the view is read-only and additive; `test_data` writes are
  untouched. **No data moves.**

### Phase 2 — Artifacts fold

- Migrate `performance_datasets` → `raw_data` (`data_type='performance'`) and
  `performance_dataset_files` → `raw_data_files` via a forward-only
  `INSERT…SELECT` migration. Column mapping is in [`data-model.md`](./data-model.md).
- **Backup first** (Article IV): a DB snapshot precedes the migration; the fold
  **keeps the old performance tables** until the copy is verified (their removal
  is a separate, later approved cleanup — not in this reform's committed scope).
- Add old-route redirects (`/performance-datasets`, `/performance`,
  `/api/performance-datasets…` behavior — see [`contracts/routes-and-api.md`](./contracts/routes-and-api.md)).
- Frontend shows performance as an artifact type under Raw Data / Artifacts.
- **Migration:** `migrations/NNN_fold_performance_into_raw_data.sql`.
- **Testing:** assert folded rows are queryable via `raw_data` with
  `data_type='performance'`; assert `/performance-datasets` redirects; smoke-green.

### Phase 3 — Transforms unification

- Make Visualization able to operate over the `measurements` view; reposition
  Processing as a general **Analysis** transform; unify the nav "Analysis" area
  (Visualization + Analyze/Process presented together over Measurements).
- Deprecate redundant endpoints behind redirects (see
  [`contracts/routes-and-api.md`](./contracts/routes-and-api.md)).
- **Migration:** none required beyond Phase 1's view (visualization gains a
  view-sourced path; parsed-only chart paths remain for chart types that need
  layout columns absent from the view — see Risks).
- **Testing:** assert visualization-over-view; assert Analysis nav + legacy
  `/processing` redirect; smoke-green.

## Data Model Changes

- **Phase 1 migration** — `migrations/NNN_measurements_view.sql`: `CREATE VIEW
  measurements AS SELECT … FROM test_data UNION ALL SELECT … FROM parsed_records`.
  Read-only; no tables/rows altered.
- **Phase 2 migration** — `migrations/NNN_fold_performance_into_raw_data.sql`:
  `INSERT INTO raw_data (…) SELECT … FROM performance_datasets` +
  `INSERT INTO raw_data_files (…) SELECT … FROM performance_dataset_files JOIN …`.
  Forward-only, additive. Source tables retained.
- **Data-safety note:** the view introduces no deletable entity. Folded
  performance artifacts become ordinary `raw_data` rows, inheriting the existing
  Strong-tier deletion (`delete_raw_data` → `backup_database()` +
  `ON DELETE CASCADE` on `raw_data_files` + archive/audit). The pre-existing
  `performance_datasets` deletion row in `docs/Data_Flow.md` stays until those
  tables are removed in a later cleanup.
- Full column mappings and the exact view SQL: [`./data-model.md`](./data-model.md).

## API / Route Contracts

The reform is primarily a **behavioral / navigational** contract, not a set of
brand-new endpoints. Key behavior changes:

| Aspect | Current | Target |
|--------|---------|--------|
| Analysis source | `run_processing` reads `test_data` only | reads `measurements` view (both sources) |
| Visualization source | `parsed_records` only | may source `measurements` view |
| Performance nav | top-level block + `/api/performance-datasets` | artifact type `data_type='performance'` under Raw Data; route redirects |
| "Data Base" nav | `/test-data` labelled "Data Base" | relabelled "Measurements / 测试结果" (same route) |
| Legacy routes | `/raw-data`, `/test-data`, `/performance-datasets`, `/processing`, `/data`, `/performance` | all still resolve (redirect/alias) |

Full current→target route mapping, redirect notes, and endpoint behavior:
[`./contracts/routes-and-api.md`](./contracts/routes-and-api.md).

## Affected Modules & Files (per phase)

- **Phase 0:** `frontend/src/utils/constants.ts`; the manual test-data entry
  page/form (`frontend/src/pages/*` — reframe as "Add a measurement", label/UX
  only, backend write path untouched); docs copy (`docs/DOMAIN_MODEL.md`
  follow-ups, `docs/ARCHITECTURE.md` glossary if needed).
- **Phase 1:** `migrations/NNN_measurements_view.sql`;
  `app/features/processing.py` (`fetch_processing_source`); `tests/smoke_test.py`.
- **Phase 2:** `migrations/NNN_fold_performance_into_raw_data.sql`;
  `app/features/performance.py` / `app/features/raw_data.py` (create-path
  reframe); `app/http/handler.py` (performance route redirects);
  `frontend/src/router/index.tsx`, `frontend/src/pages/*`; `tests/smoke_test.py`;
  `docs/Data_Flow.md`.
- **Phase 3:** `app/features/visualization.py` (view-sourced path);
  `frontend/src/utils/constants.ts` + `frontend/src/router/index.tsx` (Analysis
  grouping + redirects); `app/http/handler.py` (`/processing` alias);
  `tests/smoke_test.py`; `docs/ARCHITECTURE.md` / `docs/BACKEND_MODULES.md`.

## Sequence / Flow (Phase 1 Analysis, the representative path)

1. `POST /api/process` arrives at `route()` → `run_processing(payload)`.
2. Validation via `validation.*`; `sample_exists` check; raise `ValueError`.
3. `fetch_processing_source(conn, …)` runs parameterized SQL against the
   **`measurements` view** (both sources) instead of `test_data`.
4. `run_stats` / `run_qc` / `run_normalize` operate over the combined rows.
5. Result persisted to `processing_results`; serialized JSON response out.

## Risks & Trade-offs

- **Data-migration risk (Phase 2).** `INSERT…SELECT` into `raw_data` must
  generate a valid `raw_data_code` (a `UNIQUE NOT NULL` column with a
  `RD-<uid>-<TYPE>-<date>-NNN` convention) and satisfy `raw_data`'s `NOT NULL`
  columns (`raw_data_name`, `data_type`). Performance rows have no equivalent
  code and no `raw_data_code`-shaped identity. **Mitigation:** synthesize a
  deterministic code in the migration (see [`data-model.md`](./data-model.md));
  take a backup first; keep the source tables until verified.
- **Column-mapping gaps (Phase 2).** `performance_dataset_files` has **no
  `sha256`, `file_ext`, `relative_path`-as-`raw_data`-expects, or
  `preview_supported`** column; `raw_data_files` requires/defaults them.
  `performance_datasets.total_bytes` maps to `raw_data.total_size`;
  `collected_at`/`operator`/`status`/`notes` map cleanly, but
  `aliquot_code`/`test_type`/`data_format`/`source_folder_name` have **no
  `raw_data` home** and must be preserved in `metadata_json`. Detailed in
  [`data-model.md`](./data-model.md).
- **View column-mapping gaps (Phase 1).** `parsed_records` has **no
  `metric_name`** (derived per `data_type` via `CASE` — RC-2), **no `unit`**
  (emit `''` — RC-3), and **no `measured_at`** (use `created_at`). This is an
  honest projection for the read model — acceptable because the view is additive
  and Analysis groups by metric name + unit. Resolved in the spec's Resolved
  Clarifications (RC-1..RC-4).
- **Metric-grouping usefulness (Phase 1, validation).** The parsed `metric_name`
  `CASE` composes a per-type label (`cd_sem` from `side`/`direction`/`row_group`;
  `resistance` literal; else `data_type`). This is a **design choice, not a
  proven grouping** — operators should confirm the resulting metric buckets are
  actually useful for Analysis before the derivation is considered final; the
  per-type composition is cheap to adjust in the view migration if not.
- **Route/URL breakage → redirects.** Kept legacy routes as redirects/aliases
  (the router already aliases `/data`→TestData and `/performance`→Performance, so
  the pattern exists). Risk is low but must be covered by smoke assertions.
- **Frontend rework.** Regrouping nav (Phase 3) is the largest UI change; bounded
  by keeping page components intact and only re-labeling/re-grouping.
- **Transitional dual-read.** Analysis reads a UNION view; slightly more work per
  query than a single-table scan. At lab data volume this is negligible; indexes
  on `test_data(metric_name)` and `parsed_records(data_type)` already exist.
- **Scope discipline.** Characterization fold, physical unified table, and
  deleting deprecated performance tables are all explicitly deferred to prevent
  scope creep (Article X).

## Testing Approach

- **Baseline:** run `python3 tests/smoke_test.py` before each phase.
- **Phase 0:** assert no migration added (`schema_migrations` unchanged); smoke green — covers AC-001..AC-003.
- **Phase 1:** seed manual + parsed numeric data; assert view returns both and
  Analysis `source_count` reflects both — covers AC-004..AC-006.
- **Phase 2:** apply fold; assert folded rows queryable via `raw_data`
  (`data_type='performance'`); assert `/performance-datasets` redirects; assert a
  pre-fold backup exists — covers AC-007..AC-009.
- **Phase 3:** assert visualization-over-view; assert Analysis nav + `/processing`
  redirect — covers AC-010..AC-012.
- **Manual checks:** click each relabelled nav entry and each legacy URL to
  confirm redirects resolve.
