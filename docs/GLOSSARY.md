# Glossary

Plain-language definitions of the domain and technical terms used in SCRmonitor. Each entry ties back to this project where relevant.

## Domain / lab terms

**LIMS (Laboratory Information Management System)** — software for tracking samples, tests, and results in a lab. SCRmonitor's sample, test-data, characterization, and performance features are its LIMS side.

**MES (Manufacturing Execution System)** — software that tracks a unit of work as it moves step by step through a process route on the shop floor. SCRmonitor's MES side defines route templates and advances each sample through its layers and steps.

**LIMS vs MES** — LIMS answers "what was measured on this sample and what are the results?"; MES answers "where is this sample in the process and what step is next?". SCRmonitor combines both around a shared `samples` table.

**CD / CD-SEM (Critical Dimension / CD Scanning Electron Microscope)** — the critical dimension is the smallest measured feature width on a wafer; a CD-SEM measures it. SCRmonitor ingests CD/SEM CSV/XLSX files and renders them as violin plots.

**STDF (Standard Test Data Format)** — a binary industry-standard format for semiconductor test data. Not currently ingested by SCRmonitor (which uses CSV/XLSX), but a likely future raw-data type.

**21 CFR Part 11** — the US FDA regulation governing electronic records and signatures (audit trails, access control, data integrity). SCRmonitor's deletion-audit and optional RBAC are steps in that direction, not a certified implementation.

**ISO 17025** — the international standard for the competence of testing and calibration laboratories. Relevant as the quality framework a lab LIMS/MES is expected to support.

**SENAITE** — a mature open-source LIMS (built on Plone). A reference point for what a full-featured lab system looks like; SCRmonitor is a lighter, purpose-built alternative.

## Data / persistence terms

**DB (database)** — an organized store of structured data. SCRmonitor's DB is a single SQLite file.

**SQLite** — a serverless, file-based SQL database engine bundled with Python's standard library. SCRmonitor stores everything in one SQLite file under the data directory.

**PostgreSQL** — a full client/server relational database. SCRmonitor does not use it; it's the natural upgrade path if the app ever outgrows a single-file local store.

**WAL (Write-Ahead Logging)** — a SQLite journaling mode where changes are written to a separate log first, allowing reads to proceed concurrently with writes. SCRmonitor enables it on every connection.

**ORM (Object-Relational Mapping)** — a library that maps database rows to objects so you write less raw SQL. SCRmonitor deliberately uses **no ORM** — plain parameterized SQL via `sqlite3`.

**Migration** — a versioned, ordered change to the database schema. SCRmonitor applies forward-only, checksum-guarded SQL files from `migrations/`.

**Audit trail** — an append-only record of who/what changed, for traceability and recoverability. SCRmonitor's `deletion_audit` table and MES `step_events` are examples.

**Soft delete** — marking a row as deleted (e.g. a status flag) instead of removing it, so it can be recovered. SCRmonitor currently does **hard** deletes but snapshots the row into `deletion_audit` first; full soft-delete is a deferred future direction.

## Backend / web terms

**OSS (Open-Source Software)** — software whose source is publicly available and reusable under a license (e.g. SQLite, React, SENAITE).

**REST / RESTful** — an HTTP API style where resources live at URLs and HTTP methods (GET/POST/PUT/PATCH/DELETE) express actions. SCRmonitor's `/api/...` endpoints follow this style.

**RBAC (Role-Based Access Control)** — restricting actions by a user's role. SCRmonitor's optional auth defines admin/operator/viewer roles with per-method permissions; it is off by default.

**Smoke test** — a fast, shallow test that confirms the system boots and core paths work. SCRmonitor's `tests/smoke_test.py` boots the server against a temp database and hits the key endpoints.

## Frontend terms

**SPA (Single-Page Application)** — a web app that loads one HTML page and updates the view with JavaScript instead of full page reloads. SCRmonitor's frontend is a React SPA; the backend serves its built files and falls back to `index.html` for client routes.

**React** — a JavaScript/TypeScript library for building component-based user interfaces. SCRmonitor uses React 19.

**TypeScript** — JavaScript with static types, catching type errors at build time. The SCRmonitor frontend is written in TypeScript.

**Vite** — a fast frontend build tool and dev server. SCRmonitor uses it to run the dev server (`npm run dev`) and produce the production build (`npm run build` → `frontend/dist`).
