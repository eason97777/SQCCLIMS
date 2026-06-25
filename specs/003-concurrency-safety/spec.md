# Feature Specification: Concurrent-Writer Safety

> This spec describes **WHAT** the feature does and **WHY** it exists — never
> **HOW** it is built (that lives in [`./plan.md`](./plan.md)). It complies with
> the project [constitution](../../.specify/memory/constitution.md); the matching
> [`./plan.md`](./plan.md) proves that compliance article-by-article.

## Metadata

| Field | Value |
|-------|-------|
| Feature name | Concurrent-Writer Safety |
| Feature number | 003 |
| Status | Implemented |
| Created | 2026-06-17 |
| Author | Genevieve Cote |

## Summary

The SQCCLIMS server handles each incoming request on its own thread, so two lab
staff can hit a write endpoint (for example, registering a sample) at the very
same moment. Today that overlap is unsafe: the second writer can be bounced with
a confusing **"internal server error" (HTTP 500)** instead of waiting its turn,
and two simultaneous sample registrations can quietly mint **the same business
identifier (`SMP-YYYY-NNNNNN`)** for two different samples — a silent data-integrity
defect that is hard to notice and harder to undo. This feature makes concurrent
writes **safe and honest**: contended writers wait briefly and then succeed,
sample identifiers stay unique even under simultaneous creation, and when a write
genuinely cannot proceed the system returns a truthful, typed status code
(conflict or temporarily-unavailable) rather than a generic server error. No new
capability is added for users; existing capabilities are made correct under
concurrency. This is a data-safety hardening (constitution **Article IV**) built
entirely on the standard library (**Article I**).

## User Scenarios / User Stories

- **US-1.** As an **operator**, when a colleague and I save new samples at the
  same moment, I want both saves to succeed and each sample to receive a
  **distinct** identifier, so that no two samples ever share a UID and neither of
  us silently loses or corrupts the other's record.
- **US-2.** As an **operator**, when the database is momentarily busy because
  another write is in flight, I want my save to **wait a short while and then
  complete**, rather than failing instantly with an alarming error, so that
  normal concurrent use does not look like an outage.
- **US-3.** As an **operator/admin**, when a write truly cannot be completed — a
  real conflict, or sustained contention beyond the wait window — I want a
  **clear, honest result** (a conflict is reported as a conflict; a temporary
  busy state is reported as temporarily-unavailable), so that I and any
  automation can tell "retry shortly" apart from "your input was wrong" apart from
  "the server is broken."
- **US-4.** As a **maintainer**, I want a repeatable test that fires many
  simultaneous sample creations and proves they all succeed with unique
  identifiers and **zero** spurious server errors, so that this guarantee does
  not silently regress.

> Concurrent-create flow (US-1 → US-2):
>
> 1. Two operators submit "create sample" requests within milliseconds of each
>    other; the server processes them on separate threads.
> 2. One write proceeds; the other finds the database briefly locked and **waits**
>    within a bounded window instead of erroring.
> 3. Both writes commit. Each resulting sample carries a **unique** identifier;
>    no duplicate UID is created.
> 4. In the rare event the wait window is exhausted, the waiting request returns a
>    truthful temporarily-unavailable result that signals "retry shortly," not a
>    generic 500.

## Functional Requirements

- **FR-001.** When two or more write requests contend for the database at the
  same time, the system MUST cause the later writer(s) to **wait** within a
  bounded time window for the lock to clear and then proceed, rather than failing
  immediately. *(US-2)*
- **FR-002.** The system MUST guarantee that every sample receives a **unique**
  business identifier (`SMP-YYYY-NNNNNN`), even when multiple samples are created
  simultaneously; it MUST NOT allow two persisted samples to share an identifier. *(US-1)*
- **FR-003.** When concurrent creation would otherwise mint a duplicate
  identifier, the system MUST resolve the collision (by assigning the next
  available identifier) so that both creations still succeed with distinct
  identifiers. *(US-1)*
- **FR-004.** When a write fails because it would violate a uniqueness/integrity
  rule that cannot be auto-resolved, the system MUST report it as a **conflict**
  (HTTP 409), not as an internal server error (HTTP 500). *(US-3)*
- **FR-005.** When a write cannot proceed because the database remains locked
  beyond the bounded wait window, the system MUST report it as
  **temporarily-unavailable** (HTTP 503), not as an internal server error
  (HTTP 500). *(US-3)*
- **FR-006.** The system MUST preserve all existing error semantics for
  non-concurrency failures: invalid input remains a 400, a missing entity remains
  a 404, and a domain conflict remains a 409. *(US-3)*
- **FR-007.** The system MUST NOT introduce any new runtime dependency; all
  concurrency safety MUST be achieved with the standard library and the existing
  database engine's own capabilities. *(NFR-002, Article I)*
- **FR-008.** Resolving identifier uniqueness MUST NOT corrupt or renumber any
  existing valid sample identifier; it only governs how *new* identifiers are
  assigned and how the uniqueness rule is enforced going forward. *(US-1)*
- **FR-009.** The system MUST handle any pre-existing duplicate identifiers in
  legacy data when enforcing the new uniqueness rule, per the resolved policy in
  **Open Questions**, so that enforcing uniqueness does not fail on dirty data. *(US-1)*

## Non-Functional Requirements

- **NFR-001.** This is a **data-safety** feature: it MUST NOT weaken any existing
  recoverability guarantee (startup snapshot, pre-strong-delete snapshot,
  deletion audit) and MUST strengthen integrity by making duplicate identifiers
  impossible to persist, per constitution **Article IV** (Data Safety).
- **NFR-002.** The feature MUST be implemented **stdlib-only** — using the
  database engine's built-in locking/wait facilities and the standard library —
  with **no new third-party runtime dependency** anywhere in the backend core,
  per constitution **Article I**.
- **NFR-003.** All errors MUST be surfaced through the project's
  exception→status convention (a single central mapping), never by hand-built
  status codes, per constitution **Article VI**.
- **NFR-004.** Any schema/constraint change MUST be delivered as a **new,
  forward-only, checksum-guarded migration** — never by editing an applied
  migration or the historical baseline, per constitution **Article V**.
- **NFR-005.** The chosen mechanism MUST be the **simplest** that meets the
  guarantee: it MUST prefer the database engine's native wait-for-lock behavior
  over a hand-rolled global write-lock or other speculative concurrency
  abstraction, per constitution **Article X** (Simplicity).
- **NFR-006.** The feature MUST function with authentication disabled (the
  default) and, when auth is enabled, MUST NOT change the existing
  `GET ≤ operator-write ≤ admin-delete` policy, per constitution **Article XI**.
- **NFR-007.** The concurrency guarantee MUST be exercised by the smoke test,
  which is the green-light oracle for the feature, per constitution **Article IX**.

## Key Entities

> Conceptual only; aligns with [`docs/GLOSSARY.md`](../../docs/GLOSSARY.md). Actual
> columns/constraints/indexes are in [`./data-model.md`](./data-model.md).

- **Sample identity (the sample UID)** — the server-generated business identifier
  of a sample, of the form `SMP-YYYY-NNNNNN` (year + zero-padded sequence). It is
  what one operator's sample must never share with another's. This feature makes
  that identifier **provably unique** at the data layer, not merely by convention.
  It is distinct from the sample's internal surrogate key and from its display
  code (which is already uniqueness-enforced).
- **A write operation** — any create/update/delete that mutates the database. Its
  important property here is its behavior **under contention**: it should wait,
  succeed, or fail honestly — never silently corrupt or surface a misleading
  error.

## Out of Scope

- **Multi-process / multi-host / networked-database concurrency.** SQCCLIMS runs
  as a single process on a single workstation against a local database; this
  feature addresses *in-process, multi-thread* writers only. Distributed
  concurrency is deliberately out of scope.
- **Optimistic concurrency / record versioning on updates** (e.g. "this record
  changed since you loaded it" detection on sample/edit). Lost-update protection
  for concurrent *edits of the same row* is **deferred** per **Article X**; this
  feature guarantees safe, honest, unique *creates* and honest error reporting,
  not full optimistic-locking on updates.
- **Unbounded retry / queueing of writes.** The wait window is bounded; beyond it
  the system reports temporarily-unavailable rather than queueing indefinitely.
- **Performance tuning / write throughput optimization** beyond removing the
  spurious-error and duplicate-identifier defects. No new caching, connection
  pooling, or batching is introduced.
- **Changing any user-facing capability or API surface.** No new endpoints; only
  the *behavior under concurrency* and the *status code on contention/conflict*
  change.

## Open Questions / Clarifications

> All clarifications are **resolved** below (required for **Approved** status).

- **Resolved — legacy duplicate identifiers.** Older databases may already
  contain duplicate sample UIDs created before this feature (the old generator
  was racy). **Policy:** the uniqueness-enforcing migration MUST first detect any
  pre-existing duplicate UIDs and **renumber the duplicates** — keeping the
  earliest-created row's UID untouched and reassigning each later colliding row a
  fresh, non-colliding UID within the same year series — so the uniqueness rule
  can be enforced without data loss and without failing on dirty data. The
  earliest valid identifier is never changed (**FR-008**); only true duplicates
  are reassigned. The migration MUST be idempotent under the forward-only,
  checksum-guarded migration policy (**Article V**).
- **Resolved — wait window length.** The bounded wait window is a fixed,
  conservative duration (on the order of a few seconds) chosen so that normal
  concurrent lab use never trips the temporarily-unavailable path, while a truly
  stuck writer still fails in bounded time rather than hanging. The exact value is
  a plan-level detail (see [`./plan.md`](./plan.md)).
- **Resolved — scope of honest error mapping.** The conflict (409) and
  temporarily-unavailable (503) mappings are **cross-cutting**: they apply to
  **all write endpoints**, because the underlying contention/integrity conditions
  can arise on any write. See [`./contracts/error-handling.md`](./contracts/error-handling.md).

## Acceptance Criteria

> Given/When/Then, mapped to FRs. These are expressible in / covered by the smoke
> test (constitution **Article IX**).

- **AC-001.** Given two operators, when each creates a different sample within the
  same instant, then both creations succeed (2xx) and the two resulting samples
  have **distinct** `sample_uid` values. *(FR-001, FR-002, FR-003)*
- **AC-002.** Given **N** simultaneous "create sample" requests (the smoke-test
  concurrency case), when they are fired together, then **all** succeed, the
  returned `sample_uid` values are **all distinct**, and **zero** responses are
  HTTP 500. *(FR-001, FR-002, FR-003, NFR-007)*
- **AC-003.** Given the database is briefly held by an in-flight write, when a
  second write arrives, then it **waits** within the bounded window and then
  completes successfully, rather than failing immediately. *(FR-001)*
- **AC-004.** Given a write that would violate a uniqueness/integrity rule which
  cannot be auto-resolved, when it is attempted, then the response is **409
  Conflict** (not 500), with a JSON `{"error": ...}` body. *(FR-004, FR-006)*
- **AC-005.** Given the database remains locked beyond the bounded wait window,
  when a write times out waiting, then the response is **503
  Service Unavailable** (not 500), with a JSON `{"error": ...}` body. *(FR-005)*
- **AC-006.** Given a database that already contains duplicate sample UIDs in
  legacy data, when the uniqueness migration runs at startup, then it completes
  successfully, the duplicates are resolved per the renumbering policy, the
  earliest valid identifier of each set is unchanged, and the uniqueness rule is
  thereafter enforced. *(FR-009, FR-008)*
- **AC-007.** Given non-concurrency failures, when they occur after this feature,
  then invalid input is still 400, a missing entity is still 404, and an existing
  domain conflict is still 409 — no existing error semantics regress. *(FR-006)*
- **AC-008.** The smoke test MUST include the concurrency case (AC-002) and
  continue to pass all existing cases. *(Article IX)*
