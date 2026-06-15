# Contributing

How to work on SQCCLIMS. Read `docs/ARCHITECTURE.md` for the layer map and `docs/CODE_PRINCIPLES.md` for the conventions you must follow.

## Repository layout

The application lives directly at the repo root (`SQCCLIMS/`):

```
SQCCLIMS/                  # repo root
├── README.md
├── CONTRIBUTING.md          # this file
├── docs/                    # ARCHITECTURE, CODE_PRINCIPLES, GLOSSARY (+ legacy notes)
├── server.py               # thin entrypoint (~38 lines)
├── app/                    # backend package
│   ├── config.py, db.py, migrations.py, validation.py, errors.py,
│   │   storage.py, logging_setup.py, backup.py, auth.py
│   ├── http/handler.py     # AppHandler: routing + dispatch
│   └── features/           # one module per domain area
├── parsers/                # resistance + CD/SEM parsers and visualizers
├── migrations/             # forward-only SQL migrations
├── frontend/               # React + TS + Vite SPA (active)
├── templates/              # downloadable import templates
├── tests/smoke_test.py     # regression smoke test
└── history/                # legacy snapshots — large, gitignored, never committed
```

Unless noted otherwise, run backend commands from the repo root.

## Dev workflow

1. **Branch off `main`** — never commit directly to `main`.
2. **Capture a baseline:** `python3 tests/smoke_test.py` before you start.
3. Make your change in the right layer (thin HTTP handler; logic in features).
4. **Keep the smoke test green:** run it again after your change. Add coverage for any endpoint you add or change.
5. If you touched the frontend, build it: `cd frontend && npm install && npm run build`.
6. Open a PR. Don't commit runtime data, secrets, or build output (see Git conventions).

## Adding a new endpoint

1. **Pick the right feature module** under `app/features/` (or, rarely, add a new one — one feature = one module). Implement the handler function there with input validation and **parameterized SQL** via `connect_db()`.
2. **Register the route** in `app/http/handler.py` → `handle_api()`: add a `method`/`path` branch that calls your feature function and returns `self.send_json(result[, status=...])`. Keep the handler thin — no business logic.
3. **Signal errors with exceptions**, not status codes: `ValueError` (400), `LookupError` (404), `ConflictError` (409), `AuthenticationError` (401), `AuthorizationError` (403). The handler maps them centrally.
4. **Add a migration** if the endpoint needs schema changes (see below).
5. **Extend `tests/smoke_test.py`** to exercise the new endpoint, and keep the whole suite green.

## Adding a DB migration

Migrations are **forward-only and checksum-guarded** (`app/migrations.py`; rules in `migrations/README.md`).

1. Create the **next-numbered** file: `migrations/NNN_short_description.sql` (monotonic numeric prefix, descriptive name — not `fix.sql`/`update.sql`).
2. Write plain SQL only (`CREATE TABLE`, `ALTER TABLE`, `CREATE INDEX`, `UPDATE` for backfills). **Do not** wrap statements in `BEGIN`/`COMMIT` — `run_migrations()` owns the transaction per file.
3. **Never edit or rename an applied migration.** Each file's SHA-256 is recorded in `schema_migrations`; if it changes after being applied, startup aborts. To change something, add a new migration.
4. Don't add new schema to `init_db()` — that holds the historical baseline only.
5. Apply by starting the server (`python3 server.py ...`); confirm the new version appears in `schema_migrations` and that restarting does not re-run it.

## Enabling auth

Auth is **off by default**. Turn it on with environment variables (read at startup/call time):

| Env var | Effect |
|---------|--------|
| `LIMS_AUTH_ENABLED=1` | enables token auth + RBAC for `/api/` paths |
| `LIMS_AUTH_DISABLED=1` | hard override — keeps auth OFF even if enabled |
| `LIMS_API_TOKENS` | `token1:admin,token2:operator,token3:viewer` |

Roles and permissions: `viewer` (GET), `operator` (GET + POST/PUT/PATCH), `admin` (all, including DELETE). Clients send the token as `Authorization: Bearer <token>` or `X-API-Key: <token>`. Non-API paths (the SPA) are never guarded.

## Git conventions

- **Don't commit to `main` directly** — branch and open a PR.
- **`data/` and `history/` are gitignored.** Never commit runtime data: the SQLite database (`*.db`, `*.sqlite`, WAL/SHM files), uploads, outputs, logs, backups, or real experimental data.
- Also ignored: `node_modules/`, virtualenvs, Python caches, `frontend/dist/`, packaging output.
- Before staging, sanity-check with `git status` / `git add -n .` that no secrets, data, database files, or build artifacts are included.
- Do not commit `.env` or any credentials.
