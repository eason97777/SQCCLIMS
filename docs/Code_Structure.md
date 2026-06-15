# Code Structure

This document explains the main directories and source files in SQCCLIMS.

> For the layered backend design and request lifecycle, see
> [`docs/ARCHITECTURE.md`](ARCHITECTURE.md). For a per-module backend reference
> (responsibility, key functions, endpoints), see
> [`docs/BACKEND_MODULES.md`](BACKEND_MODULES.md). Environment variables are
> documented in the repository [`README.md`](../README.md) (there is no
> `.env.example`).

## Top-Level Layout

The application lives directly at the repo root (`SQCCLIMS/`).

- `README.md` — project overview, startup, configuration (env vars).
- `CONTRIBUTING.md` — dev workflow, how to add an endpoint / migration.
- `docs/` — `ARCHITECTURE.md`, `BACKEND_MODULES.md`, `Data_Flow.md`,
  `CODE_PRINCIPLES.md`, `GLOSSARY.md` (+ these legacy notes).
- `.gitignore` — excludes secrets, dependency folders, runtime data, generated
  files, packaging output, and caches.
- `server.py`, `app/`, `parsers/`, `migrations/`, `frontend/`, `templates/`,
  `tests/` — the active application (see below).
- `history/` — legacy snapshots; gitignored, never committed.

## Backend

The backend is a layered Python package (standard library only). Dependency
direction is low-level ← features ← http.

- `server.py` — thin entrypoint (~60 lines). Parses args/env, configures paths,
  prepares directories, sets up logging, initializes the SQLite schema, runs
  migrations, takes a startup backup, writes a `server.pid` file, and serves.
- `app/` — the backend package:
  - **Low-level / data:** `config.py` (runtime paths + constants),
    `db.py` (`connect_db`, `record_deletion`, schema helpers),
    `validation.py` (input coercion, safe-path helpers, `now_iso`),
    `errors.py` (domain exceptions + exception→HTTP status map),
    `storage.py` (filesystem path resolution + uploaded/generated file storage).
  - **Infra:** `migrations.py` (`init_db` + forward-only `run_migrations`),
    `logging_setup.py` (rotating file + stderr logging),
    `backup.py` (startup SQLite snapshots with retention),
    `archive.py` (append-only content-addressed upload archive),
    `auth.py` (optional token auth + RBAC, off by default),
    `deletion.py` (centralized file cleanup + cascade-preview helpers).
  - **HTTP:** `http/handler.py` — `AppHandler`: parse, authorize, route
    `/api/` to feature handlers (else serve the SPA), serialize JSON / stream
    downloads, access logging. No business logic.
  - **Features:** `features/*.py` — one module per domain area (samples,
    test_data, process_records, mes, raw_data, parsing, visualization,
    characterization, performance, processing, summary). Each owns its
    HTTP-facing handlers and the SQL behind them.
- `requirements.txt` — the one optional dependency (XLSX support).
- `scripts/` — maintenance tools: `restore_db.py` (DB snapshot restore),
  `restore_file.py` (archive file recovery), `cleanup_dev_orphans.py`.
- `tests/smoke_test.py` — regression smoke test.

Runtime database files are not source code and must not be committed.

## Frontend

The active frontend is `frontend/` (React + TypeScript +
Vite). Important files:

- `package.json` / `package-lock.json` — dependency graph.
- `vite.config.ts` — Vite config; `tsconfig*.json` — TypeScript; `eslint.config.js` — linting.
- `index.html` — Vite HTML entry; `public/` — static assets.
- `src/main.tsx` — mounts React; `src/App.tsx` — app shell; `src/router/` — routing.
- `src/pages/` — page views; `src/components/` — reusable UI by feature area.
- `src/api/` — API client wrappers; `src/stores/` — state; `src/types/` — TS models; `src/utils/` — utilities.

Generated build output in `frontend/dist` must not be committed.

## Parsers And Data Processing

`parsers/` contains backend-side parser and visualizer
modules, invoked by the `parsing` / `visualization` features:

- `resistance_csv_parser.py` — parse resistance CSV/XLSX into die/area records.
- `resistance_heatmap_visualizer.py` — generate resistance wafer heatmaps.
- `cd_template_parser.py` — parse CD/SEM template CSV files.
- `cd_violin_visualizer.py` — generate CD/SEM violin plots.
- `__init__.py` — marks the parser package.

## Migrations

`migrations/` contains forward-only, checksum-guarded
SQLite migration files (`NNN_description.sql`) and a `README.md` with the rules.
Migration files are source-controlled; runtime database files are not. See
[`docs/ARCHITECTURE.md`](ARCHITECTURE.md) and `migrations/README.md`.

## Templates

`templates/` holds downloadable import templates shipped
with the app (e.g. `cd_sem_template.csv`). These are source templates, not
runtime uploads.

## Tools And Packaging

- `tools/` — utility scripts (e.g. local-open helpers).
- `packaging/` — build/install scripts, service config,
  installer scripts, packaging docs. Generated package output
  (`packaging/output/`, `packaging/staging/`, installer binaries) is not source.

## Runtime-Only Directories

These are runtime-only and must not be committed (only `.gitkeep` placeholders):

- `data/` — `sample_testing.db`, `uploads/`, `outputs/`,
  `logs/`, `backups/`, `archive/`.
- frontend build output, dependency folders, Python cache folders, and any real
  experimental or business data.
