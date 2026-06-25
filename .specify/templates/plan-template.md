# Implementation Plan: [FEATURE NAME]

> A plan describes **HOW** the feature in the parent `spec.md` is built. It turns
> the WHAT/WHY into concrete layer placement, data-model changes, contracts, and
> a sequence of work. It MUST pass the **Constitution Check** below before any
> task is generated. Replace bracketed prompts with real content; delete
> guidance lines (`>`) when done.

## Parent Spec

- **Spec:** [`./spec.md`](./spec.md)
- **Feature number:** [NNN]
- **Status of spec:** [Approved is required before implementation begins]

## Constitution Check

> Confirm compliance with each relevant Article of the
> [constitution](../../.specify/memory/constitution.md). For each, write
> **PASS** with a one-line justification, **N/A** if the Article does not apply
> to this feature, or **DEVIATION** with an explicit, scoped justification (a
> deviation requires human approval — see Governance).

| Article | Verdict | Notes |
|---------|---------|-------|
| I — Zero runtime dependencies (stdlib backend) | PASS / N/A / DEVIATION | [no new backend deps] |
| II — Layered architecture, one-way dependencies | PASS / N/A / DEVIATION | [no new cycles; correct layer placement] |
| III — One feature owns its domain | PASS / N/A / DEVIATION | [single `app/features/*` module] |
| IV — Data safety is non-negotiable | PASS / N/A / DEVIATION | [deletes follow tiers/archive/audit] |
| V — Forward-only checksummed migrations | PASS / N/A / DEVIATION | [schema change is a new `migrations/NNN`] |
| VI — Errors via exception convention | PASS / N/A / DEVIATION | [raises ValueError/LookupError/ConflictError] |
| VII — Parameterized SQL only | PASS / N/A / DEVIATION | [no user input in SQL strings] |
| VIII — Runtime config read at call time | PASS / N/A / DEVIATION | [uses `config.<NAME>`] |
| IX — Smoke test is the green-light oracle | PASS / N/A / DEVIATION | [smoke test extended for new endpoints] |
| X — Simplicity over cleverness | PASS / N/A / DEVIATION | [no speculative abstraction] |
| XI — Optional-but-real auth & RBAC | PASS / N/A / DEVIATION | [no-op when disabled; correct role policy] |

> If any row is **DEVIATION**, summarize the approved justification here and link
> the approval. No unapproved deviations may proceed.

## Technical Context

> The stack and where this feature lives. SQCCLIMS is stdlib-only Python
> (`http.server` + `sqlite3`) backend + React 19 / TypeScript / Vite frontend.
> Identify the layer(s) touched (HTTP / Feature / Domain-Data / Infra) and the
> existing references that ground this plan.

- **Backend layer(s) touched:** [HTTP / feature module / db / validation / storage / deletion / migrations / ...]
- **Frontend area(s):** [`frontend/src/api/*`, `frontend/src/pages/*`]
- **Relevant references:** [`docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md),
  [`docs/BACKEND_MODULES.md`](../../docs/BACKEND_MODULES.md),
  [`docs/Data_Flow.md`](../../docs/Data_Flow.md),
  [`docs/Code_Structure.md`](../../docs/Code_Structure.md)

## Architecture & Approach

> Describe the design: how the request flows through the layers, the chosen
> approach and why, and how it fits the existing patterns. Keep it concrete but
> at design altitude (not line-by-line code). Note the thin-handler contract:
> `handler.py` parses/routes/serializes; the feature module owns logic + SQL.

[Approach here.]

## Data Model Changes

> Tables, columns, indexes, and constraints to add or alter — each delivered as
> a **new** `migrations/NNN_*.sql` (Article V; never edit an applied file).
> Specify foreign keys and `ON DELETE` behavior, and if a new deletable entity
> is introduced, state how it satisfies the data-safety policy (Article IV) and
> note its row in `docs/Data_Flow.md`. Cross-link a `data-model.md` if used.

- **Migration:** `migrations/[NNN]_[description].sql`
- **New/changed tables:** [table → columns, FKs, `ON DELETE` rule]
- **Indexes:** [index → columns, purpose]
- **Data-safety note:** [cascade behavior; archive/audit handling for deletes]
- See [`./data-model.md`](./data-model.md) [if present].

## API Contracts

> Summarize the endpoints (method + path + purpose + auth role). Full
> request/response shapes live in [`./contracts/`](./contracts/). Note the
> exception→status mapping each endpoint relies on (Article VI).

| Method | Path | Purpose | Min role (if auth on) |
|--------|------|---------|-----------------------|
| GET | `/api/[...]` | [list/detail] | viewer |
| POST | `/api/[...]` | [create] | operator |
| DELETE | `/api/[...]` | [delete — note tier] | admin |

- Detailed contracts: [`./contracts/`](./contracts/)

## Affected Modules & Files

> List the concrete files to add or change, by layer. Keep within the
> one-feature-one-module rule (Article III).

- **Feature:** `app/features/[name].py` — [handlers + service logic + SQL]
- **HTTP:** `app/http/handler.py` — [add dispatch entries only, no logic]
- **Migration:** `migrations/[NNN]_[description].sql`
- **Domain/Infra:** [`app/deletion.py` / `app/validation.py` / ... if touched]
- **Frontend:** `frontend/src/api/[name].ts`, `frontend/src/pages/[Page].tsx`
- **Tests:** `tests/smoke_test.py` — [new coverage]

## Sequence / Flow

> Walk the main path(s) step by step through the layers — request in, validation,
> SQL, file handling, response out. Include the delete preview/confirm flow if
> the feature deletes anything with children or files (Strong tier).

1. [Request arrives at `route()` → dispatch → feature handler.]
2. [Validation via `validation.*`; raise `ValueError`/`LookupError`/`ConflictError`.]
3. [Parameterized SQL via `connect_db()`.]
4. [File handling via `storage.py` / archive / `deletion.py` if applicable.]
5. [Serialize JSON response.]

## Risks & Trade-offs

> Surface the hard parts: migration/back-compat risk, file/disk concerns,
> performance at lab data volume, anything intentionally deferred and why.

- [Risk / trade-off and mitigation.]

## Testing Approach

> How correctness is proven. The smoke test is the green-light oracle
> (Article IX): state the baseline run, the new cases added, and any manual
> verification steps. List the acceptance criteria from the spec that each
> test covers.

- Baseline: run `python3 tests/smoke_test.py` before changes.
- New coverage: [endpoints/cases added to the smoke test] — covers [AC-00x].
- Manual checks: [if any].
