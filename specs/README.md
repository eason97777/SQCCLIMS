# Specs — Spec-Driven Development for SQCCLIMS

This directory holds the **forward-looking** specifications for SQCCLIMS,
following [GitHub Spec Kit](https://github.com/github/spec-kit) conventions. Each
feature is specified, planned, broken into tasks, and only then implemented —
the **Spec → Plan → Tasks → Implement** flow.

Everything here is governed by the project
[**constitution**](../.specify/memory/constitution.md). Read it first: every
spec, plan, and task list MUST comply with its Articles, and every `plan.md`
carries a Constitution Check that proves it.

## The SDD workflow

```
  spec.md   ──►   plan.md   ──►   tasks.md   ──►   implement
  WHAT/WHY        HOW             ordered work     code + smoke test green
  (no code)       (constitution   (dependency
                   check)          order)
```

1. **Spec** (`spec.md`) — define **WHAT** the feature does and **WHY**. No
   implementation details: no modules, tables, endpoints, or libraries. Captures
   user stories, functional/non-functional requirements (FR-00x / NFR-00x), key
   entities (conceptually), out-of-scope, open questions
   (`[NEEDS CLARIFICATION]`), and acceptance criteria.
2. **Plan** (`plan.md`) — define **HOW**. Starts with the **Constitution Check**,
   then technical context, architecture, data-model/migration changes, API
   contracts, affected modules, sequence, risks, and testing approach.
3. **Tasks** (`tasks.md`) — an ordered, checkboxed task list derived from the
   plan, grouped by phase (Data → Feature → HTTP → Frontend → Tests → Docs),
   each task referencing the FR it satisfies and its dependencies.
4. **Implement** — execute tasks in dependency order. A change is done only when
   `python3 tests/smoke_test.py` is green (constitution Article IX).

## Directory layout

```
.specify/
  memory/
    constitution.md        # non-negotiable principles + governance (start here)
  templates/
    spec-template.md       # clone for each new spec.md
    plan-template.md       # clone for each new plan.md
    tasks-template.md      # clone for each new tasks.md

specs/
  README.md                # this file
  001-samples/             # one directory per feature (zero-padded number + slug)
    spec.md
    plan.md
    tasks.md
    data-model.md          # optional: schema/migration detail
    contracts/             # optional: per-endpoint request/response contracts
  002-raw-data-parsing/
    ...
```

## Feature numbering

Feature directories are named `NNN-slug`:

- **`NNN`** — a zero-padded, sequential number (`001`, `002`, `003`, …), assigned
  in creation order. It does not change once assigned.
- **`slug`** — a short, hyphenated, lowercase name (`samples`,
  `raw-data-parsing`).

To start a new feature: pick the next number, create `specs/NNN-slug/`, and copy
the three templates from `.specify/templates/` into it as `spec.md`, `plan.md`,
and `tasks.md`.

## Worked exemplars

Two features exist as worked examples to **clone and learn from** — they show the
expected depth and how the sections map onto SQCCLIMS:

- [`001-samples/`](./001-samples/) — the root sample entity (CRUD, UID
  generation, identity validation).
- [`002-raw-data-parsing/`](./002-raw-data-parsing/) — raw-data upload and the
  parse pipeline into normalized parsed records.

When in doubt about format or altitude, match these.

## Relationship to `docs/`

There are two documentation layers, and they do not overlap:

| Layer | Question it answers | Audience |
|-------|---------------------|----------|
| **`specs/`** (this dir) | *What/why/how* for a feature, **forward-looking** | whoever is building the next change |
| [`docs/`](../docs/) | *How the system is built today*, **as-built reference** | anyone reading the current system |

Specs **cross-link** to `docs/` rather than duplicating it. The key references:

- [`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md) — layers, request lifecycle,
  data model, migration system.
- [`docs/BACKEND_MODULES.md`](../docs/BACKEND_MODULES.md) — per-module reference.
- [`docs/CODE_PRINCIPLES.md`](../docs/CODE_PRINCIPLES.md) — coding conventions
  (the constitution restates these as binding principles).
- [`docs/Data_Flow.md`](../docs/Data_Flow.md) — data flow and the authoritative
  deletion / data-safety policy.
- [`docs/Code_Structure.md`](../docs/Code_Structure.md),
  [`docs/Development_Guide.md`](../docs/Development_Guide.md),
  [`docs/GLOSSARY.md`](../docs/GLOSSARY.md) — structure, workflow, vocabulary.

When a spec finishes implementation, update the relevant `docs/` files so the
as-built layer stays accurate (Phase 6 of the tasks template).

---

**Start here:** [`.specify/memory/constitution.md`](../.specify/memory/constitution.md)
