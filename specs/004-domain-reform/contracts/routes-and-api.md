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
    parsed data / Measurements context; no standalone top-level block required)

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
| POST | `/api/process` | `run_processing` reads `test_data` only | reads **`measurements` view** (manual + parsed) | 1 |
| GET | `/api/process-results` | list `processing_results` | unchanged (results now reflect both sources) | 1 |
| GET | `/api/test-data` | list manual measurements | unchanged (backs the relabelled "Measurements" screen) | 0 |
| POST | `/api/test-data`, `/api/test-data/bulk` | create manual measurements | unchanged (manual entry → `source='manual'`) | 0 |
| POST | `/api/parsed-data/{id}/visualize` | visualize from `parsed_records` | may also source the **`measurements` view** (both sources) | 3 |
| GET | `/api/performance-datasets` | list performance datasets | **deprecated**; behavior served via Raw Data (`data_type='performance'`). Kept responding for back-compat or 308-redirected to `/api/raw-data?data_type=performance` | 2 |
| POST | `/api/performance-datasets` | create performance dataset (multipart) | **deprecated**; uploads reframed to the Artifact store (`raw_data`, `data_type='performance'`) | 2 |
| GET | `/api/performance-datasets/{id}/files` | list dataset files | served via `raw_data` file listing after fold | 2 |
| DELETE | `/api/performance-datasets/{id}` | Strong-tier delete | folded artifacts deleted via `raw_data` Strong-tier path | 2 |
| GET | `/api/processing-jobs` | list parse/visualization job log | unchanged; **presented as "parse / visualization job log"** in copy | 0 |

### Redirect / back-compat notes

- **Frontend routes** (`/performance-datasets`, `/performance`, `/processing`,
  `/test-data`, `/data`) MUST all continue to resolve. Relabels (Phase 0) keep
  the route; folds (Phase 2/3) turn removed blocks into client-side redirects to
  their new home so bookmarks do not 404 (FR-008).
- **API endpoints** for performance are **deprecated, not deleted**, during this
  reform. Preferred target: keep them responding (thin shims over `raw_data`) or
  issue an HTTP redirect to the Raw Data equivalent. Hard removal of the
  performance API + tables is a separate, later, approved cleanup — **out of
  scope** here.
- **Auth posture unchanged** (Article XI): relabelled/redirected routes keep
  `GET ≤ operator-write ≤ admin-delete` and remain a true no-op when auth is
  disabled. Redirects do not bypass `authorize()`.
- **Error mapping unchanged** (Article VI): feature code still raises
  `ValueError` / `LookupError` / `ConflictError`; `route()` maps centrally.

## 4. What this contract does NOT change

- No new database-writing endpoints are introduced by the reform (the view is
  read-only; the fold is a migration, not an endpoint).
- Parser and chart *algorithms* are untouched — only the *source* a transform
  reads from may change (to the view).
- Characterization, samples, MES, and process-records endpoints are unchanged.
