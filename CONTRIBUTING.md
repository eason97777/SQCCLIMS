# Contributing

How to work on SQCCLIMS. Read `docs/ARCHITECTURE.md` for the layer map and `docs/CODE_PRINCIPLES.md` for the conventions you must follow.

## Repository layout

The application lives directly at the repo root (`SQCCLIMS/`); the annotated directory tree is in [`docs/Code_Structure.md`](docs/Code_Structure.md). Unless noted otherwise, run backend commands from the repo root.

The `docs/` set: ARCHITECTURE (design), BACKEND_MODULES (module reference), Code_Structure (directory map), CODE_PRINCIPLES (coding conventions), Data_Flow (data flow + deletion/safety policy), GLOSSARY (terminology).

## Dev workflow

New features follow the Spec-Driven Development flow in [`specs/README.md`](specs/README.md) (constitution → spec → plan → tasks → implement). Write the spec/plan/tasks before coding; the [constitution](.specify/memory/constitution.md) governs them all.

1. **Branch off `main`** — never commit directly to `main`.
2. **Capture a baseline:** `python3 tests/smoke_test.py` before you start.
3. Make your change in the right layer (thin HTTP handler; logic in features).
4. **Keep the smoke test green:** run it again after your change. Add coverage for any endpoint you add or change.
5. If you touched the frontend, lint and build it: `cd frontend && npm install && npm run lint && npm run build`.
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

## Working on parsers

Parser source lives in `parsers/`. When changing parser behavior:

1. Keep parsing logic in the parser modules — don't embed it in UI code.
2. Keep generated charts, reports, and intermediate files in the runtime output directory.
3. Don't commit uploaded files or real experimental datasets used for manual testing.
4. Update the docs when adding a new supported file format or changing expected input templates.
5. Add or update `templates/` only with safe examples or required source templates.

## Enabling auth

Auth is off by default. See the auth section in [`README.md`](README.md) for the environment variables, roles, and how to turn it on.

## Git conventions

- **Don't commit to `main` directly** — branch and open a PR.
- For the full "what not to commit" list (runtime data, databases, secrets, build artifacts), see [`docs/Data_Flow.md`](docs/Data_Flow.md).
- Before staging, sanity-check with `git status` / `git add -n .` that no secrets, data, database files, or build artifacts are included.
- Do not commit `.env` or any credentials.
