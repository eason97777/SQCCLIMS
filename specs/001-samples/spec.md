# Feature Specification: Samples

> This is an **as-built / retroactive** specification. It documents the
> *already implemented* Samples feature of SQCCLIMS in Spec Kit format so it can
> serve as a worked exemplar. It describes **WHAT** the feature does and **WHY**
> it exists — never **HOW** it is built (that lives in [`./plan.md`](./plan.md)).
>
> This spec complies with the project
> [constitution](../../.specify/memory/constitution.md); the matching
> [`./plan.md`](./plan.md) proves that compliance article-by-article.

## Metadata

| Field | Value |
|-------|-------|
| Feature name | Samples |
| Feature number | 001 |
| Status | Implemented |
| Created | 2026-06-16 |
| Author | Genevieve Cote |

## Summary

A **sample** is the root record of all laboratory work in SQCCLIMS: every
measurement, raw-data upload, parsed record, process record, MES route, and
characterization or performance file ultimately belongs to one sample. This
feature lets lab staff register a wafer/semiconductor sample, find it later,
keep its registration data accurate, and — when a sample's entire body of work
must be removed — delete it together with all of its child data in one safe,
recoverable, auditable operation. Because every other feature hangs off the
sample, getting sample identity and sample deletion right is foundational to the
whole system.

## User Scenarios / User Stories

- **US-1.** As an **operator**, I want to register a new sample with its project
  number, name, process type, and sequence so that all subsequent test data can
  be attached to a single, identifiable record.
- **US-2.** As a **viewer**, I want to search and filter the sample list (by free
  text and by status) so that I can quickly locate the sample I need to inspect.
- **US-3.** As an **operator**, I want to correct or update a sample's
  registration details so that the record stays accurate over its lifecycle,
  without the system letting me create an inconsistent or duplicate identity.
- **US-4.** As an **operator/admin**, before deleting a sample I want to see
  exactly how much child data (test data, raw files, parsed records,
  characterization files, performance datasets, etc.) would be removed, so that
  I understand the blast radius before I confirm.
- **US-5.** As an **admin**, I want to delete a sample and have *all* of its
  child data and files removed in one operation that is recoverable, so that
  obsolete work can be cleared without leaving orphaned rows or files behind.
- **US-6.** As a **viewer**, I want to open a sample's MES route and its
  characterization tree so that I can review its process flow and accumulated
  files in context.

> Strong-tier delete flow (US-4 → US-5):
>
> 1. The operator selects a sample and requests a **deletion preview**.
> 2. The system reports the counts of every category of child data and the total
>    number of files that would be removed — without deleting anything.
> 3. The operator confirms.
> 4. The system takes a recoverable checkpoint, removes the sample and every
>    descendant row, snapshots the deleted sample for audit, and removes the
>    associated files from the live store.

## Functional Requirements

- **FR-001.** The system MUST allow creating a sample from a project number
  (`sample_code`), sample name, process type (`category`), sample sequence
  (`batch`), and status, plus optional owner, received date, and notes. *(US-1)*
- **FR-002.** On creation the system MUST assign each sample a unique,
  server-generated identifier of the form `SMP-YYYY-NNNNNN` (year + a
  zero-padded sequence) that the client never supplies. *(US-1)*
- **FR-003.** The system MUST derive a human-readable **display code** for each
  sample from its project number, name, process type, and sequence, and MUST
  guarantee that display code is unique across all samples. *(US-1, US-3)*
- **FR-004.** The system MUST reject a create or update whose resulting display
  code duplicates an existing sample's, with a clear message naming the fields
  to change. *(US-1, US-3)*
- **FR-005.** The system MUST require project number, sample name, process type,
  sample sequence, and status to be non-empty, and MUST reject input containing
  suspected garbled/mojibake characters or a malformed sample sequence. *(US-1, US-3)*
- **FR-006.** The system MUST enforce identity consistency: all samples sharing a
  project number MUST share the same sample name, and all samples sharing a
  project number and process type MUST share the same sample name. *(US-1, US-3)*
- **FR-007.** The system MUST return a list of samples, each enriched with its
  measurement count and most-recent measurement time, ordered most-recent-first. *(US-2)*
- **FR-008.** The system MUST support filtering the list by a free-text query
  (matching identifier, display code, project number, name, process type,
  sequence, or owner) and by exact status. *(US-2)*
- **FR-009.** The system MUST allow updating a sample's registration fields while
  preserving its server-generated identifier, re-validating identity and
  uniqueness on every update. *(US-3)*
- **FR-010.** The system MUST provide a non-destructive **deletion preview** that
  reports, per child category, how many rows and how many files would be removed
  if the sample were deleted. *(US-4)*
- **FR-011.** The system MUST delete a sample together with **all** of its child
  data — test data, process records, raw data and raw-data files, parsed data
  and parsed records, characterization collections and files, performance
  datasets and files, MES routes, and processing jobs/results — leaving no
  orphaned rows or files. *(US-5)*
- **FR-012.** The system MUST treat sample deletion as a destructive Strong-tier
  operation: a recoverable checkpoint MUST precede the delete, and the deleted
  sample MUST be snapshotted for audit. *(US-5)*
- **FR-013.** The system MUST expose a sample's latest MES route and its
  characterization tree (collections and files, optionally filtered by text). *(US-6)*
- **FR-014.** The system MUST return a clear, typed error when an operation
  targets a sample that does not exist. *(US-3, US-4, US-5)*

## Non-Functional Requirements

- **NFR-001.** Sample deletion MUST be preceded by a recoverable checkpoint and
  MUST snapshot the deleted record before destruction; child file cleanup MUST be
  centralized and confined to the managed live store, per constitution
  **Article IV** (Data Safety). The append-only archive retains immutable copies
  so live-file removal is recoverable.
- **NFR-002.** The deletion preview MUST be a true read-only operation — it MUST
  NOT modify any data — so it can be shown before the user confirms (Strong-tier
  preview-then-confirm gate, **Article IV**).
- **NFR-003.** The feature MUST function with authentication disabled (the
  default) and, when auth is enabled, MUST follow
  `GET ≤ operator-write ≤ admin-delete`: reads need viewer, create/update need
  operator, delete needs admin (constitution **Article XI**).
- **NFR-004.** All errors MUST be surfaced through the project's
  exception→status convention (invalid input → 400, missing sample → 404), never
  by hand-built status codes (**Article VI**).
- **NFR-005.** All sample queries MUST be parameterized; no user input is ever
  formatted into SQL (**Article VII**).
- **NFR-006.** The list endpoint MUST remain responsive at expected
  single-workstation lab data volumes; pagination is intentionally deferred
  (**Article X**).
- **NFR-007.** The samples endpoints MUST be exercised by the smoke test, which
  is the green-light oracle for the feature (**Article IX**).

## Key Entities

> Conceptual only; aligns with [`docs/GLOSSARY.md`](../../docs/GLOSSARY.md) and
> the data model in [`docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md). Actual
> columns/relationships are in [`./data-model.md`](./data-model.md).

- **Sample** — the root entity. Represents one registered wafer/semiconductor
  sample under test. Its identity is the server-generated **sample UID**
  (`SMP-YYYY-NNNNNN`) and the unique **display code** derived from project
  number + name + process type + sequence. Carries registration metadata
  (project number, name, process type, sequence, owner, status, received date,
  notes) and ownership of all child work.
- **Test data** — individual measurements belonging to a sample.
- **Process record** — a recorded process/MES stage entry for a sample.
- **Raw data & raw-data files** — an uploaded dataset and its backing files,
  owned by a sample.
- **Parsed data & parsed records** — structured results derived from raw data,
  owned by a sample.
- **Characterization collection & files** — grouped characterization artifacts
  and their files for a sample.
- **Performance dataset & files** — performance test artifacts for a sample.
- **MES sample route** — the manufacturing-execution route instance for a sample.
- **Processing job / processing result** — generated visualization/processing
  artifacts referencing a sample (route-detached on delete, but cleaned up by the
  sample's own delete path so nothing orphans).

## Out of Scope

- A dedicated single-sample **detail** read endpoint (`GET /api/samples/{id}`).
  Detail data is currently obtained from the list response; this is a known,
  intentional gap (see the frontend `samplesApi` TODO).
- **Soft-delete / restore from the UI.** Deletion is hard (with archive + audit
  recovery), not a reversible soft-delete. Soft-delete is deliberately deferred
  per **Article X**.
- **Pagination / server-side sorting** of the sample list beyond the fixed
  most-recent-first ordering. Deferred per **Article X**.
- Creating or editing child entities (test data, raw data, MES routes,
  characterization, performance) — those belong to their own features. This
  feature only *owns sample identity and the sample-rooted cascade delete*.

## Open Questions / Clarifications

- None outstanding (as-built). All previously open points are resolved by the
  existing implementation:
  - UID format → `SMP-YYYY-NNNNNN`, year-scoped, gap-tolerant max-sequence + 1.
  - Display-code uniqueness → enforced both by validation and a DB unique
    constraint.
  - Identity consistency rules → enforced across project number and process
    type.
  - The missing `GET /api/samples/{id}` is documented under **Out of Scope**.

## Acceptance Criteria

> Given/When/Then, mapped to FRs. These are expressible in / covered by the smoke
> test (constitution **Article IX**).

- **AC-001.** Given valid sample fields, when an operator creates a sample, then
  the response includes a `sample_uid` matching `SMP-YYYY-NNNNNN` and a unique
  `sample_display_code`. *(FR-001, FR-002, FR-003)*
- **AC-002.** Given an existing sample, when a create/update would produce a
  duplicate display code, then the request is rejected with a 400 and a message
  naming the fields to change. *(FR-004)*
- **AC-003.** Given a payload missing a required field or containing garbled
  text, when a create/update is attempted, then it is rejected with a 400. *(FR-005)*
- **AC-004.** Given several samples sharing a project number, when one is created
  or updated with a different sample name, then the request is rejected with a
  400. *(FR-006)*
- **AC-005.** Given samples exist, when a viewer lists with a query and/or status
  filter, then only matching samples are returned, each with `data_count` and
  `last_measured_at`, ordered most-recent-first. *(FR-007, FR-008)*
- **AC-006.** Given a sample with child data, when a deletion preview is
  requested, then per-category counts and `files_total` are returned and no data
  is modified. *(FR-010, NFR-002)*
- **AC-007.** Given a sample with child data, when an admin deletes it, then the
  sample and all descendant rows are gone, the associated live files are removed,
  a recoverable checkpoint was taken, and the sample is snapshotted in the
  deletion audit. *(FR-011, FR-012, NFR-001)*
- **AC-008.** Given a non-existent sample id, when any read/update/delete/preview
  targets it, then the system responds 404. *(FR-014, NFR-004)*
- **AC-009.** The smoke test MUST cover create, list (with filters), update,
  delete-preview, and cascade delete of a sample. *(Article IX)*
