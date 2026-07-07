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
| 2 | rows in `raw_data` / `raw_data_files` | data copy (`INSERT…SELECT`) | No — copies; source retained |
| — | `test_data`, `parsed_records` | kept as-is (view reads them) | No |
| — | `performance_datasets`, `performance_dataset_files` | kept until verified, then later cleanup (out of scope) | No |

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
`samples` for the display columns `run_qc`/`run_normalize` emit). The output
column names (`metric_name`, `unit`, `numeric_value`, `sample_*`) are preserved
so `run_stats`/`run_qc`/`run_normalize` are unchanged.

---

## Phase 2 — Performance fold into `raw_data` / `raw_data_files`

**Purpose.** Make performance datasets ordinary **Artifacts** of type
`performance` (files-only, no parser), so "attach files to a sample" is one
concept. Forward-only `INSERT…SELECT`; source tables retained until verified.

### `performance_datasets` → `raw_data` (`data_type='performance'`)

| `raw_data` column | Source / value | Notes |
|-------------------|----------------|-------|
| `sample_id` | `pd.sample_id` | clean map |
| `sample_uid` | `s.sample_uid` (join `samples`) | `performance_datasets` stores no uid |
| `sample_display_code` | `s.sample_display_code` (join `samples`) | ditto |
| `raw_data_code` | **synthesized** — e.g. `'RD-' || s.sample_uid || '-PERFORMANCE-' || <yyyymmdd from pd.collected_at/created_at> || '-' || printf('%03d', row_seq)` | `raw_data_code` is `UNIQUE NOT NULL`; performance has no code. Must be deterministic + collision-free (see risk). |
| `raw_data_name` | `pd.dataset_name` | `NOT NULL`; `dataset_name` is `NOT NULL` — clean |
| `data_type` | literal `'performance'` | the artifact-type marker |
| `data_category` | literal `'performance'` (or `'other'`) | `raw_data` has `data_category`; performance has no analogue. `RAW_DATA_TYPES` would gain a `performance` entry (config, files-only, no parser) |
| `source_type` | `pd.data_format` or `''` | best-fit |
| `instrument` | `''` | performance has no instrument column |
| `operator` | `pd.operator` | clean |
| `measured_at` | `pd.collected_at` | clean |
| `parser_status` | literal `'not_parsed'` | performance is files-only; **never parsed** |
| `status` | `pd.status` (or literal `'imported'`) | `pd.status` default is `待处理`; map to `'imported'` to match `raw_data` conventions |
| `file_count` | `pd.file_count` | clean |
| `total_size` | `pd.total_bytes` | **column rename**: `total_bytes` → `total_size` |
| `storage_path` | `pd.storage_dir` | **column rename**: `storage_dir` → `storage_path` |
| `metadata_json` | **JSON blob** preserving `aliquot_code`, `test_type`, `data_format`, `source_folder_name` | these have **no `raw_data` home**; preserve them here so nothing is lost |
| `notes` | `pd.notes` | clean |
| `created_at` | `pd.created_at` | clean |
| `updated_at` | `pd.created_at` | `performance_datasets` has **no `updated_at`**; seed from `created_at` |

**Columns that do NOT map cleanly (must be preserved in `metadata_json`):**
`aliquot_code`, `test_type`, `data_format`, `source_folder_name`. There is no
lossless `raw_data` column for these; the migration must fold them into
`metadata_json` rather than drop them (Article IV spirit — no silent loss).

### `performance_dataset_files` → `raw_data_files`

| `raw_data_files` column | Source / value | Notes |
|-------------------------|----------------|-------|
| `raw_data_id` | the new `raw_data.id` for the parent dataset | requires a join/lookup mapping old `dataset_id` → new `raw_data.id` |
| `original_filename` | `pdf.original_filename` | clean |
| `stored_filename` | `pdf.stored_filename` | clean |
| `relative_path` | `pdf.relative_path` | clean |
| `file_path` | `pdf.storage_path` | **column rename**: `storage_path` → `file_path` |
| `file_ext` | derived from `original_filename` suffix, else `''` | `performance_dataset_files` has **no `file_ext`** |
| `mime_type` | `pdf.mime_type` | clean |
| `file_size` | `pdf.file_size` | clean |
| `sha256` | `''` | `performance_dataset_files` has **no `sha256`**; default empty (archive at upload already covered originals) |
| `file_role` | literal `'raw'` | default matches `raw_data_files` default |
| `preview_supported` | `0` (or derive via `preview_type_for_file`) | no such column in source; default 0 |
| `created_at` | `pdf.created_at` | clean |

**Mapping the parent id.** `performance_dataset_files.dataset_id` references the
old `performance_datasets.id`; the fold must translate that to the *new*
`raw_data.id`. Options (decide at implementation): (a) fold datasets first while
recording a `dataset_id → raw_data_id` map (e.g. via the synthesized
`raw_data_code` as a stable join key), then fold files joining on that; or
(b) a single migration that stores the old `dataset_id` in `raw_data.metadata_json`
to bridge the join. Option (a) is preferred for clarity.

### Deletion / data-safety (Article IV)

Folded performance artifacts become ordinary `raw_data` rows and inherit
`raw_data`'s existing **Strong-tier** deletion: `delete_raw_data()` already calls
`backup_database()`, cascades `raw_data_files` via `ON DELETE CASCADE`, and
records `deletion_audit`. No new deletable-entity semantics are introduced. The
pre-existing `performance_datasets` row in `docs/Data_Flow.md` remains valid
until those source tables are removed in a later, separately-approved cleanup.

---

## Kept / deprecated / deferred

| Table / object | Status after this reform |
|----------------|--------------------------|
| `test_data` | **Kept, read-write.** Manual measurements still write here; the view reads it. |
| `parsed_records` | **Kept, read-write.** Parser still writes here; the view reads it. |
| `measurements` (view) | **New, read-only.** The unified read model. |
| `raw_data` / `raw_data_files` | **Kept, extended** to host `data_type='performance'` artifacts. |
| `performance_datasets` / `performance_dataset_files` | **Deprecated but retained** after Phase 2 (read-only in practice once the create path is reframed). Physical removal is out of scope. |
| `characterization_*` | **Unchanged.** Fold explicitly deferred. |
| `processing_jobs` | **Unchanged.** Renamed *in copy only* to "parse / visualization job log". |
| `processing_results` | **Unchanged.** Analysis output. |
| `process_records` | **Unchanged.** MES / 工艺记录 traveller. |
| Physical unified `measurements` table | **Not built.** Out of scope; the view is the deliverable. |

## Per-phase migration approach (all forward-only)

1. **Phase 1:** `migrations/NNN_measurements_view.sql` — one `CREATE VIEW`.
2. **Phase 2:** `migrations/NNN_fold_performance_into_raw_data.sql` — the two
   `INSERT…SELECT` blocks above, preceded operationally by a DB backup; source
   tables retained.
3. **Phase 0 & 3:** no schema; frontend/docs/feature-source changes only.

No applied migration is ever edited; each new file carries a monotonic numeric
prefix and is checksum-guarded by `run_migrations()` (Article V).
