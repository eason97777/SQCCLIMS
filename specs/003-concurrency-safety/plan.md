# Implementation Plan: Concurrent-Writer Safety

> This plan describes **HOW** the feature in [`./spec.md`](./spec.md) is built. It
> MUST pass the **Constitution Check** below before any task is generated.

## Parent Spec

- **Spec:** [`./spec.md`](./spec.md)
- **Feature number:** 003
- **Status of spec:** Approved (required before implementation begins)

## Constitution Check

| Article | Verdict | Notes |
|---------|---------|-------|
| I — Zero runtime dependencies (stdlib backend) | PASS | All fixes use `sqlite3` PRAGMAs / `BEGIN IMMEDIATE` / standard-library `contextlib`. **No new dependency** anywhere; nothing is added to `requirements.txt`. |
| II — Layered architecture, one-way dependencies | PASS | Changes stay within their layers: infra (`app/db.py`), feature (`app/features/samples.py`), HTTP mapping (`app/http/handler.py`). No new imports reverse the Infra/Domain ← Features ← HTTP direction; no cycles introduced. |
| III — One feature owns its domain | PASS | Sample-creation logic stays in `app/features/samples.py`; `handler.py` only gains two `except` arms (transport-level mapping, not business logic). The connection PRAGMA is shared infra, not feature logic. |
| IV — Data safety is non-negotiable | PASS | Strengthens integrity: makes duplicate `sample_uid` impossible to persist, and the legacy-duplicate migration renumbers (never deletes) colliding rows. No recoverability guarantee is weakened; `busy_timeout` only makes contended writers wait. |
| V — Forward-only checksummed migrations | PASS | The `sample_uid` uniqueness constraint + legacy-duplicate cleanup ship as a **new** `migrations/006_*.sql`. No applied migration or `init_db()` baseline is edited. Migration SQL contains no `BEGIN`/`COMMIT` (`run_migrations()` owns the transaction). |
| VI — Errors via exception convention | PASS | New mappings are added to the **single** central mapping point in `AppHandler.route()` (`sqlite3.IntegrityError → 409`, locked `sqlite3.OperationalError → 503`). Feature code keeps raising typed exceptions; no hand-built status codes. |
| VII — Parameterized SQL only | PASS | No user input is interpolated. The migration is fixed DDL/DML built entirely in code; the retry path reuses the existing parameterized `INSERT`. |
| VIII — Runtime config read at call time | PASS | `connect_db()` already reads `config.DB_PATH` / `config.DATA_DIR` at call time; the added `PRAGMA busy_timeout` does not bind any path at import. |
| IX — Smoke test is the green-light oracle | PASS | `tests/smoke_test.py` gains a concurrency case (N simultaneous `POST /api/samples`, assert all succeed, UIDs distinct, zero 500s). Baseline captured before changes. |
| X — Simplicity over cleverness | PASS | Prefers the engine's native `busy_timeout` + `BEGIN IMMEDIATE` over a hand-rolled global Python write-lock (rejected — see Risks). Smallest change that meets the guarantee; no speculative abstraction. |
| XI — Optional-but-real auth & RBAC | N/A | No auth surface changes. Existing `GET ≤ operator-write ≤ admin-delete` policy and no-op-when-disabled behavior are untouched. |

> No row is **DEVIATION**. No unapproved deviation proceeds.

## Technical Context

> SQCCLIMS is stdlib-only Python (`http.server` `ThreadingHTTPServer` +
> `sqlite3`) backend + React 19 / TypeScript / Vite frontend. This feature is
> **backend-only** and **cross-cutting** (touches infra, one feature module, and
> the HTTP error mapping). No frontend change.

- **Backend layer(s) touched:** infra (`app/db.py`), feature (`app/features/samples.py`),
  HTTP mapping (`app/http/handler.py`), migrations (`migrations/006_*.sql`),
  tests (`tests/smoke_test.py`).
- **Frontend area(s):** none.
- **Relevant references:** [`docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md),
  [`docs/BACKEND_MODULES.md`](../../docs/BACKEND_MODULES.md),
  [`docs/CODE_PRINCIPLES.md`](../../docs/CODE_PRINCIPLES.md) (§4 exception→status,
  §8 migrations), [`docs/Data_Flow.md`](../../docs/Data_Flow.md).

### The problem, grounded in current code

- `server.py:35` starts a `ThreadingHTTPServer`, so each request runs on its own
  thread → real concurrent writers.
- `app/db.py:7` `connect_db()` opens a **fresh** connection per call (correctly
  per-thread, not shared) with `PRAGMA foreign_keys = ON`,
  `journal_mode = WAL`, `synchronous = NORMAL`. It sets **no `busy_timeout`** —
  the SQLite default is `0`, so a second writer that meets the single write lock
  raises `sqlite3.OperationalError: database is locked` immediately.
- That `OperationalError` is **unmapped** in `app/http/handler.py:60-84`, so it
  falls through to the generic `except Exception` → **HTTP 500**.
- `app/features/samples.py:10` `generate_sample_uid()` does
  `SELECT … WHERE sample_uid LIKE 'SMP-YYYY-%'`, computes `max+1` in Python, and
  the INSERT happens later (`create_sample`, lines 162-181). The transaction is
  **deferred** (it begins with SELECTs in `validate_sample_hierarchy`), so the
  write lock is **not** held during the read — the read-then-write race window is
  real. `sample_uid` has **no UNIQUE constraint** (only `sample_display_code` is
  unique, plus the `idx_samples_identity_unique` composite), so two concurrent
  creates of *different* samples can mint **duplicate UIDs that persist
  silently**.
- A constraint collision in the race window raises `sqlite3.IntegrityError`,
  which is also unmapped → 500 (should be 409). Note: `create_sample` already
  catches `IntegrityError` and re-raises a `ValueError` for the *display-code*
  case (samples.py:179-180); that path is about display-code duplication and
  stays a 400 — the new 409 mapping is the **fallback** for integrity errors that
  reach the handler (e.g. a future/raw integrity failure), and the UID path is
  made robust by retry rather than by surfacing an error.
- `with connect_db() as conn:` commits/rolls back but does **not** close the
  connection (left to GC) — a minor resource concern under sustained concurrency
  (optional fix E).

## Architecture & Approach

Five scoped changes, cheapest-first. The first alone removes the 500-storm; the
rest make identity correct and errors honest.

1. **(A) Add `PRAGMA busy_timeout` in `connect_db()`** (`app/db.py`). Set a fixed
   timeout (5000 ms) on every connection so a contended writer **waits inside
   SQLite** for the lock to clear and then proceeds, instead of erroring
   instantly. Biggest win, near-zero risk, one line. *(FR-001, NFR-005)*

2. **(B) Make `sample_uid` unique + make creation robust.** Ship a **new**
   `migrations/006_samples_uid_unique.sql` that (i) detects and **renumbers**
   pre-existing duplicate UIDs (keep earliest, reassign later collisions), then
   (ii) creates a UNIQUE index on `sample_uid` (scoped to non-empty values).
   In `app/features/samples.py`, make `create_sample` **robust to the race**:
   generate the UID and attempt the INSERT inside a bounded **retry loop** —
   on a `sqlite3.IntegrityError` that is specifically a `sample_uid` collision,
   regenerate the UID (now seeing the committed row) and retry; give up after a
   small fixed number of attempts. The existing display-code `IntegrityError`
   handling (→ `ValueError` → 400) is preserved. *(FR-002, FR-003, FR-008, FR-009)*

3. **(C) Use `BEGIN IMMEDIATE` for the read-then-write create path**
   (`app/features/samples.py`). Take the write lock **up front** before the
   validation SELECTs, so the transaction does not start deferred and then have
   to *upgrade* its lock mid-flight (the upgrade is the classic busy/deadlock
   trigger). Combined with (A), a second creator waits for the lock at `BEGIN
   IMMEDIATE` time and then runs cleanly. *(FR-001)*

4. **(D) Honest error mapping in `app/http/handler.py`.** Add two `except` arms
   to the **single** `route()` mapping: `sqlite3.IntegrityError → 409 Conflict`
   and `sqlite3.OperationalError` whose message indicates "database is locked"
   (i.e. busy-timeout exhausted) `→ 503 Service Unavailable`. All existing arms
   (`ValueError → 400`, `LookupError → 404`, `ConflictError → 409`, etc.) are
   kept, and these new arms are ordered so they do not shadow them. *(FR-004,
   FR-005, FR-006, NFR-003)*

5. **(E, optional) Close connections explicitly.** Wrap `connect_db()` usage in
   `contextlib.closing` (or close in `connect_db`'s own management) so
   connections are released deterministically under sustained concurrency rather
   than at GC. Low priority; does not affect correctness of A–D. *(NFR-001)*

Thin-handler contract is preserved: `handler.py` only gains transport-level
exception mapping; all create/UID logic stays in the `samples` feature module;
the PRAGMA is shared infra.

## Data Model Changes

> Delivered as a **new** `migrations/006_*.sql` (Article V). No applied migration
> or `init_db()` baseline is edited. Migration SQL contains no `BEGIN`/`COMMIT`.

- **Migration:** `migrations/006_samples_uid_unique.sql`
- **New/changed tables:** none structurally. The `samples` table gains a
  **uniqueness guarantee** on `sample_uid`; no column is added or dropped.
- **Indexes:** add `idx_samples_uid_unique` — a **UNIQUE** index on
  `samples(sample_uid)` scoped to non-empty values (`WHERE sample_uid != ''`), so
  legacy/blank UIDs do not collide and only real business identifiers are
  constrained. This mirrors the existing partial-unique pattern
  `idx_samples_display_code_unique` (`app/migrations.py:599-605`).
- **Legacy-duplicate handling:** before creating the unique index, the migration
  **renumbers** any pre-existing duplicate UIDs: for each `sample_uid` value held
  by more than one row, the earliest-created row keeps its UID and every later
  colliding row is reassigned the next free `SMP-YYYY-NNNNNN` in that year series.
  This must run *before* the `CREATE UNIQUE INDEX` or index creation would fail on
  dirty data. (See [`./data-model.md`](./data-model.md) for the detection/cleanup
  strategy and why `sample_uid` was previously unconstrained.)
- **Data-safety note:** no cascade/delete behavior changes. No new deletable
  entity is introduced, so `docs/Data_Flow.md`'s per-entity deletion table is
  unchanged. The renumber-not-delete policy preserves every row (Article IV).
- See [`./data-model.md`](./data-model.md).

## API Contracts

> No new endpoints. This is a **behavioral / cross-cutting** contract change: the
> status code returned by **all write endpoints** under contention/integrity
> conditions changes from a misleading 500 to an honest 409/503. Full detail and
> example bodies in [`./contracts/error-handling.md`](./contracts/error-handling.md).

| Method | Path | Purpose | Min role (if auth on) |
|--------|------|---------|-----------------------|
| (all writes) | `POST` / `PUT` / `PATCH` / `DELETE` `/api/*` | unchanged purpose; **error behavior under contention** changes | unchanged (operator-write / admin-delete) |

- The exception→status mapping each write endpoint relies on (Article VI) gains:
  `sqlite3.IntegrityError → 409`, locked `sqlite3.OperationalError → 503`.
- Error bodies remain `{"error": "<message>"}` (the 500 path's extra `"detail"`
  no longer fires for these now-mapped conditions).
- Detailed contract: [`./contracts/error-handling.md`](./contracts/error-handling.md).

## Affected Modules & Files

- **Infra:** `app/db.py` — add `PRAGMA busy_timeout` in `connect_db()` (A);
  optionally provide explicit-close support (E).
- **Feature:** `app/features/samples.py` — `BEGIN IMMEDIATE` for the create
  transaction (C) and the UID-collision retry loop in `create_sample`/around
  `generate_sample_uid` (B). No other feature module needs logic changes; they
  inherit `busy_timeout` (A) and the new handler mapping (D) for free.
- **HTTP:** `app/http/handler.py` — add `except sqlite3.IntegrityError` (→409) and
  `except sqlite3.OperationalError` locked (→503) arms to `route()` (D). Dispatch
  table unchanged; no business logic added.
- **Migration:** `migrations/006_samples_uid_unique.sql` — legacy-duplicate
  renumber + UNIQUE index (B).
- **Tests:** `tests/smoke_test.py` — add the concurrency case (N threads doing
  simultaneous `POST /api/samples`; assert all 2xx, all UIDs distinct, zero 500s).
- **Docs (Phase 6):** `docs/BACKEND_MODULES.md` (note busy_timeout + the new error
  mappings), `docs/CODE_PRINCIPLES.md` §4 (extend the exception→status table with
  409/503 DB mappings), `docs/ARCHITECTURE.md` (note the `sample_uid` unique
  constraint if it documents the schema).

## Sequence / Flow

> Two concurrent `POST /api/samples` under `busy_timeout` + `BEGIN IMMEDIATE`:

1. Requests R1 and R2 arrive on separate threads (`ThreadingHTTPServer`); each
   gets its own connection from `connect_db()` (now with `busy_timeout = 5000`).
2. R1 enters the create transaction with `BEGIN IMMEDIATE` → acquires the single
   write lock immediately.
3. R2 enters `BEGIN IMMEDIATE` → lock is held → SQLite **waits up to 5000 ms**
   (busy_timeout) instead of raising.
4. R1 runs `validate_sample_hierarchy` (SELECTs), `generate_sample_uid` (sees no
   conflicting committed row), INSERTs, commits → releases the lock. R1 returns
   201 with `sample_uid = SMP-2026-000012`.
5. R2's wait clears the instant R1 commits; R2 acquires the lock, generates its
   UID **after** R1's commit is visible (so it computes `...000013`), INSERTs,
   commits → 201 with a **distinct** UID.
6. **Defense in depth:** if R2 had computed the same UID (e.g. a residual race),
   the new UNIQUE index makes the INSERT raise `IntegrityError`; the retry loop
   regenerates the UID and re-inserts. Only an *unresolvable* integrity error
   reaches the handler → 409. If `busy_timeout` is exhausted under pathological
   load, the `OperationalError` reaches the handler → 503.

## Risks & Trade-offs

- **busy_timeout can still time out under heavy sustained write load.** A 5000 ms
  wait is generous for single-workstation lab use but not infinite; beyond it the
  honest answer is 503 (FR-005), signaling "retry shortly." *Mitigation:* the
  value is conservative for the expected volume; 503 is a truthful, retryable
  signal rather than a corrupt write or a misleading 500.
- **Global Python write-lock alternative — considered and rejected.** A
  process-wide `threading.Lock` serializing all writes would also prevent the
  race, but it (a) duplicates the database engine's own locking, (b) adds a
  speculative concurrency abstraction the codebase does not otherwise have
  (violates Article X simplicity), (c) does nothing for correctness that
  `busy_timeout` + a UNIQUE constraint + `BEGIN IMMEDIATE` don't already do, and
  (d) would not survive a future move to multiple processes. We prefer the native
  mechanism. (NFR-005 / Article X.)
- **Migration on dirty data.** Old databases may hold duplicate UIDs. The
  migration must renumber duplicates **before** creating the unique index, or
  index creation aborts startup. *Mitigation:* the renumber step is explicit,
  preserves the earliest row, and is checksum-guarded so it runs exactly once
  (Article V); see the analogous guarded rebuild in
  `ensure_samples_composite_unique` (`app/migrations.py:467`) for the established
  pattern.
- **Retry-loop bound.** The UID retry must be bounded (a few attempts) so a
  genuinely stuck condition surfaces as a 409 rather than spinning. *Mitigation:*
  fixed small attempt cap; after it, the integrity error propagates to the
  handler (→409).
- **`BEGIN IMMEDIATE` slightly widens lock-hold time** (the lock is taken before
  the validation SELECTs instead of at INSERT). *Mitigation:* the create
  transaction is short; this is the standard, recommended pattern for
  read-then-write under SQLite and is what makes the wait deterministic.

## Testing Approach

- **Baseline:** run `python3 tests/smoke_test.py` before any change and record it
  green (Article IX).
- **New coverage:** add a concurrency case to `tests/smoke_test.py` that spawns
  **N** threads each issuing `POST /api/samples` simultaneously, then asserts:
  every response is 2xx (no 500s), the collected `sample_uid` values are **all
  distinct**, and the created samples are all present in the list. Covers
  **AC-001, AC-002, AC-003** (and exercises the busy_timeout + retry path).
- **Honest-error checks:** where feasible, assert that a forced integrity
  collision returns 409 and (best-effort) that a forced locked condition returns
  503 — covers **AC-004, AC-005**. The legacy-duplicate migration (AC-006) is
  verified by a one-off check that seeding duplicate UIDs then running migrations
  yields a clean, uniquely-indexed table with the earliest UID preserved.
- **Regression:** confirm all pre-existing smoke cases (create/list/update/
  delete-preview/cascade-delete) still pass — covers **AC-007, AC-008**.
- **Manual:** none required beyond the smoke test.
