-- Make the sample business identifier (sample_uid) provably unique at the data
-- layer. Historically sample_uid had NO unique constraint: it was assumed unique
-- by construction (generate_sample_uid reads max+1), an assumption that breaks
-- under concurrent writers, so two rows could persist with the same UID silently.
--
-- This migration:
--   1. Renumbers any PRE-EXISTING duplicate sample_uid values (legacy dirty
--      data) so the unique index can be created without failing. Policy: keep
--      the earliest-created row's UID unchanged (order by created_at, then id);
--      reassign each later colliding row a fresh, non-colliding SMP-YYYY-NNNNNN
--      in the SAME year series, above the current max sequence for that year and
--      above anything reassigned in this run. No row is ever deleted.
--   2. Creates a partial UNIQUE index on the non-empty UID values, mirroring the
--      established idx_samples_display_code_unique precedent (so blank/legacy
--      empty UIDs, which default to '', do not collide with one another).
--
-- run_migrations() owns the transaction, so this file contains NO BEGIN/COMMIT.
-- Statements are run one at a time (sqlite3.complete_statement boundaries), so
-- the rebuild is expressed as standalone statements. The renumber step is a
-- no-op on a clean database (the duplicate set is empty), and correct whether or
-- not duplicates exist.

-- Step 1: renumber duplicate sample_uids.
--
-- "dups": every colliding row EXCEPT the earliest-created one of each UID set,
-- tagged with a per-year ordinal (rn) used to offset it past the current max.
-- "year_max": the current highest sequence already in use for each year series
-- (across ALL rows, not just duplicates), so reassigned UIDs never collide with
-- an existing valid UID. Each duplicate row gets max_seq + its global per-year
-- rank, guaranteeing distinct, free sequence numbers within the year.
WITH dups AS (
    SELECT
        id,
        substr(sample_uid, 5, 4) AS yr,
        ROW_NUMBER() OVER (
            PARTITION BY substr(sample_uid, 5, 4)
            ORDER BY
                CASE WHEN id IN (
                    SELECT MIN(id) FROM (
                        SELECT id, sample_uid, created_at,
                               MIN(created_at || '#' || printf('%020d', id)) OVER (PARTITION BY sample_uid) AS earliest
                        FROM samples
                        WHERE sample_uid != ''
                    )
                    WHERE (created_at || '#' || printf('%020d', id)) = earliest
                    GROUP BY sample_uid
                ) THEN NULL
                ELSE created_at || '#' || printf('%020d', id)
            END
        ) AS rn
    FROM samples
    WHERE sample_uid != ''
      AND sample_uid IN (
          SELECT sample_uid FROM samples
          WHERE sample_uid != ''
          GROUP BY sample_uid
          HAVING COUNT(*) > 1
      )
      AND id NOT IN (
          SELECT MIN(id) FROM (
              SELECT id, sample_uid, created_at,
                     MIN(created_at || '#' || printf('%020d', id)) OVER (PARTITION BY sample_uid) AS earliest
              FROM samples
              WHERE sample_uid != ''
          )
          WHERE (created_at || '#' || printf('%020d', id)) = earliest
          GROUP BY sample_uid
      )
),
year_max AS (
    SELECT
        substr(sample_uid, 5, 4) AS yr,
        MAX(CAST(substr(sample_uid, 10) AS INTEGER)) AS max_seq
    FROM samples
    WHERE sample_uid LIKE 'SMP-____-%'
      AND substr(sample_uid, 10) GLOB '[0-9]*'
    GROUP BY substr(sample_uid, 5, 4)
)
UPDATE samples
SET sample_uid = 'SMP-' || (
        SELECT dups.yr FROM dups WHERE dups.id = samples.id
    ) || '-' || printf('%06d',
        (SELECT COALESCE(year_max.max_seq, 0)
         FROM year_max
         WHERE year_max.yr = (SELECT dups.yr FROM dups WHERE dups.id = samples.id))
        + (SELECT dups.rn FROM dups WHERE dups.id = samples.id)
    )
WHERE id IN (SELECT id FROM dups);

-- Step 2: enforce uniqueness going forward (partial: ignores blank/legacy UIDs).
CREATE UNIQUE INDEX IF NOT EXISTS idx_samples_uid_unique
ON samples(sample_uid)
WHERE sample_uid != '';
