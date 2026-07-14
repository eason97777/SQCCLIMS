# Amendment A — Artifact Branch is a Category, not a `data_type`

> **Status:** Draft — requires human approval before any code.
> **Amends:** [`spec.md`](./spec.md) **FR-005** and the Phase 2 data model.
> **Supersedes in part:** the shipped Phase 2a/2b flat model
> (`data_type='performance'`). This is **forward-only** — it does not edit
> migration `008` or rewrite the 2a/2b commits; it layers a corrected model on
> top via a new migration + a frontend refactor.

## Why (the problem)

Phase 2 folded performance datasets into the unified Artifact list by projecting
them as **`data_type='performance'`** — a *peer value* alongside `resistance`,
`cd_sem`, `xps`, … But performance is not a peer type; it is a **different
branch** of artifact with a different shape:

| | Parseable raw data | Performance data |
|--|--------------------|------------------|
| Parser pipeline | yes (`parsed_data`/`parsed_records`) | **no — files only** |
| Backing table | `raw_data` | `performance_datasets` |
| Detail view | parse / visualize | files + metadata |
| Upload | single/multi file | folder-based |

Putting `performance` into `data_type` **conflates two levels** — a *branch*
(which kind of artifact) with a *type* (which specific measurement). The visible
symptom: the list's **数据类型** filter now lists **性能数据集 (a branch)** at the
same level as **电阻测试数据 (a type)**. The structural symptom: three fields
(`source`, `data_type`, `data_category`) all encode the same branch for
performance rows, and the codebase special-cases performance in ~6 places
(route-by-source, separate detail, hidden delete, separate upload, type-options
split). Pervasive special-casing is the evidence that the branch is a *category*,
not a *type*.

## What (the revised model)

Two orthogonal axes for an Artifact — a **symmetric** two-level model:

- **Branch (category)** — *which kind of artifact.* Two values:
  - **`raw`** — parseable raw data (today's `raw_data`).
  - **`performance`** — files-only performance data (today's
    `performance_datasets`; no parser).
  - This axis is backed physically by **`source`** (`raw_data` /
    `performance`), which the `artifacts` view already exposes and which
    route-by-source already relies on. **`source` IS the branch** — we stop
    duplicating it into `data_type`.
- **Type** — *the specific measurement within its branch* (`data_type`).
  Meaningful for **both** branches, with disjoint vocabularies:
  - `raw` → `resistance`, `cd_sem`, `xps`, …
  - `performance` → `IV`, `CV`, `EIS`, `寿命` (from `test_type`, now a fixed enum).

```
Branch (= source)          Type (= data_type)
  原始数据 (raw) ───────────  resistance / cd_sem / xps / …
  性能数据集 (performance) ──  IV / CV / EIS / 寿命
```

> **Naming guard.** The `raw` branch is **NOT** "characterization" —
> Characterization (表征数据中心 / `characterization_collections`) is a *separate*
> store that this reform explicitly does not fold (see spec Out of Scope). The
> two Artifact branches are **原始数据 (Raw)** and **性能数据集 (Performance)**.

### FR-005 (revised)

> Performance datasets MUST be presented as a distinct Artifact **branch**
> (`性能数据集 / Performance`), discriminated by the artifact `source`
> (`performance`) — **not** by a `data_type` value peer to `resistance`/`cd_sem`.
> The unified Artifacts UI MUST present the branch as the primary axis (filter /
> group by branch first) and the specific `data_type` as a secondary axis
> **within** the chosen branch. Within `performance`, the secondary axis is the
> performance **test type** (`IV` / `CV` / `EIS` / `寿命`), promoted from a
> free-text field to a controlled vocabulary. The `artifacts` view MUST NOT
> overload `data_type='performance'`; for performance rows `data_type` carries the
> test type.

## Data-model impact

- **New migration `009_artifacts_view_v2.sql`** (forward-only; does **not** edit
  `008`): redefine the `artifacts` view so the performance branch emits
  **`data_type = pd.test_type`** (the secondary axis) instead of the literal
  `'performance'`. The branch is read from `source`. `test_type` is dropped from
  the `metadata_json` fold (it is now a first-class column, no longer buried).
  *(Article V: new file, `008` untouched; the view is replaced via
  `DROP VIEW artifacts; CREATE VIEW artifacts …` inside `009`.)*
- **No schema/column change, no data moves.** `test_type` is already a `TEXT`
  column on `performance_datasets`; making it an enum is a *frontend write-side*
  constraint (the upload dropdown), not a DB constraint. Legacy free-text
  `test_type` values still display (via the label fallback) — no backfill needed.
- **Branch label is frontend-derived from `source`** (RD-2): the view adds no
  branch-label column; the UI maps `source → 原始数据 / 性能数据集`.

## Frontend impact

- **`ARTIFACT_TYPE_OPTIONS`** (added in `d16082b`) is retired in favor of a
  **branch-scoped** type model:
  - `RAW_DATA_TYPE_OPTIONS` (unchanged) — the `raw` branch's types.
  - **new** `PERFORMANCE_TEST_TYPE_OPTIONS` — the `performance` branch's types
    (`IV` / `CV` / `EIS` / `寿命`).
- **Two-level filter** (`RawDataFilter`): a branch selector (全部 / 原始数据 /
  性能数据集); when a branch is chosen, a second selector offers that branch's
  types. Filtering maps to the existing `data_type` query param (values are
  disjoint across branches, so `data_type` alone still disambiguates rows).
- **Upload form** (`DatasetImportPanel`): the free-text 测试类型 input becomes a
  dropdown bound to `PERFORMANCE_TEST_TYPE_OPTIONS`.
- **Label lookup** (`typeLabel`): branch label derived from `source`; type label
  resolved against the branch's option list.
- Route-by-source, the performance detail panel, and the upload tab are otherwise
  **unchanged** — they already key on `source`, which this amendment makes the
  canonical discriminator (so they get *more* consistent, not reworked).

## What this supersedes / migration reality

Phase 2a/2b **shipped** the flat `data_type='performance'` model. This amendment
does not unwind them; it corrects forward:

1. `008` and the 2a/2b commits stay as-is (history intact).
2. A new phase (call it **Phase 2d**) adds migration `009` + the two-level
   frontend filter and drops the `data_type='performance'` projection.
3. Until Phase 2d ships, the flat model keeps working (no regression).

## Constitution check (delta)

| Article | Verdict | Note |
|---------|---------|------|
| V — Forward-only migrations | **PASS** | New `009`; `008` never edited. The view is replaced via a forward `DROP VIEW`+`CREATE VIEW` in `009`. |
| X — Simplicity over cleverness | **PASS (net simpler)** | Removes a 3×-redundant discriminator and ~6 special-cases; the branch axis (`source`) already exists. |
| IX — Smoke test | **PASS** | Extend `check_artifacts_view` to assert performance rows are branch-discriminated by `source`, not `data_type`. |
| others | unchanged | No auth/layering/SQL-safety impact. |

## Resolved decisions

- **RD-1 — Performance sub-types: YES.** The `performance` branch gets a
  secondary type axis via `test_type`, promoted to a controlled vocabulary
  (`IV` / `CV` / `EIS` / `寿命`). The model is symmetric: `data_type` = "specific
  type within branch" for both branches.
- **RD-2 — Branch label: frontend-derived from `source`.** No branch-label
  column in the view; the UI maps `source → 原始数据 / 性能数据集`.
- **RD-3 — Sequence: separate PR (Phase 2d) after 2b merges.** 2b ships as its
  own build-verified unit; Phase 2d branches off updated `main` with migration
  `009` + the two-level frontend.

## Acceptance criteria

- **AC-A1.** The `artifacts` view (v2) emits performance rows with
  `data_type = test_type` (not the literal `'performance'`); the branch is read
  from `source`. Smoke test asserts this. *(FR-005 revised, RD-1)*
- **AC-A2.** The unified Artifacts filter presents branch as the primary axis;
  the secondary type selector offers the chosen branch's vocabulary (raw types
  vs performance test types). No branch value appears as a peer of a type value.
  *(FR-005 revised)*
- **AC-A3.** The performance upload form's 测试类型 field is a dropdown bound to
  `PERFORMANCE_TEST_TYPE_OPTIONS`. *(RD-1)*
- **AC-A4.** Route-by-source, performance detail, and upload otherwise work
  unchanged; smoke test green (extended per Article IX). *(RD-2)*
