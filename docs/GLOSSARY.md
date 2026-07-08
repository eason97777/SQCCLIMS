# Glossary

Plain-language definitions of the domain and technical terms used in SQCCLIMS. Each entry ties back to this project where relevant.

## Domain / lab terms

**LIMS (Laboratory Information Management System)** — software for tracking samples, tests, and results in a lab. SQCCLIMS's sample, test-data, characterization, and performance features are its LIMS side.

**MES (Manufacturing Execution System)** — software that tracks a unit of work as it moves step by step through a process route on the shop floor. SQCCLIMS's MES side defines route templates and advances each sample through its layers and steps.

**LIMS vs MES** — LIMS answers "what was measured on this sample and what are the results?"; MES answers "where is this sample in the process and what step is next?". SQCCLIMS combines both around a shared `samples` table.

**Measurements (测试结果)** — the unified concept for numeric points about a sample, regardless of how they arrived: typed in by hand (`test_data`, `source='manual'`) or extracted from an instrument file (`parsed_records`, `source='parsed'`). Spec 004 relabels the former "测试数据库 / Data Base" screen as **测试结果 / Measurements**; from Phase 1 both are exposed through one `measurements` read model.

**Artifact (原始数据 / Artifacts)** — files attached to a sample, discriminated by `data_type`. The general Artifact store is `raw_data`; from Phase 2 the `artifacts` read model presents performance datasets alongside it as `data_type='performance'`.

**The three "processing" concepts (disambiguated by spec 004)** — SQCCLIMS historically overloaded the word "processing". They are three distinct things: (1) **解析 / 可视化任务日志** — the `processing_jobs` table, an audit log of parse and visualization jobs on Raw Data; (2) **数据分析 / Analysis** — the stats/QC/normalize feature at `/processing` (`POST /api/process`), which operates over Measurements; (3) **工艺记录 / MES traveller** — `process_records`, the shop-floor process record. Only the traveller is "process" in the MES sense.

**CD / CD-SEM (Critical Dimension / CD Scanning Electron Microscope)** — the critical dimension is the smallest measured feature width on a wafer; a CD-SEM measures it. SQCCLIMS ingests CD/SEM CSV/XLSX files and renders them as violin plots.

**STDF (Standard Test Data Format)** — a binary industry-standard format for semiconductor test data. Not currently ingested by SQCCLIMS (which uses CSV/XLSX), but a likely future raw-data type.

**21 CFR Part 11** — the US FDA regulation governing electronic records and signatures (audit trails, access control, data integrity). SQCCLIMS's deletion-audit and optional RBAC are steps in that direction, not a certified implementation.

**ISO 17025** — the international standard for the competence of testing and calibration laboratories. Relevant as the quality framework a lab LIMS/MES is expected to support.

**SENAITE** — a mature open-source LIMS (built on Plone). A reference point for what a full-featured lab system looks like; SQCCLIMS is a lighter, purpose-built alternative.

## Data / persistence terms

**DB (database)** — an organized store of structured data. SQCCLIMS's DB is a single SQLite file.

**SQLite** — a serverless, file-based SQL database engine bundled with Python's standard library. SQCCLIMS stores everything in one SQLite file under the data directory.

**PostgreSQL** — a full client/server relational database. SQCCLIMS does not use it; it's the natural upgrade path if the app ever outgrows a single-file local store.

**WAL (Write-Ahead Logging)** — a SQLite journaling mode where changes are written to a separate log first, allowing reads to proceed concurrently with writes. SQCCLIMS enables it on every connection.

**ORM (Object-Relational Mapping)** — a library that maps database rows to objects so you write less raw SQL. SQCCLIMS deliberately uses **no ORM** — plain parameterized SQL via `sqlite3`.

**Migration** — a versioned, ordered change to the database schema. SQCCLIMS applies forward-only, checksum-guarded SQL files from `migrations/`.

**Audit trail** — an append-only record of who/what changed, for traceability and recoverability. SQCCLIMS's `deletion_audit` table and MES `step_events` are examples.

**Soft delete** — marking a row as deleted (e.g. a status flag) instead of removing it, so it can be recovered. SQCCLIMS currently does **hard** deletes but snapshots the row into `deletion_audit` first; full soft-delete is a deferred future direction.

## Backend / web terms

**OSS (Open-Source Software)** — software whose source is publicly available and reusable under a license (e.g. SQLite, React, SENAITE).

**REST / RESTful** — an HTTP API style where resources live at URLs and HTTP methods (GET/POST/PUT/PATCH/DELETE) express actions. SQCCLIMS's `/api/...` endpoints follow this style.

**RBAC (Role-Based Access Control)** — restricting actions by a user's role. SQCCLIMS's optional auth defines admin/operator/viewer roles with per-method permissions; it is off by default.

**Smoke test** — a fast, shallow test that confirms the system boots and core paths work. SQCCLIMS's `tests/smoke_test.py` boots the server against a temp database and hits the key endpoints.

## Frontend terms

**SPA (Single-Page Application)** — a web app that loads one HTML page and updates the view with JavaScript instead of full page reloads. SQCCLIMS's frontend is a React SPA; the backend serves its built files and falls back to `index.html` for client routes.

**React** — a JavaScript/TypeScript library for building component-based user interfaces. SQCCLIMS uses React 19.

**TypeScript** — JavaScript with static types, catching type errors at build time. The SQCCLIMS frontend is written in TypeScript.

**Vite** — a fast frontend build tool and dev server. SQCCLIMS uses it to run the dev server (`npm run dev`) and produce the production build (`npm run build` → `frontend/dist`).
