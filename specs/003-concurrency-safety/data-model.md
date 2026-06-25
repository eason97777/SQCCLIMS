# Data Model: Concurrent-Writer Safety

> This feature makes **one** data-model change: the sample business identifier
> (`sample_uid`) becomes provably unique at the data layer. No column is added,
> dropped, or retyped. The authoritative baseline schema lives in
> `app/migrations.py` `init_db()`; the relationship/cascade reference is
> [`docs/Data_Flow.md`](../../docs/Data_Flow.md). The existing `samples` schema is
> documented in [`../001-samples/data-model.md`](../001-samples/data-model.md).

## The change: `sample_uid` becomes UNIQUE

### Why it was previously unconstrained

In the baseline schema (`app/migrations.py` `init_db()`, lines 92-107) the
`samples` table declares `sample_uid TEXT NOT NULL DEFAULT ''` with **no UNIQUE
constraint**. The only uniqueness on `samples` is:

- `UNIQUE(sample_display_code)` (table constraint) +
  `idx_samples_display_code_unique` (partial unique, `WHERE sample_display_code
  != ''`, `app/migrations.py:599-605`), and
- `idx_samples_identity_unique` on `(sample_code, name, category, batch)`
  (`app/migrations.py:471-474`).

`sample_uid` was left unconstrained because it is **server-generated** and was
*assumed* unique by construction: `generate_sample_uid()`
(`app/features/samples.py:10-22`) reads the current max year-suffix and returns
`max + 1`. That assumption holds for a single writer but **breaks under
concurrency**: two threads can both read the same max, both compute the same
`+1`, and both INSERT — and because nothing at the data layer forbids it, **two
rows persist with the same UID, silently**. Defaulting to `''` (rather than NULL)
also means a naive plain UNIQUE index would treat multiple legacy blank UIDs as
collisions; hence the partial-index approach below.

### New unique index (DDL approach)

A **partial UNIQUE index** on the non-empty UID values, mirroring the established
`idx_samples_display_code_unique` pattern:

```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_samples_uid_unique
ON samples(sample_uid)
WHERE sample_uid != '';
```

- **Partial (`WHERE sample_uid != ''`)** so legacy/blank UIDs (the column default)
  do not collide with one another and only genuine `SMP-YYYY-NNNNNN` business
  identifiers are constrained. This matches how display-code uniqueness is already
  handled.
- Delivered as a **new** `migrations/006_samples_uid_unique.sql` (Article V).
  The migration file contains **no `BEGIN`/`COMMIT`** — `run_migrations()`
  (`app/migrations.py:67-79`) wraps each file in its own transaction.
- The migration is **forward-only and checksum-guarded**: once applied, its
  SHA-256 is stored in `schema_migrations` and startup aborts if the file is later
  edited (`app/migrations.py:54-62`).

### Legacy-duplicate detection & cleanup strategy

Because old databases may already hold duplicate UIDs (created before this
feature), `CREATE UNIQUE INDEX` would **fail** on dirty data. The migration must
therefore **renumber duplicates first, in the same migration, before creating the
index**. Strategy:

1. **Detect** colliding UIDs:

   ```sql
   SELECT sample_uid
   FROM samples
   WHERE sample_uid != ''
   GROUP BY sample_uid
   HAVING COUNT(*) > 1;
   ```

2. **Resolve (renumber, never delete).** For each colliding `sample_uid`:
   - Keep the **earliest-created** row's UID unchanged (order by `created_at`,
     tie-break by `id`). This satisfies **FR-008** — no valid identifier is
     renumbered.
   - Reassign every **later** colliding row a fresh, non-colliding
     `SMP-YYYY-NNNNNN` in the **same year series** as its current UID, taking the
     next free sequence above the current max for that year (and above any UID
     already reassigned in this run).

3. **Then** create `idx_samples_uid_unique`.

Because SQLite migration files are plain SQL run statement-by-statement
(`iter_sql_statements`, `app/migrations.py:24-34`), the renumber step is expressed
as deterministic SQL (a correlated/`ROW_NUMBER`-style `UPDATE` over the duplicate
sets, or a small set of `UPDATE`s computing the next free sequence). The exact SQL
is an implementation detail of T002; the **invariants** it must guarantee are:

- every previously-duplicate UID becomes unique,
- the earliest row of each duplicate set is untouched,
- no row is deleted,
- the result passes `CREATE UNIQUE INDEX … WHERE sample_uid != ''`.

The established precedent for a guarded, data-aware samples migration is
`ensure_samples_composite_unique` (`app/migrations.py:467-530`), which likewise
checks for duplicates before enforcing a unique constraint (it *raises* on
duplicate identities; here we *renumber* UIDs instead of raising, because UIDs are
server-assigned and safe to reassign, whereas identity tuples are user data).

### Runtime guarantee (feature module, not schema)

The unique index is the **last line of defense**. The primary guarantee is in
`create_sample` (`app/features/samples.py:148-181`):

- the create transaction takes the write lock up front (`BEGIN IMMEDIATE`),
- `generate_sample_uid` runs after the lock is held, so it sees committed rows,
- the INSERT is wrapped in a **bounded retry loop**: a `sample_uid` collision
  (`sqlite3.IntegrityError` against `idx_samples_uid_unique`) triggers a
  regenerate-and-retry; an unresolved collision after the attempt cap propagates
  to the handler as a 409.

## What does NOT change

- No column added, dropped, or retyped on `samples` or any table.
- No foreign key or `ON DELETE` behavior changes; the Strong-tier sample cascade
  (Article IV) is untouched.
- No new deletable entity is introduced, so the per-entity deletion table in
  [`docs/Data_Flow.md`](../../docs/Data_Flow.md) is unchanged.
- `sample_display_code` and `idx_samples_identity_unique` uniqueness are unchanged.
