-- Deletion-audit snapshots for lightweight recoverability and audit trail.

CREATE TABLE IF NOT EXISTS deletion_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name TEXT NOT NULL,
    row_pk TEXT,
    snapshot_json TEXT NOT NULL,
    deleted_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_deletion_audit_table_deleted_at
    ON deletion_audit(table_name, deleted_at);
