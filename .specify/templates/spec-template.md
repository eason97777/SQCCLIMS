# Feature Specification: [FEATURE NAME]

> **This is a template — no implementation details.** A spec describes **WHAT**
> the feature does and **WHY** it exists. It never describes **HOW** it is built
> (no modules, tables, endpoints, libraries, or code). The HOW belongs in
> `plan.md`. Replace every bracketed prompt with real content and delete the
> guidance lines (`>`), or keep them if helpful to reviewers.
>
> This spec MUST comply with the project
> [constitution](../../.specify/memory/constitution.md). The matching
> `plan.md` will prove that compliance; the spec's job is to stay free of
> implementation so the plan has room to choose the HOW.

## Metadata

| Field | Value |
|-------|-------|
| Feature name | [human-readable name] |
| Feature number | [NNN, zero-padded — matches the `specs/NNN-slug/` directory] |
| Status | Draft / In Review / Approved / Implemented |
| Created | [YYYY-MM-DD] |
| Author | [name] |

## Summary

> One short paragraph: what this feature is and the problem it solves, in plain
> language a lab user or stakeholder would understand. No jargon beyond domain
> terms (sample, raw data, parsed record, MES route, etc. — see
> [`docs/GLOSSARY.md`](../../docs/GLOSSARY.md)).

[Summary here.]

## User Scenarios / User Stories

> Capture the concrete workflows. Use the role-based form. Roles map to the
> RBAC vocabulary where relevant (viewer / operator / admin).

- **US-1.** As a [role], I want [capability] so that [outcome].
- **US-2.** As a [role], I want [capability] so that [outcome].
- **US-3.** As a [role], I want [capability] so that [outcome].

> For complex flows, add a short narrative or a step list:
>
> 1. The operator does X.
> 2. The system responds with Y.
> 3. ...

## Functional Requirements

> Numbered, testable statements of what the system MUST do. One requirement per
> line. Use "MUST" / "MUST NOT" / "SHOULD". Each should be verifiable by an
> acceptance criterion below. Reference user stories where useful.

- **FR-001.** The system MUST [requirement]. *(US-1)*
- **FR-002.** The system MUST [requirement].
- **FR-003.** The system MUST NOT [prohibited behavior].
- **FR-004.** When [condition], the system MUST [behavior].

## Non-Functional Requirements

> Qualities and constraints rather than behaviors: data-safety expectations,
> recoverability, performance envelope, auth/RBAC posture, offline/single-
> workstation operation, packaging. Tie to constitution Articles where they
> apply (e.g. "deletes follow the Strong-tier policy — Article IV").

- **NFR-001.** [e.g. Any destructive action MUST be preceded by a recoverable
  checkpoint, per constitution Article IV.]
- **NFR-002.** [e.g. The feature MUST function with auth disabled (default) and,
  when auth is enabled, follow `GET ≤ operator-write ≤ admin-delete`.]
- **NFR-003.** [e.g. List responses MUST remain responsive at the expected lab
  data volume.]

## Key Entities

> Describe the data **conceptually** — what each entity represents and its
> important relationships. NO schema, column types, or SQL. Naming should align
> with [`docs/GLOSSARY.md`](../../docs/GLOSSARY.md) and the existing data model
> in [`docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md).

- **[Entity]** — what it represents; its parent/child relationships; its
  identity (what makes one instance distinct).
- **[Entity]** — ...

## Out of Scope

> Explicitly list what this feature does NOT cover, to prevent scope creep and
> set reviewer expectations. Call out anything intentionally deferred (e.g.
> "soft-delete is out of scope — see Article X / docs deferred list").

- [Out-of-scope item.]
- [Out-of-scope item.]

## Open Questions / Clarifications

> Track unknowns. Mark each unresolved point with a `[NEEDS CLARIFICATION]`
> tag so it is greppable. A spec SHOULD NOT move to **Approved** while
> `[NEEDS CLARIFICATION]` markers remain.

- [NEEDS CLARIFICATION] [question].
- [NEEDS CLARIFICATION] [question].

## Acceptance Criteria

> Concrete, checkable conditions that prove the feature is done and correct.
> Prefer Given/When/Then. Each criterion should map back to one or more FRs and
> should be expressible in the smoke test (constitution Article IX).

- **AC-001.** Given [context], when [action], then [observable result]. *(FR-001)*
- **AC-002.** Given [context], when [action], then [observable result]. *(FR-002)*
- **AC-003.** [The smoke test MUST cover the new/changed endpoints.] *(Article IX)*
