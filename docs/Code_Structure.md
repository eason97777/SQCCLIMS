# Code Structure

This document explains the main directories and source files in JIQT_2.

## Top-Level Layout

- `.gitignore` defines source-control exclusions for secrets, dependency folders, runtime data, generated files, packaging outputs, and caches.
- `.env.example` documents safe placeholder environment variables.
- `README.md` gives the project overview and startup guidance.
- `docs/` contains project-level explanation documents.
- `SCRmonitor/` contains the active backend, frontend, parser, migration, template, tool, and packaging source.

The top-level `frontend/` directory is not part of the active application unless manually confirmed. It appears to be an old or empty scaffold.

## Backend

- `SCRmonitor/server.py` is the main backend entry point. It creates the HTTP server, defines API routing, manages SQLite connections, runs migrations, handles uploads, serves generated outputs, and serves frontend static files.
- `SCRmonitor/requirements.txt` lists Python dependencies used for packaging and spreadsheet support.
- `SCRmonitor/scripts/cleanup_dev_orphans.py` is a maintenance utility for cleaning orphaned development upload folders.

Runtime database files are not source code and must not be committed.

## Frontend

The active frontend is `SCRmonitor/frontend`.

Important files:

- `package.json` and `package-lock.json` define the frontend dependency graph.
- `vite.config.ts` configures Vite.
- `tsconfig.json`, `tsconfig.app.json`, and `tsconfig.node.json` configure TypeScript.
- `eslint.config.js` configures linting.
- `index.html` is the Vite HTML entry.
- `public/` contains static assets copied by Vite.
- `src/main.tsx` mounts the React application.
- `src/App.tsx` defines the application shell.
- `src/router/` defines frontend routing.
- `src/pages/` contains page-level views.
- `src/components/` contains reusable UI components grouped by feature area.
- `src/api/` contains API client wrappers for backend endpoints.
- `src/stores/` contains frontend state management modules.
- `src/types/` contains TypeScript data model definitions.
- `src/utils/` contains shared frontend utilities.
- `src/assets/` contains source assets used by the frontend.

Generated frontend output in `SCRmonitor/frontend/dist` must not be committed.

## Parsers And Data Processing

`SCRmonitor/parsers/` contains backend-side parser and visualization modules:

- `cd_template_parser.py` parses CD SEM template CSV files.
- `resistance_csv_parser.py` parses resistance CSV files.
- `cd_violin_visualizer.py` generates CD violin visualization outputs.
- `resistance_heatmap_visualizer.py` generates resistance heatmap visualization outputs.
- `__init__.py` marks the parser package.

Python cache files under `__pycache__/` are generated and must not be committed.

## Migrations

`SCRmonitor/migrations/` contains SQLite migration files and rules:

- `001_baseline_marker.sql`
- `002_add_mes_flow_tables.sql`
- `003_seed_jjtest_mes_route.sql`
- `README.md`

Migration files are source-controlled because they define reproducible database structure and seed behavior. Runtime database files are not source-controlled.

## Templates

`SCRmonitor/templates/` contains source templates shipped with the application. These are not runtime uploads. Current template files should be committed when they are required for the app to work or for users to reproduce supported import formats.

## Tools

`SCRmonitor/tools/` contains utility scripts, such as local-open helpers, that support project operation.

## Packaging

`SCRmonitor/packaging/` contains source scripts and installer configuration:

- build scripts
- install/uninstall scripts
- service configuration
- installer scripts
- packaging documentation

Generated package folders and binaries are not source:

- `SCRmonitor/packaging/output/`
- `SCRmonitor/packaging/staging/`
- generated `.exe` or installer artifacts

## Runtime-Only Directories

These directories are runtime-only and should not be uploaded to Git:

- `.local_run_data/`
- `SCRmonitor/.local-data/`
- `SCRmonitor/data/` contents except `.gitkeep`
- upload folders
- output folders
- export/report/artifact folders
- log folders
- backup folders
- frontend build output
- dependency folders
- Python cache folders

