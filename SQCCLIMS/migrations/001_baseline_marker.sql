-- Baseline marker.
-- Existing schema is created by init_db().
-- Future schema changes should be added as new migrations.

CREATE TABLE IF NOT EXISTS migration_baseline_marker (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO migration_baseline_marker (id) VALUES (1);
