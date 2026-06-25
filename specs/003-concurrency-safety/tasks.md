# Tasks: Concurrent-Writer Safety

> Tasks are **derived from [`./plan.md`](./plan.md)** (which is derived from
> [`./spec.md`](./spec.md)). Execute them **in dependency order**. Each task
> references the functional requirement (FR-00x) it satisfies and notes any task
> it depends on. Check a box only when the task is complete *and* the smoke test
> is still green (constitution **Article IX**). Mark parallelizable tasks `[P]`.
>
> Status: **Implemented** — all tasks complete; smoke test green (20 passed,
> including the concurrency case and the legacy-duplicate migration check).

## Phase 0 — Baseline

- [x] T001 Capture a baseline: run `python3 tests/smoke_test.py` and record it
  green before any change. *(Article IX)*

## Phase 1 — Data Layer (migration & schema)

> A **new** `migrations/006_*.sql` (Article V — never edit an applied migration;
> no `BEGIN`/`COMMIT` in the file). See [`./data-model.md`](./data-model.md).

- [x] T002 Write `migrations/006_samples_uid_unique.sql` that **first** detects
  and **renumbers** pre-existing duplicate `sample_uid` values (keep the
  earliest-created row's UID; reassign each later collision the next free
  `SMP-YYYY-NNNNNN` in that year series), **then** creates
  `idx_samples_uid_unique` as a UNIQUE index on `samples(sample_uid)` scoped to
  `WHERE sample_uid != ''`. *(FR-002, FR-008, FR-009; depends on T001)*
- [x] T003 Apply migrations locally against (a) a clean DB and (b) a DB seeded
  with duplicate UIDs; confirm both succeed, the earliest UID of each set is
  preserved, the index exists and is unique, and `schema_migrations` records
  `006_*.sql` with its checksum. *(FR-009, Article V; depends on T002)*

## Phase 2 — Infra (connection behavior)

> Shared infra in `app/db.py`. No feature logic here (Articles II, III).

- [x] T004 In `app/db.py` `connect_db()`, add `PRAGMA busy_timeout = 5000` so
  contended writers wait-and-retry inside SQLite instead of erroring instantly.
  *(FR-001, NFR-005; depends on T001)*
- [x] T005 [P] (optional, NFR-001) Make connection close deterministic under
  sustained concurrency — e.g. wrap `connect_db()` usage in `contextlib.closing`
  or close within `connect_db`'s management — without changing call sites'
  commit/rollback semantics. *(NFR-001; depends on T004)*

## Phase 3 — Feature Module (create path)

> Create/UID logic stays in `app/features/samples.py` (Article III); parameterized
> SQL only (Article VII); typed exceptions only (Article VI).

- [x] T006 In `app/features/samples.py` `create_sample`, begin the create
  transaction with `BEGIN IMMEDIATE` so the write lock is taken **before** the
  validation SELECTs, avoiding a deferred lock-upgrade busy/deadlock. *(FR-001;
  depends on T004)*
- [x] T007 Make `create_sample` robust to the UID race: wrap UID
  generation + INSERT in a **bounded retry loop** — on a `sqlite3.IntegrityError`
  that is specifically a `sample_uid` collision, regenerate via
  `generate_sample_uid` (now seeing the committed row) and retry; after a small
  fixed attempt cap, let the error propagate. Preserve the existing
  display-code `IntegrityError → ValueError` (400) handling. *(FR-002, FR-003,
  FR-006; depends on T002, T006)*

## Phase 4 — HTTP Routes (thin handler error mapping)

> Add transport-level exception mapping only — no business logic in `handler.py`
> (Articles II, III, VI). Single central mapping point in `route()`.

- [x] T008 In `app/http/handler.py` `route()`, add `except sqlite3.IntegrityError`
  → **409 Conflict** and `except sqlite3.OperationalError` (message indicates
  "database is locked") → **503 Service Unavailable**, ordered so they do not
  shadow the existing `ValueError`/`LookupError`/`ConflictError`/auth arms. Import
  `sqlite3` in the handler. *(FR-004, FR-005, FR-006, NFR-003; depends on T001)*
- [x] T009 Confirm existing error semantics are unchanged: 400 invalid input, 404
  missing entity, 409 domain `ConflictError`, and that the generic 500 arm now
  only catches genuinely-unexpected errors. *(FR-006; depends on T008)*

## Phase 5 — Tests

> The smoke test is the green-light oracle (Article IX).

- [x] T010 Extend `tests/smoke_test.py` with a **concurrency case**: spawn **N**
  threads each issuing `POST /api/samples` simultaneously; assert every response
  is 2xx (zero 500s) and the collected `sample_uid` values are **all distinct**.
  *(AC-001, AC-002, AC-003; depends on T004, T006, T007, T008)*
- [x] T011 [P] Add honest-error assertions where feasible: a forced
  integrity/uniqueness collision returns **409**; (best-effort) a forced locked
  condition returns **503**. *(AC-004, AC-005; depends on T008)*
- [x] T012 [P] Verify the legacy-duplicate migration: seed duplicate UIDs, run
  migrations, assert a clean uniquely-indexed table with the earliest UID
  preserved. *(AC-006; depends on T003)*
- [x] T013 Run the full smoke test and confirm it is green, including all
  pre-existing cases. *(AC-007, AC-008; depends on T010, T011, T012)*

## Phase 6 — Docs

> Keep the as-built reference layer accurate.

- [x] T014 Update [`docs/CODE_PRINCIPLES.md`](../../docs/CODE_PRINCIPLES.md) §4
  exception→status table with `sqlite3.IntegrityError → 409` and locked
  `sqlite3.OperationalError → 503`. *(depends on T013)*
- [x] T015 [P] Update [`docs/BACKEND_MODULES.md`](../../docs/BACKEND_MODULES.md)
  to note the `busy_timeout` on every connection, the `sample_uid` uniqueness +
  create-retry behavior, and the new DB-error mappings; update
  [`docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md) if it documents the
  `samples` schema/indexes. *(depends on T013)*
- [x] T016 Update the parent [`./spec.md`](./spec.md) status to **Implemented**.
  *(depends on T013)*
