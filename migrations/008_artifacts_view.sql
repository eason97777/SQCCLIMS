-- Spec 004 Phase 2: the unified Artifacts read model (list only).
--
-- Present performance datasets alongside raw-data in one Artifacts LIST, so an
-- operator sees a single "files attached to a sample" concept -- WITHOUT moving
-- data. Additive, read-only: the source tables are read in place, no row/file is
-- copied or altered, and no deletable entity is introduced.
--
-- Scope: this view backs the LIST query only. Artifact detail, file listing,
-- download, and delete keep using the existing per-source endpoints (raw-data for
-- source='raw_data'; performance for source='performance'); the frontend routes a
-- row's actions by `source`. The two detail shapes genuinely differ, so unifying
-- the list (not the detail) is deliberate (Article X). No cross-source file view.
--
-- Identity: raw_data.id and performance_datasets.id overlap, so the view exposes a
-- `source` discriminator ('raw_data' / 'performance') plus `source_row_id`; any
-- consumer that links to or acts on a row keys off (source, source_row_id).
--
-- Columns mirror raw_data's shape so the existing list renderer works unchanged.
-- The performance branch maps into that shape: total_bytes->total_size,
-- storage_dir->storage_path, collected_at->measured_at, dataset_name->raw_data_name;
-- performance has no code, so raw_data_code is a readable synthetic label
-- ('PERF-<id>'); its aliquot_code/test_type/data_format/source_folder_name have no
-- raw_data home and are surfaced via a code-authored json_object metadata_json
-- (Article VII: no request data). raw_data_files vs performance_dataset_files are
-- NOT unified (file listing stays per-source).
--
-- run_migrations() owns the transaction, so this file contains NO BEGIN/COMMIT.

CREATE VIEW IF NOT EXISTS artifacts AS
    SELECT
        'raw_data'              AS source,
        rd.id                   AS source_row_id,
        rd.sample_id            AS sample_id,
        rd.sample_uid           AS sample_uid,
        rd.sample_display_code  AS sample_display_code,
        rd.raw_data_code        AS raw_data_code,
        rd.raw_data_name        AS raw_data_name,
        rd.data_type            AS data_type,
        rd.data_category        AS data_category,
        rd.source_type          AS source_type,
        rd.instrument           AS instrument,
        rd.operator             AS operator,
        rd.measured_at          AS measured_at,
        rd.parser_status        AS parser_status,
        rd.status               AS status,
        rd.file_count           AS file_count,
        rd.total_size           AS total_size,
        rd.storage_path         AS storage_path,
        rd.metadata_json        AS metadata_json,
        rd.notes                AS notes,
        rd.created_at           AS created_at,
        rd.updated_at           AS updated_at
    FROM raw_data rd

    UNION ALL

    SELECT
        'performance'           AS source,
        pd.id                   AS source_row_id,
        pd.sample_id            AS sample_id,
        s.sample_uid            AS sample_uid,
        s.sample_display_code   AS sample_display_code,
        'PERF-' || pd.id        AS raw_data_code,
        pd.dataset_name         AS raw_data_name,
        'performance'           AS data_type,
        'performance'           AS data_category,
        pd.data_format          AS source_type,
        ''                      AS instrument,
        pd.operator             AS operator,
        pd.collected_at         AS measured_at,
        'not_parsed'            AS parser_status,
        pd.status               AS status,
        pd.file_count           AS file_count,
        pd.total_bytes          AS total_size,
        pd.storage_dir          AS storage_path,
        json_object(
            'aliquot_code',       pd.aliquot_code,
            'test_type',          pd.test_type,
            'data_format',        pd.data_format,
            'source_folder_name', pd.source_folder_name
        )                       AS metadata_json,
        pd.notes                AS notes,
        pd.created_at           AS created_at,
        pd.created_at           AS updated_at
    FROM performance_datasets pd
    JOIN samples s ON s.id = pd.sample_id;
