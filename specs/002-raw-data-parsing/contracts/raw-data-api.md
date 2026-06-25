# API Contracts: Raw Data Upload, Parsing & Visualization

> As-built. Routes are dispatched in
> [`app/http/handler.py`](../../../app/http/handler.py); field shapes come from
> [`app/features/raw_data.py`](../../../app/features/raw_data.py),
> [`app/features/parsing.py`](../../../app/features/parsing.py), and
> [`app/features/visualization.py`](../../../app/features/visualization.py).
> Error status codes follow the exception convention (constitution Article VI):
> `ValueError`→400, `AuthenticationError`→401, `AuthorizationError`→403,
> `LookupError`→404, `ConflictError`→409, anything else→500. Auth (when enabled)
> gates per Article XI: GET ≤ operator-write ≤ admin-delete. All bodies are JSON
> unless noted as multipart.

---

## Raw data records

### GET /api/raw-data

List raw data records (cap 500, newest first).

- **Query:** `sample_id`, `data_type`, `parser_status`, `status`, `query` (all
  optional). `query` matches code, name, sample identifiers, instrument,
  operator, notes.
- **200** → `RawDataRecord[]` (without nested `files`; includes the record's own
  columns).

### POST /api/raw-data

Create a raw data record.

- **Request (JSON):**
  ```json
  {
    "sample_id": 12,
    "raw_data_name": "Wafer 7 resistance map",
    "data_type": "resistance",
    "source_type": "instrument",
    "instrument": "4-point probe",
    "operator": "alice",
    "measured_at": "2026-06-16",
    "metadata_json": "{}",
    "notes": ""
  }
  ```
  Required: `sample_id` (numeric), `raw_data_name`, `data_type` (must be a known
  type). `metadata_json` may be a JSON string or object; invalid JSON → 400.
- **201** → `RawDataRecord` with `files: []`, `parsed_data_count`,
  `processing_job_count`, generated `raw_data_code`, derived `data_category`,
  `parser_status: "not_parsed"`, `status: "imported"`.
- **400** sample_id not numeric / name missing / unsupported data_type / invalid
  metadata JSON. **404** sample not found.

### GET /api/raw-data/{id}

Retrieve one record with its files.

- **200** → `RawDataRecord` including `files: RawDataFile[]` (newest first),
  `parsed_data_count`, `processing_job_count`.
- **404** not found. **400** non-numeric id.

### DELETE /api/raw-data/{id}

Strong-tier cascade delete. Takes a DB backup, snapshots the row into
`deletion_audit`, deletes `processing_jobs` / `parsed_records` / `parsed_data` /
the record, then removes the on-disk files, the storage directory, and
visualization outputs.

- **200** → `{ "deleted": <id> }`.
- **404** not found.

### GET /api/raw-data/{id}/delete-preview

Read-only cascade preview (deletes nothing).

- **200** →
  ```json
  {
    "raw_data_code": "RD-...",
    "raw_data_files": 1,
    "parsed_data": 1,
    "parsed_records": 1872,
    "files_total": 1
  }
  ```
- **404** not found.

### POST /api/raw-data/{id}/files

Upload one or more files (**multipart/form-data**).

- **Request:** `multipart/form-data` with one or more file parts (the frontend
  sends them under field name `files`). At least one file is required.
- Each accepted file is saved under the record's directory with a checksum and
  archived (append-only, content-addressed); the record's `file_count` /
  `total_size` are updated.
- **201** → `RawDataRecord` (refreshed, with `files`).
- **400** no files provided / invalid storage path. **404** record not found.
- **Note:** non-multipart body → 400 (`request body must be multipart/form-data`).

---

## Raw data files

### GET /api/raw-data-files/{id}/download

Stream the original uploaded file as an attachment (`Content-Disposition:
attachment`, original filename, RFC 5987 `filename*`).

- **200** → file bytes (streamed). **404** file row or on-disk file missing.

### DELETE /api/raw-data-files/{id}

Delete a single file — **only when it is the record's sole file**. Strong-tier:
per-delete DB backup, cascades the parent record's `parsed_data` /
`parsed_records` / `processing_jobs`, removes the file and the parent's
visualization outputs, and resets the parent's `file_count`/`total_size` to 0 and
`parser_status` to `not_parsed`.

- **200** →
  ```json
  {
    "deleted_file_id": 5,
    "raw_data_id": 3,
    "deleted_parsed_data_ids": [9],
    "deleted_processing_job_ids": [14, 15],
    "deleted_output_paths": ["outputs/visualizations/..."],
    "strategy": "single_file_raw_data_cascade",
    "raw_data": { ...refreshed RawDataRecord... }
  }
  ```
- **409** the parent raw_data has more than one file (precise single-file delete
  is intentionally blocked — delete the whole raw_data instead). **404** not
  found.

### GET /api/raw-data-files/{id}/delete-preview

Read-only preview for a single-file delete.

- **200** → `{ "original_filename", "parsed_data", "parsed_records",
  "files_total" }`. **404** not found.

---

## Parsing

### POST /api/raw-data/{id}/parse

Parse the record's parseable file synchronously. Resistance records use
`resistance_csv_parser` (CSV/XLSX); CD/SEM records use `cd_template_parser`
(CSV). Sets `parser_status` to `parsing`, then `parsed` or `parse_failed`;
creates a `processing_jobs` row and, on success, a `parsed_data` dataset with
`parsed_records`.

- **Request (JSON, optional):** `{ "parser_name": "resistance_csv_parser" }` —
  if supplied it must match the record's data type's parser.
- **200** → refreshed `RawDataRecord` (now `parser_status: "parsed"`).
- **400** unsupported data type / wrong parser name / no parseable file found /
  parser validation error (record marked `parse_failed`). **404** record not
  found.

> A test-only fixture endpoint `POST /api/parsed-data/mock` exists for seeding
> parsed data from arbitrary JSON; it is **disabled** unless `LIMS_ENABLE_MOCK`
> is truthy and returns 404 otherwise. Not part of the production contract.

---

## Parsed data & normalized records

### GET /api/parsed-data

List parsed datasets (cap 500, newest first).

- **Query:** `raw_data_id`, `sample_id`, `data_type` (all optional).
- **200** → `ParsedDataRecord[]`.

### GET /api/parsed-data/{id}

- **200** → `ParsedDataRecord` (`summary_json`, `record_count`, `plots_json`,
  `warnings_json`, `errors_json`, parser metadata, etc.). **404** not found.

### GET /api/parsed-data/{id}/records

Page and filter the normalized records.

- **Query:** `page` (default 1), `page_size` (default 100, max 500),
  `data_type`, `die_id`, `area`, `is_outlier`, `is_na`, `row_group`, `side`,
  `direction`, `dose`, `location`, `q` (free-text). `side`/`direction` accept
  aliases (`l/r`, `h/v`).
- **200** →
  ```json
  {
    "items": [ /* ParsedRecordItem[] */ ],
    "total": 1872,
    "page": 1,
    "page_size": 100,
    "total_pages": 19,
    "filters": { "parsed_data_id": 9, "die_id": null, "area": null, "...": null }
  }
  ```
- **404** parsed data not found.

### GET /api/parsed-data/{id}/record-options

Distinct filterable values for building valid filters.

- **200** →
  ```json
  {
    "parsed_data_id": 9,
    "data_type": "resistance",
    "options": {
      "die_id": ["A1","A2","..."],
      "area": ["A","B","C","D"],
      "row_group": [], "side": [], "direction": [], "dose": [], "location": [],
      "is_outlier": [0],
      "is_na": [0, 1]
    },
    "counts": { "total": 1872 }
  }
  ```
- **404** not found.

---

## Resistance summary & visualization

### POST /api/parsed-data/{id}/resistance-summary

Compute per-die / per-area / overall resistance statistics with user cleaning
limits. Read-only (no job created).

- **Request (JSON, optional):**
  ```json
  {
    "cleaning_config": { "lower": 10.0, "upper": 500.0 },
    "metric": "cleaned_value",
    "area": "A",
    "die_id": "E7"
  }
  ```
  `metric` ∈ {`numeric_value`,`cleaned_value`,`raw_value`} (default
  `cleaned_value`); `area` ∈ {A,B,C,D}; `lower` must not exceed `upper`.
- **200** → `ResistanceSummaryResponse`: `{ parsed_data_id, cleaning_config,
  metric, filters, overall_summary, die_summary[], area_summary[],
  layout_values[] }`. Each summary carries `count_total/valid/na/normal/outlier`,
  `yield_rate`, `max`, `min`, `range`, `average`, `std`, `three_sigma`,
  `uniformity`.
- **400** parsed data is not resistance / invalid metric / area / lower>upper.
  **404** parsed data not found.

### POST /api/parsed-data/{id}/visualize

Render a chart. Dispatches by the dataset's data type. Creates a
`processing_jobs` row and returns it.

- **Resistance** request requires `chart_type: "resistance_wafer_heatmap"`, plus
  `summary` (with `overall_summary` + `die_summary[]` + `area_summary[]`) and
  `layout_values[]`; optional `metric`, `area`, `cleaning_config`, `display`.
- **CD/SEM** request: `chart_type: "violin"` (only violin supported) with
  optional `x_field`/`y_field`/`hue_field`/`facet_field`/`filters`/`split_field`/
  `series_field`/`merge_field`/`merge_rule`/`output_mode`/`title`/`unit`/etc.
- **201** → `ProcessingJobRecord` (status `success` with `output_json` holding
  chart/report URLs and paths, or status `failed` with `error_message`).
- **400** unsupported chart type / missing required summary or layout_values /
  data type has no visualization support / no CD records found. **404** parsed
  data not found.

### GET /api/processing-jobs/{id}/charts/download

Download selected charts from a successful visualization job as a single ZIP.

- **Query:** `chart_key` (repeatable) — the chart keys to include.
- **200** → `application/zip` attachment (`CD_Violin_Selected_<job>_<ts>.zip`).
- **400** no keys selected / job not a successful visualization / output has no
  multi-chart result / a selected key is missing. **404** job not found / a
  selected chart's file missing on disk.

### GET /api/processing-jobs

List processing jobs (parse + visualization), cap 500, newest first.

- **Query:** `raw_data_id`, `sample_id`, `job_type`, `status` (optional).
- **200** → `ProcessingJobRecord[]`.

---

## Generated output files

### GET /api/outputs/{path}

Stream a generated chart/report artifact (referenced by `chart_url` etc. in a
job's `output_json`). Path-confined to the output directory.

- **200** → file bytes. **404** outside the output root or missing.
