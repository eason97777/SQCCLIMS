# Data Flow

This document summarizes how data moves through JIQT_2.

## Sample Creation

Users create and maintain samples through frontend sample pages. The frontend calls backend API endpoints from modules in `SCRmonitor/frontend/src/api/`. The backend validates request data, writes records to SQLite, and returns normalized JSON responses to the frontend.

Sample records are stored in the SQLite database located under the configured runtime data directory.

## Raw Data Upload

Raw Data workflows begin in the frontend Raw Data page. Users create Raw Data records and upload files associated with those records. Uploaded files are written under the runtime upload directory, usually beneath:

```text
SCRmonitor/data/uploads/
```

or the directory configured by `JIQT_DATA_DIR`.

Uploaded files are runtime/business data and must not be committed.

## Parser Processing

Parser modules in `SCRmonitor/parsers/` process supported measurement file formats. The backend calls these modules after upload or when a parse/visualization endpoint is requested.

Current parser responsibilities include:

- reading CD SEM template CSV data
- reading resistance CSV data
- producing normalized parsed records
- generating visualization artifacts such as charts or reports

Generated parser outputs are stored in the runtime output directory. They are reproducible artifacts or local analysis results and must not be committed.

## Normalized Records

After parsing, the backend stores normalized metadata and record summaries in SQLite. This lets frontend pages display parsed data, detail panels, summaries, record tables, and processing status without reading raw uploaded files directly from the browser.

The database is runtime state and must not be uploaded.

## Frontend API Consumption

Frontend API wrappers live in `SCRmonitor/frontend/src/api/`. Page and component code calls these wrappers to load and update:

- samples
- test data
- process records
- raw data
- parsed data
- processing jobs
- characterization collections/files
- performance datasets
- dashboard summaries
- MES route templates and flow records

The frontend consumes JSON from the backend and renders feature-specific pages under `SCRmonitor/frontend/src/pages/`.

## Runtime File Storage

The backend runtime directory is controlled by `JIQT_DATA_DIR` or defaults to `SCRmonitor/data`.

Expected runtime subdirectories include:

- `uploads/` for uploaded user files
- `outputs/` for generated charts, visualizations, reports, and downloads
- `logs/` for runtime logs
- `backups/` for local backups when created

Only placeholder `.gitkeep` files should be committed under `SCRmonitor/data`.

## Generated Files That Must Not Be Committed

Do not commit:

- SQLite databases
- uploaded Raw Data files
- characterization uploads
- generated charts
- generated reports
- generated exports
- generated downloads
- logs
- backups
- packaging output
- frontend build output
- dependency folders
- Python bytecode/cache files
- real experimental or business data

