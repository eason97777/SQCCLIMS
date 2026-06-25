# Changelog

All notable changes to SQCCLIMS are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-06-25

First consolidated release. The `restructure/layered-architecture` branch becomes
`main`: the codebase moves from a single-file server to a layered package with a
data-safety posture, optional auth, a Spec-Driven Development layer, and
concurrency-safe writes.

### Added
- **Layered backend** — `server.py` split into an `app/` package along clear
  layers (HTTP → features → domain/data → infra), one module per feature domain.
- **Structured logging** — per-request access log plus full stack traces on 500s.
- **Data safety** — SQLite WAL mode, startup database backups with retention, and
  append-only `deletion_audit` snapshots.
- **Optional auth + RBAC** — token-based viewer/operator/admin roles, disabled by
  default; login UI and `GET /api/auth/me`.
- **Upload archive** — append-only, content-addressed (SHA-256) storage of
  uploaded files.
- **Deletion policy** — cascade fixes, file cleanup, delete-preview endpoints,
  per-delete backup, and a delete-confirmation dialog in the UI.
- **Database restore CLI** — completes the backup/restore feature.
- **Spec-Driven Development layer** — `.specify/` (constitution v1.0.0 +
  spec/plan/tasks templates) and `specs/` with worked exemplars
  (`001-samples`, `002-raw-data-parsing`).
- **Root AI entrypoint** — `CLAUDE.md`/`AGENTS.md` with the project rules and the
  new-feature recipe.
- **Concurrent-writer safety** (spec `003`) — `PRAGMA busy_timeout`, a
  `db_session()` helper with deterministic connection close, race-safe
  `sample_uid` generation via `BEGIN IMMEDIATE` + bounded retry, a unique-index
  migration, and honest `409`/`503` error mapping. Concurrency covered by the
  smoke test.

### Changed
- Renamed the project SCRmonitor → **SQCCLIMS** and the env-var prefix
  `JIQT_` → `LIMS_`.
- De-nested the repository to a flat `SQCCLIMS` root.
- Consolidated documentation to one source of truth per topic; `docs/` is the
  as-built reference and `specs/` the per-feature SDD layer.
  `docs/Development_Guide.md` is now a redirect.

### Fixed
- Resolved gap-audit findings (P1–P4).
- Concurrent sample creates could silently mint duplicate `sample_uid`s; now
  prevented by a partial unique index plus in-feature retry.
- Stale SCRmonitor/JIQT references in the packaging docs.
