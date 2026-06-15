-- Bring parsed_records.parsed_data_id into line with the uniform ON DELETE
-- CASCADE policy. Historically this FK had no ON DELETE rule and could BLOCK a
-- parent delete with a foreign-key violation. SQLite cannot ALTER a foreign
-- key, so rebuild the table with the standard recipe, preserving all columns,
-- data, and indexes. parsed_records is a leaf table (no other table references
-- it), so the rebuild is safe with foreign_keys on.

CREATE TABLE parsed_records_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parsed_data_id INTEGER NOT NULL,
    raw_data_id INTEGER,
    sample_id INTEGER,
    sample_uid TEXT,
    raw_data_code TEXT,
    data_type TEXT NOT NULL,
    record_index INTEGER,
    primary_key TEXT,
    group_key TEXT,
    x_value REAL,
    y_value REAL,
    numeric_value REAL,
    raw_value TEXT,
    cleaned_value TEXT,
    is_outlier INTEGER DEFAULT 0,
    outlier_reason TEXT,
    die_id TEXT,
    area TEXT,
    row_index INTEGER,
    col_index INTEGER,
    row_header TEXT,
    col_header TEXT,
    row_group TEXT,
    side TEXT,
    direction TEXT,
    dose TEXT,
    location TEXT,
    extra_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(parsed_data_id) REFERENCES parsed_data(id) ON DELETE CASCADE
);

INSERT INTO parsed_records_new SELECT * FROM parsed_records;

DROP TABLE parsed_records;

ALTER TABLE parsed_records_new RENAME TO parsed_records;

CREATE INDEX IF NOT EXISTS idx_parsed_records_parsed_data_id ON parsed_records(parsed_data_id);
CREATE INDEX IF NOT EXISTS idx_parsed_records_raw_data_id ON parsed_records(raw_data_id);
CREATE INDEX IF NOT EXISTS idx_parsed_records_data_type ON parsed_records(data_type);
CREATE INDEX IF NOT EXISTS idx_parsed_records_die_area ON parsed_records(parsed_data_id, die_id, area);
CREATE INDEX IF NOT EXISTS idx_parsed_records_cd_sem_filters ON parsed_records(parsed_data_id, row_group, side, direction, dose, location);
CREATE INDEX IF NOT EXISTS idx_parsed_records_outlier ON parsed_records(parsed_data_id, is_outlier);
