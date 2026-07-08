# SQCCLIMS — AI agent entrypoint

**SQCCLIMS** = a stdlib-only Python LIMS backend (`http.server` + `sqlite3`, no web framework/ORM) plus a React/TypeScript frontend. A single-workstation lab tool for semiconductor sample quality control.

## STOP — read before changing code

Any feature or change MUST follow the **Spec-Driven Development (SDD)** flow. Do not start editing code from a cold prompt.

1. **Read the rules first:** [`.specify/memory/constitution.md`](.specify/memory/constitution.md) — the 11 Articles. They are non-negotiable.
2. **Follow the flow:** [`specs/README.md`](specs/README.md) — Spec → Plan → Tasks → Implement.

Every `spec.md`, `plan.md`, and `tasks.md` MUST comply with the constitution, and every `plan.md` carries a Constitution Check table proving it.

## Start a new feature (recipe)

1. **Find the next number:** list `specs/` and take the next zero-padded `NNN` (e.g. after `002-…` comes `003`).
2. **Create the dir and clone the three templates:**
   ```sh
   mkdir specs/NNN-slug
   cp .specify/templates/spec-template.md  specs/NNN-slug/spec.md
   cp .specify/templates/plan-template.md  specs/NNN-slug/plan.md
   cp .specify/templates/tasks-template.md specs/NNN-slug/tasks.md
   ```
3. **Fill in order:** `spec.md` (WHAT/WHY) → `plan.md` (HOW; complete the Constitution Check table) → `tasks.md` → implement.
4. **Put detail in the right place:** API contracts in `specs/NNN-slug/contracts/`, schema/migration detail in `specs/NNN-slug/data-model.md`.
5. **Match the worked exemplar:** [`specs/001-samples/`](specs/001-samples/).

## Development workflow (git)

We use **GitHub Flow**. `main` is always deployable — **never commit to or push `main` directly.**

- **Branch first.** Before starting any work, cut a short-lived branch off `main`: `feat/<slug>`, `fix/<slug>`, or `chore/<slug>`.
- **Atomic, conventional commits.** Keep each commit small and self-contained. Use Conventional Commits: `feat:`, `fix:`, `refactor:`, `chore:`, `docs:` (scopes allowed, e.g. `feat(samples):`).
- **Confirm before committing.** Stage the change, then show the human the **diff** and the **proposed commit message**, and wait for explicit confirmation before running `git commit`. Never commit unprompted.
- **Push only when green + complete for scope.** A branch is ready to push when it is self-consistent, its gates pass (build + smoke, no *new* lint errors), and it is complete for its stated scope. Use the PR for *judgment* — design choices and trade-offs — never to finish mechanical or half-done work. If a change is merely unfinished, finish it first. **One owner per branch.**
- **Humans own PRs.** Prepare the branch and commits and surface the diff; a human opens and approves the Pull Request. **Do not open or merge a PR unless explicitly asked.**
- **Review comments are the next task.** When given PR review feedback, treat each comment as a work item — address every one, then re-surface the updated diff.
- **Never rewrite history without explicit confirmation.** No `push --force`, `reset --hard`, rebase, or other history-rewriting command unless the human asks for it in that moment.

The full loop (branch → commit → PR → review → squash-merge) is documented for humans in [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Green light

```sh
python3 tests/smoke_test.py
```

This MUST pass **before and after** any change — it is the authoritative go/no-go (constitution Article IX). When you add or change an endpoint, extend the smoke test to cover it.

## The "don't" list (distilled from the constitution)

- **No third-party imports outside `parsers/`** — the core (`server.py`, `app/**`) is stdlib-only. ([Article I](.specify/memory/constitution.md))
- **Keep `handler.py` thin; respect one-way layering (Infra/Domain ← Features ← HTTP); no import cycles.** ([Articles II, III](.specify/memory/constitution.md))
- **Never edit an applied migration** — add a new forward-only `migrations/NNN_*.sql` instead. ([Article V](.specify/memory/constitution.md))
- **No destructive op without a backup + `deletion_audit` snapshot.** ([Article IV](.specify/memory/constitution.md))
- **Parameterized SQL only** — never string-format user input into SQL. ([Article VII](.specify/memory/constitution.md))
- **Raise `ValueError` / `LookupError` / `ConflictError`** — never hand-build HTTP status codes. ([Article VI](.specify/memory/constitution.md))
- **Read `config.<NAME>` at call time**, not via `from app.config import …` at import. ([Article VIII](.specify/memory/constitution.md))
- **Auth is off-by-default and all-or-nothing** — a complete no-op or a complete gate, never half-built. ([Article XI](.specify/memory/constitution.md))
- **Simplest solution that works** — no speculative abstraction; deferred features stay deferred. ([Article X](.specify/memory/constitution.md))

## Human docs

- [`README.md`](README.md) — onboarding / quickstart / project one-liner.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — dev workflow (adding endpoints, migrations).
- [`docs/`](docs/) — the **as-built** technical reference (how the system is built today).
- [`specs/`](specs/) — the per-feature **SDD** layer, governed by the constitution.
