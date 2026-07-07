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
  `parse` (file → measurements), `visualize` (measurements → charts),
  `analyze`/`process` (measurements → stats/QC/normalize).

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
- **FR-005.** Performance datasets MUST be represented as **Artifacts** of type
  `data_type='performance'` under the general Artifact store (files-only, no
  parser), rather than as a separate top-level entity. *(US-3; Phase 2)*
- **FR-006.** The reform MUST migrate existing performance rows into the Artifact
  store via a **forward-only, additive** migration (`INSERT…SELECT`) that copies
  rather than mutates, and MUST NOT delete the original performance tables until
  the copy is verified. *(US-3, US-6; Phase 2)*
- **FR-007.** The Visualization transform MUST be able to operate over the
  unified Measurements read model (both sources), not only over `parsed_records`.
  *(US-2; Phase 3)*
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
  rewrite existing rows to introduce the new model. The performance fold copies
  data (`INSERT…SELECT`) and retains the source tables until verified
  (Article IV). Old routes are kept as redirects (Article V spirit: additive,
  reversible where possible).
- **NFR-002. Backup precedes destruction.** The only phase that moves data
  (Phase 2, performance fold) MUST take a DB snapshot before the migration and
  before any later cleanup of the deprecated tables, per constitution Article IV.
- **NFR-003. Smoke-green per phase.** Every phase MUST run `tests/smoke_test.py`
  as its green-light oracle, extending it to cover the new/changed behavior
  (Article IX).
- **NFR-004. No new runtime dependencies.** The reform MUST be implementable with
  the stdlib-only backend core and the existing frontend footprint; the
  `measurements` view, the fold migration, and route redirects add **no**
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
  files and optional parse pipeline) and, after Phase 2, performance datasets as
  type `performance` (files-only). Characterization is a *related but separate*
  file store, explicitly **not** folded in this reform.
- **Measurement** *(Axis A, kind 2)* — one numeric point about a sample, with a
  metric name, value, unit, timestamp, and a `source` discriminator: `manual`
  (typed via the Measurements/测试结果 screen, today's `test_data`) or `parsed`
  (extracted from an Artifact file, today's `parsed_records`). Introduced first
  as a **read model** (a view) over the two existing stores.
- **Transform** *(Axis B, conceptual capability)* — an operation over
  measurements/artifacts: `parse` (Artifact file → parsed Measurements),
  `visualize` (Measurements → charts), `analyze`/`process` (Measurements →
  stats/QC/normalize). Transforms are *capabilities available across
  measurements*, not storage.

## Out of Scope

- **Folding Characterization** into the Artifact store. Characterization has a
  distinct two-level `collection → files` structure and different semantics; it
  **stays separate** and its fold is explicitly deferred (see
  [`data-model.md`](./data-model.md)).
- **A physical unified `measurements` table.** This reform introduces only the
  **read model** (a SQL view). Physically consolidating `test_data` +
  `parsed_records` into one table is a later, optional step and is **out of
  scope** here.
- **Auth / RBAC changes.** The reform preserves existing auth behavior and
  introduces no new roles or gates.
- **Parser or visualization *algorithm* changes.** Only the *source* the
  transforms read from changes (to the view); the numeric/chart logic is
  untouched.
- **MES / `process_records` restructuring.** The traveller is only *renamed for
  disambiguation* (FR-009); its data model is unchanged.
- **Deleting the deprecated performance tables.** Phase 2 copies and keeps them;
  their eventual removal is a separate, later, approved cleanup — not part of
  this reform's committed scope.

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
- **RC-4 — Performance upload UI: redirect + reframe.** After the Phase 2 fold,
  the standalone `/performance-datasets` route **redirects**, and uploading
  performance files is **reframed as a normal Artifact upload**
  (`data_type='performance'`) in the unified Artifacts area. The performance API
  endpoints are deprecated (kept as back-compat shims / redirects), not deleted,
  in this reform. See [`contracts/routes-and-api.md`](./contracts/routes-and-api.md)
  and **FR-005** / **FR-008**.

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

**Phase 2 — artifacts fold:**
- **AC-007.** Given performance datasets exist, when the fold migration is
  applied, then each `performance_datasets` row appears in `raw_data` with
  `data_type='performance'` and each `performance_dataset_files` row appears in
  `raw_data_files`, while the original performance tables are **retained**.
  *(FR-005, FR-006)*
- **AC-008.** Given a DB snapshot was taken before the fold, when the migration
  runs, then a recoverable checkpoint exists per Article IV. *(NFR-002)*
- **AC-009.** Given a user visits `/performance-datasets`, when the page loads,
  then it resolves via a redirect/alias and does not 404. *(FR-008)*

**Phase 3 — transforms unification:**
- **AC-010.** Given the Visualization transform, when it runs, then it can source
  measurements from the `measurements` view (both sources). *(FR-007)*
- **AC-011.** Given the nav "Analysis" area, when the operator opens it, then
  Visualization and Analyze/Process are presented as transforms over
  Measurements, and legacy `/processing` resolves via redirect. *(FR-001, FR-008)*
- **AC-012.** The smoke test MUST cover the view-backed Analysis, the folded
  performance artifact path, and each legacy-route redirect. *(Article IX)*
