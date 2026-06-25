# Tasks: Raw Data Upload, Parsing & Visualization

> Derived from [`./plan.md`](./plan.md) / [`./spec.md`](./spec.md). This is an
> **as-built** task list: every box is checked `[x]` because the feature is
> already implemented and the smoke test (`tests/smoke_test.py`, Article IX) is
> green. Numbering is sequential across phases; `[P]` marks work that was (or
> could be) done in parallel.

## Phase 1 — Data Layer (schema & indexes)

> Baseline tables live in `init_db()`; later columns added idempotently in
> `migrate_db()`. Any *future* change MUST be a new `migrations/NNN_*.sql`
> (Article V).

- [x] T001 Define `raw_data` (unique `raw_data_code`, FK→`samples` ON DELETE CASCADE) in `init_db()`. *(FR-001, FR-002)*
- [x] T002 Define `raw_data_files` (FK→`raw_data` ON DELETE CASCADE, `sha256`, `file_size`, `preview_supported`). *(FR-005, FR-006)*
- [x] T003 Define `parsed_data` (FK→`raw_data`/`samples` ON DELETE CASCADE; summary/plots/warnings/errors JSON, `record_count`). *(FR-009, FR-011)*
- [x] T004 Define `parsed_records` (union schema for resistance + CD/SEM; FK→`parsed_data` ON DELETE CASCADE) and its filter indexes (die/area, cd_sem filters, outlier). *(FR-008, FR-012)*
- [x] T005 Define `processing_jobs` (FKs ON DELETE SET NULL) for parse/visualization audit. *(FR-007, FR-015)*
- [x] T006 [P] Backfill `parsed_data.record_count` / `parsed_data.updated_at` idempotently in `migrate_db()`. *(FR-009)*
- [x] T007 Record the new deletable entities (`raw_data`, `raw_data_files`, `parsed_data`) in the per-entity deletion table of [`docs/Data_Flow.md`](../../docs/Data_Flow.md) with cascade/archive/audit handling. *(FR-017, FR-018, Article IV)*

## Phase 2 — Feature Module(s) (service logic + SQL)

> Three lifecycle-stage modules under `app/features/` (see plan Article III note).
> Errors via the exception convention (Article VI); parameterized SQL (VII);
> `config.<NAME>` at call time (VIII).

- [x] T008 `raw_data.py`: `create_raw_data` (validate type via `config.RAW_DATA_TYPES`, derive category, generate `raw_data_code`, insert). *(FR-001, FR-002, depends T001)*
- [x] T009 `raw_data.py`: `get_raw_data_list` (filter by sample/type/parser_status/status + free-text search) and `get_raw_data_detail` (with files + counts). *(FR-003, FR-004, depends T001)*
- [x] T010 `raw_data.py`: `upload_raw_data_files` — save each file via `storage.save_raw_data_file`, archive via `archive.archive_file`, insert rows, update `file_count`/`total_size`. *(FR-005, FR-006, depends T002)*
- [x] T011 `parsing.py`: `parse_raw_data` — pick parser by data type, select parseable file, run parser, persist parser_status transitions + `processing_jobs`. *(FR-007, FR-010, depends T008, T010)*
- [x] T012 `parsing.py`: `insert_parsed_data` + `insert_parsed_records` (explode points using `config.PARSED_RECORD_INSERT_COLUMNS`, map keys via `config.PARSED_RECORD_MAPPED_KEYS`). *(FR-008, FR-009, depends T011)*
- [x] T013 [P] `parsers/resistance_csv_parser.py` — parse the 13×13 die-matrix CSV/XLSX into per-cell records + per-die/area/overall summary with strict validation. *(FR-008)*
- [x] T014 [P] `parsers/cd_template_parser.py` — parse the CD/SEM template CSV into per-measurement records (row_group/side/direction/die_no/dose/location/cd_value) with warnings. *(FR-008)*
- [x] T015 `parsing.py`: `get_parsed_data_list`, `get_parsed_data_detail`, `get_parsed_data_records` (paged + filtered), `get_parsed_record_options`. *(FR-011, FR-012, FR-013, depends T012)*
- [x] T016 `visualization.py`: `get_resistance_summary` — clean/classify points, compute per-die/area/overall stats from cleaning limits + metric. *(FR-014, depends T012)*
- [x] T017 `visualization.py`: `create_resistance_visualization_job` + `visualize_parsed_data` (CD violin) writing artifacts under `OUTPUT_DIR` and recording `processing_jobs`. *(FR-015, depends T016)*
- [x] T018 [P] `parsers/resistance_heatmap_visualizer.py` + `parsers/cd_violin_visualizer.py` — render the chart/report artifacts (matplotlib, approved Article I exception). *(FR-015)*
- [x] T019 `visualization.py`: `get_visualization_chart_archive` (zip selected charts) + `get_processing_jobs`. *(FR-016, depends T017)*
- [x] T020 `raw_data.py`: `delete_raw_data` and `delete_raw_data_file` — `backup_database()`, `record_deletion()` audit, cascade rows, central file/output cleanup; block multi-file single-file delete with `ConflictError`. *(FR-018, FR-019, depends T008)*
- [x] T021 `deletion.py`: `raw_data_delete_preview` + `raw_data_file_delete_preview` (read-only blast-radius counts). *(FR-017, depends T020)*

## Phase 3 — HTTP Routes (thin handler)

> Dispatch only — no business logic in `handler.py` (Articles II, III).

- [x] T022 Register raw-data routes: `GET/POST /api/raw-data`, `GET/DELETE /api/raw-data/{id}`, `GET /api/raw-data/{id}/delete-preview`. *(FR-001..FR-004, FR-017, FR-018, depends T008, T020)*
- [x] T023 Register `POST /api/raw-data/{id}/files` (multipart via `read_multipart`) and `POST /api/raw-data/{id}/parse`. *(FR-005, FR-007, depends T010, T011)*
- [x] T024 Register raw-data-file routes: `GET /api/raw-data-files/{id}/download` (stream), `DELETE`, `GET .../delete-preview`. *(FR-016, FR-018, FR-017, depends T020)*
- [x] T025 Register parsed-data routes: list/detail/records/record-options, `POST .../resistance-summary`, `POST .../visualize`. *(FR-011..FR-015, depends T015, T016, T017)*
- [x] T026 Register `GET /api/processing-jobs`, `GET /api/processing-jobs/{id}/charts/download`, and `GET /api/outputs/{path}` streaming. *(FR-015, FR-016, depends T019)*
- [x] T027 Confirm `authorize()` gates all these `/api/` paths uniformly (no-op when disabled; GET ≤ operator-write ≤ admin-delete when enabled). *(NFR-003, Article XI, depends T022)*

## Phase 4 — Frontend

- [x] T028 `frontend/src/types/rawData.ts` — types for records, files, parsed data, records, options, summary, jobs, visualization payloads. *(FR-001..FR-015)*
- [x] T029 `frontend/src/api/rawDataApi.ts` — client wrappers for every endpoint (incl. multipart upload + file/chart downloads). *(FR-001..FR-016)*
- [x] T030 `frontend/src/pages/RawDataPage.tsx` + components (`ParsedDataRecordsTable`, `ResistanceSummaryPanel`, `ResistanceVisualizationPanel`, `ResistanceWaferHeatmap`, `VisualizationPreviewPanel`) — record mgmt, upload, parse, record browsing, summary, and visualization UI. *(US-1..US-6)*

## Phase 5 — Tests

- [x] T031 Extend `tests/smoke_test.py` to cover create → upload → parse → records/options → resistance-summary → visualize → download → delete-preview → delete, asserting status codes and no orphaned rows/files. *(Article IX, all FRs)*

## Phase 6 — Docs

- [x] T032 Document the raw upload → parsing → normalized records flow and the per-entity deletion rows in [`docs/Data_Flow.md`](../../docs/Data_Flow.md). *(FR-017, FR-018)*
- [x] T033 [P] Document the three feature modules + parsers in [`docs/BACKEND_MODULES.md`](../../docs/BACKEND_MODULES.md) and [`docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md); align terms in [`docs/GLOSSARY.md`](../../docs/GLOSSARY.md). *(Key Entities)*
