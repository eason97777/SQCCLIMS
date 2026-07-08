# Contract — Routes, Navigation & API Behavior (Target)

> The target route/nav map for [`spec.md`](../spec.md) / [`plan.md`](../plan.md).
> This is primarily a **behavioral / navigational** contract — most endpoints are
> unchanged in shape; what changes is *what they read from*, *how they are
> labelled/grouped*, and *which legacy URLs redirect*. It is **not** a set of
> brand-new endpoints.
>
> **Draft.** Nothing here authorizes code; it defines the intended contract for
> human review.

## 1. Target navigation (frontend `NAV_ITEMS` / `VIEW_META`)

Sample-rooted, two-axis grouping (conceptual — exact component layout TBD):

- **总览** — `/` (unchanged)
- **样品信息库** — `/samples` (unchanged; the root of everything)
- **工艺记录** — `/process-records` (unchanged; MES traveller)
- **Storage — Artifacts**
  - **原始数据 / Artifacts** — `/raw-data` (Raw Data; hosts `data_type='performance'` after Phase 2)
  - **表征数据中心** — `/characterization` (unchanged; separate store, not folded)
- **Storage — Measurements**
  - **Measurements / 测试结果** — `/test-data` (**relabelled** from "测试数据库 / Data Base")
- **Analysis (Transforms over Measurements)**
  - **数据处理 / Analysis** — `/processing` (analyze/process; reads the view)
  - Visualization — surfaced as a transform over Measurements (entered from
    parsed data / Measurements context; no standalone top-level block required).
    *Navigational grouping only* — it still reads `parsed_records` (FR-007 deferred).

Performance **ceases to be a top-level nav block**; it becomes an artifact type
under Raw Data / Artifacts.

## 2. Current → Target route mapping (frontend)

| Current route | Current label | Target | Back-compat |
|---------------|---------------|--------|-------------|
| `/test-data` | 测试数据库 / "Data Base" | **Measurements / 测试结果** (same screen) | Route kept; **relabelled only** (Phase 0) |
| `/data` | alias → TestDataPage | alias → Measurements | Kept as alias (already exists in router) |
| `/raw-data` | 原始数据 / Raw Data | 原始数据 / **Artifacts** | Route kept; label broadened |
| `/performance-datasets` | 性能数据集 | folded into Artifacts | **Redirect** → `/raw-data?data_type=performance` (Phase 2) |
| `/performance` | alias → PerformanceDatasetPage | folded into Artifacts | **Redirect** → `/raw-data?data_type=performance` (Phase 2) |
| `/processing` | 数据处理模块 / Processing | **Analysis** | Route kept; label → Analysis (Phase 0/3) |
| `/characterization` | 表征数据中心 | unchanged | Kept (not folded) |
| `/process-records` | 工艺记录 | unchanged | Kept (disambiguated in copy) |
| `/samples`, `/samples/maintenance`, `/` | — | unchanged | Kept |

> The router already demonstrates the alias pattern (`/data` → `TestDataPage`,
> `/performance` → `PerformanceDatasetPage`), so keeping legacy paths as
> redirects/aliases follows existing precedent (`frontend/src/router/index.tsx`).

## 3. Target API endpoint behavior changes (backend)

Endpoints keep their method + path; the **behavior** shifts as noted.

| Method | Path | Current behavior | Target behavior | Phase |
|--------|------|------------------|-----------------|-------|
| POST | `/api/process` | `run_processing` reads `test_data` only | reads **`measurements` view** (manual + parsed); QC/normalize rows gain a `source` field (`manual`/`parsed`) beside `source_row_id` (replacing the old ambiguous `id`) | 1 |
| GET | `/api/process-results` | list `processing_results` | unchanged (results now reflect both sources) | 1 |
| GET | `/api/test-data` | list manual measurements | unchanged (backs the relabelled "Measurements" screen) | 0 |
| POST | `/api/test-data`, `/api/test-data/bulk` | create manual measurements | unchanged (manual entry → `source='manual'`) | 0 |
| POST | `/api/parsed-data/{id}/visualize` | visualize from `parsed_records` | **unchanged** — still `parsed_records` (FR-007 deferred) | — |
| GET | `/api/performance-datasets` | list performance datasets | **unchanged & live** (reads the retained tables); deprecated in the UI only — the Artifacts page lists performance via the `artifacts` view | 2 |
| POST | `/api/performance-datasets` | create performance dataset (multipart) | **unchanged & live**, but **deprecated**: new uploads go through the Artifact store (`POST /api/raw-data`, `data_type='performance'`) instead | 2 |
| GET | `/api/performance-datasets/{id}/files` | list dataset files | **unchanged & live** — performance-origin artifact detail/files stay on this endpoint (no cross-source file view) | 2 |
| DELETE | `/api/performance-datasets/{id}` | Strong-tier delete | **unchanged** — performance-origin artifacts delete here; raw_data-origin via `/api/raw-data` (the Artifacts UI routes by `source`) | 2 |
| GET | `/api/processing-jobs` | list parse/visualization job log | unchanged; **presented as "parse / visualization job log"** in copy | 0 |

### Unified Artifacts list — list-only, detail per-source

The `artifacts` **view** (Phase 2) backs the unified Artifacts **list** query
(`GET /api/raw-data`, repointed `FROM artifacts`) — each row carries a `source`
(`raw_data` / `performance`) + `source_row_id`. Artifact **detail, file listing,
download, and delete stay on the existing per-source endpoints** unchanged; the
frontend routes a row's detail/actions to `/api/raw-data/...` or
`/api/performance-datasets/...` by `source`. No new artifact endpoints, no
`handler.py` change, and no cross-source file view. Rationale and trade-off in
[`../plan.md`](../plan.md) (Risks) and [`../data-model.md`](../data-model.md).

### Redirect / back-compat notes

- **Frontend routes** (`/performance-datasets`, `/performance`, `/processing`,
  `/test-data`, `/data`) MUST all continue to resolve. Relabels (Phase 0) keep
  the route; removed blocks (Phase 2/3) become **client-side** redirects to their
  new home so bookmarks do not 404 (FR-008). This reuses the router's existing
  alias pattern (`/data`→TestData, `/performance`→Performance).
- **No backend redirects are introduced.** Because the performance tables are
  retained, the performance **API** endpoints stay **live and unchanged** over
  those tables through the deprecation window — no 308, no shim rewrite, no new
  transport pattern in `handler.py`. Hard removal of the performance API + tables
  is a separate, later, approved cleanup — **out of scope** here.
- **Auth posture unchanged** (Article XI): relabelled routes keep
  `GET ≤ operator-write ≤ admin-delete` and remain a true no-op when auth is
  disabled. The frontend redirects are client-side and do not touch
  `authorize()`.
- **Error mapping unchanged** (Article VI): feature code still raises
  `ValueError` / `LookupError` / `ConflictError`; `route()` maps centrally.

## 4. What this contract does NOT change

- No new database-writing endpoints are introduced by the reform (the
  `measurements` and `artifacts` views are read-only — they are migrations, not
  endpoints).
- Parser and chart *algorithms* are untouched — only the *source* a transform
  reads from may change (to the view).
- Characterization, samples, MES, and process-records endpoints are unchanged.
