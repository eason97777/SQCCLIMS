# Tasks: Domain Model Reform — Sample-Rooted Two-Axis Model

> Derived from [`./plan.md`](./plan.md) (from [`./spec.md`](./spec.md)). Organized
> by the four **phases** of the roadmap (0–3); each phase is independently
> shippable and MUST leave `tests/smoke_test.py` green before the next begins
> (Article IX). Numbering is sequential `T001…` across all phases; `[P]` marks
> tasks that can run in parallel. Each task references its FR and dependencies.
>
> **Draft — all tasks UNCHECKED.** This blueprint requires human approval before
> any task is executed. Do **not** check a box until the task is done *and* the
> smoke test is green.

## Phase 0 — Naming / clarity (ZERO schema)

> Reversible copy/label changes only. No migration.

- [ ] T001 Capture a smoke baseline: run `python3 tests/smoke_test.py` and record the result. *(Article IX)*
- [ ] T002 [P] Relabel "Data Base" → **"Measurements / 测试结果"** in `frontend/src/utils/constants.ts`: update the `NAV_ITEMS` label for `/test-data` and the `VIEW_META` `title`/`eyebrow` for `/test-data` and `/data`. *(FR-002)*
- [ ] T002b [P] Reframe the manual test-data entry form as **"Add a measurement"** under the Measurements / 测试结果 area (`frontend/src/pages/*` + any `frontend/src/utils/constants.ts` copy). **Frontend/UX/label only** — do NOT change the backend write path: `create_test_data` and bulk create still write `test_data` as `source='manual'`; no physical unified table. Non-destructive. *(FR-002b, US-2b)*
- [ ] T003 [P] Disambiguate the three "processing" meanings in UI copy: present `processing_jobs` as the **"parse / visualization job log"**, the Analysis block as **"Analysis"**, and keep `process_records` as **工艺记录 / MES**. *(FR-009)*
- [ ] T004 [P] Reflect the same disambiguation + the two-axis framing in docs (`docs/DOMAIN_MODEL.md` follow-ups, glossary in `docs/ARCHITECTURE.md` if needed). *(FR-009)*
- [ ] T005 Run `python3 tests/smoke_test.py`; confirm green and that `schema_migrations` is unchanged (no migration added in Phase 0). *(FR-012, AC-001, AC-002, AC-003, Article IX)*

## Phase 1 — Measurements read model (SQL VIEW)

> Additive, non-destructive. One new forward-only migration; repoint Analysis.

- [ ] T006 Write `migrations/NNN_measurements_view.sql` creating the `measurements` VIEW as a `UNION ALL` of `test_data` (`source='manual'`) and `parsed_records` (`source='parsed'`) with the common columns, per [`./data-model.md`](./data-model.md). Derive the parsed-row `metric_name` per `data_type` via the pure-SQL `CASE` (compose `side`/`direction`/`row_group` for `cd_sem`; literal `'resistance'`; else `data_type`) and keep `data_type` as its own column (RC-2). No `BEGIN`/`COMMIT`. *(FR-003, FR-010, FR-011, Article V, Article VII, depends on T005)*
- [ ] T007 Apply migrations locally; confirm `schema_migrations` records the new file with a checksum and that no `test_data`/`parsed_records` row was altered. *(FR-010, FR-011, depends on T006)*
- [ ] T008 Repoint `app/features/processing.py :: fetch_processing_source()` to source rows from the `measurements` view (joined to `samples` for display columns). `run_stats` is unchanged; update `run_qc` and `run_normalize` to emit `source` + `source_row_id` instead of `row["id"]` (the view has no bare `id` — `test_data.id`/`parsed_records.id` overlap). The frontend `ProcessingResultViewer` ignores that field today, so this is consumer-invisible. *(FR-004, Article VII, depends on T007)*
- [ ] T009 Verify parameterized SQL only and config read at call time in the changed query path (Articles VII, VIII). *(depends on T008)*
- [ ] T010 Extend `tests/smoke_test.py`: seed a sample with one manual `test_data` row and one parsed record; assert the view returns both and Analysis `source_count` reflects both sources. *(AC-004, AC-005, AC-006, depends on T008)*
- [ ] T011 Run `python3 tests/smoke_test.py`; confirm green. *(FR-012, Article IX, depends on T010)*

## Phase 2 — Artifacts read model (performance via the `artifacts` view)

> Additive, non-destructive. Two new read-only VIEWs; no data moves; no backup needed.

- [ ] T012 Add a `performance` entry to `RAW_DATA_TYPES` in `app/config.py` (files-only, no parser, category `performance`/`other`) so new performance uploads categorize as Artifacts. *(FR-005, depends on T011)*
- [ ] T013 Write `migrations/NNN_artifacts_view.sql`: `CREATE VIEW artifacts` UNION-ing `raw_data` (identity map, `source='raw_data'`) with `performance_datasets` mapped into `raw_data`'s shape (`data_type='performance'`, `source='performance'`, `source_row_id=pd.id`, `total_bytes→total_size`, `storage_dir→storage_path`, `collected_at→measured_at`, and `aliquot_code`/`test_type`/`data_format`/`source_folder_name` folded into a code-authored `metadata_json` expression). Then `CREATE VIEW artifact_files` UNION-ing `raw_data_files` with `performance_dataset_files` (`storage_path→file_path`, derive `file_ext`, default `sha256=''`/`preview_supported=0`, carry `source` + `parent_source_row_id`). Per [`./data-model.md`](./data-model.md). No `BEGIN`/`COMMIT`. *(FR-005, FR-006, FR-010, Article V, Article VII, depends on T012)*
- [ ] T014 Apply migrations locally; confirm the views are created, `schema_migrations` records the file with a checksum, and **no** `raw_data`/`performance_datasets`/file row was altered (nothing is copied; no pre-migration snapshot required). *(FR-006, FR-011, NFR-001, NFR-002, AC-008, Article IV, depends on T013)*
- [ ] T015 Assert each `performance_datasets` row is queryable via the `artifacts` view with `data_type='performance'` (and its files via `artifact_files`), joined on `(source, source_row_id)`. *(FR-005, AC-007, depends on T014)*
- [ ] T016 Point the Artifact list/detail reads (`app/features/raw_data.py`) at the `artifacts`/`artifact_files` views; reframe the performance create path (`app/features/performance.py`) so new uploads write `raw_data` (`data_type='performance'`); route deletes by `source` to the existing owning delete path. Keep the existing performance endpoints live over the retained tables per [`./contracts/routes-and-api.md`](./contracts/routes-and-api.md). *(FR-005, FR-008, depends on T015)*
- [ ] T017 [P] Add **frontend-only** legacy-route redirects in `frontend/src/router/index.tsx` for `/performance-datasets` and `/performance` → Raw Data / Artifacts (`data_type=performance`), reusing the existing alias pattern. No `handler.py` change. *(FR-008, AC-009, depends on T015)*
- [ ] T018 [P] Frontend: present performance as an artifact type under Raw Data / Artifacts (`frontend/src/pages/*`, `frontend/src/utils/constants.ts` nav). *(FR-005, depends on T015)*
- [ ] T019 Confirm `docs/Data_Flow.md` still holds: performance-origin artifacts delete via the existing `delete_performance_dataset` path and raw_data-origin via `delete_raw_data`; note the deprecated (retained, read-in-place) performance tables. No new deletion semantics. *(Article IV, depends on T015)*
- [ ] T020 Extend `tests/smoke_test.py`: assert performance rows are queryable via the `artifacts` view (`data_type='performance'`) and that `/performance-datasets` resolves via the frontend redirect. *(AC-007, AC-009, depends on T016, T017)*
- [ ] T021 Run `python3 tests/smoke_test.py`; confirm green. *(FR-012, Article IX, depends on T020)*

## Phase 3 — Transforms unification (nav only)

> Analysis nav grouping + `/processing` frontend redirect. Visualization-over-view deferred (FR-007).

- [ ] T022 [P] Reposition Processing as a general **Analysis** transform and unify the nav "Analysis" area (Analyze/Process, with Visualization as a navigational grouping only) in `frontend/src/utils/constants.ts` + `frontend/src/router/index.tsx`. *(FR-001, depends on T011)*
- [ ] T023 [P] Add/confirm the `/processing` → Analysis **frontend** redirect/alias (reusing the existing router alias pattern; no backend change). *(FR-008, AC-011, depends on T022)*
- [ ] T024 Extend `tests/smoke_test.py`: assert the Analysis nav grouping + the `/processing` frontend redirect resolve. *(AC-011, AC-012, depends on T022, T023)*
- [ ] T025 Run `python3 tests/smoke_test.py`; confirm green. *(FR-012, Article IX, depends on T024)*

> **FR-007 / AC-010 (visualization over the read model) are deferred** and carry
> no task in this reform — see [`./spec.md`](./spec.md) Out of Scope.

## Closeout (after all phases approved & shipped)

- [ ] T026 Update `docs/ARCHITECTURE.md` and `docs/BACKEND_MODULES.md` to describe the two-axis model, the `measurements` and `artifacts` read models, and performance-as-artifact. *(depends on T025)*
- [ ] T027 Keep `spec.md` Status current as phases land: the spec's clarifications are already resolved (RC-1..RC-4, no `[NEEDS CLARIFICATION]` remaining), so advance Status from **Draft** toward **Implemented** as each phase ships, and reconfirm the operator-confirmable details (RC-2 metric grouping) held up in practice. *(depends on T025)*
- [ ] T028 (Separate, later, approved change — **out of this reform's scope**) Plan the physical consolidation/removal of the deprecated `performance_datasets` / `performance_dataset_files` tables once the `artifacts` view is fully validated in production. *(not part of committed scope)*
