# Tasks: [FEATURE NAME]

> Tasks are **derived from [`./plan.md`](./plan.md)** (which is derived from
> [`./spec.md`](./spec.md)). Execute them **in dependency order** — later phases
> assume earlier ones are done. Each task references the functional requirement
> (FR-00x) it satisfies and notes any task it depends on. Check a box only when
> the task is complete *and* the smoke test is still green
> (constitution Article IX).
>
> Numbering is sequential `T001`, `T002`, … across all phases. Mark tasks that
> can run in parallel with `[P]`. Keep the standard phase order below; add or
> remove phases only if the feature genuinely needs it.

## Phase 1 — Data Layer (migrations & schema)

> New/changed tables, columns, indexes via a **new** `migrations/NNN_*.sql`
> (Article V — never edit an applied migration). Foreign keys and `ON DELETE`
> rules per the data-safety policy (Article IV).

- [ ] T001 Write `migrations/[NNN]_[description].sql` with [tables/columns/FKs/indexes]. *(FR-00x)*
- [ ] T002 Apply migrations locally and confirm `schema_migrations` records the new file with a checksum. *(depends on T001)*
- [ ] T003 If a new deletable entity is introduced, add its row to the per-entity table in [`docs/Data_Flow.md`](../../docs/Data_Flow.md) and define its cascade/archive/audit handling. *(FR-00x, Article IV)*

## Phase 2 — Feature Module (service logic + SQL)

> One module under `app/features/` owns handlers, validation, and parameterized
> SQL (Articles III, VII). Errors via the exception convention (Article VI).

- [ ] T004 Create/extend `app/features/[name].py` with the feature functions. *(FR-00x, depends on T002)*
- [ ] T005 Add input validation via `validation.*`; raise `ValueError` / `LookupError` / `ConflictError` appropriately. *(FR-00x, depends on T004)*
- [ ] T006 Implement file handling through `storage.py` / archive / `deletion.py` if the feature stores or deletes files. *(FR-00x, depends on T004)*
- [ ] T007 [P] Read runtime paths via `config.<NAME>` at call time, not at import (Article VIII). *(depends on T004)*

## Phase 3 — HTTP Routes (thin handler)

> Add dispatch entries only — no business logic in `handler.py` (Articles II, III).

- [ ] T008 Register routes in `app/http/handler.py` dispatch table mapping to the feature functions. *(FR-00x, depends on T004)*
- [ ] T009 If auth is in scope, confirm `GET ≤ operator-write ≤ admin-delete` enforcement and no-op-when-disabled behavior (Article XI). *(depends on T008)*

## Phase 4 — Frontend

> API wrapper + page/component, matching existing structure under `frontend/src/`.

- [ ] T010 Add the API wrapper in `frontend/src/api/[name].ts`. *(FR-00x, depends on T008)*
- [ ] T011 [P] Build/extend the page or component in `frontend/src/pages/[Page].tsx`. *(FR-00x, depends on T010)*
- [ ] T012 [P] For Strong-tier deletes, wire the cascade-preview dialog before confirming (Article IV). *(depends on T010)*

## Phase 5 — Tests

> The smoke test is the green-light oracle (Article IX).

- [ ] T013 Capture a baseline: run `python3 tests/smoke_test.py` before changes (recorded earlier in the plan). *(Article IX)*
- [ ] T014 Extend `tests/smoke_test.py` to cover the new/changed endpoints and acceptance criteria. *(AC-00x, depends on T008)*
- [ ] T015 Run the full smoke test and confirm it is green. *(depends on T014)*

## Phase 6 — Docs

> Update the as-built reference layer so `docs/` stays accurate.

- [ ] T016 Update [`docs/BACKEND_MODULES.md`](../../docs/BACKEND_MODULES.md) (and [`docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md) if the data model changed) to reflect the new module/endpoints. *(depends on T015)*
- [ ] T017 Update the parent [`./spec.md`](./spec.md) status to **Implemented** and resolve any remaining `[NEEDS CLARIFICATION]`. *(depends on T015)*
