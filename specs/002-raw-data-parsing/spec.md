# Feature Specification: Raw Data Upload, Parsing & Visualization

> **Retroactive / as-built spec.** This documents a feature that is **already
> implemented** in SQCCLIMS, written in GitHub Spec Kit format to serve as a
> worked exemplar. It describes **WHAT** the feature does and **WHY**; the
> **HOW** lives in [`plan.md`](./plan.md). This spec complies with the project
> [constitution](../../.specify/memory/constitution.md).

## Metadata

| Field | Value |
|-------|-------|
| Feature name | Raw Data Upload, Parsing & Visualization |
| Feature number | 002 |
| Status | Implemented |
| Created | 2026-06-16 |
| Author | SQCCLIMS maintainers |

## Summary

A lab user attaches instrument output files to a wafer sample, turns those raw
files into clean, structured measurement records, and views the result as a
chart. The feature owns the full lifecycle of a *raw data record*: create the
record against a sample, upload one or more files to it, parse a supported file
into normalized per-point records plus a summary, browse and filter those
records, render a visualization (a wafer resistance heatmap or a CD/SEM violin
plot), download the original files or the generated charts, and safely delete a
record (or a single file) with a previewed cascade. Today two measurement
families are parsed end-to-end — wafer **resistance** matrices and **CD/SEM**
critical-dimension tables — while other raw-data types may still be stored and
downloaded as plain files. See [`docs/GLOSSARY.md`](../../docs/GLOSSARY.md) for
domain terms and [`docs/Data_Flow.md`](../../docs/Data_Flow.md) for the raw
upload → parsing → normalized records flow.

## User Scenarios / User Stories

- **US-1.** As an **operator**, I want to register a raw data record against a
  sample (naming it, choosing its data type, and recording instrument/operator
  metadata) so that instrument output is tracked under the correct sample with a
  stable, human-readable code.
- **US-2.** As an **operator**, I want to upload one or more measurement files to
  a raw data record so that the original instrument output is preserved and
  available for parsing and download.
- **US-3.** As an **operator**, I want to parse a raw data record so that its raw
  file becomes clean, structured per-point records plus a summary I can analyze,
  without re-typing anything by hand.
- **US-4.** As a **viewer**, I want to browse, page through, filter, and search
  the normalized records of a parsed dataset (by die, area, outlier/NA status,
  CD/SEM position fields, or free text) so that I can inspect specific
  measurement points.
- **US-5.** As an **operator**, I want to compute a resistance summary with my
  own cleaning limits and render a wafer heatmap, or render a CD/SEM violin
  plot, so that I can see distribution and uniformity visually.
- **US-6.** As a **viewer**, I want to download the original uploaded files and
  the generated charts so that I can share or archive them outside the system.
- **US-7.** As an **operator**, I want to preview exactly what will be removed
  before I delete a raw data record or a single file, and have that delete
  cascade cleanly, so that I never silently lose derived data and can recover if
  needed.

## Functional Requirements

> MUST-level requirements. Each references the user story it serves.

- **FR-001.** The system MUST let a user create a raw data record bound to an
  existing sample, capturing a record name, a data type, and optional source
  type, instrument, operator, measurement date, free-form metadata, and notes.
  *(US-1)*
- **FR-002.** On creation the system MUST reject an unknown or missing data type,
  derive the record's data category from its data type, and assign a unique,
  human-readable raw data code that encodes the sample, data type, and date.
  *(US-1)*
- **FR-003.** The system MUST let a user list raw data records and filter them by
  sample, data type, parser status, and record status, and search by code, name,
  sample identifiers, instrument, operator, or notes. *(US-1, US-4)*
- **FR-004.** The system MUST let a user retrieve a single raw data record with
  its attached files and counts of derived parsed datasets and processing jobs.
  *(US-1, US-4)*
- **FR-005.** The system MUST let a user upload one or more files to a raw data
  record, requiring at least one file, and MUST maintain the record's file count
  and total size as files are added. *(US-2)*
- **FR-006.** For every uploaded file the system MUST record its original name,
  size, type, and a content checksum, and MUST preserve an immutable copy of the
  file content for recoverability. *(US-2, NFR-002)*
- **FR-007.** The system MUST let a user parse a raw data record whose data type
  is supported, selecting an appropriate parseable file, and MUST reflect parse
  progress and outcome in the record's parser status (not parsed → parsing →
  parsed or parse failed). *(US-3)*
- **FR-008.** Parsing a resistance record MUST produce a normalized point record
  per matrix cell (carrying die, area, row/column position and headers, raw and
  cleaned value, and numeric value), and parsing a CD/SEM record MUST produce a
  normalized record per measurement (carrying row group, side, direction, die,
  dose, location, unit, and CD value). *(US-3)*
- **FR-009.** Each parse MUST produce a parsed dataset that records its parser,
  a summary, the record count, any plots, and any warnings or errors surfaced by
  the parser. *(US-3)*
- **FR-010.** When a parse finds no parseable file for the record's data type, or
  the file fails validation, the system MUST report a clear error and mark the
  record as parse failed without producing partial normalized records. *(US-3)*
- **FR-011.** The system MUST let a user list parsed datasets (filterable by raw
  data record, sample, and data type) and retrieve a single parsed dataset.
  *(US-4)*
- **FR-012.** The system MUST let a user page through a parsed dataset's
  normalized records and filter them by data type, die, area, outlier status,
  NA/empty status, CD/SEM position fields (row group, side, direction, dose,
  location), and a free-text query, returning total and page counts. *(US-4)*
- **FR-013.** The system MUST expose the distinct filterable values available
  within a parsed dataset (the option lists for die, area, the CD/SEM position
  fields, outlier, and NA status) so a user can build valid filters. *(US-4)*
- **FR-014.** For a resistance parsed dataset the system MUST compute a summary —
  per die, per area, and overall — honoring user-supplied cleaning limits (lower
  / upper) and a chosen metric, classifying each point as normal, outlier, or NA,
  and reporting counts, yield, range, average, standard deviation, three-sigma,
  and uniformity. *(US-5)*
- **FR-015.** The system MUST render a resistance wafer heatmap from a resistance
  summary, and a CD/SEM violin plot from CD/SEM records, producing downloadable
  chart and report artifacts and recording each render as a tracked job with a
  success or failed outcome. *(US-5)*
- **FR-016.** The system MUST let a user download an original uploaded file and
  download generated chart artifacts (including a selection of multiple charts as
  a single archive). *(US-6)*
- **FR-017.** The system MUST provide a delete preview for a raw data record and
  for a single file that reports, without deleting anything, the blast radius:
  the counts of dependent parsed datasets, normalized records, and files that
  would be removed. *(US-7)*
- **FR-018.** Deleting a raw data record MUST cascade-remove its files, parsed
  datasets, normalized records, and processing jobs, and remove the associated
  on-disk files and generated outputs; deleting a single file (only when it is
  the record's sole file) MUST cascade-remove that record's derived parsed data,
  records, jobs, and outputs. *(US-7)*
- **FR-019.** Before any such destructive operation the system MUST take a
  recoverable checkpoint and snapshot the removed row for audit. *(US-7,
  NFR-002)*

## Non-Functional Requirements

- **NFR-001 (Data safety — Article IV).** Every delete in this feature is
  Strong-tier: gated by a cascade-preview, snapshotted into the deletion audit,
  and preceded by a database backup, per the authoritative policy in
  [`docs/Data_Flow.md`](../../docs/Data_Flow.md). File cleanup is centralized,
  never ad-hoc per handler.
- **NFR-002 (File integrity & archival — Article IV).** Every accepted upload is
  checksummed (SHA-256) and copied into an append-only, content-addressed archive
  at upload time, so the original bytes remain recoverable even after the live
  file is deleted. Identical content is stored once.
- **NFR-003 (Auth & RBAC — Article XI).** When optional auth is enabled, this
  feature's reads require at least viewer, writes (create / upload / parse /
  visualize) require operator, and deletes require admin; when auth is disabled
  the feature behaves as if auth did not exist.
- **NFR-004 (Performance at lab volume).** Listing endpoints are bounded (record
  and parsed-dataset lists are capped), and normalized-record browsing is paged
  so a parsed dataset of thousands of points (a full wafer is hundreds–thousands
  of cells) stays responsive on a single lab workstation.
- **NFR-005 (Stdlib backend — Article I).** The backend parsing/serving path adds
  no third-party runtime dependency beyond what is already vetted; chart
  rendering is the one approved exception (matplotlib) confined to the
  `parsers/` visualizers.

## Key Entities

> Conceptual, aligned with [`docs/GLOSSARY.md`](../../docs/GLOSSARY.md). The
> physical schema lives in [`data-model.md`](./data-model.md).

- **Raw data record** — a tracked unit of instrument output attached to one
  sample. Has a unique human-readable code, a data type and category, a parser
  status, and aggregate file count/size. Owns its files and any parsed datasets
  derived from it.
- **Raw data file** — one uploaded file belonging to a raw data record. Carries
  its original name, stored name, size, type, content checksum, and whether it is
  previewable.
- **Parsed data (parsed dataset)** — the structured result of parsing a raw data
  record's file: which parser ran, a summary, record count, plots, warnings, and
  errors. One raw data record can have several parsed datasets over time.
- **Parsed record (normalized record)** — a single normalized measurement point
  within a parsed dataset: its position/identity (die, area, row/column for
  resistance; row group, side, direction, dose, location for CD/SEM), its raw and
  cleaned values, numeric value, and outlier flag.
- **Processing job** — an audit record of a parse or visualization run: its type,
  the script and version used, input parameters, output references, status, and
  any error. (Owned conceptually by this lifecycle; surfaced read-only.)

## Out of Scope

- Parsing of data types other than resistance and CD/SEM (SEM image, XPS, XRD,
  AFM, report, instrument folder, generic file) — those are stored and
  downloadable but not normalized.
- STDF or other binary instrument formats; only CSV (and XLSX for resistance, if
  the optional reader is available) are parsed.
- Editing or correcting normalized records after parsing (re-parse instead).
- Soft delete / record recovery UI — deletes are hard, with archive + audit
  recoverability handled out-of-band (a deferred constitutional decision).
- Deleting one file out of a multi-file raw data record (intentionally blocked
  until per-file derivation tracking exists).
- Asynchronous/queued parsing — parsing and visualization run synchronously
  within the request.

## Open Questions / Clarifications

None outstanding (as-built). This feature is implemented and in use; every
behavior above reflects current code.

## Acceptance Criteria

> Given/When/Then, each tied to the FRs it proves. The smoke test
> (`tests/smoke_test.py`) is the green-light oracle (constitution Article IX) and
> exercises the create → upload → parse → records → visualize → delete path.

- **AC-1.** *Given* an existing sample, *when* an operator creates a raw data
  record with a valid data type, *then* the record is created with a unique code,
  a derived category, and parser status "not parsed". *(FR-001, FR-002)*
- **AC-2.** *Given* a data type that is not recognized, *when* a create is
  attempted, *then* it is rejected with a validation error and no record is
  created. *(FR-002)*
- **AC-3.** *Given* a raw data record, *when* an operator uploads one or more
  files, *then* each file is stored with a checksum and archived, and the
  record's file count and total size reflect the upload. *(FR-005, FR-006)*
- **AC-4.** *Given* a resistance record with a parseable matrix file, *when* it
  is parsed, *then* a parsed dataset is created with one normalized record per
  matrix cell and a per-die/per-area/overall summary, and the record's status
  becomes "parsed". *(FR-007, FR-008, FR-009)*
- **AC-5.** *Given* a CD/SEM record with a valid template file, *when* it is
  parsed, *then* a parsed dataset is created with one normalized record per valid
  measurement carrying row group, side, direction, die, dose, location, and CD
  value. *(FR-008, FR-009)*
- **AC-6.** *Given* a record whose type has no parseable file, *when* a parse is
  attempted, *then* it fails with a clear message, the record is marked parse
  failed, and no normalized records are produced. *(FR-010)*
- **AC-7.** *Given* a parsed dataset, *when* a viewer requests its records with
  filters and a page, *then* only matching records for that page are returned
  with correct total and page counts, and the available filter options can be
  retrieved. *(FR-012, FR-013)*
- **AC-8.** *Given* a resistance parsed dataset and cleaning limits, *when* a
  summary is requested, *then* per-die, per-area, and overall statistics are
  returned with points classified as normal/outlier/NA. *(FR-014)*
- **AC-9.** *Given* a computed resistance summary (or CD/SEM records), *when* a
  visualization is requested, *then* a chart job completes successfully and its
  chart/report artifacts are downloadable. *(FR-015, FR-016)*
- **AC-10.** *Given* a raw data record with derived data, *when* a delete preview
  is requested, *then* the counts of dependent parsed data, records, and files
  are reported and nothing is deleted; *when* the delete is then executed, *then*
  all of that cascades away (rows and files) after a backup and audit snapshot.
  *(FR-017, FR-018, FR-019)*
