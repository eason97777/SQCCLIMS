# Domain Model Review

> **Status:** advisory / descriptive · **Date:** 2026-07-06
>
> This does not mandate a refactor. It names how today's blocks are positioned,
> defines the boundaries the code leaves implicit, and gives a north-star model
> so the next feature isn't built on the same ambiguity.

Cross-refs: [`ARCHITECTURE.md`](ARCHITECTURE.md) (data-model tree) ·
[`Data_Flow.md`](Data_Flow.md) · [`BACKEND_MODULES.md`](BACKEND_MODULES.md) ·
[`GLOSSARY.md`](GLOSSARY.md).

## 1. The problem in one sentence

The system is organized around **top-level blocks added per new data shape or
operation** — resistance files became Raw Data, manual metrics became Test Data
(labeled "Data Base"), performance files became Performance Datasets, statistics
became Processing — and this conflates two orthogonal concepts, producing
overlapping stores, dead-end bins, and name collisions.

## 2. The two axes

Two independent axes are collapsed into one flat sidebar:

- **Axis A — Storage (entities).** A `sample` *has* data. There are two natural
  kinds: **Artifacts** (files/records attached to a sample — raw-data,
  performance, characterization are all *types* of this) and **Measurements**
  (numeric points — parsed or manually entered are *sources* of this).
- **Axis B — Transforms (operations).** Things you *do* to data: **parse**,
  **visualize**, **analyze/process**. These are capabilities that should apply
  *across* entities, not properties of one bin.

**Thesis:** today these two axes are flattened into a single peer list, so three
storage entities (Raw Data, Test Data, Performance Datasets) and one operation
(Processing) appear as co-equal siblings.

## 3. Current blocks mapped onto the axes

| Block (sidebar label + route) | Axis | Entity or Operation | Storage table(s) | Transforms it has | Notes |
|---|---|---|---|---|---|
| Raw Data (`/raw-data`) | A | Artifact | `raw_data`, `raw_data_files`, `parsed_data`, `parsed_records` | parse, visualize | FK to `samples` `ON DELETE CASCADE`; the only block with a full parse→visualize pipeline |
| Test Data / "Data Base" (`/test-data`) | A | Measurement | `test_data` (flat, `numeric_value`) | analyze (via Processing) | No files; leaf child of `samples`; the **only** store Processing reads |
| Performance Datasets (`/performance-datasets`) | A | Artifact | `performance_datasets`, `performance_dataset_files` | **none** | Dead-end file store; no reader downstream; `status` defaults to `待处理` but never advances |
| Processing (`/processing`) | B | **Operation** | output only: `processing_results` | is itself a transform | Not a storage entity; sidebar route `/processing`, API `POST /api/process`; reads `test_data` via `fetch_processing_source`; FK `samples` `ON DELETE SET NULL`; **absent** from the ARCHITECTURE data-model tree |
| Characterization (`/characterization`) | A | Artifact | `characterization_collections`, `characterization_files` | none (grouped uploads) | Shown for context; a third file-artifact type alongside Raw Data and Performance |

Grounding: schemas in [`app/migrations.py`](../app/migrations.py) `init_db()`;
routes in [`app/http/handler.py`](../app/http/handler.py); Processing logic in
[`app/features/processing.py`](../app/features/processing.py); performance store
in [`app/features/performance.py`](../app/features/performance.py); manual metrics
in [`app/features/test_data.py`](../app/features/test_data.py).

## 4. The missing boundaries

These are the decision rules the code leaves implicit. Writing them down is the
most useful thing this document does.

### `test_data` vs `parsed_records`

Both are "a number measured on a sample" — each carries a `numeric_value`
column — yet they are **unlinked, disjoint stores** that never feed each other.

- `parsed_records` = values *extracted by a parser* from an uploaded Raw Data
  file. Wide and instrument-specific: `die_id`, `area`, `dose`, `row_group`,
  `side`, `direction`, `is_outlier`, … (see the column list in
  [`app/migrations.py`](../app/migrations.py) and
  `PARSED_RECORD_INSERT_COLUMNS` in [`app/config.py`](../app/config.py)).
- `test_data` = values *entered manually or CSV-imported directly* (flat
  scalar: `test_name`, `metric_name`, `numeric_value`, `unit`). It is the
  **only** store the Processing block reads (`fetch_processing_source` in
  [`app/features/processing.py`](../app/features/processing.py) selects
  `FROM test_data`).

**Rule of thumb:** parser output → `parsed_records`; hand-entered / bulk-imported
scalars → `test_data`. A value's analytical reach today is decided by which of
these two it landed in, not by anything intrinsic to the value.

### `performance_datasets` vs `raw_data`

Both attach instrument files to a sample and share the same upload archive
(`archive_file(..., source="performance")` vs the raw-data upload path). The gap
is not conceptual — it's pipeline:

- `raw_data.data_type` already includes `instrument_folder` and `generic_file`
  (`RAW_DATA_TYPES` in [`app/config.py`](../app/config.py)), which cover the same
  "folder of instrument files" case Performance Datasets exists for.
- **Difference today:** Raw Data has a parse → visualize pipeline; Performance is
  file-storage only, with no parser, no visualizer, and no downstream reader. Its
  `status` even defaults to `待处理` ("pending") but nothing ever advances it.

**When each is used today** (so users aren't lost): use **Raw Data** when the
files should be parsed/visualized (resistance, CD/SEM, …); use **Performance
Datasets** when you only need to archive a folder of performance-test files
against a sample. The overlap is flagged, not resolved.

## 5. Naming collisions & fossils

### "processing" means three unrelated things

| Name | What it is | Source table | Output / endpoint | Module |
|---|---|---|---|---|
| the `/processing` block (API `/api/process`) | stats / qc / normalize over `test_data` | reads `test_data` | writes `processing_results`; `GET /api/process-results` | `processing.py` |
| the `processing_jobs` table | the **Raw Data** parse/visualize job log | written per parse/visualize | `GET /api/processing-jobs` | `parsing.py`, `visualization.py` |
| `processing_results` | the `/process` block's actual output | — | the block's result rows | `processing.py` |

Same word, three different source tables, outputs, and endpoints. `processing_jobs`
in particular belongs to the **Raw Data** lineage (it logs parse and visualization
jobs) despite the name suggesting the Processing block.

### "Data Base" label

The `/test-data` block's eyebrow reads "Data Base", which collides with
[`GLOSSARY.md`](GLOSSARY.md): "DB (database) … a single SQLite file." The block is
not the database — it is the *test-results / metrics* table (`test_data`).

### Fossils (accreted-design signals)

- `parsed_data.plots_json` is written but effectively always `[]` — charts come
  from the separate visualization mechanism (`processing_jobs` + the outputs
  directory), not from this column.
- `performance_datasets.status` default `待处理` never transitions — there is no
  code path that advances it.
- `processing_results` is missing from the [`ARCHITECTURE.md`](ARCHITECTURE.md)
  data-model diagram, reflecting that Processing was never modeled as part of the
  storage graph.
- `parsed_records` denormalizes `raw_data_id` / `sample_id` **with no FK** (only
  `parsed_data_id` has a real foreign key), while its parent `parsed_data` carries
  proper FKs to both `raw_data` and `samples`.

## 6. Transform coverage is siloed

| Transform | Applies to | Does not apply to |
|---|---|---|
| parse | `raw_data` only | test_data, performance |
| visualize | `raw_data` (via `parsed_data`) only | test_data, performance |
| analyze / process | `test_data` only | raw_data/parsed_records, performance |
| (performance) | — | Performance Datasets has no transform at all |

**Point:** a value's transform capability is an accident of which table it landed
in, not a property of the data. A manually entered number can be analyzed but not
visualized; a parsed number can be visualized but is invisible to Processing;
performance files can do neither.

## 7. North-star model

*Aspirational. Explicitly not scheduled.*

The factored target separates the two axes:

```
Sample
├── Artifacts        (typed:  raw | performance | characterization)
└── Measurements     (sourced: parsed | manual)

Transforms  (parse | visualize | analyze)  — capabilities that apply
            across Artifacts and Measurements, not owned by one bin
```

Under this model:

- **"Performance"** becomes a `raw_data` `data_type`, not a peer storage block.
- **"Data Base"** becomes a measurement *source* (manual) alongside parsed.
- **"Processing"** becomes a transform surface over Measurements, not a sibling
  storage block.

None of these is a peer storage entity in the target. **This is a direction, not
a planned migration** — consolidation is a separate decision with real cost
(data migration, URL/route changes, frontend rework) and is out of scope here.

## 8. Guidance until/unless that happens

What *not* to do next, so the ambiguity doesn't compound:

- **Don't add a new top-level block for each new data shape.** Prefer a new
  `data_type` (Artifacts) or a new source (Measurements) inside an existing
  entity.
- **Model new transforms as capabilities** over Measurements/Artifacts, not as
  new sibling blocks in the sidebar.
- **If you touch this area, resolve one naming collision** (e.g. rename the
  "Data Base" eyebrow, or clarify `processing_jobs`) rather than adding another.

---

See also: [`ARCHITECTURE.md`](ARCHITECTURE.md) for the layered design and the
data-model tree, [`Data_Flow.md`](Data_Flow.md) for how data moves and the
deletion policy, [`BACKEND_MODULES.md`](BACKEND_MODULES.md) for the per-module
reference, and [`GLOSSARY.md`](GLOSSARY.md) for the domain terms used above.
