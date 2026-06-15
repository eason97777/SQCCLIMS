import hashlib
import json
import re
import sqlite3
from pathlib import Path

import app.config as config
from app.db import add_column_if_missing, connect_db, ensure_schema_migrations, process_records_has_legacy_unique, samples_has_legacy_code_unique
from app.validation import now_iso


def migration_version(filename):
    match = re.match(r"^(\d+)_.*\.sql$", filename)
    if not match:
        raise ValueError(
            f"Invalid migration filename: {filename}. Expected format like 001_description.sql"
        )
    return match.group(1)

def migration_checksum(path):
    content = path.read_text(encoding="utf-8")
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

def iter_sql_statements(sql):
    buffer = []
    for line in sql.splitlines():
        buffer.append(line)
        candidate = "\n".join(buffer).strip()
        if candidate and sqlite3.complete_statement(candidate):
            yield candidate
            buffer = []
    remainder = "\n".join(buffer).strip()
    if remainder:
        yield remainder

def run_migrations():
    config.MIGRATIONS_DIR.mkdir(exist_ok=True)
    migration_files = sorted(config.MIGRATIONS_DIR.glob("*.sql"), key=lambda path: path.name)

    with connect_db() as conn:
        ensure_schema_migrations(conn)
        applied_rows = conn.execute(
            "SELECT version, filename, checksum FROM schema_migrations"
        ).fetchall()
        applied = {row["version"]: row for row in applied_rows}

        pending_count = 0
        for migration_file in migration_files:
            filename = migration_file.name
            version = migration_version(filename)
            checksum = migration_checksum(migration_file)
            applied_row = applied.get(version)

            if applied_row:
                if applied_row["checksum"] != checksum:
                    raise RuntimeError(
                        "Migration checksum mismatch. "
                        f"File: {filename}; "
                        f"database checksum: {applied_row['checksum']}; "
                        f"current checksum: {checksum}. "
                        "Executed migrations must not be modified; add a new migration instead."
                    )
                continue

            pending_count += 1
            print(f"Running migration: {filename}")
            try:
                sql = migration_file.read_text(encoding="utf-8")
                conn.execute("BEGIN")
                for statement in iter_sql_statements(sql):
                    conn.execute(statement)
                conn.execute(
                    """
                    INSERT INTO schema_migrations (version, filename, checksum, applied_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (version, filename, checksum, now_iso()),
                )
                conn.execute("COMMIT")
                print(f"Migration applied: {filename}")
            except Exception as exc:
                conn.execute("ROLLBACK")
                raise RuntimeError(f"Migration failed: {filename}: {exc}") from exc

        if pending_count == 0:
            print("No pending migrations.")

def init_db():
    with connect_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sample_uid TEXT NOT NULL DEFAULT '',
                sample_display_code TEXT NOT NULL DEFAULT '',
                sample_code TEXT NOT NULL,
                name TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT '',
                batch TEXT NOT NULL DEFAULT '',
                owner TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT '待测试',
                received_at TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(sample_display_code)
            );

            CREATE TABLE IF NOT EXISTS test_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sample_id INTEGER NOT NULL,
                test_name TEXT NOT NULL,
                metric_name TEXT NOT NULL,
                numeric_value REAL NOT NULL,
                unit TEXT NOT NULL DEFAULT '',
                measured_at TEXT NOT NULL,
                operator TEXT NOT NULL DEFAULT '',
                environment TEXT NOT NULL DEFAULT '',
                raw_note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY(sample_id) REFERENCES samples(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS characterization_collections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sample_id INTEGER NOT NULL,
                category TEXT NOT NULL DEFAULT '',
                name TEXT NOT NULL,
                technique TEXT NOT NULL DEFAULT '',
                instrument TEXT NOT NULL DEFAULT '',
                captured_at TEXT NOT NULL DEFAULT '',
                operator TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                storage_dir TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(sample_id) REFERENCES samples(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS characterization_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                collection_id INTEGER,
                sample_id INTEGER NOT NULL,
                category TEXT NOT NULL DEFAULT '',
                technique TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL DEFAULT '',
                original_filename TEXT NOT NULL,
                stored_filename TEXT NOT NULL,
                storage_path TEXT NOT NULL,
                mime_type TEXT NOT NULL DEFAULT '',
                file_size INTEGER NOT NULL DEFAULT 0,
                relative_path TEXT NOT NULL DEFAULT '',
                thumbnail_path TEXT NOT NULL DEFAULT '',
                captured_at TEXT NOT NULL DEFAULT '',
                operator TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY(collection_id) REFERENCES characterization_collections(id) ON DELETE CASCADE,
                FOREIGN KEY(sample_id) REFERENCES samples(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS performance_datasets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sample_id INTEGER NOT NULL,
                aliquot_code TEXT NOT NULL DEFAULT '',
                dataset_name TEXT NOT NULL,
                test_type TEXT NOT NULL DEFAULT '',
                data_format TEXT NOT NULL DEFAULT '',
                source_folder_name TEXT NOT NULL DEFAULT '',
                storage_dir TEXT NOT NULL DEFAULT '',
                file_count INTEGER NOT NULL DEFAULT 0,
                total_bytes INTEGER NOT NULL DEFAULT 0,
                collected_at TEXT NOT NULL DEFAULT '',
                operator TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT '待处理',
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY(sample_id) REFERENCES samples(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS performance_dataset_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dataset_id INTEGER NOT NULL,
                relative_path TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                stored_filename TEXT NOT NULL,
                storage_path TEXT NOT NULL,
                mime_type TEXT NOT NULL DEFAULT '',
                file_size INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY(dataset_id) REFERENCES performance_datasets(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS processing_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_name TEXT NOT NULL,
                method TEXT NOT NULL,
                sample_id INTEGER,
                parameters_json TEXT NOT NULL,
                result_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(sample_id) REFERENCES samples(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS process_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sample_id INTEGER NOT NULL,
                sample_uid TEXT NOT NULL DEFAULT '',
                sample_display_code TEXT NOT NULL DEFAULT '',
                stage TEXT NOT NULL,
                layer_name TEXT NOT NULL DEFAULT '默认图层',
                record_no INTEGER NOT NULL DEFAULT 1,
                record_label TEXT NOT NULL DEFAULT '第1次记录',
                substrate_type TEXT NOT NULL DEFAULT '',
                resistance_type TEXT NOT NULL DEFAULT '',
                wafer_thickness TEXT NOT NULL DEFAULT '',
                details_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'draft',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(sample_id) REFERENCES samples(id) ON DELETE CASCADE,
                UNIQUE(sample_id, stage, layer_name, record_no)
            );

            CREATE TABLE IF NOT EXISTS raw_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sample_id INTEGER NOT NULL,
                sample_uid TEXT NOT NULL DEFAULT '',
                sample_display_code TEXT NOT NULL DEFAULT '',
                raw_data_code TEXT NOT NULL UNIQUE,
                raw_data_name TEXT NOT NULL,
                data_type TEXT NOT NULL,
                data_category TEXT NOT NULL DEFAULT '',
                source_type TEXT NOT NULL DEFAULT '',
                instrument TEXT NOT NULL DEFAULT '',
                operator TEXT NOT NULL DEFAULT '',
                measured_at TEXT NOT NULL DEFAULT '',
                parser_status TEXT NOT NULL DEFAULT 'not_parsed',
                status TEXT NOT NULL DEFAULT 'imported',
                file_count INTEGER NOT NULL DEFAULT 0,
                total_size INTEGER NOT NULL DEFAULT 0,
                storage_path TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(sample_id) REFERENCES samples(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS raw_data_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                raw_data_id INTEGER NOT NULL,
                original_filename TEXT NOT NULL,
                stored_filename TEXT NOT NULL,
                relative_path TEXT NOT NULL DEFAULT '',
                file_path TEXT NOT NULL,
                file_ext TEXT NOT NULL DEFAULT '',
                mime_type TEXT NOT NULL DEFAULT '',
                file_size INTEGER NOT NULL DEFAULT 0,
                sha256 TEXT NOT NULL DEFAULT '',
                file_role TEXT NOT NULL DEFAULT 'raw',
                preview_supported INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY(raw_data_id) REFERENCES raw_data(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS parsed_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                raw_data_id INTEGER NOT NULL,
                sample_id INTEGER NOT NULL,
                sample_uid TEXT NOT NULL DEFAULT '',
                sample_display_code TEXT NOT NULL DEFAULT '',
                raw_data_code TEXT NOT NULL DEFAULT '',
                data_type TEXT NOT NULL,
                parser_name TEXT NOT NULL DEFAULT '',
                parser_version TEXT NOT NULL DEFAULT '',
                parsed_status TEXT NOT NULL DEFAULT 'success',
                schema_version TEXT NOT NULL DEFAULT '1.0',
                records_json TEXT NOT NULL DEFAULT '[]',
                summary_json TEXT NOT NULL DEFAULT '{}',
                record_count INTEGER NOT NULL DEFAULT 0,
                plots_json TEXT NOT NULL DEFAULT '[]',
                warnings_json TEXT NOT NULL DEFAULT '[]',
                errors_json TEXT NOT NULL DEFAULT '[]',
                output_file_path TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT '',
                FOREIGN KEY(raw_data_id) REFERENCES raw_data(id) ON DELETE CASCADE,
                FOREIGN KEY(sample_id) REFERENCES samples(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS parsed_records (
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
                FOREIGN KEY(parsed_data_id) REFERENCES parsed_data(id)
            );

            CREATE TABLE IF NOT EXISTS processing_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_type TEXT NOT NULL,
                job_name TEXT NOT NULL DEFAULT '',
                raw_data_id INTEGER,
                parsed_data_id INTEGER,
                sample_id INTEGER,
                sample_uid TEXT NOT NULL DEFAULT '',
                data_type TEXT NOT NULL DEFAULT '',
                script_name TEXT NOT NULL DEFAULT '',
                script_version TEXT NOT NULL DEFAULT '',
                input_json TEXT NOT NULL DEFAULT '{}',
                output_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT '',
                error_message TEXT NOT NULL DEFAULT '',
                started_at TEXT NOT NULL DEFAULT '',
                finished_at TEXT NOT NULL DEFAULT '',
                FOREIGN KEY(raw_data_id) REFERENCES raw_data(id) ON DELETE SET NULL,
                FOREIGN KEY(parsed_data_id) REFERENCES parsed_data(id) ON DELETE SET NULL,
                FOREIGN KEY(sample_id) REFERENCES samples(id) ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_test_data_sample ON test_data(sample_id);
            CREATE INDEX IF NOT EXISTS idx_test_data_metric ON test_data(metric_name);
            CREATE INDEX IF NOT EXISTS idx_characterization_collection_sample ON characterization_collections(sample_id);
            CREATE INDEX IF NOT EXISTS idx_characterization_collection_category ON characterization_collections(category);
            CREATE INDEX IF NOT EXISTS idx_characterization_sample ON characterization_files(sample_id);
            CREATE INDEX IF NOT EXISTS idx_characterization_category ON characterization_files(category);
            CREATE INDEX IF NOT EXISTS idx_performance_dataset_sample ON performance_datasets(sample_id);
            CREATE INDEX IF NOT EXISTS idx_performance_file_dataset ON performance_dataset_files(dataset_id);
            CREATE INDEX IF NOT EXISTS idx_processing_created ON processing_results(created_at);
            CREATE INDEX IF NOT EXISTS idx_process_records_sample ON process_records(sample_id);
            CREATE INDEX IF NOT EXISTS idx_process_records_stage ON process_records(stage);
            CREATE INDEX IF NOT EXISTS idx_raw_data_sample ON raw_data(sample_id);
            CREATE INDEX IF NOT EXISTS idx_raw_data_type ON raw_data(data_type);
            CREATE INDEX IF NOT EXISTS idx_raw_data_code ON raw_data(raw_data_code);
            CREATE INDEX IF NOT EXISTS idx_raw_data_file_parent ON raw_data_files(raw_data_id);
            CREATE INDEX IF NOT EXISTS idx_parsed_data_raw ON parsed_data(raw_data_id);
            CREATE INDEX IF NOT EXISTS idx_parsed_data_sample ON parsed_data(sample_id);
            CREATE INDEX IF NOT EXISTS idx_parsed_data_type ON parsed_data(data_type);
            CREATE INDEX IF NOT EXISTS idx_parsed_records_parsed_data_id ON parsed_records(parsed_data_id);
            CREATE INDEX IF NOT EXISTS idx_parsed_records_raw_data_id ON parsed_records(raw_data_id);
            CREATE INDEX IF NOT EXISTS idx_parsed_records_data_type ON parsed_records(data_type);
            CREATE INDEX IF NOT EXISTS idx_parsed_records_die_area ON parsed_records(parsed_data_id, die_id, area);
            CREATE INDEX IF NOT EXISTS idx_parsed_records_cd_sem_filters ON parsed_records(parsed_data_id, row_group, side, direction, dose, location);
            CREATE INDEX IF NOT EXISTS idx_parsed_records_outlier ON parsed_records(parsed_data_id, is_outlier);
            CREATE INDEX IF NOT EXISTS idx_processing_jobs_raw ON processing_jobs(raw_data_id);
            CREATE INDEX IF NOT EXISTS idx_processing_jobs_sample ON processing_jobs(sample_id);
            CREATE INDEX IF NOT EXISTS idx_processing_jobs_type ON processing_jobs(job_type);
            """
        )
        migrate_db(conn)

def extract_process_layer_name(details_json):
    try:
        details = json.loads(details_json or "{}")
    except json.JSONDecodeError:
        details = {}
    if not isinstance(details, dict):
        return "默认图层"
    layer_name = str(details.get("layer") or details.get("processLayer") or "").strip()
    return layer_name or "默认图层"

def normalize_process_layer_name(value):
    layer_name = str(value or "").strip()
    return layer_name or "默认图层"

def ensure_process_records_instance_unique(conn):
    add_column_if_missing(conn, "process_records", "layer_name", "TEXT NOT NULL DEFAULT '默认图层'")
    add_column_if_missing(conn, "process_records", "record_no", "INTEGER NOT NULL DEFAULT 1")
    add_column_if_missing(conn, "process_records", "record_label", "TEXT NOT NULL DEFAULT '第1次记录'")

    rows = conn.execute("SELECT id, details_json FROM process_records").fetchall()
    for row in rows:
        layer_name = extract_process_layer_name(row["details_json"])
        conn.execute(
            """
            UPDATE process_records
            SET layer_name = CASE WHEN TRIM(COALESCE(layer_name, '')) = '' THEN ? ELSE layer_name END,
                record_no = CASE WHEN record_no IS NULL OR record_no < 1 THEN 1 ELSE record_no END,
                record_label = CASE WHEN TRIM(COALESCE(record_label, '')) = '' THEN '第1次记录' ELSE record_label END
            WHERE id = ?
            """,
            (layer_name, row["id"]),
        )

    if process_records_has_legacy_unique(conn):
        conn.execute("PRAGMA foreign_keys = OFF")
        try:
            conn.executescript(
                """
                CREATE TABLE process_records_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sample_id INTEGER NOT NULL,
                    sample_uid TEXT NOT NULL DEFAULT '',
                    sample_display_code TEXT NOT NULL DEFAULT '',
                    stage TEXT NOT NULL,
                    layer_name TEXT NOT NULL DEFAULT '默认图层',
                    record_no INTEGER NOT NULL DEFAULT 1,
                    record_label TEXT NOT NULL DEFAULT '第1次记录',
                    substrate_type TEXT NOT NULL DEFAULT '',
                    resistance_type TEXT NOT NULL DEFAULT '',
                    wafer_thickness TEXT NOT NULL DEFAULT '',
                    details_json TEXT NOT NULL DEFAULT '{}',
                    status TEXT NOT NULL DEFAULT 'draft',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(sample_id) REFERENCES samples(id) ON DELETE CASCADE,
                    UNIQUE(sample_id, stage, layer_name, record_no)
                );

                INSERT INTO process_records_new (
                    id, sample_id, sample_uid, sample_display_code, stage,
                    layer_name, record_no, record_label, substrate_type,
                    resistance_type, wafer_thickness, details_json, status,
                    created_at, updated_at
                )
                SELECT
                    id, sample_id, sample_uid, sample_display_code, stage,
                    CASE WHEN TRIM(COALESCE(layer_name, '')) = '' THEN '默认图层' ELSE layer_name END,
                    CASE WHEN record_no IS NULL OR record_no < 1 THEN 1 ELSE record_no END,
                    CASE WHEN TRIM(COALESCE(record_label, '')) = '' THEN '第1次记录' ELSE record_label END,
                    substrate_type, resistance_type, wafer_thickness, details_json,
                    status, created_at, updated_at
                FROM process_records;

                DROP TABLE process_records;
                ALTER TABLE process_records_new RENAME TO process_records;
                """
            )
        finally:
            conn.execute("PRAGMA foreign_keys = ON")

    conn.execute("DROP INDEX IF EXISTS idx_process_records_instance_unique")
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_process_records_lookup
        ON process_records(sample_id, stage, layer_name)
        """
    )

def ensure_samples_composite_unique(conn):
    if not samples_has_legacy_code_unique(conn):
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_samples_identity_unique
            ON samples(sample_code, name, category, batch)
            """
        )
        return

    duplicate = conn.execute(
        """
        SELECT sample_code, name, category, batch, COUNT(*) AS count
        FROM samples
        GROUP BY sample_code, name, category, batch
        HAVING count > 1
        LIMIT 1
        """
    ).fetchone()
    if duplicate:
        raise RuntimeError("duplicate sample identity exists; cannot migrate samples")

    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.executescript(
            """
            CREATE TABLE samples_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sample_uid TEXT NOT NULL DEFAULT '',
                sample_display_code TEXT NOT NULL DEFAULT '',
                sample_code TEXT NOT NULL,
                name TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT '',
                batch TEXT NOT NULL DEFAULT '',
                owner TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT '',
                received_at TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(sample_display_code)
            );

            INSERT INTO samples_new (
                id, sample_uid, sample_display_code, sample_code, name, category,
                batch, owner, status, received_at, notes, created_at, updated_at
            )
            SELECT
                id, '', '', sample_code, name, category, batch, owner, status,
                received_at, notes, created_at, updated_at
            FROM samples;

            DROP TABLE samples;
            ALTER TABLE samples_new RENAME TO samples;
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_samples_identity_unique
            ON samples(sample_code, name, category, batch)
            """
        )
    finally:
        conn.execute("PRAGMA foreign_keys = ON")

def ensure_characterization_collections(conn):
    rows = conn.execute(
        """
        SELECT cf.*, s.sample_code
        FROM characterization_files cf
        JOIN samples s ON s.id = cf.sample_id
        WHERE cf.collection_id IS NULL
        ORDER BY cf.sample_id, cf.category, cf.technique, cf.captured_at, cf.created_at, cf.id
        """
    ).fetchall()
    collection_cache = {}
    for row in rows:
        key = (
            row["sample_id"],
            row["category"] or "未分类",
            row["technique"] or "",
            row["captured_at"] or "",
            row["operator"] or "",
        )
        collection_id = collection_cache.get(key)
        if collection_id is None:
            category = key[1]
            technique = key[2]
            captured_at = key[3]
            name_parts = [part for part in (technique, category, captured_at) if part]
            collection_name = " / ".join(name_parts) or row["title"] or "未命名表征数据包"
            storage_dir = str(Path(row["storage_path"]).parent) if row["storage_path"] else ""
            timestamp = row["created_at"] or now_iso()
            cursor = conn.execute(
                """
                INSERT INTO characterization_collections (
                    sample_id, category, name, technique, instrument, captured_at,
                    operator, notes, storage_dir, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["sample_id"],
                    category,
                    collection_name,
                    technique,
                    "",
                    captured_at,
                    row["operator"] or "",
                    "由已有表征文件自动生成",
                    storage_dir,
                    timestamp,
                    timestamp,
                ),
            )
            collection_id = cursor.lastrowid
            collection_cache[key] = collection_id

        relative_path = row["relative_path"] if "relative_path" in row.keys() and row["relative_path"] else row["original_filename"]
        conn.execute(
            """
            UPDATE characterization_files
            SET collection_id = ?, relative_path = ?
            WHERE id = ?
            """,
            (collection_id, relative_path, row["id"]),
        )

def migrate_db(conn):
    ensure_samples_composite_unique(conn)
    add_column_if_missing(conn, "samples", "sample_uid", "TEXT NOT NULL DEFAULT ''")
    add_column_if_missing(conn, "samples", "sample_display_code", "TEXT NOT NULL DEFAULT ''")
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_samples_display_code_unique
        ON samples(sample_display_code)
        WHERE sample_display_code != ''
        """
    )
    add_column_if_missing(conn, "characterization_files", "collection_id", "INTEGER")
    add_column_if_missing(conn, "characterization_files", "relative_path", "TEXT NOT NULL DEFAULT ''")
    add_column_if_missing(conn, "characterization_files", "thumbnail_path", "TEXT NOT NULL DEFAULT ''")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_characterization_file_collection ON characterization_files(collection_id)")
    add_column_if_missing(conn, "process_records", "details_json", "TEXT NOT NULL DEFAULT '{}'")
    ensure_process_records_instance_unique(conn)
    add_column_if_missing(conn, "parsed_data", "record_count", "INTEGER NOT NULL DEFAULT 0")
    add_column_if_missing(conn, "parsed_data", "updated_at", "TEXT NOT NULL DEFAULT ''")
    ensure_characterization_collections(conn)
