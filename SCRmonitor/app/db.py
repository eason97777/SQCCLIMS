import sqlite3

import app.config as config


def connect_db():
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def ensure_schema_migrations(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            checksum TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
        """
    )

def table_columns(conn, table_name):
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}

def add_column_if_missing(conn, table_name, column_name, definition):
    if column_name not in table_columns(conn, table_name):
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")

def unique_index_columns(conn, index_name):
    rows = conn.execute(f"PRAGMA index_info({index_name})").fetchall()
    return [row["name"] for row in rows]

def samples_has_legacy_code_unique(conn):
    for row in conn.execute("PRAGMA index_list(samples)").fetchall():
        if not row["unique"]:
            continue
        if unique_index_columns(conn, row["name"]) == ["sample_code"]:
            return True
    return False

def process_records_has_legacy_unique(conn):
    for row in conn.execute("PRAGMA index_list(process_records)").fetchall():
        if not row["unique"]:
            continue
        if unique_index_columns(conn, row["name"]) == ["sample_id", "stage"]:
            return True
    return False
