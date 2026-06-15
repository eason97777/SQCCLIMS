# SQCCLIMS

SQCCLIMS is a locally-run **LIMS/MES** for a semiconductor / materials sample-testing lab. It runs as a single desktop-grade web application that keeps sample tracking, process records, MES process routes, raw measurement data, parsing, and visualization together in one local SQLite store — no cloud, no external services.

## What it does

- **Sample tracking (LIMS)** — register samples, test data, characterization files, and performance datasets.
- **Process records** — capture per-sample, per-layer process records (substrate, resistance type, wafer thickness, free-form details).
- **MES process routes** — define route templates (project → layers → steps) and instantiate them per sample, advancing samples step by step with an event history.
- **Raw-data ingestion** — upload resistance and CD/SEM measurement files (CSV/XLSX) against raw-data records.
- **Parsing** — turn raw files into normalized, queryable parsed records (resistance maps, CD/SEM measurements).
- **Visualization** — generate **heatmaps** (resistance) and **violin plots** (CD/SEM) as downloadable chart artifacts.

## Tech stack

| Layer | Technology |
|-------|-----------|
| Backend | Python **standard library only** (`http.server` + `sqlite3`) — no third-party web framework |
| Database | SQLite (WAL mode), file-based, lives under the data directory |
| Frontend | **React 19 + TypeScript + Vite** single-page app |
| Parsers/visualizers | `parsers/` package (resistance + CD/SEM), invoked from the backend |

The backend is intentionally dependency-free so it can be packaged and run on a lab workstation with just a Python install. Spreadsheet support (XLSX) is the one optional dependency declared in `SQCCLIMS/requirements.txt`.

## Repository layout

```
SCRmonitor/               # repo root (folder rename to SQCCLIMS pending reorganize)
├── README.md               # this file
├── CONTRIBUTING.md         # dev workflow, adding endpoints / migrations
├── docs/                   # ARCHITECTURE, CODE_PRINCIPLES, GLOSSARY (+ legacy notes)
├── frontend/               # (legacy/empty scaffold — active SPA is below)
├── history/                # legacy snapshots, gitignored
└── SQCCLIMS/             # the application
    ├── server.py           # thin entrypoint
    ├── app/                # backend package (config, db, http, features, …)
    ├── parsers/            # resistance + CD/SEM parsers and visualizers
    ├── migrations/         # forward-only SQL migrations
    ├── frontend/           # React + TS + Vite SPA (active)
    ├── templates/          # downloadable import templates
    └── tests/smoke_test.py # regression smoke test
```

## Quickstart

### Backend

From `SCRmonitor/SQCCLIMS/`:

```bash
python3 server.py --host 127.0.0.1 --port 8000
# optional explicit data directory:
python3 server.py --host 127.0.0.1 --port 8000 --data-dir ./data
```

On startup the server configures paths, ensures data directories, initializes the SQLite schema, runs pending migrations, and takes a startup backup before serving. It then serves the API under `/api/` and the built SPA for all other routes.

Install the optional spreadsheet dependency if you need XLSX ingestion:

```bash
pip install -r requirements.txt
```

### Frontend

From `SCRmonitor/SQCCLIMS/frontend/`:

```bash
npm install
npm run build      # outputs to frontend/dist, which the backend serves
# or, for live development:
npm run dev        # Vite dev server on :5173
```

The backend serves the production build from `frontend/dist`. For a fully working app, build the frontend before (or alongside) running the backend.

### Where data lives

All runtime state lives under the **data directory**:

- default: `SCRmonitor/SQCCLIMS/data/`
- override with `--data-dir DIR` or the `LIMS_DATA_DIR` environment variable.

Subdirectories: `sample_testing.db` (the SQLite database), `uploads/`, `outputs/`, `logs/`, `backups/`. None of this is committed to git — only `.gitkeep` placeholders are.

### Smoke test

```bash
python3 tests/smoke_test.py        # from SCRmonitor/SQCCLIMS/
```

Boots the server against a throwaway temp data directory, exercises the key read endpoints plus one create round-trip, and exits non-zero on any regression. Keep it green.

## Configuration

| Env var | Meaning | Default |
|---------|---------|---------|
| `LIMS_HOST` | bind host | `0.0.0.0` |
| `PORT` | bind port | `8000` |
| `LIMS_DATA_DIR` | runtime data directory | `SQCCLIMS/data` |
| `LIMS_ARCHIVE_DIR` | append-only upload archive directory (may live on a separate/larger disk) | `<data-dir>/archive` |
| `LIMS_AUTH_ENABLED` | turn token auth ON (truthy: `1`/`true`/`yes`) | off |
| `LIMS_AUTH_DISABLED` | hard-override that keeps auth OFF even if enabled | off |
| `LIMS_API_TOKENS` | token→role map, format `token:role,token:role` (roles: `viewer`/`operator`/`admin`) | empty |
| `LIMS_ENABLE_MOCK` | enable the test-only `POST /api/parsed-data/mock` endpoint (404 otherwise) | off |

Auth is **disabled by default**; see `docs/ARCHITECTURE.md` and `CONTRIBUTING.md` for details.

### Enabling auth

The frontend supports token auth. To turn it on:

1. Set `LIMS_AUTH_ENABLED=1` and `LIMS_API_TOKENS="<token>:admin,<token>:operator,<token>:viewer"`.
2. Restart the server and open the app — it shows a **login screen**. Each user
   pastes their access token; the frontend validates it via `GET /api/auth/me`,
   stores it (localStorage), and attaches it (`Authorization: Bearer`) to every
   request (including file downloads). A role badge + **Logout** appear in the top bar.
3. RBAC: `GET` needs `viewer`+, `POST/PUT/PATCH` need `operator`+, `DELETE` needs
   `admin`. An expired/invalid token returns the user to the login screen (401);
   an insufficient role surfaces a permission error (403).

When auth is OFF (default), no login is shown and no token is sent — behaviour is
unchanged. `LIMS_AUTH_DISABLED=1` hard-forces auth off even if enabled.

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — layered architecture, request lifecycle, data model, infra.
- [`docs/BACKEND_MODULES.md`](docs/BACKEND_MODULES.md) — per-module backend reference (responsibility, key functions, endpoints).
- [`docs/Data_Flow.md`](docs/Data_Flow.md) — data flow + the authoritative deletion & data-safety policy.
- [`docs/CODE_PRINCIPLES.md`](docs/CODE_PRINCIPLES.md) — conventions for humans and coding agents.
- [`docs/GLOSSARY.md`](docs/GLOSSARY.md) — plain-language definitions of domain and tech terms.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — dev workflow, adding endpoints, adding migrations.
- [`SQCCLIMS/migrations/README.md`](SQCCLIMS/migrations/README.md) — migration mechanics.
