# Data Model: Raw Data Upload, Parsing & Visualization

> As-built. These tables are part of the historical baseline in
> [`app/migrations.py`](../../app/migrations.py) `init_db()` (not a new
> `migrations/NNN` file — see [plan.md](./plan.md) Constitution Check, Article
> V). Cross-references: [`docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md)
> (data model), [`docs/Data_Flow.md`](../../docs/Data_Flow.md) (flow + deletion
> policy).

## Conceptual relationships

```
samples (1) ──< raw_data (1) ──< raw_data_files          [uploaded source files]
                       │
                       ├──< parsed_data (1) ──< parsed_records   [normalized points]
                       │
                       └──< processing_jobs                       [parse + viz audit]
```

- A **sample** owns many **raw_data** records.
- A **raw_data** record owns many **raw_data_files** (the uploaded originals) and
  many **parsed_data** datasets (one per parse run).
- A **parsed_data** dataset owns many **parsed_records** (one normalized
  measurement point each).
- **processing_jobs** records each parse and each visualization run; it
  references raw_data / parsed_data / sample with `ON DELETE SET NULL` and is
  cleaned up explicitly by the owning delete paths (it is not part of this
  feature's editable surface — surfaced read-only via `GET /api/processing-jobs`
  and the chart-download route).

### Cascade & data-safety summary (Article IV)

| Parent | Children removed | Files removed | Recovery |
|--------|------------------|---------------|----------|
| `raw_data` (Strong) | `raw_data_files`, `parsed_data`, `parsed_records`; `processing_jobs` rows deleted explicitly | uploaded files **and** visualization outputs | append-only archive + DB backup + `deletion_audit` snapshot |
| `raw_data_files` — one file (Strong) | parent's `parsed_data`, `parsed_records`, `processing_jobs` | the file **and** the parent's visualization outputs; per-delete DB backup | archive + DB backup + `deletion_audit` |
| `parsed_data` (Strong) | `parsed_records` | generated outputs | DB backup |

`FOREIGN KEY ... ON DELETE CASCADE` is declared on the child tables and enforced
with `PRAGMA foreign_keys = ON`; `processing_jobs` uses `ON DELETE SET NULL` and
is therefore deleted explicitly in the owning delete path so nothing is orphaned.
See [`docs/Data_Flow.md`](../../docs/Data_Flow.md) "Deletion & Data-Safety
Policy".

---

## Table: `raw_data`

A tracked unit of instrument output attached to one sample.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | autoincrement |
| `sample_id` | INTEGER NOT NULL | FK → `samples(id)` ON DELETE CASCADE |
| `sample_uid` | TEXT | denormalized sample UID |
| `sample_display_code` | TEXT | denormalized sample display code |
| `raw_data_code` | TEXT NOT NULL **UNIQUE** | `RD-<sample_uid>-<TYPE_TOKEN>-<YYYYMMDD>-<NNN>` |
| `raw_data_name` | TEXT NOT NULL | required, user-supplied |
| `data_type` | TEXT NOT NULL | one of `config.RAW_DATA_TYPES` (resistance, cd_sem, sem_image, xps, xrd, afm, report, instrument_folder, generic_file) |
| `data_category` | TEXT | derived from data type (e.g. resistance → `electrical`, cd_sem → `metrology`) |
| `source_type` | TEXT | optional |
| `instrument` | TEXT | optional |
| `operator` | TEXT | optional |
| `measured_at` | TEXT | optional; feeds the code's date token |
| `parser_status` | TEXT | `not_parsed` → `parsing` → `parsed` / `parse_failed` |
| `status` | TEXT | `imported` on create |
| `file_count` | INTEGER | maintained on upload / file delete |
| `total_size` | INTEGER | sum of file sizes, maintained on upload |
| `storage_path` | TEXT | record's upload directory, data-dir-relative |
| `metadata_json` | TEXT | validated JSON string (or `''`) |
| `notes` | TEXT | optional |
| `created_at` / `updated_at` | TEXT | ISO timestamps |

Indexes: `idx_raw_data_sample(sample_id)`, `idx_raw_data_type(data_type)`,
`idx_raw_data_code(raw_data_code)`.

---

## Table: `raw_data_files`

One uploaded file belonging to a `raw_data` record.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | autoincrement |
| `raw_data_id` | INTEGER NOT NULL | FK → `raw_data(id)` ON DELETE CASCADE |
| `original_filename` | TEXT NOT NULL | as uploaded |
| `stored_filename` | TEXT NOT NULL | `<uuid4hex>-<safe-name>` on disk |
| `relative_path` | TEXT | `<raw_data_code>/<stored_filename>` |
| `file_path` | TEXT NOT NULL | data-dir-relative storage path |
| `file_ext` | TEXT | lowercased extension |
| `mime_type` | TEXT | guessed/declared |
| `file_size` | INTEGER | bytes on disk |
| `sha256` | TEXT | content checksum (also the archive key) |
| `file_role` | TEXT | default `raw` |
| `preview_supported` | INTEGER | `1` if previewable, else `0` |
| `created_at` | TEXT | ISO timestamp |

Index: `idx_raw_data_file_parent(raw_data_id)`.

---

## Table: `parsed_data`

The structured result of one parse run over a `raw_data` record.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | autoincrement |
| `raw_data_id` | INTEGER NOT NULL | FK → `raw_data(id)` ON DELETE CASCADE |
| `sample_id` | INTEGER NOT NULL | FK → `samples(id)` ON DELETE CASCADE |
| `sample_uid` / `sample_display_code` / `raw_data_code` | TEXT | denormalized identity |
| `data_type` | TEXT NOT NULL | mirrors raw_data |
| `parser_name` | TEXT | e.g. `resistance_csv_parser`, `cd_template_parser` |
| `parser_version` | TEXT | parser version string |
| `parsed_status` | TEXT | `success` (or `failed` if errors present) |
| `schema_version` | TEXT | normalized-record schema version (default `1.0`) |
| `records_json` | TEXT | retained `'[]'` — points live in `parsed_records`, not inline |
| `summary_json` | TEXT | parser summary object |
| `record_count` | INTEGER | number of normalized records |
| `plots_json` | TEXT | parser-declared plots (currently `[]`) |
| `warnings_json` | TEXT | parser warnings |
| `errors_json` | TEXT | parser errors |
| `output_file_path` | TEXT | optional generated-output path |
| `created_at` / `updated_at` | TEXT | ISO timestamps |

Indexes: `idx_parsed_data_raw(raw_data_id)`, `idx_parsed_data_sample(sample_id)`,
`idx_parsed_data_type(data_type)`.

> Note: bulk point data is **not** stored in `records_json`; it is exploded into
> `parsed_records` rows so it can be filtered, paged, and indexed in SQL.

---

## Table: `parsed_records`

One normalized measurement point within a `parsed_data` dataset. The schema is a
**union** that serves both resistance (matrix) and CD/SEM (template) families;
each parser populates the subset relevant to it. Parser-specific keys not mapped
to a column are preserved in `extra_json`.

| Column | Type | Used by | Notes |
|--------|------|---------|-------|
| `id` | INTEGER PK | both | |
| `parsed_data_id` | INTEGER NOT NULL | both | FK → `parsed_data(id)` ON DELETE CASCADE |
| `raw_data_id` | INTEGER | both | denormalized |
| `sample_id` | INTEGER | both | denormalized |
| `sample_uid` | TEXT | both | denormalized |
| `raw_data_code` | TEXT | both | denormalized |
| `data_type` | TEXT NOT NULL | both | `resistance` or `cd_sem` |
| `record_index` | INTEGER | both | 1-based ordering within the dataset |
| `primary_key` | TEXT | resistance | e.g. `A1:R01:C01` (die:row:col) |
| `group_key` | TEXT | both | optional grouping key |
| `x_value` / `y_value` | REAL | both | optional plot coordinates |
| `numeric_value` | REAL | both | the analyzable number (resistance value / CD value) |
| `raw_value` | TEXT | both | original cell/field text |
| `cleaned_value` | TEXT | both | post-cleaning text value |
| `is_outlier` | INTEGER | both | 0/1; resistance outliers set at summary time |
| `outlier_reason` | TEXT | both | e.g. `below_lower_limit` / `above_upper_limit` |
| `die_id` | TEXT | both | wafer die label (resistance `A1`…`M5`; CD/SEM die_no maps here) |
| `area` | TEXT | resistance | quadrant `A`/`B`/`C`/`D` within a die |
| `row_index` / `col_index` | INTEGER | resistance | 1-based matrix position |
| `row_header` / `col_header` | TEXT | resistance | matrix axis headers |
| `row_group` | TEXT | cd_sem | `row_1` / `row_2` |
| `side` | TEXT | cd_sem | `Left` / `Right` |
| `direction` | TEXT | cd_sem | `Horizontal` / `Vertical` |
| `dose` | TEXT | cd_sem | exposure dose label |
| `location` | TEXT | cd_sem | measurement location |
| `extra_json` | TEXT | both | unmapped parser fields (e.g. `unit`, `source_file`) |
| `created_at` | TEXT | both | defaults to CURRENT_TIMESTAMP |

Indexes: `idx_parsed_records_parsed_data_id`, `idx_parsed_records_raw_data_id`,
`idx_parsed_records_data_type`,
`idx_parsed_records_die_area(parsed_data_id, die_id, area)`,
`idx_parsed_records_cd_sem_filters(parsed_data_id, row_group, side, direction,
dose, location)`, `idx_parsed_records_outlier(parsed_data_id, is_outlier)`.

The column set and the mapping of inbound parser keys are centralized in
`config.PARSED_RECORD_INSERT_COLUMNS` and `config.PARSED_RECORD_MAPPED_KEYS`
([`app/config.py`](../../app/config.py)).

---

## Supporting table (read-only here): `processing_jobs`

Audit of parse and visualization runs. Key columns: `job_type`
(`parse` / `visualization`), `job_name`, `raw_data_id`, `parsed_data_id`,
`sample_id`, `script_name`, `script_version`, `input_json`, `output_json`,
`status` (`running` / `success` / `failed`), `error_message`, `started_at`,
`finished_at`. FKs to `raw_data` / `parsed_data` / `samples` are `ON DELETE SET
NULL`; the owning delete paths remove these rows explicitly and clean up their
output files (Article IV).
