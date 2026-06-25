# SQCCLIMS Constitution

**Version:** 1.0.0
**Ratified:** 2026-06-16
**Last amended:** 2026-06-16

## Preamble

This constitution defines the non-negotiable principles that govern SQCCLIMS —
a Laboratory Information Management System for semiconductor/wafer sample quality
control. It is the highest authority in the Spec-Driven Development (SDD)
workflow: every `spec.md`, `plan.md`, and `tasks.md` under [`specs/`](../../specs/)
MUST comply with the Articles below, and every `plan.md` MUST include a
**Constitution Check** that confirms compliance article-by-article or explicitly
justifies a deviation.

These Articles are derived from values already established in the codebase and
its as-built reference docs — not invented here. Where an Article restates an
existing rule, the authoritative technical detail lives in `docs/` and is
cross-linked; this document states the *principle* and *why it is binding*. The
relevant references are
[`docs/CODE_PRINCIPLES.md`](../../docs/CODE_PRINCIPLES.md),
[`docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md), and
[`docs/Data_Flow.md`](../../docs/Data_Flow.md).

A principle being "deferred" elsewhere (e.g. soft-delete, a repository layer,
pagination) is itself a constitutional decision: do not bolt on a partial
version without an amendment or an explicit, justified plan deviation.

---

## Article I — Standard-Library Backend Core, with a Single Sanctioned Dependency Boundary

**Principle.** The backend **core** — `server.py` and everything under `app/**`
(http, features, db, validation, storage, deletion, migrations, auth, etc.) — is
built **exclusively on the Python 3 standard library** (`http.server`,
`sqlite3`, etc.). No web framework, no ORM, no chart library, and no third-party
runtime package may be imported by the core. This is the **non-negotiable** part:
it is what lets the server run unchanged on a bare lab workstation and be
packaged as a lean, self-contained executable.

The **one sanctioned exception** is the `parsers/` layer. Because numerical
visualization and spreadsheet ingest are impractical to implement in pure
standard library, `parsers/` is the single boundary where confined,
well-justified third-party **scientific** dependencies are permitted — currently
**matplotlib** for chart rendering
(`parsers/resistance_heatmap_visualizer.py`, `parsers/cd_violin_visualizer.py`)
and **openpyxl** for XLSX ingest (`parsers/resistance_csv_parser.py`). Every such
dependency MUST be:

1. **Confined to `parsers/`** — it MUST NOT be imported by `server.py` or any
   `app/**` module.
2. **Declared in `requirements.txt`** — an imported-but-undeclared dependency is
   a defect.
3. **Optional/lazy where feasible** — imported inside the function that needs it
   so that core operation (serving, ingest, deletion) degrades gracefully when
   the library is absent, rather than failing at startup.

**Rationale.** SQCCLIMS is designed to run on a single lab workstation and to be
packaged as a self-contained Windows executable (PyInstaller). Every dependency
must be vetted, frozen, packaged, and maintained on an air-gapped or restricted
lab machine, so the core stays dependency-free by rule. The scientific work in
`parsers/` is the genuine exception where stdlib-only would be self-defeating;
keeping those dependencies quarantined behind one named boundary preserves the
core's "runs anywhere" property while letting visualization and spreadsheet
parsing use the right tools. The frontend uses npm normally but MUST keep its
footprint lean.

**Compliance.** Introducing any third-party runtime dependency **outside
`parsers/`** is prohibited without a constitution amendment (see Governance).
Every allowed dependency MUST appear in `requirements.txt`; a `parsers/` import
with no matching `requirements.txt` entry, or a third-party import anywhere under
`app/**` or in `server.py`, is a violation that blocks the change.

---

## Article II — Layered Architecture with One-Way Dependencies

**Principle.** The system is layered **Infra/Domain ← Features ← HTTP**:

- `app/http/handler.py` may import from `app/features/*` and infra.
- `app/features/*` may import `db`, `validation`, `storage`, `deletion`,
  `errors`, `config`.
- Infra/domain modules MUST NOT import features or the HTTP layer.

There are **no import cycles**. Where a low-level module genuinely needs a
higher-level helper, the cycle is broken with a **function-local import** (as
`db.record_deletion` does for `validation.now_iso`) — never by reversing the
dependency direction.

**Rationale.** A single enforced dependency direction keeps the system legible,
testable, and packageable. Cycles are the first symptom of a layer boundary
eroding. See [`docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md).

---

## Article III — One Feature Owns Its Domain

**Principle.** Each domain area is a **single module** under `app/features/` that
owns its HTTP-facing handler functions, its service/validation logic, and its
parameterized SQL. `handler.py` stays thin — parse, route, dispatch, serialize —
and contains **no business logic**. A feature is not spread across multiple
modules.

**Rationale.** "One feature = one module" makes ownership obvious, keeps the HTTP
layer a pure transport concern, and prevents logic from leaking into the router.
See [`docs/CODE_PRINCIPLES.md`](../../docs/CODE_PRINCIPLES.md) §3 and
[`docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md).

---

## Article IV — Data Safety Is Non-Negotiable

**Principle.** No destructive operation may run without a preceding recoverable
checkpoint, and the data-safety policy in
[`docs/Data_Flow.md`](../../docs/Data_Flow.md) ("Deletion & Data-Safety Policy")
is **authoritative**. Concretely:

1. **Row cascade is uniform and DB-enforced** — every child table references its
   parent `ON DELETE CASCADE`, with `PRAGMA foreign_keys = ON` on every
   connection. The documented `ON DELETE SET NULL` exceptions
   (`processing_jobs`, `processing_results.sample_id`) are handled explicitly by
   the owning delete path so nothing is orphaned.
2. **File cleanup is centralized** in `app/deletion.py`; no ad-hoc per-handler
   file removal.
3. **Backup precedes destruction** — uploaded files are copied into the
   append-only, content-addressed archive at upload time; a DB snapshot is taken
   at startup and before strong-tier deletes; the targeted row is snapshotted
   into `deletion_audit` at delete time.
4. **Confirmation tiers by blast radius** — Simple (leaf row) vs. Strong
   (anything with children or files, gated by a cascade-preview endpoint).

Any **new deletable entity** MUST be added to the per-entity deletion table in
`docs/Data_Flow.md` and implemented to match these rules.

**Rationale.** This is process/measurement data for semiconductor QC; an
unrecoverable loss is unacceptable. Recoverability is engineered in by default,
not left to operator discipline.

---

## Article V — Forward-Only, Checksum-Guarded Migrations

**Principle.** Every schema change — new tables, columns, indexes, data
backfills — goes into a new `migrations/NNN_*.sql` file with a monotonic numeric
prefix. An applied migration is **immutable**: its SHA-256 is stored in
`schema_migrations`, and startup **aborts** if a previously-applied file's
checksum changes. Schema changes are never made by editing an applied migration
or by appending to `init_db()` (which holds the historical baseline only).
Migration SQL contains no `BEGIN`/`COMMIT` — `run_migrations()` owns the
transaction per file.

**Rationale.** Forward-only, checksummed migrations make every database's history
reproducible and tamper-evident across lab machines. See
[`docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md) ("Migration system") and
`migrations/README.md`.

---

## Article VI — Errors via the Exception Convention

**Principle.** Feature code never builds HTTP status codes by hand. It raises the
correct exception (`ValueError`, `LookupError`, `ConflictError`, etc.) and lets
`AppHandler.route()` map it centrally. See the full exception→HTTP-status mapping
in [`docs/CODE_PRINCIPLES.md`](../../docs/CODE_PRINCIPLES.md#exception--http-status-mapping).

**Rationale.** A single mapping point keeps status semantics consistent and keeps
features focused on domain meaning (invalid input, missing entity, conflict)
rather than transport. See [`docs/CODE_PRINCIPLES.md`](../../docs/CODE_PRINCIPLES.md) §4.

---

## Article VII — Parameterized SQL Only

**Principle.** User input is **never** string-formatted into SQL. All queries use
`?` placeholders or named parameters with values passed as the parameter
tuple/dict. The only acceptable interpolation is for trusted identifiers built
entirely in code (e.g. a fixed column list) — never request data.

**Rationale.** This eliminates SQL injection as a class and is already the
uniform practice across every feature module. See
[`docs/CODE_PRINCIPLES.md`](../../docs/CODE_PRINCIPLES.md) §5.

---

## Article VIII — Runtime Config Read at Call Time

**Principle.** `config.configure_paths()` reassigns the path globals
(`DATA_DIR`, `DB_PATH`, `UPLOAD_DIR`, `OUTPUT_DIR`, `LOG_DIR`) at startup.
Therefore code MUST `import app.config as config` and read `config.<NAME>` at
call time. Binding a path via `from app.config import DB_PATH` at import time is
prohibited because it freezes a stale value.

**Rationale.** Runtime path configuration (driven by `LIMS_DATA_DIR`, archive
dir, etc.) only works if every consumer resolves paths late. See
[`docs/CODE_PRINCIPLES.md`](../../docs/CODE_PRINCIPLES.md) §2.

---

## Article IX — The Smoke Test Is the Green-Light Oracle

**Principle.** `tests/smoke_test.py` MUST pass before a change is considered
done. It is run to capture a baseline before work and to prove no regression
after. When an endpoint is added or changed, the smoke test MUST be extended to
cover it.

**Rationale.** With no heavyweight test framework and a stdlib-only stance, the
smoke test is the project's single, fast, authoritative signal that the system
still works end-to-end. See [`docs/CODE_PRINCIPLES.md`](../../docs/CODE_PRINCIPLES.md) §7.

---

## Article X — Simplicity Over Cleverness

**Principle.** The simplest solution that works wins. No speculative
abstraction, no premature generalization, no over-engineering. Follow existing
naming conventions and file structure. Comment non-obvious logic and invariants —
not what the code plainly says. Features explicitly **deferred** in the docs
(full cascading soft-delete, a repository/data-access layer, pagination) stay
deferred; if one is genuinely needed, raise it rather than shipping a partial
version.

**Rationale.** A deliberately small system — with a dependency-free core and
dependencies confined to the one sanctioned `parsers/` boundary (Article I) —
stays small only if restraint is a rule, not a mood. See
[`docs/CODE_PRINCIPLES.md`](../../docs/CODE_PRINCIPLES.md) §9 and its
"Deliberately deferred" section.

---

## Article XI — Optional-But-Real Auth & RBAC

**Principle.** Token authentication and role-based access control
(`viewer` / `operator` / `admin`) are **off by default** and MUST remain so
unless explicitly enabled (`LIMS_AUTH_ENABLED` truthy and `LIMS_AUTH_DISABLED`
not set). When disabled, `authorize()` is a true no-op and the API behaves as if
auth did not exist. When enabled, it MUST be enforced uniformly on `/api/` paths
with the documented `GET ≤ operator-write ≤ admin-delete` policy. Auth is never
half-built: it is either a complete no-op or a complete gate. All auth env vars
are read at call time.

**Rationale.** Single-workstation labs often need no auth; multi-user or audited
deployments need real auth. Making it optional but *complete* avoids a false
sense of security. See [`docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md)
("Optional auth").

---

## Governance

### Authority
This constitution supersedes ad-hoc convention. When a spec, plan, task, or pull
request conflicts with an Article, the Article wins unless an amendment changes
the Article first.

### Compliance
- Every `plan.md` MUST contain a **Constitution Check** section that addresses
  each relevant Article and either confirms compliance or records a justified,
  scoped deviation.
- A deviation without a recorded justification is a defect and blocks the plan.
- Reviewers MUST reject changes that violate an Article without an approved
  amendment.

### Amendment procedure
1. Propose the change as a normal spec/PR describing the Article added, modified,
   or removed and the motivating need.
2. A human maintainer MUST approve. Agents may draft amendments but MUST NOT
   ratify them.
3. On approval, update this file, bump the version, update **Last amended**, and
   reconcile any affected `docs/` reference.

### Versioning (semantic)
- **MAJOR** — an Article is removed or redefined in a backward-incompatible way
  (existing specs/plans may no longer comply).
- **MINOR** — a new Article is added, or an existing one is materially expanded.
- **PATCH** — clarifications, wording, cross-link fixes; no change in obligation.

### Relationship to `docs/`
`docs/` is the **as-built technical reference** (how the system is implemented
today). This constitution is the **forward-looking authority** (what must always
hold). When they disagree on a *principle*, this document governs and `docs/`
is corrected; when they disagree on a *technical detail*, `docs/` is authoritative
and this document is cross-linked, not duplicated.
