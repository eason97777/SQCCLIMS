# Tasks: Samples

> Derived from [`./plan.md`](./plan.md) (itself derived from
> [`./spec.md`](./spec.md)). This is an **as-built** task list: it is written as
> if planning the build, but boxes are checked `- [x]` to reflect that the
> Samples feature is already implemented and shipping. Numbering is sequential
> across phases; `[P]` marks work that could run in parallel.

## Phase 1 — Data Layer (migrations & schema)

> The `samples` table itself is part of the historical `init_db()` baseline; the
> identity columns and unique constraints were layered on via the migration
> system (Article V). FKs from children use `ON DELETE CASCADE` except the two
> documented `SET NULL` exceptions (Article IV).

- [x] T001 Define the baseline `samples` table in `app/migrations.py` `init_db()`
  with `sample_uid`, `sample_display_code`, `sample_code`, `name`, `category`,
  `batch`, `owner`, `status`, `received_at`, `notes`, timestamps, and
  `UNIQUE(sample_display_code)`. *(FR-001, FR-003)*
- [x] T002 Add identity migrations: backfill/ensure `sample_uid` &
  `sample_display_code`, create `idx_samples_identity_unique` on
  `(sample_code, name, category, batch)` and `idx_samples_display_code_unique`,
  and drop the legacy single-column `UNIQUE(sample_code)`
  (`ensure_samples_composite_unique`). *(FR-003, FR-004, depends on T001)*
- [x] T003 Confirm every child table references `samples(id)` with
  `ON DELETE CASCADE`, and that `processing_jobs`/`processing_results` use
  `ON DELETE SET NULL`, recorded in the per-entity table in
  [`docs/Data_Flow.md`](../../docs/Data_Flow.md). *(FR-011, Article IV, depends on T001)*

## Phase 2 — Feature Module (service logic + SQL)

> `app/features/samples.py` owns handlers, validation, and parameterized SQL
> (Articles III, VII); errors via the exception convention (Article VI).

- [x] T004 Implement `generate_sample_uid()` (year-scoped `SMP-YYYY-NNNNNN`,
  gap-tolerant max-seq + 1) and `build_sample_display_code()`. *(FR-002, FR-003, depends on T002)*
- [x] T005 Implement `validate_sample_payload()` and
  `validate_sample_hierarchy()`: required fields, garbled-text + sequence checks,
  display-code uniqueness, and name consistency across project number and
  project+process type; raise `ValueError`. *(FR-004, FR-005, FR-006, depends on T004)*
- [x] T006 Implement `create_sample()` and `update_sample()`: build fields,
  default `status="待测试"`, run hierarchy validation, parameterized INSERT/UPDATE,
  map `IntegrityError` → `ValueError`, raise `LookupError` for missing sample on
  update. *(FR-001, FR-009, FR-014, depends on T005)*
- [x] T007 Implement `get_samples()`: optional `query`/`status` `WHERE`, LEFT
  JOIN `test_data` for `data_count` & `last_measured_at`, order
  `created_at DESC, id DESC`, all params bound. *(FR-007, FR-008, depends on T004)*
- [x] T008 Implement Strong-tier `delete_sample()`: `backup_database()`,
  collect descendant + `processing_jobs` output paths, `record_deletion` audit
  snapshot, explicit `processing_jobs` delete, sample delete (DB cascade), then
  `remove_files()` after commit. *(FR-011, FR-012, depends on T006)*
- [x] T009 [P] Implement read-only `sample_delete_preview()` in
  `app/deletion.py` returning per-category counts + `files_total`, modifying
  nothing. *(FR-010, depends on T003)*
- [x] T010 [P] Read all paths via `connect_db()` / `app.config` at call time, not
  at import (Article VIII). *(depends on T004)*

## Phase 3 — HTTP Routes (thin handler)

> Dispatch entries only — no business logic in `handler.py` (Articles II, III).

- [x] T011 Register `GET /api/samples`, `POST /api/samples` (201),
  `PUT /api/samples/{id}`, `DELETE /api/samples/{id}` in
  `app/http/handler.py`. *(FR-001, FR-007, FR-009, FR-011, depends on T006, T007, T008)*
- [x] T012 Register `GET /api/samples/{id}/delete-preview`,
  `/mes-route`, and `/characterization-tree`, matched **before** the generic
  `/api/samples/` PUT/DELETE branch so suffixes aren't swallowed. *(FR-010, FR-013, depends on T009)*
- [x] T013 Confirm `authorize()` enforces `GET ≤ operator-write ≤ admin-delete`
  on these paths when auth is enabled, and is a no-op when disabled
  (Article XI). *(depends on T011)*

## Phase 4 — Frontend

> API wrapper + types + page, matching existing `frontend/src/` structure.

- [x] T014 Add `frontend/src/api/samplesApi.ts` wrappers: `getSamples`,
  `createSample`, `updateSample`, `deleteSample`, `getSampleDeletePreview`. *(FR-001, FR-007, FR-009, depends on T011)*
- [x] T015 [P] Define `frontend/src/types/sample.ts`
  (`Sample`, `SamplePayload`, `SampleListParams`, `SampleDeletePreview`,
  `DeleteResponse`). *(depends on T014)*
- [x] T016 [P] Build `frontend/src/pages/SamplesPage.tsx`: list with
  query/status filters, create/edit form, and the delete-preview dialog that
  shows cascade counts before confirming the Strong-tier delete (Article IV). *(FR-008, FR-010, depends on T014)*

## Phase 5 — Tests

> The smoke test is the green-light oracle (Article IX).

- [x] T017 Capture a baseline: run `python3 tests/smoke_test.py` before changes. *(Article IX)*
- [x] T018 Extend `tests/smoke_test.py`: create (assert UID shape + display
  code), list with filters, update, delete-preview (assert counts), and cascade
  delete (assert children/files gone + audit row). *(AC-001…AC-009, depends on T011, T012)*
- [x] T019 Run the full smoke test and confirm green. *(depends on T018)*

## Phase 6 — Docs

> Keep the as-built reference layer accurate.

- [x] T020 Reflect the samples module/endpoints in
  [`docs/BACKEND_MODULES.md`](../../docs/BACKEND_MODULES.md) and the data model in
  [`docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md) /
  [`docs/Data_Flow.md`](../../docs/Data_Flow.md). *(depends on T019)*
- [x] T021 Keep this spec set in sync; spec status is **Implemented** with no
  remaining `[NEEDS CLARIFICATION]`. *(depends on T019)*

> **Known deferred (not tasks):** `GET /api/samples/{id}` detail endpoint,
> pagination, and soft-delete are intentionally out of scope (Article X / spec
> Out of Scope).
