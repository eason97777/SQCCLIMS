# Data Model — Domain Model Reform (Target)

> The concrete **target schema** for [`spec.md`](./spec.md) / [`plan.md`](./plan.md).
> All column names are grounded in `app/migrations.py` (the as-built schema).
> Every change here is delivered as a **new** forward-only `migrations/NNN_*.sql`
> (Article V); no applied migration or `init_db()` baseline is edited.
>
> **Draft — illustrative SQL.** The SQL below is the intended shape for review,
> not a committed migration file. Exact column lists must be re-verified against
> the live schema at implementation time.

## Overview of changes

| Phase | Object | Kind | Destructive? |
|-------|--------|------|--------------|
| 1 | `measurements` view | new SQL VIEW (read model) | No — additive, read-only |
| 2 | `artifacts` / `artifact_files` views | new SQL VIEWs (read model) | No — additive, read-only |
| — | `test_data`, `parsed_records` | kept as-is (measurements view reads them) | No |
| — | `raw_data`, `raw_data_files` | kept as-is (artifacts views read them) | No |
| — | `performance_datasets`, `performance_dataset_files` | kept as-is (artifacts views read them); physical consolidation out of scope | No |

---

## Phase 1 — The `measurements` read model (SQL VIEW)

**Purpose.** Present the two existing measurement stores through one common shape
so transforms can operate over *all* measurements with **no data migration**.

**Source tables (as-built, from `app/migrations.py`):**

- `test_data(id, sample_id, test_name, metric_name, numeric_value, unit,
  measured_at, operator, environment, raw_note, created_at)` — the **manual**
  source. Has a real `metric_name`, `unit`, and `measured_at`.
- `parsed_records(id, parsed_data_id, raw_data_id, sample_id, sample_uid,
  raw_data_code, data_type, record_index, …, numeric_value, raw_value,
  cleaned_value, …, created_at)` — the **parsed** source. Has `numeric_value` and
  `data_type` but **no `metric_name`, no `unit`, no `measured_at`**.

**Common projected columns (the read model contract):**

| View column | manual (`test_data`) | parsed (`parsed_records`) | Note |
|-------------|----------------------|---------------------------|------|
| `source` | literal `'manual'` | literal `'parsed'` | discriminator |
| `source_row_id` | `td.id` | `pr.id` | row identity within its source |
| `sample_id` | `td.sample_id` | `pr.sample_id` | |
| `metric_name` | `td.metric_name` | **derived per `data_type`** via `CASE` (see below) | parsed has no `metric_name` column; the view derives a finer label per type (RC-2). `cd_sem` composes `side`/`direction`/`row_group`; `resistance` → `'resistance'`; else `data_type`. |
| `data_type` | `td.test_name` | `pr.data_type` | keep both groupings available |
| `numeric_value` | `td.numeric_value` | `pr.numeric_value` | the analyzable number |
| `unit` | `td.unit` | `''` | parsed has no unit column (deferred; some units live in `extra_json`) |
| `measured_at` | `td.measured_at` | `pr.created_at` | parsed has no measured-at → use `created_at` |
| `created_at` | `td.created_at` | `pr.created_at` | |

**Illustrative view SQL** (to live in `migrations/NNN_measurements_view.sql`):

```sql
-- Additive, non-destructive read model. UNION of the two measurement stores.
-- Column list is fixed and code-authored (Article VII: no request data in SQL).
CREATE VIEW IF NOT EXISTS measurements AS
    SELECT
        'manual'            AS source,
        td.id               AS source_row_id,
        td.sample_id        AS sample_id,
        td.metric_name      AS metric_name,
        td.test_name        AS data_type,
        td.numeric_value    AS numeric_value,
        td.unit             AS unit,
        td.measured_at      AS measured_at,
        td.created_at       AS created_at
    FROM test_data td
    WHERE td.numeric_value IS NOT NULL

    UNION ALL

    SELECT
        'parsed'            AS source,
        pr.id               AS source_row_id,
        pr.sample_id        AS sample_id,
        -- metric_name derived per data_type (RC-2). Pure, code-authored SQL —
        -- no request data (Article VII). data_type is also kept as its own
        -- column below so Analysis can group by either.
        CASE pr.data_type
            WHEN 'cd_sem' THEN
                'cd_sem'
                || COALESCE('/' || NULLIF(pr.side, ''), '')
                || COALESCE('/' || NULLIF(pr.direction, ''), '')
                || COALESCE(' ' || NULLIF(pr.row_group, ''), '')
            WHEN 'resistance' THEN 'resistance'
            ELSE pr.data_type
        END                 AS metric_name,
        pr.data_type        AS data_type,
        pr.numeric_value    AS numeric_value,
        ''                  AS unit,
        pr.created_at       AS measured_at,
        pr.created_at       AS created_at
    FROM parsed_records pr
    WHERE pr.numeric_value IS NOT NULL;
```

Notes:
- **Parsed `metric_name` derivation (RC-2).** The `CASE pr.data_type` expression
  yields a finer metric label for parsed rows while `data_type` is retained as
  its own column. `cd_sem` composes from the CD/SEM position fields — `side`,
  `direction`, `row_group` (all real `TEXT` columns on `parsed_records`, verified
  in `app/migrations.py`) — e.g. `cd_sem/left/x row1`; empty position fields are
  dropped via `NULLIF(...,'')` + `COALESCE`. `resistance` maps to the literal
  `'resistance'` (its finer dimensions — `die_id`, `area`, `row_index`,
  `col_index` — remain their own columns, not folded into the label). Every other
  type falls back to bare `data_type`. The expression uses only fixed,
  code-authored SQL (Article VII: no request data). The exact per-type
  composition is operator-confirmable.
- `UNION ALL` (not `UNION`) — the two sources never collide on identity and we
  must not silently drop duplicate numeric values.
- Parsed rows without a `numeric_value` (e.g. text-only records) are excluded so
  Analysis math never sees NULLs — matching how `run_processing` treats
  `test_data.numeric_value` as `NOT NULL` today.
- The view does **not** need its own index; SQLite pushes predicates down to the
  base-table indexes (`idx_test_data_metric`, `idx_parsed_records_data_type`,
  and the `sample_id` indexes), which already exist.
- **No `BEGIN`/`COMMIT`** in the migration file — `run_migrations()` owns the
  per-file transaction (Article V).

**Consumer change (Phase 1, feature layer — not schema):**
`app/features/processing.py :: fetch_processing_source()` changes its `FROM
test_data td JOIN samples s` to source rows from `measurements` (joined to
`samples` for the display columns `run_qc`/`run_normalize` emit). `run_stats` is
unchanged (it reads `metric_name`/`unit`/`numeric_value`). **`run_qc` and
`run_normalize` today emit `row["id"]`** — but the view exposes `source_row_id`
+ `source` rather than a bare `id` (because `test_data.id` and `parsed_records.id`
overlap and would be ambiguous once unioned), so those two functions must emit
`source` + `source_row_id` instead. The frontend `ProcessingResultViewer`
ignores that field today (it renders `metric_name`/`value`/sample columns), so
the change is consumer-invisible; the added `source` is reflected in the
`/api/process` contract.

---

## Phase 2 — The `artifacts` read model (SQL VIEWs)

**Purpose.** Present performance datasets as ordinary **Artifacts** of type
`performance` (files-only, no parser), so "attach files to a sample" is one
concept — **without moving data**. Mirrors Phase 1: an `artifacts` VIEW over
`raw_data` ∪ `performance_datasets`, and an `artifact_files` VIEW over
`raw_data_files` ∪ `performance_dataset_files`. Additive, read-only; the source
tables are read in place. New performance uploads are reframed to write
`raw_data` (`data_type='performance'`) going forward; a physical consolidation
of the legacy performance rows is out of scope.

**Identity.** `raw_data.id` and `performance_datasets.id` overlap, so the view
carries `source` (`'raw_data'` / `'performance'`) + `source_row_id`. Reads,
links, and deletes MUST key off `(source, source_row_id)` — a performance-origin
artifact is created/deleted against `performance_datasets`, a raw_data-origin one
against `raw_data`.

### `artifacts` view — `raw_data` branch (identity map) ∪ `performance_datasets` branch

The `raw_data` branch projects its own columns 1:1 (`source='raw_data'`,
`source_row_id=rd.id`). The `performance_datasets` branch maps into the same
shape:

| `artifacts` column | `raw_data` branch | `performance_datasets` branch | Note |
|--------------------|-------------------|-------------------------------|------|
| `source` | `'raw_data'` | `'performance'` | discriminator |
| `source_row_id` | `rd.id` | `pd.id` | row identity within its source |
| `sample_id` | `rd.sample_id` | `pd.sample_id` | |
| `sample_uid` | `rd.sample_uid` | `s.sample_uid` (join `samples`) | `performance_datasets` stores no uid |
| `sample_display_code` | `rd.sample_display_code` | `s.sample_display_code` (join `samples`) | ditto |
| `artifact_code` | `rd.raw_data_code` | **derived** — e.g. `'PERF-' || pd.id` (a stable display label; not a `raw_data` insert, so no `UNIQUE NOT NULL` constraint applies) | performance has no code; the view only needs a readable label |
| `artifact_name` | `rd.raw_data_name` | `pd.dataset_name` | |
| `data_type` | `rd.data_type` | literal `'performance'` | the artifact-type marker |
| `data_category` | `rd.data_category` | literal `'performance'` | `RAW_DATA_TYPES` gains a `performance` entry (config, files-only, no parser) so new uploads categorize |
| `source_type` | `rd.source_type` | `pd.data_format` | best-fit |
| `instrument` | `rd.instrument` | `''` | performance has no instrument column |
| `operator` | `rd.operator` | `pd.operator` | |
| `measured_at` | `rd.measured_at` | `pd.collected_at` | **rename** |
| `parser_status` | `rd.parser_status` | literal `'not_parsed'` | performance is files-only; **never parsed** |
| `status` | `rd.status` | `pd.status` | |
| `file_count` | `rd.file_count` | `pd.file_count` | |
| `total_size` | `rd.total_size` | `pd.total_bytes` | **rename**: `total_bytes` → `total_size` |
| `storage_path` | `rd.storage_path` | `pd.storage_dir` | **rename**: `storage_dir` → `storage_path` |
| `metadata_json` | `rd.metadata_json` | **JSON expression** folding `aliquot_code` / `test_type` / `data_format` / `source_folder_name` | these have **no `raw_data` home**; surface them here so nothing is hidden |
| `notes` | `rd.notes` | `pd.notes` | |
| `created_at` | `rd.created_at` | `pd.created_at` | |
| `updated_at` | `rd.updated_at` | `pd.created_at` | `performance_datasets` has **no `updated_at`**; use `created_at` |

> The `metadata_json` fold for the performance branch is a pure, code-authored
> SQL expression (e.g. `json_object('aliquot_code', pd.aliquot_code, …)` or a
> fixed string concat) — no request data (Article VII).

### `artifact_files` view — `raw_data_files` branch ∪ `performance_dataset_files` branch

| `artifact_files` column | `raw_data_files` branch | `performance_dataset_files` branch | Note |
|-------------------------|-------------------------|------------------------------------|------|
| `source` | `'raw_data'` | `'performance'` | discriminator |
| `source_row_id` | `rdf.id` | `pdf.id` | |
| `parent_source_row_id` | `rdf.raw_data_id` | `pdf.dataset_id` | id of the owning artifact **within the same `source`** |
| `original_filename` | `rdf.original_filename` | `pdf.original_filename` | |
| `stored_filename` | `rdf.stored_filename` | `pdf.stored_filename` | |
| `relative_path` | `rdf.relative_path` | `pdf.relative_path` | |
| `file_path` | `rdf.file_path` | `pdf.storage_path` | **rename**: `storage_path` → `file_path` |
| `file_ext` | `rdf.file_ext` | derived from `original_filename` suffix, else `''` | `performance_dataset_files` has **no `file_ext`** |
| `mime_type` | `rdf.mime_type` | `pdf.mime_type` | |
| `file_size` | `rdf.file_size` | `pdf.file_size` | |
| `sha256` | `rdf.sha256` | `''` | `performance_dataset_files` has **no `sha256`**; default empty (the upload archive already keyed originals by hash) |
| `file_role` | `rdf.file_role` | literal `'raw'` | matches `raw_data_files` default |
| `preview_supported` | `rdf.preview_supported` | `0` | no such column in source; default 0 |
| `created_at` | `rdf.created_at` | `pdf.created_at` | |

**Joining files to their artifact.** Because the parent id is only unique *within
a source*, a file is matched to its artifact on `(source, parent_source_row_id)`
= `(source, source_row_id)` — never on `source_row_id` alone.

### Deletion / data-safety (Article IV)

**Nothing is copied**, so a physical file is still referenced by exactly one
row/owner, exactly as today. Deletes route by `source`: a raw_data-origin
artifact deletes via `delete_raw_data()` (`backup_database()` + `ON DELETE
CASCADE` on `raw_data_files` + `deletion_audit`); a performance-origin artifact
deletes via the existing `delete_performance_dataset()` path (same guarantees).
No new deletable-entity semantics are introduced, and there is no shared-file /
double-delete hazard. The existing `performance_datasets` / `raw_data` rows in
`docs/Data_Flow.md` remain valid unchanged.

---

## Kept / deprecated / deferred

| Table / object | Status after this reform |
|----------------|--------------------------|
| `test_data` | **Kept, read-write.** Manual measurements still write here; the view reads it. |
| `parsed_records` | **Kept, read-write.** Parser still writes here; the view reads it. |
| `measurements` (view) | **New, read-only.** The unified measurement read model. |
| `artifacts` / `artifact_files` (views) | **New, read-only.** The unified artifact read model. |
| `raw_data` / `raw_data_files` | **Kept, read-write.** Uploads still write here; the `artifacts` views read them. New performance uploads write here as `data_type='performance'`. |
| `performance_datasets` / `performance_dataset_files` | **Kept, read (write path reframed).** The `artifacts` views read them in place; the standalone API stays live over them. Physical removal is out of scope. |
| `characterization_*` | **Unchanged.** Fold explicitly deferred. |
| `processing_jobs` | **Unchanged.** Renamed *in copy only* to "parse / visualization job log". |
| `processing_results` | **Unchanged.** Analysis output. |
| `process_records` | **Unchanged.** MES / 工艺记录 traveller. |
| Physical unified `measurements` / `artifacts` tables | **Not built.** Out of scope; the views are the deliverable. |

## Per-phase migration approach (all forward-only)

1. **Phase 1:** `migrations/NNN_measurements_view.sql` — one `CREATE VIEW`.
2. **Phase 2:** `migrations/NNN_artifacts_view.sql` — two `CREATE VIEW` blocks
   (`artifacts`, `artifact_files`). Additive, read-only; no data moves, so no
   pre-migration backup is required.
3. **Phase 0 & 3:** no schema; frontend/docs/feature-source changes only.

No applied migration is ever edited; each new file carries a monotonic numeric
prefix and is checksum-guarded by `run_migrations()` (Article V).
