-- Spec 004 Phase 1: the unified Measurements read model.
--
-- Present the two existing measurement stores through one common shape so the
-- Analysis transform (stats / QC / normalize) can operate over ALL measurements
-- -- manually-typed (test_data) and instrument-parsed (parsed_records) -- with
-- NO data migration. This view is additive and read-only: it alters no row and
-- introduces no deletable entity.
--
-- Identity: test_data.id and parsed_records.id overlap, so the view exposes a
-- `source` discriminator ('manual' / 'parsed') plus `source_row_id`, never a
-- bare ambiguous `id`. Consumers key off (source, source_row_id).
--
-- Parsed rows lack metric_name / unit / measured_at columns, so:
--   * metric_name is derived per data_type via a fixed, code-authored CASE
--     (Article VII: no request data) -- cd_sem composes side/direction/row_group;
--     resistance maps to the literal 'resistance'; every other type falls back to
--     data_type. data_type is also kept as its own column so Analysis can group
--     by either.
--   * unit is emitted as '' (deferred; some units live in extra_json).
--   * measured_at falls back to created_at.
-- Rows without a numeric_value are excluded so Analysis math never sees NULLs,
-- matching how run_processing treats test_data.numeric_value today.
--
-- UNION ALL (not UNION): the two sources never collide on (source, source_row_id)
-- and duplicate numeric values must not be silently dropped.
--
-- run_migrations() owns the transaction, so this file contains NO BEGIN/COMMIT.

CREATE VIEW IF NOT EXISTS measurements AS
    SELECT
        'manual'            AS source,
        td.id               AS source_row_id,
        td.sample_id        AS sample_id,
        td.metric_name      AS metric_name,
        td.test_name        AS data_type,
        td.numeric_value    AS numeric_value,
        td.unit             AS unit,
        td.measured_at      AS measured_at,
        td.created_at       AS created_at
    FROM test_data td
    WHERE td.numeric_value IS NOT NULL

    UNION ALL

    SELECT
        'parsed'            AS source,
        pr.id               AS source_row_id,
        pr.sample_id        AS sample_id,
        CASE pr.data_type
            WHEN 'cd_sem' THEN
                'cd_sem'
                || COALESCE('/' || NULLIF(pr.side, ''), '')
                || COALESCE('/' || NULLIF(pr.direction, ''), '')
                || COALESCE(' ' || NULLIF(pr.row_group, ''), '')
            WHEN 'resistance' THEN 'resistance'
            ELSE pr.data_type
        END                 AS metric_name,
        pr.data_type        AS data_type,
        pr.numeric_value    AS numeric_value,
        ''                  AS unit,
        pr.created_at       AS measured_at,
        pr.created_at       AS created_at
    FROM parsed_records pr
    WHERE pr.numeric_value IS NOT NULL;
