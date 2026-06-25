# Data Model: Samples

> As-built data model for the Samples feature. The `samples` table is the **root**
> of the SQCCLIMS data graph: nearly every other table references it. Conceptual
> naming aligns with [`docs/GLOSSARY.md`](../../docs/GLOSSARY.md); the
> authoritative schema lives in `app/migrations.py` and the relationship/cascade
> reference is [`docs/Data_Flow.md`](../../docs/Data_Flow.md).

## `samples` table (baseline schema)

Defined in `app/migrations.py` `init_db()`; identity columns/indexes are layered
on by the migration system (Article V).

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK AUTOINCREMENT | Internal surrogate key; the value used in `/api/samples/{id}` paths and child `sample_id` FKs. |
| `sample_uid` | TEXT NOT NULL DEFAULT '' | Server-generated business identifier `SMP-YYYY-NNNNNN`. Never client-supplied. |
| `sample_display_code` | TEXT NOT NULL DEFAULT '' | Human-readable code derived from `sample_code-name-category-batch`. **UNIQUE.** |
| `sample_code` | TEXT NOT NULL | Project number (项目编号). |
| `name` | TEXT NOT NULL | Sample name (样品名称). |
| `category` | TEXT NOT NULL DEFAULT '' | Process type (工艺类型). |
| `batch` | TEXT NOT NULL DEFAULT '' | Sample sequence (样品序号). |
| `owner` | TEXT NOT NULL DEFAULT '' | Responsible person (optional). |
| `status` | TEXT NOT NULL DEFAULT '待测试' | Sample status; defaults to "待测试" (pending test). |
| `received_at` | TEXT NOT NULL DEFAULT '' | Received date (free-text ISO/date string). |
| `notes` | TEXT NOT NULL DEFAULT '' | Free-text remarks. |
| `created_at` | TEXT NOT NULL | UTC ISO-8601 timestamp at creation. |
| `updated_at` | TEXT NOT NULL | UTC ISO-8601 timestamp, refreshed on update. |

### Constraints & indexes

- `UNIQUE(sample_display_code)` — table-level constraint.
- `idx_samples_display_code_unique` on `(sample_display_code)`.
- `idx_samples_identity_unique` on `(sample_code, name, category, batch)` —
  enforces that the four identity components are unique together; replaces the
  legacy single-column `UNIQUE(sample_code)` (migrated by
  `ensure_samples_composite_unique`).

### Identity rules (enforced in the feature module, not the schema)

- **UID:** `generate_sample_uid()` → `SMP-{year}-{seq:06d}`, where `seq` is
  `max(existing year suffix) + 1` (gap-tolerant).
- **Display code:** `build_sample_display_code()` joins normalized
  `sample_code`, `name`, `category`, `batch` with `-` (empty → `-`).
- **Name consistency:** all rows sharing `sample_code` must share `name`; all
  rows sharing `sample_code` + `category` must share `name`
  (`validate_sample_hierarchy`).

## Read enrichment (not stored)

`get_samples()` returns each sample augmented with computed fields via a LEFT
JOIN on `test_data`:

| Field | Source | Meaning |
|-------|--------|---------|
| `data_count` | `COUNT(td.id)` | Number of test-data rows for the sample. |
| `last_measured_at` | `MAX(td.measured_at)` | Most recent measurement time (or null). |

## Relationships (child entities)

Every relationship below is keyed by `child.sample_id → samples.id`. `ON DELETE`
behavior is what makes the Strong-tier cascade delete work (Article IV).

| Child table | FK on delete | Cascade-removed by sample delete? |
|-------------|--------------|-----------------------------------|
| `test_data` | CASCADE | Yes (DB). |
| `process_records` | CASCADE | Yes (DB). |
| `raw_data` | CASCADE | Yes (DB); `raw_data_files` cascade off `raw_data`. |
| `parsed_data` | CASCADE | Yes (DB). |
| `parsed_records` | (via `sample_id`, nullable) | Counted in preview; removed with the cascade. |
| `characterization_collections` | CASCADE | Yes (DB); `characterization_files` cascade off the collection. |
| `characterization_files` | CASCADE | Yes (DB). |
| `performance_datasets` | CASCADE | Yes (DB); `performance_dataset_files` cascade off the dataset. |
| `mes_sample_routes` | CASCADE | Yes (DB). |
| `processing_results` | **SET NULL** | Row kept, `sample_id` nulled. |
| `processing_jobs` | **SET NULL** | Deleted **explicitly** by `delete_sample()` so its output files/rows don't orphan. |

> The two `SET NULL` exceptions are why `delete_sample()` exists as more than a
> single `DELETE`: it collects the files those rows reference *before* deleting,
> explicitly deletes `processing_jobs`, and removes the live files after commit.

## Deletion data-safety model (Article IV)

1. **Backup precedes destruction** — `backup_database()` snapshots the DB before
   the delete transaction; uploaded files already have immutable archive copies.
2. **Audit snapshot** — `record_deletion(conn, "samples", row)` writes the full
   deleted sample row (JSON) into `deletion_audit` with `deleted_at`.
3. **DB cascade** — child rows removed by FK `ON DELETE CASCADE`.
4. **Centralized file cleanup** — `app/deletion.py` collects descendant file
   paths (raw-data files, characterization files, performance files, parsed
   outputs) + job outputs, and `remove_files()` unlinks only paths confined to
   the live store, after the row delete commits.

## `deletion_audit` (recovery target)

Written by `record_deletion`; not specific to samples but the recovery record for
a sample delete:

| Column | Meaning |
|--------|---------|
| `table_name` | `"samples"` for a sample delete. |
| `row_pk` | The deleted sample's `id` (as text). |
| `snapshot_json` | Full JSON snapshot of the deleted row. |
| `deleted_at` | UTC ISO-8601 timestamp of the delete. |
