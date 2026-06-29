# SQCCLIMS

SQCCLIMS is a locally-run **LIMS/MES** for a semiconductor / materials sample-testing lab. It runs as a single desktop-grade web application that keeps sample tracking, process records, MES process routes, raw measurement data, parsing, and visualization together in one local SQLite store — no cloud, no external services.

## Start here

**New to the codebase?** Read in this order, then trace one request through the code:

1. This README — get it running (see [Quickstart](#quickstart)) and confirm health: `python3 tests/smoke_test.py`.
2. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — the mental model: 4 layers (HTTP → Features → Domain/Data → Infra) and the one-way dependency rule. **Most important doc.**
3. [`docs/Code_Structure.md`](docs/Code_Structure.md) — where everything lives.
4. [`docs/BACKEND_MODULES.md`](docs/BACKEND_MODULES.md) — per-module reference. Then **deep-read one feature**: `app/features/samples.py` alongside [`specs/001-samples/`](specs/001-samples/). One feature teaches all of them — they share the same shape.
5. [`docs/Data_Flow.md`](docs/Data_Flow.md) — how data moves + the deletion/data-safety policy (read before touching any delete path).
6. [`docs/GLOSSARY.md`](docs/GLOSSARY.md) — keep it open for the domain terms.

> **Best single move:** trace `GET /api/samples` through the layers — dispatched in `app/http/handler.py` → handled in `app/features/samples.py` → SQL via `app/db.py`. That 15-minute trace beats an hour of reading.

**Ready to make a change?**

- Rules you must follow: [`.specify/memory/constitution.md`](.specify/memory/constitution.md) (the short, distilled version is in [`CLAUDE.md`](CLAUDE.md) / [`AGENTS.md`](AGENTS.md) at the repo root).
- How-to (add an endpoint, add a migration, git conventions): [`CONTRIBUTING.md`](CONTRIBUTING.md).
- **Non-trivial feature** → follow the SDD flow: write `specs/NNN-slug/spec.md` (what/why) → `plan.md` (how, with the Constitution Check) → `tasks.md` → implement. Clone [`specs/001-samples/`](specs/001-samples/) as your example. See [`specs/README.md`](specs/README.md).
- **Small fix** → skip the spec; just respect the constitution and keep `python3 tests/smoke_test.py` green before and after.

`docs/` explains the system **as-built**; `specs/` is how new features get **specified**; the constitution governs both. If a doc ever disagrees with the code, trust the code and flag the doc.

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

The backend is intentionally dependency-free so it can be packaged and run on a lab workstation with just a Python install. The `parsers/` visualizers depend on **matplotlib** (chart rendering) and **openpyxl** (XLSX) — the runtime third-party dependencies, declared in `requirements.txt`; **pyinstaller** is used only for Windows packaging.

## Repository layout

```
SQCCLIMS/                 # repo root
├── README.md               # this file
├── CLAUDE.md / AGENTS.md   # AI-agent entrypoint (identical twins): rules + workflow
├── CONTRIBUTING.md         # dev workflow (GitHub Flow), adding endpoints / migrations
├── CHANGELOG.md            # release history
├── server.py               # thin entrypoint
├── requirements.txt        # parsers/ runtime deps (matplotlib, openpyxl) + pyinstaller
├── app/                    # backend package (config, db, http, features, …)
├── parsers/                # resistance + CD/SEM parsers and visualizers
├── migrations/             # forward-only SQL migrations
├── frontend/               # React + TS + Vite SPA
├── .specify/               # SDD constitution + spec/plan/tasks templates
├── specs/                  # per-feature specs (spec/plan/tasks/contracts)
├── docs/                   # ARCHITECTURE, BACKEND_MODULES, Code_Structure, CODE_PRINCIPLES, Data_Flow, GLOSSARY
├── scripts/                # DB/file restore + maintenance CLIs
├── packaging/              # Windows service / installer build
├── templates/              # downloadable import templates
├── tools/                  # local dev utilities
└── tests/smoke_test.py     # regression smoke test
```

The tree above is a top-level overview; [`docs/Code_Structure.md`](docs/Code_Structure.md) is the full directory map.

## Quickstart

### Backend

From the repo root:

```bash
python3 server.py --host 127.0.0.1 --port 8000
# optional explicit data directory:
python3 server.py --host 127.0.0.1 --port 8000 --data-dir ./data
```

On startup the server configures paths, ensures data directories, initializes the SQLite schema, runs pending migrations, and takes a startup backup before serving. It then serves the API under `/api/` and the built SPA for all other routes.

Install the `parsers/` runtime dependencies (matplotlib for charts, openpyxl for XLSX):

```bash
pip install -r requirements.txt
```

### Frontend

From `frontend/`:

```bash
npm install
npm run build      # outputs to frontend/dist, which the backend serves
# or, for live development:
npm run dev        # Vite dev server on :5173
```

The backend serves the production build from `frontend/dist`. For a fully working app, build the frontend before (or alongside) running the backend.

### Where data lives

All runtime state lives under the **data directory**:

- default: `data/`
- override with `--data-dir DIR` or the `LIMS_DATA_DIR` environment variable.

Subdirectories: `sample_testing.db` (the SQLite database), `uploads/`, `outputs/`, `logs/`, `backups/`. None of this is committed to git — only `.gitkeep` placeholders are.

### Smoke test

```bash
python3 tests/smoke_test.py        # from the repo root
```

Boots the server against a throwaway temp data directory, exercises the key read endpoints plus one create round-trip, and exits non-zero on any regression. Keep it green.

## Configuration

| Env var | Meaning | Default |
|---------|---------|---------|
| `LIMS_HOST` | bind host | `0.0.0.0` |
| `PORT` | bind port | `8000` |
| `LIMS_DATA_DIR` | runtime data directory | `data` |
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

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — layered architecture design (layer diagram, dependency direction, data model, infra).
- [`docs/BACKEND_MODULES.md`](docs/BACKEND_MODULES.md) — per-module backend reference (responsibility, key functions, endpoints).
- [`docs/Code_Structure.md`](docs/Code_Structure.md) — the full directory map.
- [`docs/CODE_PRINCIPLES.md`](docs/CODE_PRINCIPLES.md) — coding conventions for humans and coding agents.
- [`docs/Data_Flow.md`](docs/Data_Flow.md) — data flow + the authoritative deletion & data-safety policy.
- [`docs/GLOSSARY.md`](docs/GLOSSARY.md) — plain-language definitions of domain and tech terms.
- [`docs/Development_Guide.md`](docs/Development_Guide.md) — redirect to [`CONTRIBUTING.md`](CONTRIBUTING.md) / this README.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — GitHub Flow (branch → PR → review → squash-merge), dev workflow, adding endpoints/migrations.
- [`migrations/README.md`](migrations/README.md) — migration mechanics.

### Spec-Driven Development (SDD)

`docs/` is the **as-built** technical reference; `specs/` is the forward-looking, per-feature **what/why/how** layer, governed by the project constitution.

- [`specs/README.md`](specs/README.md) — the SDD workflow (Spec → Plan → Tasks → Implement) and feature numbering.
- [`.specify/memory/constitution.md`](.specify/memory/constitution.md) — the project constitution: non-negotiable principles + governance.
- Worked exemplars under [`specs/`](specs/): [`001-samples/`](specs/001-samples/) and [`002-raw-data-parsing/`](specs/002-raw-data-parsing/).
