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
- [ ] T008 Repoint `app/features/processing.py :: fetch_processing_source()` to source rows from the `measurements` view (joined to `samples` for display columns), preserving the output column names so `run_stats`/`run_qc`/`run_normalize` are unchanged. *(FR-004, Article VII, depends on T007)*
- [ ] T009 Verify parameterized SQL only and config read at call time in the changed query path (Articles VII, VIII). *(depends on T008)*
- [ ] T010 Extend `tests/smoke_test.py`: seed a sample with one manual `test_data` row and one parsed record; assert the view returns both and Analysis `source_count` reflects both sources. *(AC-004, AC-005, AC-006, depends on T008)*
- [ ] T011 Run `python3 tests/smoke_test.py`; confirm green. *(FR-012, Article IX, depends on T010)*

## Phase 2 — Artifacts fold (performance → raw_data)

> Forward-only `INSERT…SELECT`; backup first; source tables retained until verified.

- [ ] T012 Add a `performance` entry to `RAW_DATA_TYPES` in `app/config.py` (files-only, no parser, category `performance`/`other`). *(FR-005, depends on T011)*
- [ ] T013 Write `migrations/NNN_fold_performance_into_raw_data.sql`: `INSERT…SELECT` `performance_datasets` → `raw_data` (`data_type='performance'`), synthesizing `raw_data_code`, mapping `total_bytes→total_size`, `storage_dir→storage_path`, seeding `updated_at` from `created_at`, and folding `aliquot_code`/`test_type`/`data_format`/`source_folder_name` into `metadata_json`. Then `INSERT…SELECT` `performance_dataset_files` → `raw_data_files`, mapping `storage_path→file_path`, deriving `file_ext`, defaulting `sha256=''`/`preview_supported=0`, and translating `dataset_id` → new `raw_data.id`. Per [`./data-model.md`](./data-model.md). No `BEGIN`/`COMMIT`. *(FR-005, FR-006, FR-010, Article V, depends on T012)*
- [ ] T014 Confirm a DB snapshot (`backup_database()` / startup snapshot) precedes the fold, and that the source performance tables are **retained** after it (not dropped). *(FR-006, NFR-002, AC-008, Article IV, depends on T013)*
- [ ] T015 Apply migrations locally; assert each `performance_datasets` row appears in `raw_data` with `data_type='performance'` and each `performance_dataset_files` row appears in `raw_data_files`. *(FR-005, AC-007, depends on T013)*
- [ ] T016 Reframe the performance create/upload path (`app/features/performance.py` / `app/features/raw_data.py`) so uploads target the Artifact store; keep or shim the existing performance endpoints for back-compat per [`./contracts/routes-and-api.md`](./contracts/routes-and-api.md). *(FR-005, FR-008, depends on T015)*
- [ ] T017 [P] Add legacy-route redirects in `app/http/handler.py` and `frontend/src/router/index.tsx` for `/performance-datasets` and `/performance` → Raw Data / Artifacts (`data_type=performance`), preserving auth policy. *(FR-008, AC-009, Article XI, depends on T015)*
- [ ] T018 [P] Frontend: present performance as an artifact type under Raw Data / Artifacts (`frontend/src/pages/*`, `frontend/src/utils/constants.ts` nav). *(FR-005, depends on T015)*
- [ ] T019 Update `docs/Data_Flow.md` to reflect folded performance artifacts inheriting `raw_data`'s Strong-tier deletion, and note the deprecated (retained) performance tables. *(Article IV, depends on T015)*
- [ ] T020 Extend `tests/smoke_test.py`: assert folded rows are queryable via `raw_data` (`data_type='performance'`) and that `/performance-datasets` redirects/resolves. *(AC-007, AC-009, depends on T016, T017)*
- [ ] T021 Run `python3 tests/smoke_test.py`; confirm green. *(FR-012, Article IX, depends on T020)*

## Phase 3 — Transforms unification

> Visualization over the view; Analysis nav grouping; deprecate-behind-redirect.

- [ ] T022 Allow `app/features/visualization.py` to source measurements from the `measurements` view (both sources) where the chart type does not require parsed-only layout columns; keep parsed-only paths for charts that need them (per Risks in [`./plan.md`](./plan.md)). *(FR-007, Article VII, depends on T011)*
- [ ] T023 [P] Reposition Processing as a general **Analysis** transform and unify the nav "Analysis" area (Visualization + Analyze/Process over Measurements) in `frontend/src/utils/constants.ts` + `frontend/src/router/index.tsx`. *(FR-001, depends on T011)*
- [ ] T024 [P] Add/confirm the `/processing` → Analysis redirect/alias and deprecate any redundant endpoints behind redirects, preserving auth policy, per [`./contracts/routes-and-api.md`](./contracts/routes-and-api.md). *(FR-008, AC-011, Article XI, depends on T023)*
- [ ] T025 Extend `tests/smoke_test.py`: assert visualization can source the view, and assert the Analysis nav + `/processing` redirect resolve. *(AC-010, AC-011, AC-012, depends on T022, T024)*
- [ ] T026 Run `python3 tests/smoke_test.py`; confirm green. *(FR-012, Article IX, depends on T025)*

## Closeout (after all phases approved & shipped)

- [ ] T027 Update `docs/ARCHITECTURE.md` and `docs/BACKEND_MODULES.md` to describe the two-axis model, the `measurements` view, and performance-as-artifact. *(depends on T026)*
- [ ] T028 Keep `spec.md` Status current as phases land: the spec's clarifications are already resolved (RC-1..RC-4, no `[NEEDS CLARIFICATION]` remaining), so advance Status from **Draft** toward **Implemented** as each phase ships, and reconfirm the operator-confirmable details (RC-2 metric grouping) held up in practice. *(depends on T026)*
- [ ] T029 (Separate, later, approved change — **out of this reform's scope**) Plan the physical removal of the deprecated `performance_datasets` / `performance_dataset_files` tables once the fold is fully verified in production. *(not part of committed scope)*
