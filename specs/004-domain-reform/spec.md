# Feature Specification: Domain Model Reform — Sample-Rooted Two-Axis Model

> This spec describes **WHAT** the reform does and **WHY**. The **HOW** (phases,
> migrations, contracts) lives in [`plan.md`](./plan.md),
> [`data-model.md`](./data-model.md), and [`contracts/`](./contracts/).
>
> This spec MUST comply with the project
> [constitution](../../.specify/memory/constitution.md). It is a **forward-looking
> design blueprint** — a proposal that requires human approval before any code is
> written. It does not authorize implementation.

## Metadata

| Field | Value |
|-------|-------|
| Feature name | Domain Model Reform — Sample-Rooted Two-Axis Model |
| Feature number | 004 |
| Status | **Draft** |
| Created | 2026-07-07 |
| Author | Genevieve Cote |

## Summary

Today the application exposes a **flat list of top-level "blocks"** — Raw Data,
Test Data ("Data Base"), Performance Datasets, Processing, Visualization,
Characterization — that grew organically. Two problems follow from this. First,
operators cannot tell *where a thing goes*: a numeric result can live in
`test_data` (typed by hand) **or** in `parsed_records` (extracted from a file),
and the two are analyzed by different, non-overlapping tools. Second, the word
"processing" means three different things (the *Processing/Analysis* block, the
`processing_jobs` parse/visualization log, the `process_records` MES traveller),
which confuses navigation and docs.

This reform restructures the top-level domain around a single root — **Sample** —
with **two orthogonal axes** instead of a flat block list:

- **Axis A — Storage entities:** what is *attached to* a sample. Two kinds:
  **Artifacts** (files, discriminated by `type`) and **Measurements** (numeric
  points about a sample, discriminated by `source`: `parsed` vs `manual`).
- **Axis B — Transforms:** capabilities that *operate across* measurements —
  `parse` (file → measurements), `analyze`/`process` (measurements →
  stats/QC/normalize), and `visualize` (measurements → charts). *Note:* only
  `analyze`/`process` is repointed onto the unified Measurements read model by
  this reform. `visualize` keeps sourcing `parsed_records` (its charts need
  per-record layout columns the scalar read model omits) — see the deferred
  FR-007.

The north-star rationale is captured in the companion review
[`docs/DOMAIN_MODEL.md`](../../docs/DOMAIN_MODEL.md); this spec is its
**deployable refinement** — a concrete, phased, non-destructive roadmap that a
live system can adopt one shippable step at a time. Crucially, the first real
schema step is a **read model** (a SQL `measurements` VIEW UNION-ing the two
existing tables) so that transforms can immediately operate over *all*
measurements **with no data migration**.

## User Scenarios / User Stories

- **US-1.** As an **operator**, I want the navigation to name things by what they
  *are* (Samples → their Artifacts, Measurements, Analysis) so that I never have
  to guess whether a result belongs under "Data Base" or "Raw Data".
- **US-2.** As an **operator**, I want a measurement to be analyzable *regardless
  of how it arrived* — typed in by hand or parsed from an instrument file — so
  that statistics/QC cover the whole picture, not just the manually-entered half.
- **US-2b.** As an **operator**, when I type in a numeric result by hand, I want
  the screen to be framed as **"Add a measurement"** under the Measurements /
  测试结果 area (rather than a separate "Data Base" entry form) so that manual
  and parsed measurements read as one concept, even though my entry still lands
  in the same `test_data` store as before.
- **US-3.** As an **operator**, I want performance test files to sit *alongside*
  other raw files under one "Artifacts" concept, instead of being a separate
  top-level block, so that "attach files to a sample" is one workflow, not two.
- **US-4.** As a **maintainer**, I want the three meanings of "processing"
  disambiguated in the UI copy and docs so that reviewers and new contributors
  are not misled.
- **US-5.** As an **operator** with existing bookmarks/links, I want my old URLs
  (`/raw-data`, `/test-data`, `/performance-datasets`, `/processing`) to keep
  working (as redirects) so that the reform does not break my saved paths.
- **US-6.** As a **maintainer**, I want every step to be independently shippable,
  forward-only, and provably non-destructive so that I can approve and roll out
  the reform incrementally and stop at any phase boundary.

> The reform is delivered as four independent phases (see
> [`plan.md`](./plan.md)); each phase is separately reviewable and leaves the
> smoke test green.

## Functional Requirements

> Requirements describe the **target state**. They are realized across Phases 0–3
> in the plan; each is tagged with the phase that first satisfies it.

- **FR-001.** The navigation MUST present a Sample-rooted structure whose
  Storage axis groups **Artifacts** (files) and **Measurements** (numeric
  points), and whose Transform axis groups **Analysis** capabilities
  (visualize, analyze/process) that operate over Measurements. *(US-1; Phase 0/3)*
- **FR-002.** The top-level label "Data Base" (route `/test-data`) MUST be
  relabelled **"Measurements / 测试结果"** in the UI copy and view metadata.
  *(US-1; Phase 0)*
- **FR-002b.** The manual test-data entry form (today the create/bulk-create UI
  at `/test-data`) MUST be **reframed as "Add a measurement"** within the
  Measurements / 测试结果 area — a frontend/UX change only. The backend write
  path is **unchanged**: entries still land in the `test_data` table as
  `source='manual'` (`create_test_data` / bulk create untouched). No physical
  unified measurements table is introduced (that remains out of scope). *(US-2b;
  Phase 0 label/framing, with the Measurements grouping completed in Phase 3)*
- **FR-003.** The system MUST expose a **unified Measurements read model** that
  presents `test_data` rows (as `source='manual'`) and `parsed_records` rows (as
  `source='parsed'`) through one common shape (sample identity, metric name,
  numeric value, unit, measured-at, source). *(US-2; Phase 1)*
- **FR-004.** The Analysis/Processing transform (stats / QC / normalize) MUST
  read from the unified Measurements read model, so its results reflect **both**
  manual and parsed measurements, not `test_data` alone. *(US-2; Phase 1)*
- **FR-005.** Performance datasets MUST be presented as **Artifacts** of type
  `data_type='performance'` under the general Artifact store (files-only, no
  parser), rather than as a separate top-level entity. This is realized via an
  additive **`artifacts` read model** (a view over `raw_data` ∪
  `performance_datasets`, mirroring the Phase 1 Measurements view), not by moving
  rows; new performance uploads are reframed to write `raw_data`
  (`data_type='performance'`) going forward. *(US-3; Phase 2)*
- **FR-006.** Surfacing performance rows as Artifacts MUST be **forward-only and
  non-destructive**: the `artifacts` view reads the existing
  `performance_datasets` table **in place** — no rows or files are copied, moved,
  or mutated, and the source tables are retained. *(US-3, US-6; Phase 2)*
- **FR-007.** *(Deferred — out of scope for this reform.)* Extending the
  Visualization transform to source the unified Measurements read model is
  **deferred**: its charts (resistance heatmap, CD violin) require per-record
  layout columns (`die_id` / `area` / `row_index` / `col_index` / `x_value` /
  `y_value`) that the scalar `measurements` view deliberately omits.
  Visualization remains sourced from `parsed_records`; revisit only if the read
  model is later extended with layout columns. *(US-2; deferred)*
- **FR-008.** All legacy top-level routes (`/raw-data`, `/test-data`,
  `/performance-datasets`, `/processing`, and the existing `/data`,
  `/performance` aliases) MUST continue to resolve — as redirects or aliases to
  their new locations — for backward compatibility. *(US-5; Phase 2/3)*
- **FR-009.** The three meanings of "processing" MUST be disambiguated in UI copy
  and docs: `processing_jobs` presented as the **"parse / visualization job
  log"** of Raw Data; the Analysis block presented as **"Analysis"**; and
  `process_records` remaining the **MES/工艺记录** traveller — three distinct
  names. *(US-4; Phase 0)*
- **FR-010.** Every schema change in this reform MUST be delivered as a **new**
  forward-only `migrations/NNN_*.sql` file; no applied migration and no
  `init_db()` baseline may be edited. *(US-6; Phases 1–3, Article V)*
- **FR-011.** The reform MUST NOT remove or rewrite any existing measurement or
  artifact data as part of introducing the read model; the `measurements` view
  is additive and read-only. *(US-2, US-6; Phase 1)*
- **FR-012.** Each phase MUST be independently shippable and leave
  `tests/smoke_test.py` green; a phase MUST NOT depend on a later phase to be
  correct. *(US-6, Article IX; all phases)*

## Non-Functional Requirements

- **NFR-001. Non-destructive & backward-compatible.** No phase may delete or
  rewrite existing rows to introduce the new model. **Both** unifications
  (Measurements, Phase 1; Artifacts, Phase 2) are **read-model views** over the
  existing tables — no rows or files are copied, moved, or mutated. Old routes
  are kept as redirects (Article V spirit: additive, reversible where possible).
- **NFR-002. Backup precedes destruction.** No phase in this reform moves or
  deletes data — both unifications are additive views — so **no pre-migration
  snapshot is required here**. The existing startup snapshot and the per-delete
  `backup_database()` on the existing performance / raw_data delete paths remain
  the Article IV guarantees. Any *later* cleanup that physically removes the
  deprecated performance tables MUST take its own snapshot first (out of scope).
- **NFR-003. Smoke-green per phase.** Every phase MUST run `tests/smoke_test.py`
  as its green-light oracle, extending it to cover the new/changed behavior
  (Article IX).
- **NFR-004. No new runtime dependencies.** The reform MUST be implementable with
  the stdlib-only backend core and the existing frontend footprint; the
  `measurements` and `artifacts` views and the frontend redirects add **no**
  third-party dependency (Article I).
- **NFR-005. Auth posture unchanged.** The reform MUST preserve the existing
  optional-but-real auth behavior; relabelled/redirected routes keep the same
  `GET ≤ operator-write ≤ admin-delete` policy and remain a true no-op when auth
  is disabled (Article XI).
- **NFR-006. Bounded transitional complexity.** During transition the system will
  briefly carry *both* the old block and the new grouping (e.g. a dual-read over
  the view). This transitional cost MUST be bounded by the phasing and removed as
  each phase completes; it MUST NOT become a permanent parallel structure
  (Article X).

## Key Entities

> Conceptual only — schema lives in [`data-model.md`](./data-model.md).

- **Sample** — the single root. Everything else is attached to, or computed
  about, a sample. Identity unchanged from today (`sample_display_code` /
  `sample_uid`).
- **Artifact** *(Axis A, kind 1)* — a set of files attached to a sample,
  discriminated by a `type`. Conceptually unifies today's `raw_data` (with its
  files and optional parse pipeline) and, via the Phase 2 `artifacts` read model,
  performance datasets surfaced as type `performance` (files-only, read in place
  from `performance_datasets`). Characterization is a *related but separate* file
  store, explicitly **not** folded in this reform.
- **Measurement** *(Axis A, kind 2)* — one numeric point about a sample, with a
  metric name, value, unit, timestamp, and a `source` discriminator: `manual`
  (typed via the Measurements/测试结果 screen, today's `test_data`) or `parsed`
  (extracted from an Artifact file, today's `parsed_records`). Introduced first
  as a **read model** (a view) over the two existing stores.
- **Transform** *(Axis B, conceptual capability)* — an operation over
  measurements/artifacts: `parse` (Artifact file → parsed Measurements),
  `analyze`/`process` (Measurements → stats/QC/normalize), and `visualize`
  (Measurements → charts). Transforms are *capabilities available across
  measurements*, not storage. In this reform only `analyze`/`process` is
  repointed onto the unified read model; `visualize` continues to source
  `parsed_records` (FR-007 deferred).

## Out of Scope

- **Folding Characterization** into the Artifact store. Characterization has a
  distinct two-level `collection → files` structure and different semantics; it
  **stays separate** and its fold is explicitly deferred (see
  [`data-model.md`](./data-model.md)).
- **A physical unified `measurements` table.** This reform introduces only the
  **read model** (a SQL view). Physically consolidating `test_data` +
  `parsed_records` into one table is a later, optional step and is **out of
  scope** here.
- **A physical performance → `raw_data` consolidation.** Phase 2 surfaces
  performance as Artifacts through the `artifacts` read model only. Physically
  copying performance rows/files into `raw_data` / `raw_data_files` (and later
  dropping the source tables) is a separate, deferred cleanup — **out of scope**
  here.
- **Visualization over the Measurements read model.** Deferred (FR-007);
  Visualization stays sourced from `parsed_records` in this reform.
- **Auth / RBAC changes.** The reform preserves existing auth behavior and
  introduces no new roles or gates.
- **Parser or visualization *algorithm* changes.** Only the *source* the
  transforms read from changes (to the view); the numeric/chart logic is
  untouched.
- **MES / `process_records` restructuring.** The traveller is only *renamed for
  disambiguation* (FR-009); its data model is unchanged.
- **Deleting the deprecated performance tables.** Phase 2 reads them in place and
  keeps them; their eventual removal is a separate, later, approved cleanup — not
  part of this reform's committed scope.

## Resolved Clarifications

> The four questions previously open on this spec are now **resolved** below. The
> spec remains **Draft** pending human approval; these are the decisions the
> reform commits to (a couple carry an operator-confirmable detail, noted inline).

- **RC-1 — Manual-entry UI: reframe (not keep-as-is).** The manual test-data
  entry form (today at `/test-data`) is **reframed as "Add a measurement"** under
  the Measurements / 测试结果 area. It STILL writes to the `test_data` table as
  `source='manual'` — the backend write path (`create_test_data` / bulk create)
  is unchanged and there is **no physical unified table** (out of scope). This is
  a frontend/UX/label change only. See **FR-002b** and **US-2b**.
- **RC-2 — Parsed `metric_name`: derive a finer metric per `data_type`.** In the
  `measurements` view, the `metric_name` for **parsed** rows is derived per
  `data_type` via a pure-SQL `CASE` expression (Article VII-safe — the expression
  is code-authored, no request data): `cd_sem` composes a finer label from the
  CD/SEM position fields (`side` / `direction` / `row_group`); `resistance` maps
  to the literal `'resistance'` (its finer dimensions — `die_id` / `area` / row /
  col — stay as their own columns, not part of the metric label); all other
  types fall back to `data_type`. `data_type` is **also** kept as its own
  separate view column so Analysis can group by either. The exact per-type
  composition is operator-confirmable, but this per-type-CASE derivation is the
  chosen approach. See [`data-model.md`](./data-model.md) for the exact SQL.
- **RC-3 — Parsed `unit`: empty for now.** The view emits `''` (empty) as `unit`
  for parsed rows. `parsed_records` has no `unit` column (some units live inside
  `extra_json`, e.g. CD/SEM `unit: nm`); richer unit derivation from `extra_json`
  is **deferred** to keep the view a pure, index-friendly SQL projection. This
  matches [`data-model.md`](./data-model.md).
- **RC-4 — Performance upload UI: reframe + frontend redirect.** After Phase 2,
  the standalone `/performance-datasets` **frontend** route **redirects** (a
  client-side router redirect — the same pattern the router already uses for the
  `/data` and `/performance` aliases), and uploading performance files is
  **reframed as a normal Artifact upload** (`data_type='performance'`) in the
  unified Artifacts area. The performance **API** endpoints stay **live and
  unchanged** (they read the retained `performance_datasets` tables) — no
  backend redirect or shim is introduced by this reform; their eventual hard
  removal is a separate, later, approved cleanup. See
  [`contracts/routes-and-api.md`](./contracts/routes-and-api.md) and **FR-005** /
  **FR-008**.

## Acceptance Criteria

> Given/When/Then per phase. Each phase keeps the smoke test green (Article IX).

**Phase 0 — naming/clarity (zero schema):**
- **AC-001.** Given the app is running, when the operator opens the navigation,
  then the top-level entry formerly "测试数据库 / Data Base" reads
  **"Measurements / 测试结果"** and points at the same underlying screen.
  *(FR-002)*
- **AC-002.** Given the docs and in-app copy, when a reader looks up "processing",
  then they find three distinctly-named concepts (parse/visualization job log,
  Analysis, MES traveller) with no ambiguous overlap. *(FR-009)*
- **AC-003.** Given no migration was added in Phase 0, when the smoke test runs,
  then it is green and `schema_migrations` is unchanged. *(FR-012, Article IX)*

**Phase 1 — measurements read model:**
- **AC-004.** Given the new `measurements` view migration is applied, when a
  query selects from `measurements`, then it returns both `test_data` rows
  (`source='manual'`) and `parsed_records` rows (`source='parsed'`) with the
  common columns. *(FR-003)*
- **AC-005.** Given a sample has both manual and parsed numeric data, when
  Analysis stats/QC runs for that sample, then the result count reflects **both**
  sources. *(FR-004)*
- **AC-006.** Given the view is additive, when the migration is applied, then no
  existing `test_data` or `parsed_records` row is altered or removed, and the
  smoke test (extended to cover the view-backed Analysis) is green.
  *(FR-011, FR-012, Article IX)*

**Phase 2 — artifacts read model:**
- **AC-007.** Given performance datasets exist, when the `artifacts` view
  migration is applied, then each `performance_datasets` row is queryable via the
  `artifacts` list view with `data_type='performance'` (its files remain served
  by the existing per-source detail endpoint), while the source tables are read
  **in place** and unchanged. *(FR-005, FR-006)*
- **AC-008.** Given Phase 2 moves no data, when the view migration is applied,
  then no `performance_datasets` / `performance_dataset_files` / `raw_data` row is
  altered or removed and no pre-migration snapshot is required (the existing
  startup + per-delete backups remain the Article IV guarantee). *(NFR-001, NFR-002)*
- **AC-009.** Given a user visits `/performance-datasets`, when the page loads,
  then the frontend router resolves it via a client-side redirect/alias and does
  not 404. *(FR-008)*

**Phase 3 — transforms unification (nav only):**
- **AC-010.** *(Deferred with FR-007.)* Visualization-over-the-read-model is out
  of scope; Visualization continues to source `parsed_records` and its behavior
  is unchanged by this reform. *(FR-007 — deferred)*
- **AC-011.** Given the nav "Analysis" area, when the operator opens it, then
  Analyze/Process (and Visualization, as a navigational grouping only) are
  presented as transforms over Measurements, and legacy `/processing` resolves
  via a frontend redirect. *(FR-001, FR-008)*
- **AC-012.** The smoke test MUST cover the view-backed Analysis, the
  `artifacts`-view performance path, and each legacy frontend-route redirect.
  *(Article IX)*
