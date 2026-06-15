#!/usr/bin/env python3
import argparse
import cgi
import csv
import hashlib
import json
import math
import mimetypes
import os
import re
import shutil
import sqlite3
import statistics
import uuid
import zipfile
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from parsers.cd_template_parser import parse_cd_template_csv
from parsers.cd_violin_visualizer import SCRIPT_NAME as CD_VIOLIN_SCRIPT_NAME
from parsers.cd_violin_visualizer import SCRIPT_VERSION as CD_VIOLIN_SCRIPT_VERSION
from parsers.cd_violin_visualizer import generate_cd_violin_visualization
from parsers.resistance_csv_parser import parse_resistance_csv
from parsers.resistance_heatmap_visualizer import SCRIPT_NAME as RESISTANCE_HEATMAP_SCRIPT_NAME
from parsers.resistance_heatmap_visualizer import SCRIPT_VERSION as RESISTANCE_HEATMAP_SCRIPT_VERSION
from parsers.resistance_heatmap_visualizer import generate_resistance_heatmap_visualization


ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("JIQT_DATA_DIR", ROOT / "data")).expanduser().resolve()
DB_PATH = DATA_DIR / "sample_testing.db"
STATIC_DIR = ROOT / "frontend" / "dist"
UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = DATA_DIR / "outputs"
LOG_DIR = DATA_DIR / "logs"
TEMPLATE_DIR = ROOT / "templates"
MIGRATIONS_DIR = ROOT / "migrations"
ALLOWED_TEMPLATE_FILES = {"cd_sem_template.csv"}


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def configure_paths(data_dir=None):
    global DATA_DIR, DB_PATH, UPLOAD_DIR, OUTPUT_DIR, LOG_DIR
    if data_dir:
        DATA_DIR = Path(data_dir).expanduser().resolve()
    DB_PATH = DATA_DIR / "sample_testing.db"
    UPLOAD_DIR = DATA_DIR / "uploads"
    OUTPUT_DIR = DATA_DIR / "outputs"
    LOG_DIR = DATA_DIR / "logs"


def connect_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
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
    MIGRATIONS_DIR.mkdir(exist_ok=True)
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"), key=lambda path: path.name)

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


class ConflictError(Exception):
    pass


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


def row_dict(row):
    return dict(row) if row is not None else None


def rows_dict(rows):
    return [dict(row) for row in rows]


def require_text(payload, key):
    value = str(payload.get(key, "")).strip()
    if not value:
        raise ValueError(f"{key} is required")
    return value


def optional_text(payload, key):
    return str(payload.get(key, "") or "").strip()


GARBLED_TEXT_MARKERS = ("�", "锟", "鎬", "鏍", "����")


def has_garbled_text(value):
    text = str(value or "")
    return any(marker in text for marker in GARBLED_TEXT_MARKERS)


def has_only_punctuation(value):
    return re.search(r"[A-Za-z0-9\u4e00-\u9fff]", str(value or "")) is None


def normalize_sample_text(value):
    return re.sub(r"\s+", " ", str(value or "").strip())


def build_sample_display_code(sample):
    return "-".join(
        [
            normalize_sample_text(sample.get("sample_code")) or "-",
            normalize_sample_text(sample.get("name")) or "-",
            normalize_sample_text(sample.get("category")) or "-",
            normalize_sample_text(sample.get("batch")) or "-",
        ]
    )


def generate_sample_uid(conn, year=None):
    year = year or datetime.now().year
    prefix = f"SMP-{year}-"
    rows = conn.execute(
        "SELECT sample_uid FROM samples WHERE sample_uid LIKE ?",
        (f"{prefix}%",),
    ).fetchall()
    max_seq = 0
    for row in rows:
        suffix = str(row["sample_uid"] or "").replace(prefix, "", 1)
        if suffix.isdigit():
            max_seq = max(max_seq, int(suffix))
    return f"{prefix}{max_seq + 1:06d}"


def validate_sample_payload(conn, sample, sample_id=None):
    required_fields = [
        ("sample_code", "项目编号不能为空"),
        ("name", "样品名称不能为空"),
        ("category", "工艺类型不能为空"),
        ("batch", "样品序号不能为空"),
        ("status", "样品状态不能为空"),
    ]
    for key, message in required_fields:
        sample[key] = normalize_sample_text(sample.get(key))
        if not sample[key]:
            raise ValueError(message)

    sample["owner"] = normalize_sample_text(sample.get("owner"))
    sample["notes"] = str(sample.get("notes") or "").strip()
    sample["sample_display_code"] = build_sample_display_code(sample)

    if any(
        has_garbled_text(sample.get(key, ""))
        for key in ("sample_code", "name", "category", "batch", "owner", "status", "notes")
    ):
        raise ValueError("检测到疑似乱码字符，请检查字段内容后再保存。")

    sample_seq = str(sample.get("batch", "")).strip()
    if len(sample_seq) > 32 or has_only_punctuation(sample_seq):
        raise ValueError("样品序号格式可能不规范，请检查。")

    duplicate = conn.execute(
        """
        SELECT id FROM samples
        WHERE sample_display_code = ?
          AND id != ?
        LIMIT 1
        """,
        (sample["sample_display_code"], sample_id or 0),
    ).fetchone()
    if duplicate:
        raise ValueError("当前样品显示编号已存在，请修改项目编号、样品名称、工艺类型或样品序号。")

def parse_float(value, field_name):
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be numeric")
    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be finite")
    return number


def sample_exists(conn, sample_id):
    row = conn.execute("SELECT id FROM samples WHERE id = ?", (sample_id,)).fetchone()
    return row is not None


def get_samples(query_params):
    query = query_params.get("query", [""])[0].strip()
    status = query_params.get("status", [""])[0].strip()
    where = []
    args = []
    if query:
        like = f"%{query}%"
        where.append(
            "(s.sample_display_code LIKE ? OR s.sample_uid LIKE ? OR s.sample_code LIKE ? OR s.name LIKE ? OR s.category LIKE ? OR s.batch LIKE ? OR s.owner LIKE ?)"
        )
        args.extend([like, like, like, like, like, like, like])
    if status:
        where.append("s.status = ?")
        args.append(status)

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    sql = f"""
        SELECT
            s.*,
            COUNT(td.id) AS data_count,
            MAX(td.measured_at) AS last_measured_at
        FROM samples s
        LEFT JOIN test_data td ON td.sample_id = s.id
        {where_sql}
        GROUP BY s.id
        ORDER BY s.created_at DESC, s.id DESC
    """
    with connect_db() as conn:
        return rows_dict(conn.execute(sql, args).fetchall())


def process_record_payload(row):
    if row is None:
        return None
    record = row_dict(row)
    details_json = record.pop("details_json", "{}") or "{}"
    try:
        record["details"] = json.loads(details_json)
    except json.JSONDecodeError:
        record["details"] = {}
    record["sample"] = {
        "id": record.pop("sample_id"),
        "sample_uid": record.pop("sample_uid"),
        "sample_display_code": record.pop("sample_display_code"),
        "sample_code": record.pop("sample_code", ""),
        "name": record.pop("name", ""),
        "category": record.pop("category", ""),
        "batch": record.pop("batch", ""),
        "owner": record.pop("owner", ""),
        "status": record.pop("sample_status", ""),
    }
    return record


def find_process_sample(conn, query_text):
    query_text = normalize_sample_text(query_text)
    if not query_text:
        raise ValueError("sample query is required")

    row = conn.execute(
        """
        SELECT * FROM samples
        WHERE sample_display_code = ?
           OR sample_uid = ?
           OR sample_code = ?
           OR name = ?
        ORDER BY updated_at DESC, id DESC
        LIMIT 1
        """,
        (query_text, query_text, query_text, query_text),
    ).fetchone()
    if row:
        return row

    like = f"%{query_text}%"
    return conn.execute(
        """
        SELECT * FROM samples
        WHERE sample_display_code LIKE ?
           OR sample_uid LIKE ?
           OR sample_code LIKE ?
           OR name LIKE ?
        ORDER BY updated_at DESC, id DESC
        LIMIT 1
        """,
        (like, like, like, like),
    ).fetchone()


def get_active_mes_step_for_sample(conn, sample_id):
    return conn.execute(
        """
        SELECT mss.*
        FROM mes_sample_routes msr
        JOIN mes_sample_steps mss ON mss.id = msr.current_sample_step_id
        WHERE msr.sample_id = ?
          AND msr.status != 'completed'
          AND mss.status = 'active'
        ORDER BY msr.created_at DESC, msr.id DESC
        LIMIT 1
        """,
        (sample_id,),
    ).fetchone()


def sample_available_for_process_stage(conn, sample_id, stage):
    sync_mes_route_from_submitted_process_records(conn, sample_id)
    active_step = get_active_mes_step_for_sample(conn, sample_id)
    return bool(active_step and active_step["step_name"] == stage)


def search_process_samples(query_params):
    query_text = normalize_sample_text(query_params.get("query", [""])[0])
    stage = normalize_sample_text(query_params.get("stage", [""])[0])
    with connect_db() as conn:
        if not query_text:
            rows = conn.execute(
                """
                SELECT * FROM samples
                ORDER BY updated_at DESC, id DESC
                LIMIT 20
                """
            ).fetchall()
            filtered = [row for row in rows if not stage or sample_available_for_process_stage(conn, row["id"], stage)]
            return rows_dict(filtered[:5])

        like = f"%{query_text}%"
        rows = conn.execute(
            """
            SELECT * FROM samples
            WHERE sample_display_code LIKE ?
               OR sample_uid LIKE ?
               OR sample_code LIKE ?
               OR name LIKE ?
            ORDER BY updated_at DESC, id DESC
            LIMIT 30
            """,
            (like, like, like, like),
        )
        filtered = [row for row in rows.fetchall() if not stage or sample_available_for_process_stage(conn, row["id"], stage)]
        return rows_dict(filtered[:8])


def search_process_field_suggestions(query_params):
    field = normalize_sample_text(query_params.get("field", [""])[0])
    query_text = normalize_sample_text(query_params.get("query", [""])[0])
    allowed_fields = {
        "substrate_type": "substrate_type",
        "resistance_type": "resistance_type",
        "wafer_thickness": "wafer_thickness",
    }
    column = allowed_fields.get(field)
    if not column:
        raise ValueError("unsupported process field")

    args = []
    where = [f"{column} != ''"]
    if query_text:
        where.append(f"{column} LIKE ?")
        args.append(f"%{query_text}%")

    with connect_db() as conn:
        rows = conn.execute(
            f"""
            SELECT DISTINCT {column} AS value
            FROM process_records
            WHERE {' AND '.join(where)}
            ORDER BY updated_at DESC
            LIMIT 20
            """,
            args,
        ).fetchall()
        return [row["value"] for row in rows]


def search_process_layers(query_params):
    try:
        sample_id = int(query_params.get("sample_id", ["0"])[0] or 0)
    except ValueError:
        sample_id = 0
    query_text = normalize_sample_text(query_params.get("query", [""])[0])
    if sample_id <= 0:
        return []

    with connect_db() as conn:
        rows = conn.execute(
            """
            SELECT layer_name, details_json, updated_at, created_at, id
            FROM process_records
            WHERE sample_id = ?
            ORDER BY updated_at DESC, created_at DESC, id DESC
            """,
            (sample_id,),
        ).fetchall()

    candidates = {}
    for row in rows:
        names = [row["layer_name"]]
        try:
            details = json.loads(row["details_json"] or "{}")
        except json.JSONDecodeError:
            details = {}
        if isinstance(details, dict):
            names.extend([details.get("layer"), details.get("processLayer")])
        for raw_name in names:
            layer = normalize_process_layer_name(raw_name)
            if layer == "默认图层":
                continue
            if query_text and query_text.lower() not in layer.lower():
                continue
            previous = candidates.get(layer)
            sort_key = (row["updated_at"] or "", row["created_at"] or "", row["id"])
            if previous is None or sort_key > previous:
                candidates[layer] = sort_key

    limit = 20 if query_text else 5
    return [
        layer
        for layer, _ in sorted(candidates.items(), key=lambda item: (item[1], item[0]), reverse=True)[:limit]
    ]


def get_process_record(conn, sample_id, stage, layer_name="默认图层", record_no=1):
    return conn.execute(
        """
        SELECT
            pr.*,
            s.sample_code,
            s.name,
            s.category,
            s.batch,
            s.owner,
            s.status AS sample_status
        FROM process_records pr
        JOIN samples s ON s.id = pr.sample_id
        WHERE pr.sample_id = ? AND pr.stage = ? AND pr.layer_name = ? AND pr.record_no = ?
        LIMIT 1
        """,
        (sample_id, stage, layer_name, record_no),
    ).fetchone()


def get_first_process_record(conn, sample_id, stage):
    return conn.execute(
        """
        SELECT
            pr.*,
            s.sample_code,
            s.name,
            s.category,
            s.batch,
            s.owner,
            s.status AS sample_status
        FROM process_records pr
        JOIN samples s ON s.id = pr.sample_id
        WHERE pr.sample_id = ? AND pr.stage = ?
        ORDER BY pr.record_no ASC, pr.created_at ASC, pr.id ASC
        LIMIT 1
        """,
        (sample_id, stage),
    ).fetchone()


def get_process_record_by_id(conn, record_id):
    return conn.execute(
        """
        SELECT
            pr.*,
            s.sample_code,
            s.name,
            s.category,
            s.batch,
            s.owner,
            s.status AS sample_status
        FROM process_records pr
        JOIN samples s ON s.id = pr.sample_id
        WHERE pr.id = ?
        LIMIT 1
        """,
        (record_id,),
    ).fetchone()


def lookup_process_sample(query_params):
    query_text = query_params.get("query", [""])[0]
    stage = query_params.get("stage", ["发料"])[0].strip() or "发料"
    has_record_scope = "layer_name" in query_params or "record_no" in query_params
    layer_name = query_params.get("layer_name", ["默认图层"])[0].strip() or "默认图层"
    try:
        record_no = int(query_params.get("record_no", ["1"])[0] or 1)
    except ValueError:
        record_no = 1
    record_no = max(record_no, 1)
    with connect_db() as conn:
        sample = find_process_sample(conn, query_text)
        if not sample:
            raise ValueError("未找到对应的建档样品")
        sync_mes_route_from_submitted_process_records(conn, sample["id"])
        active_step = get_active_mes_step_for_sample(conn, sample["id"])
        if not active_step:
            raise ValueError("该样品暂无可填写的流程工段")
        if active_step["step_name"] != stage:
            raise ValueError(f"该样品当前应在{active_step['step_name']}段填写，不能在{stage}段操作")
        record = (
            get_process_record(conn, sample["id"], stage, layer_name, record_no)
            if has_record_scope
            else get_first_process_record(conn, sample["id"], stage)
        )
        return {
            "sample": row_dict(sample),
            "record": process_record_payload(record),
        }


def mes_route_template_payload(conn, template_id):
    template = conn.execute(
        "SELECT * FROM mes_route_templates WHERE id = ?",
        (template_id,),
    ).fetchone()
    if not template:
        return None

    layers = rows_dict(
        conn.execute(
            """
            SELECT * FROM mes_route_layers
            WHERE route_template_id = ?
            ORDER BY sequence_no ASC, id ASC
            """,
            (template_id,),
        ).fetchall()
    )
    steps_by_layer = {}
    if layers:
        layer_ids = [layer["id"] for layer in layers]
        placeholders = ",".join("?" for _ in layer_ids)
        step_rows = rows_dict(
            conn.execute(
                f"""
                SELECT * FROM mes_route_steps
                WHERE route_layer_id IN ({placeholders})
                ORDER BY route_layer_id ASC, sequence_no ASC, id ASC
                """,
                layer_ids,
            ).fetchall()
        )
        for step in step_rows:
            steps_by_layer.setdefault(step["route_layer_id"], []).append(step)

    for layer in layers:
        layer["steps"] = steps_by_layer.get(layer["id"], [])

    payload = row_dict(template)
    payload["layers"] = layers
    return payload


def find_mes_route_template(conn, project_code, version=None, status="active"):
    project_code = normalize_sample_text(project_code)
    version = normalize_sample_text(version)
    status = normalize_sample_text(status)
    if not project_code:
        raise ValueError("project_code is required")

    where = ["project_code = ?"]
    args = [project_code]
    if version:
        where.append("version = ?")
        args.append(version)
    if status:
        where.append("status = ?")
        args.append(status)

    return conn.execute(
        f"""
        SELECT * FROM mes_route_templates
        WHERE {' AND '.join(where)}
        ORDER BY updated_at DESC, id DESC
        LIMIT 1
        """,
        args,
    ).fetchone()


def get_mes_route_templates(query_params):
    project_code = normalize_sample_text(query_params.get("project_code", [""])[0])
    status = normalize_sample_text(query_params.get("status", [""])[0])
    args = []
    where = []
    if project_code:
        where.append("project_code = ?")
        args.append(project_code)
    if status:
        where.append("status = ?")
        args.append(status)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    with connect_db() as conn:
        return rows_dict(
            conn.execute(
                f"""
                SELECT
                    rt.*,
                    COUNT(DISTINCT rl.id) AS layer_count,
                    COUNT(rs.id) AS step_count
                FROM mes_route_templates rt
                LEFT JOIN mes_route_layers rl ON rl.route_template_id = rt.id
                LEFT JOIN mes_route_steps rs ON rs.route_layer_id = rl.id
                {where_sql}
                GROUP BY rt.id
                ORDER BY rt.updated_at DESC, rt.id DESC
                """,
                args,
            ).fetchall()
        )


def get_mes_route_template_detail(template_id):
    with connect_db() as conn:
        payload = mes_route_template_payload(conn, template_id)
        if not payload:
            raise LookupError("MES route template not found")
        return payload


def get_mes_route_template_by_project(query_params):
    project_code = query_params.get("project_code", [""])[0]
    version = query_params.get("version", [""])[0]
    status = query_params.get("status", ["active"])[0] or "active"
    with connect_db() as conn:
        template = find_mes_route_template(conn, project_code, version, status)
        if not template:
            raise LookupError("MES route template not found")
        return mes_route_template_payload(conn, template["id"])


def create_mes_route_template(payload):
    project_code = optional_text(payload, "project_code")
    route_name = optional_text(payload, "route_name")
    version = optional_text(payload, "version") or "v1.0"
    status = optional_text(payload, "status") or "active"
    description = optional_text(payload, "description")
    if not project_code:
        raise ValueError("project_code is required")

    timestamp = now_iso()
    with connect_db() as conn:
        existing = find_mes_route_template(conn, project_code, version, "")
        if existing:
            return mes_route_template_payload(conn, existing["id"])

        cursor = conn.execute(
            """
            INSERT INTO mes_route_templates (
                project_code, route_name, version, status, description, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_code,
                route_name or f"{project_code} standard wafer route",
                version,
                status,
                description,
                timestamp,
                timestamp,
            ),
        )
        return mes_route_template_payload(conn, cursor.lastrowid)


def create_mes_route_layer(template_id, payload):
    layer_name = optional_text(payload, "layer_name")
    layer_type = optional_text(payload, "layer_type") or "process_layer"
    note = optional_text(payload, "note")
    if not layer_name:
        raise ValueError("layer_name is required")

    timestamp = now_iso()
    with connect_db() as conn:
        template = conn.execute(
            "SELECT * FROM mes_route_templates WHERE id = ?",
            (template_id,),
        ).fetchone()
        if not template:
            raise LookupError("MES route template not found")

        sequence_no = int(payload.get("sequence_no") or 0)
        if sequence_no <= 0:
            row = conn.execute(
                """
                SELECT COALESCE(MAX(sequence_no), 0) + 1 AS next_sequence_no
                FROM mes_route_layers
                WHERE route_template_id = ?
                """,
                (template_id,),
            ).fetchone()
            sequence_no = row["next_sequence_no"]

        conn.execute(
            """
            INSERT INTO mes_route_layers (
                route_template_id, layer_name, layer_type, sequence_no,
                default_status, note, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, 'pending', ?, ?, ?)
            """,
            (template_id, layer_name, layer_type, sequence_no, note, timestamp, timestamp),
        )
        conn.execute(
            "UPDATE mes_route_templates SET updated_at = ? WHERE id = ?",
            (timestamp, template_id),
        )
        return mes_route_template_payload(conn, template_id)


def create_mes_route_step(layer_id, payload):
    step_name = optional_text(payload, "step_name")
    step_type = optional_text(payload, "step_type") or "process_step"
    default_instruction = optional_text(payload, "default_instruction")
    is_required = 1 if payload.get("is_required", 1) in (1, "1", True, "true") else 0
    if not step_name:
        raise ValueError("step_name is required")

    timestamp = now_iso()
    with connect_db() as conn:
        layer = conn.execute(
            "SELECT * FROM mes_route_layers WHERE id = ?",
            (layer_id,),
        ).fetchone()
        if not layer:
            raise LookupError("MES route layer not found")

        sequence_no = int(payload.get("sequence_no") or 0)
        if sequence_no <= 0:
            row = conn.execute(
                """
                SELECT COALESCE(MAX(sequence_no), 0) + 1 AS next_sequence_no
                FROM mes_route_steps
                WHERE route_layer_id = ?
                """,
                (layer_id,),
            ).fetchone()
            sequence_no = row["next_sequence_no"]

        conn.execute(
            """
            INSERT INTO mes_route_steps (
                route_layer_id, step_name, step_type, sequence_no, is_required,
                default_instruction, default_status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)
            """,
            (
                layer_id,
                step_name,
                step_type,
                sequence_no,
                is_required,
                default_instruction,
                timestamp,
                timestamp,
            ),
        )
        conn.execute(
            "UPDATE mes_route_layers SET updated_at = ? WHERE id = ?",
            (timestamp, layer_id),
        )
        conn.execute(
            "UPDATE mes_route_templates SET updated_at = ? WHERE id = ?",
            (timestamp, layer["route_template_id"]),
        )
        return mes_route_template_payload(conn, layer["route_template_id"])


def mes_sample_route_payload(conn, sample_route_id):
    route = conn.execute(
        """
        SELECT
            sr.*,
            s.sample_uid,
            s.sample_display_code,
            s.sample_code,
            s.name,
            s.category,
            s.batch,
            rt.project_code,
            rt.route_name,
            rt.version AS template_version
        FROM mes_sample_routes sr
        JOIN samples s ON s.id = sr.sample_id
        JOIN mes_route_templates rt ON rt.id = sr.route_template_id
        WHERE sr.id = ?
        """,
        (sample_route_id,),
    ).fetchone()
    if not route:
        return None

    steps = rows_dict(
        conn.execute(
            """
            SELECT *
            FROM mes_sample_steps
            WHERE sample_route_id = ?
            ORDER BY layer_sequence_no ASC, step_sequence_no ASC, id ASC
            """,
            (sample_route_id,),
        ).fetchall()
    )
    payload = row_dict(route)
    payload["steps"] = steps
    return payload


def create_mes_sample_route(payload):
    sample_id = int(payload.get("sample_id") or 0)
    project_code = optional_text(payload, "project_code")
    template_id = int(payload.get("route_template_id") or 0)
    version = optional_text(payload, "version")
    if sample_id <= 0:
        raise ValueError("sample_id is required")

    timestamp = now_iso()
    with connect_db() as conn:
        sample = conn.execute("SELECT * FROM samples WHERE id = ?", (sample_id,)).fetchone()
        if not sample:
            raise LookupError("sample not found")

        template = (
            conn.execute("SELECT * FROM mes_route_templates WHERE id = ?", (template_id,)).fetchone()
            if template_id > 0
            else find_mes_route_template(conn, project_code or sample["sample_code"], version, "active")
        )
        if not template:
            raise LookupError("MES route template not found")

        existing = conn.execute(
            """
            SELECT id FROM mes_sample_routes
            WHERE sample_id = ? AND route_template_id = ? AND route_version = ?
            LIMIT 1
            """,
            (sample_id, template["id"], template["version"]),
        ).fetchone()
        if existing:
            return mes_sample_route_payload(conn, existing["id"])

        layers = conn.execute(
            """
            SELECT * FROM mes_route_layers
            WHERE route_template_id = ?
            ORDER BY sequence_no ASC, id ASC
            """,
            (template["id"],),
        ).fetchall()
        if not layers:
            raise ValueError("MES route template has no layers")

        route_cursor = conn.execute(
            """
            INSERT INTO mes_sample_routes (
                sample_id, route_template_id, route_version, status, created_at, updated_at
            )
            VALUES (?, ?, ?, 'not_started', ?, ?)
            """,
            (sample_id, template["id"], template["version"], timestamp, timestamp),
        )
        sample_route_id = route_cursor.lastrowid
        first_step_id = None

        for layer in layers:
            steps = conn.execute(
                """
                SELECT * FROM mes_route_steps
                WHERE route_layer_id = ?
                ORDER BY sequence_no ASC, id ASC
                """,
                (layer["id"],),
            ).fetchall()
            for step in steps:
                status = "active" if first_step_id is None else "pending"
                cursor = conn.execute(
                    """
                    INSERT INTO mes_sample_steps (
                        sample_route_id, sample_id, route_layer_id, route_step_id,
                        layer_name, step_name, layer_sequence_no, step_sequence_no,
                        status, instruction, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        sample_route_id,
                        sample_id,
                        layer["id"],
                        step["id"],
                        layer["layer_name"],
                        step["step_name"],
                        layer["sequence_no"],
                        step["sequence_no"],
                        status,
                        step["default_instruction"] or "",
                        timestamp,
                        timestamp,
                    ),
                )
                if first_step_id is None:
                    first_step_id = cursor.lastrowid

        if first_step_id is None:
            raise ValueError("MES route template has no steps")

        conn.execute(
            """
            UPDATE mes_sample_routes
            SET current_sample_step_id = ?, status = 'in_progress', updated_at = ?
            WHERE id = ?
            """,
            (first_step_id, timestamp, sample_route_id),
        )
        conn.execute(
            """
            INSERT INTO mes_step_events (
                sample_route_id, sample_step_id, sample_id, event_type,
                from_status, to_status, operator, note, event_at
            )
            VALUES (?, ?, ?, 'route_created', '', 'active', '', '', ?)
            """,
            (sample_route_id, first_step_id, sample_id, timestamp),
        )
        return mes_sample_route_payload(conn, sample_route_id)


def get_mes_sample_route_by_sample(sample_id):
    with connect_db() as conn:
        row = conn.execute(
            """
            SELECT id FROM mes_sample_routes
            WHERE sample_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (sample_id,),
        ).fetchone()
        if not row:
            raise LookupError("MES sample route not found")
        sync_mes_route_from_submitted_process_records(conn, sample_id)
        return mes_sample_route_payload(conn, row["id"])


def update_mes_route_step(step_id, payload):
    default_instruction = optional_text(payload, "default_instruction")
    timestamp = now_iso()

    with connect_db() as conn:
        step = conn.execute(
            """
            SELECT rs.*, rl.route_template_id
            FROM mes_route_steps rs
            JOIN mes_route_layers rl ON rl.id = rs.route_layer_id
            WHERE rs.id = ?
            """,
            (step_id,),
        ).fetchone()
        if not step:
            raise LookupError("MES route step not found")

        conn.execute(
            """
            UPDATE mes_route_steps
            SET default_instruction = ?, updated_at = ?
            WHERE id = ?
            """,
            (default_instruction, timestamp, step_id),
        )
        conn.execute(
            """
            UPDATE mes_route_templates
            SET updated_at = ?
            WHERE id = ?
            """,
            (timestamp, step["route_template_id"]),
        )
        return mes_route_template_payload(conn, step["route_template_id"])


def delete_mes_route_step(step_id):
    timestamp = now_iso()
    with connect_db() as conn:
        step = conn.execute(
            """
            SELECT rs.*, rl.route_template_id
            FROM mes_route_steps rs
            JOIN mes_route_layers rl ON rl.id = rs.route_layer_id
            WHERE rs.id = ?
            """,
            (step_id,),
        ).fetchone()
        if not step:
            raise LookupError("MES route step not found")

        conn.execute("DELETE FROM mes_route_steps WHERE id = ?", (step_id,))
        siblings = conn.execute(
            """
            SELECT id
            FROM mes_route_steps
            WHERE route_layer_id = ?
            ORDER BY sequence_no ASC, id ASC
            """,
            (step["route_layer_id"],),
        ).fetchall()
        for index, sibling in enumerate(siblings, start=1):
            conn.execute(
                "UPDATE mes_route_steps SET sequence_no = ?, updated_at = ? WHERE id = ?",
                (index, timestamp, sibling["id"]),
            )
        conn.execute(
            "UPDATE mes_route_layers SET updated_at = ? WHERE id = ?",
            (timestamp, step["route_layer_id"]),
        )
        conn.execute(
            "UPDATE mes_route_templates SET updated_at = ? WHERE id = ?",
            (timestamp, step["route_template_id"]),
        )
        return mes_route_template_payload(conn, step["route_template_id"])


def advance_mes_sample_route_step(conn, sample_route_id, action, operator="", note=""):
    to_status = "skipped" if action == "skip" else "completed"
    event_type = "step_skipped" if action == "skip" else "step_completed"
    timestamp = now_iso()

    route = conn.execute(
        "SELECT * FROM mes_sample_routes WHERE id = ?",
        (sample_route_id,),
    ).fetchone()
    if not route:
        raise LookupError("MES sample route not found")
    if route["status"] == "completed":
        return mes_sample_route_payload(conn, sample_route_id)

    current_step_id = route["current_sample_step_id"]
    if not current_step_id:
        raise ValueError("MES sample route has no active step")

    current_step = conn.execute(
        "SELECT * FROM mes_sample_steps WHERE id = ? AND sample_route_id = ?",
        (current_step_id, sample_route_id),
    ).fetchone()
    if not current_step:
        raise LookupError("MES active step not found")

    conn.execute(
        """
        UPDATE mes_sample_steps
        SET status = ?, operator = ?, note = ?, completed_at = ?, updated_at = ?
        WHERE id = ?
        """,
        (to_status, operator or "", note or current_step["note"] or "", timestamp, timestamp, current_step_id),
    )
    conn.execute(
        """
        INSERT INTO mes_step_events (
            sample_route_id, sample_step_id, sample_id, event_type,
            from_status, to_status, operator, note, event_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sample_route_id,
            current_step_id,
            route["sample_id"],
            event_type,
            current_step["status"],
            to_status,
            operator or "",
            note or "",
            timestamp,
        ),
    )

    next_step = conn.execute(
        """
        SELECT *
        FROM mes_sample_steps
        WHERE sample_route_id = ?
          AND status = 'pending'
          AND (
            layer_sequence_no > ?
            OR (layer_sequence_no = ? AND step_sequence_no > ?)
            OR (layer_sequence_no = ? AND step_sequence_no = ? AND id > ?)
          )
        ORDER BY layer_sequence_no ASC, step_sequence_no ASC, id ASC
        LIMIT 1
        """,
        (
            sample_route_id,
            current_step["layer_sequence_no"],
            current_step["layer_sequence_no"],
            current_step["step_sequence_no"],
            current_step["layer_sequence_no"],
            current_step["step_sequence_no"],
            current_step_id,
        ),
    ).fetchone()

    if next_step:
        conn.execute(
            """
            UPDATE mes_sample_steps
            SET status = 'active', started_at = COALESCE(started_at, ?), updated_at = ?
            WHERE id = ?
            """,
            (timestamp, timestamp, next_step["id"]),
        )
        conn.execute(
            """
            UPDATE mes_sample_routes
            SET current_sample_step_id = ?, status = 'in_progress', updated_at = ?
            WHERE id = ?
            """,
            (next_step["id"], timestamp, sample_route_id),
        )
        conn.execute(
            """
            INSERT INTO mes_step_events (
                sample_route_id, sample_step_id, sample_id, event_type,
                from_status, to_status, operator, note, event_at
            )
            VALUES (?, ?, ?, 'step_activated', 'pending', 'active', ?, '', ?)
            """,
            (sample_route_id, next_step["id"], route["sample_id"], operator or "", timestamp),
        )
    else:
        conn.execute(
            """
            UPDATE mes_sample_routes
            SET current_sample_step_id = NULL, status = 'completed', updated_at = ?
            WHERE id = ?
            """,
            (timestamp, sample_route_id),
        )

    return mes_sample_route_payload(conn, sample_route_id)


def has_submitted_process_record_for_mes_step(conn, sample_id, step):
    return conn.execute(
        """
        SELECT id
        FROM process_records
        WHERE sample_id = ?
          AND stage = ?
          AND status = 'submitted'
        ORDER BY updated_at DESC, id DESC
        LIMIT 1
        """,
        (sample_id, step["step_name"]),
    ).fetchone()


def sync_mes_route_from_submitted_process_records(conn, sample_id, operator=""):
    route = conn.execute(
        """
        SELECT * FROM mes_sample_routes
        WHERE sample_id = ? AND status != 'completed'
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (sample_id,),
    ).fetchone()
    if not route:
        return None

    advanced_route = None
    while route and route["current_sample_step_id"]:
        current_step = conn.execute(
            """
            SELECT * FROM mes_sample_steps
            WHERE id = ? AND sample_route_id = ? AND status = 'active'
            """,
            (route["current_sample_step_id"], route["id"]),
        ).fetchone()
        if not current_step or not has_submitted_process_record_for_mes_step(conn, sample_id, current_step):
            break

        advanced_route = advance_mes_sample_route_step(
            conn,
            route["id"],
            "complete",
            operator=operator,
            note="已提交工艺记录，自动补偿完成",
        )
        route = conn.execute(
            "SELECT * FROM mes_sample_routes WHERE id = ?",
            (route["id"],),
        ).fetchone()

    return advanced_route


def complete_mes_step_from_process_record(conn, sample_id, layer_name, stage, operator=""):
    route = conn.execute(
        """
        SELECT * FROM mes_sample_routes
        WHERE sample_id = ? AND status != 'completed'
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (sample_id,),
    ).fetchone()
    if not route or not route["current_sample_step_id"]:
        return None

    current_step = conn.execute(
        """
        SELECT * FROM mes_sample_steps
        WHERE id = ? AND sample_route_id = ?
        """,
        (route["current_sample_step_id"], route["id"]),
    ).fetchone()
    if not current_step:
        return None
    if current_step["step_name"] != stage:
        return None

    return advance_mes_sample_route_step(
        conn,
        route["id"],
        "complete",
        operator=operator,
        note="工艺记录提交后自动完成",
    )


def advance_mes_sample_route(sample_route_id, payload):
    action = optional_text(payload, "action")
    if action != "skip":
        raise ValueError("样品建档页仅允许工程师跳过工步，完成状态由工艺记录提交触发")

    operator = optional_text(payload, "operator")
    note = optional_text(payload, "note")
    with connect_db() as conn:
        return advance_mes_sample_route_step(conn, sample_route_id, "skip", operator=operator, note=note)


def save_process_record(payload):
    try:
        process_record_id = int(payload.get("id") or 0)
    except (TypeError, ValueError):
        process_record_id = 0
    sample_id = int(payload.get("sample_id") or 0)
    stage = optional_text(payload, "stage") or "发料"
    status = optional_text(payload, "status") or "draft"
    substrate_type = optional_text(payload, "substrate_type")
    resistance_type = optional_text(payload, "resistance_type")
    wafer_thickness = optional_text(payload, "wafer_thickness")
    details = payload.get("details")
    details_json = json.dumps(details if isinstance(details, dict) else {}, ensure_ascii=False)
    layer_name = optional_text(payload, "layer_name") or extract_process_layer_name(details_json)
    try:
        record_no = int(payload.get("record_no") or 1)
    except (TypeError, ValueError):
        record_no = 1
    record_no = max(record_no, 1)
    record_label = optional_text(payload, "record_label") or f"第{record_no}次记录"

    if sample_id <= 0:
        raise ValueError("sample_id is required")
    if stage not in {"发料", "光刻", "检测", "刻蚀", "镀膜", "湿法", "MBE"}:
        raise ValueError("unsupported process stage")
    if status not in {"draft", "submitted"}:
        raise ValueError("unsupported process status")

    timestamp = now_iso()
    with connect_db() as conn:
        sample = conn.execute("SELECT * FROM samples WHERE id = ?", (sample_id,)).fetchone()
        if not sample:
            raise ValueError("未找到对应的建档样品")

        if process_record_id > 0:
            existing = conn.execute(
                "SELECT id, sample_id, stage FROM process_records WHERE id = ?",
                (process_record_id,),
            ).fetchone()
            if not existing:
                raise ValueError("process record id not found")
            if existing["sample_id"] != sample_id or existing["stage"] != stage:
                raise ValueError("process record id does not match sample or stage")
        else:
            existing = conn.execute(
                """
                SELECT id, created_at
                FROM process_records
                WHERE sample_id = ? AND stage = ? AND layer_name = ? AND record_no = ?
                """,
                (sample_id, stage, layer_name, record_no),
            ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE process_records
                SET sample_uid = ?,
                    sample_display_code = ?,
                    layer_name = ?,
                    record_no = ?,
                    record_label = ?,
                    substrate_type = ?,
                    resistance_type = ?,
                    wafer_thickness = ?,
                    details_json = ?,
                    status = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    sample["sample_uid"],
                    sample["sample_display_code"],
                    layer_name,
                    record_no,
                    record_label,
                    substrate_type,
                    resistance_type,
                    wafer_thickness,
                    details_json,
                    status,
                    timestamp,
                    existing["id"],
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO process_records (
                    sample_id,
                    sample_uid,
                    sample_display_code,
                    stage,
                    layer_name,
                    record_no,
                    record_label,
                    substrate_type,
                    resistance_type,
                    wafer_thickness,
                    details_json,
                    status,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sample_id,
                    sample["sample_uid"],
                    sample["sample_display_code"],
                    stage,
                    layer_name,
                    record_no,
                    record_label,
                    substrate_type,
                    resistance_type,
                    wafer_thickness,
                    details_json,
                    status,
                    timestamp,
                    timestamp,
                ),
            )

        record = (
            get_process_record_by_id(conn, existing["id"])
            if existing
            else get_process_record(conn, sample_id, stage, layer_name, record_no)
        )
        if status == "submitted":
            complete_mes_step_from_process_record(
                conn,
                sample_id,
                layer_name,
                stage,
                operator=sample["owner"] or "",
            )
        return process_record_payload(record)


def validate_sample_hierarchy(conn, sample, sample_id=None):
    validate_sample_payload(conn, sample, sample_id)

    args = {
        "sample_code": sample["sample_code"],
        "name": sample["name"],
        "category": sample["category"],
        "id": sample_id or 0,
    }

    project_rows = conn.execute(
        """
        SELECT DISTINCT name FROM samples
        WHERE sample_code = :sample_code
          AND id != :id
        """,
        args,
    ).fetchall()
    project_names = {row["name"] for row in project_rows}
    if project_names and sample["name"] not in project_names:
        raise ValueError("同一项目编号下的样品名称需保持一致。")

    process_rows = conn.execute(
        """
        SELECT DISTINCT name FROM samples
        WHERE sample_code = :sample_code
          AND category = :category
          AND id != :id
        """,
        args,
    ).fetchall()
    process_names = {row["name"] for row in process_rows}
    if process_names and sample["name"] not in process_names:
        raise ValueError("同一项目编号和工艺类型下的样品名称需保持一致。")


def create_sample(payload):
    timestamp = now_iso()
    sample = {
        "sample_code": require_text(payload, "sample_code"),
        "name": require_text(payload, "name"),
        "category": optional_text(payload, "category"),
        "batch": optional_text(payload, "batch"),
        "owner": optional_text(payload, "owner"),
        "status": optional_text(payload, "status") or "待测试",
        "received_at": optional_text(payload, "received_at"),
        "notes": optional_text(payload, "notes"),
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    with connect_db() as conn:
        validate_sample_hierarchy(conn, sample)
        sample["sample_uid"] = generate_sample_uid(conn)
        try:
            cursor = conn.execute(
                """
                INSERT INTO samples (
                    sample_uid, sample_display_code, sample_code, name, category,
                    batch, owner, status, received_at, notes, created_at, updated_at
                )
                VALUES (
                    :sample_uid, :sample_display_code, :sample_code, :name, :category,
                    :batch, :owner, :status, :received_at, :notes, :created_at, :updated_at
                )
                """,
                sample,
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("当前样品显示编号已存在，请修改项目编号、样品名称、工艺类型或样品序号。") from exc
        return row_dict(conn.execute("SELECT * FROM samples WHERE id = ?", (cursor.lastrowid,)).fetchone())


def update_sample(sample_id, payload):
    with connect_db() as conn:
        current = conn.execute("SELECT sample_uid FROM samples WHERE id = ?", (sample_id,)).fetchone()
        if current is None:
            raise LookupError("sample not found")

        fields = {
            "sample_code": require_text(payload, "sample_code"),
            "name": require_text(payload, "name"),
            "category": optional_text(payload, "category"),
            "batch": optional_text(payload, "batch"),
            "owner": optional_text(payload, "owner"),
            "status": optional_text(payload, "status") or "待测试",
            "received_at": optional_text(payload, "received_at"),
            "notes": optional_text(payload, "notes"),
            "updated_at": now_iso(),
            "sample_uid": current["sample_uid"],
            "id": sample_id,
        }
        validate_sample_hierarchy(conn, fields, sample_id)
        try:
            cursor = conn.execute(
                """
                UPDATE samples
                SET sample_display_code = :sample_display_code,
                    sample_code = :sample_code,
                    name = :name,
                    category = :category,
                    batch = :batch,
                    owner = :owner,
                    status = :status,
                    received_at = :received_at,
                    notes = :notes,
                    updated_at = :updated_at
                WHERE id = :id
                """,
                fields,
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("当前样品显示编号已存在，请修改项目编号、样品名称、工艺类型或样品序号。") from exc
        if cursor.rowcount == 0:
            raise LookupError("sample not found")
        return row_dict(conn.execute("SELECT * FROM samples WHERE id = ?", (sample_id,)).fetchone())

def delete_sample(sample_id):
    with connect_db() as conn:
        cursor = conn.execute("DELETE FROM samples WHERE id = ?", (sample_id,))
        if cursor.rowcount == 0:
            raise LookupError("sample not found")
    return {"deleted": sample_id}


def get_test_data(query_params):
    sample_id = query_params.get("sample_id", [""])[0].strip()
    query = query_params.get("query", [""])[0].strip()
    where = []
    args = []
    if sample_id:
        where.append("td.sample_id = ?")
        args.append(sample_id)
    if query:
        like = f"%{query}%"
        where.append(
            "(s.sample_display_code LIKE ? OR s.sample_uid LIKE ? OR s.sample_code LIKE ? OR s.name LIKE ? OR td.test_name LIKE ? OR td.metric_name LIKE ? OR td.operator LIKE ?)"
        )
        args.extend([like, like, like, like, like, like, like])

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    sql = f"""
        SELECT
            td.*,
            s.sample_uid,
            s.sample_display_code,
            s.sample_code,
            s.name AS sample_name,
            s.batch AS sample_batch
        FROM test_data td
        JOIN samples s ON s.id = td.sample_id
        {where_sql}
        ORDER BY td.measured_at DESC, td.id DESC
        LIMIT 1000
    """
    with connect_db() as conn:
        return rows_dict(conn.execute(sql, args).fetchall())


def normalize_test_record(conn, payload):
    sample_id = payload.get("sample_id")
    sample_code = optional_text(payload, "sample_code")
    if sample_id in ("", None):
        if not sample_code:
            raise ValueError("sample_id or sample_code is required")
        row = conn.execute("SELECT id FROM samples WHERE sample_code = ?", (sample_code,)).fetchone()
        if row is None:
            raise ValueError(f"sample_code not found: {sample_code}")
        sample_id = row["id"]
    else:
        try:
            sample_id = int(sample_id)
        except (TypeError, ValueError):
            raise ValueError("sample_id must be numeric")
        if not sample_exists(conn, sample_id):
            raise ValueError("sample_id not found")

    measured_at = optional_text(payload, "measured_at") or now_iso()
    value = parse_float(payload.get("numeric_value"), "numeric_value")
    if value is None:
        raise ValueError("numeric_value is required")

    return {
        "sample_id": sample_id,
        "test_name": require_text(payload, "test_name"),
        "metric_name": require_text(payload, "metric_name"),
        "numeric_value": value,
        "unit": optional_text(payload, "unit"),
        "measured_at": measured_at,
        "operator": optional_text(payload, "operator"),
        "environment": optional_text(payload, "environment"),
        "raw_note": optional_text(payload, "raw_note"),
        "created_at": now_iso(),
    }


def create_test_data(payload):
    with connect_db() as conn:
        record = normalize_test_record(conn, payload)
        cursor = conn.execute(
            """
            INSERT INTO test_data (
                sample_id, test_name, metric_name, numeric_value, unit,
                measured_at, operator, environment, raw_note, created_at
            )
            VALUES (
                :sample_id, :test_name, :metric_name, :numeric_value, :unit,
                :measured_at, :operator, :environment, :raw_note, :created_at
            )
            """,
            record,
        )
        return row_dict(
            conn.execute(
                """
                SELECT td.*, s.sample_uid, s.sample_display_code, s.sample_code, s.name AS sample_name, s.batch AS sample_batch
                FROM test_data td
                JOIN samples s ON s.id = td.sample_id
                WHERE td.id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()
        )


def bulk_create_test_data(payload):
    records = payload.get("records")
    if not isinstance(records, list):
        raise ValueError("records must be a list")

    inserted = []
    errors = []
    with connect_db() as conn:
        for index, raw in enumerate(records, start=1):
            try:
                record = normalize_test_record(conn, raw)
                cursor = conn.execute(
                    """
                    INSERT INTO test_data (
                        sample_id, test_name, metric_name, numeric_value, unit,
                        measured_at, operator, environment, raw_note, created_at
                    )
                    VALUES (
                        :sample_id, :test_name, :metric_name, :numeric_value, :unit,
                        :measured_at, :operator, :environment, :raw_note, :created_at
                    )
                    """,
                    record,
                )
                inserted.append(cursor.lastrowid)
            except Exception as exc:
                errors.append({"row": index, "message": str(exc)})

    return {"inserted": len(inserted), "errors": errors}


def delete_test_data(record_id):
    with connect_db() as conn:
        cursor = conn.execute("DELETE FROM test_data WHERE id = ?", (record_id,))
        if cursor.rowcount == 0:
            raise LookupError("test data not found")
    return {"deleted": record_id}


def safe_path_parts(value, fallback="file"):
    raw_parts = re.split(r"[\\/]+", str(value or ""))
    parts = []
    for raw in raw_parts:
        cleaned = re.sub(r"[^\w.\- \u4e00-\u9fff]+", "_", raw.strip(), flags=re.UNICODE)
        cleaned = cleaned.strip(" .")
        if cleaned and cleaned not in (".", ".."):
            parts.append(cleaned)
    return parts or [fallback]


def safe_path_part(value, fallback="item"):
    return safe_path_parts(value, fallback=fallback)[0]


def storage_path_for(path):
    target = path.resolve()
    try:
        return str(target.relative_to(DATA_DIR))
    except ValueError:
        try:
            return str(target.relative_to(ROOT))
        except ValueError:
            return str(target)


def resolve_data_path(storage_path):
    raw_path = Path(str(storage_path or ""))
    if raw_path.is_absolute():
        return raw_path.resolve()

    parts = raw_path.parts
    if parts and parts[0] == DATA_DIR.name:
        raw_path = Path(*parts[1:]) if len(parts) > 1 else Path()

    data_target = (DATA_DIR / raw_path).resolve()
    if str(data_target).startswith(str(DATA_DIR.resolve())):
        return data_target
    return (ROOT / raw_path).resolve()


def ensure_upload_root():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def file_sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def save_uploaded_file(file_item, target_dir, relative_name=None):
    ensure_upload_root()
    parts = safe_path_parts(relative_name or file_item.get("filename"), fallback="upload.bin")
    original_filename = parts[-1]
    stored_filename = f"{uuid.uuid4().hex}-{original_filename}"
    target = target_dir.joinpath(*parts[:-1], stored_filename)
    target.parent.mkdir(parents=True, exist_ok=True)

    with target.open("wb") as handle:
        handle.write(file_item["content"])

    return {
        "original_filename": original_filename,
        "relative_path": "/".join(parts),
        "stored_filename": stored_filename,
        "storage_path": storage_path_for(target),
        "mime_type": file_item.get("mime_type") or mimetypes.guess_type(original_filename)[0] or "",
        "file_size": target.stat().st_size,
    }


def remove_stored_path(storage_path):
    target = resolve_data_path(storage_path)
    upload_root = UPLOAD_DIR.resolve()
    if str(target).startswith(str(upload_root)):
        if target.is_file():
            target.unlink(missing_ok=True)
        elif target.is_dir():
            shutil.rmtree(target, ignore_errors=True)


def get_sample_row(conn, sample_id):
    row = conn.execute("SELECT * FROM samples WHERE id = ?", (sample_id,)).fetchone()
    if row is None:
        raise ValueError("sample_id not found")
    return row


RAW_DATA_TYPES = {
    "resistance": {"label": "电阻测试数据", "category": "electrical"},
    "cd_sem": {"label": "CD / SEM 数据", "category": "metrology"},
    "sem_image": {"label": "SEM / 图片类数据", "category": "image"},
    "xps": {"label": "XPS / 光谱类数据", "category": "spectrum"},
    "xrd": {"label": "XRD 数据", "category": "spectrum"},
    "afm": {"label": "AFM 数据", "category": "metrology"},
    "report": {"label": "报告文件", "category": "report"},
    "instrument_folder": {"label": "仪器原始目录", "category": "folder"},
    "generic_file": {"label": "通用文件", "category": "other"},
}


def normalize_raw_data_type(value):
    data_type = re.sub(r"[^a-z0-9_]+", "_", str(value or "").strip().lower()).strip("_")
    if not data_type:
        raise ValueError("data_type is required")
    if data_type not in RAW_DATA_TYPES:
        raise ValueError("unsupported data_type")
    return data_type


def raw_data_category_for(data_type):
    return RAW_DATA_TYPES.get(data_type, RAW_DATA_TYPES["generic_file"])["category"]


def raw_data_type_token(data_type):
    token = re.sub(r"[^A-Z0-9]+", "_", data_type.upper()).strip("_")
    return token or "GENERIC_FILE"


def generate_raw_data_code(conn, sample_uid, data_type, measured_at=None):
    date_source = optional_text({"measured_at": measured_at}, "measured_at")
    date_digits = re.sub(r"\D", "", date_source)[:8] if date_source else ""
    if not date_digits:
        date_digits = datetime.now().strftime("%Y%m%d")
    token = raw_data_type_token(data_type)
    prefix = f"RD-{sample_uid}-{token}-{date_digits}-"
    rows = conn.execute(
        "SELECT raw_data_code FROM raw_data WHERE raw_data_code LIKE ?",
        (f"{prefix}%",),
    ).fetchall()
    max_seq = 0
    for row in rows:
        suffix = str(row["raw_data_code"] or "").replace(prefix, "", 1)
        if suffix.isdigit():
            max_seq = max(max_seq, int(suffix))
    return f"{prefix}{max_seq + 1:03d}"


def raw_data_row_with_files(conn, raw_data_id):
    raw_data = row_dict(
        conn.execute("SELECT * FROM raw_data WHERE id = ?", (raw_data_id,)).fetchone()
    )
    if raw_data is None:
        raise LookupError("raw data not found")
    raw_data["files"] = rows_dict(
        conn.execute(
            """
            SELECT *
            FROM raw_data_files
            WHERE raw_data_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (raw_data_id,),
        ).fetchall()
    )
    raw_data["parsed_data_count"] = conn.execute(
        "SELECT COUNT(*) AS count FROM parsed_data WHERE raw_data_id = ?",
        (raw_data_id,),
    ).fetchone()["count"]
    raw_data["processing_job_count"] = conn.execute(
        "SELECT COUNT(*) AS count FROM processing_jobs WHERE raw_data_id = ?",
        (raw_data_id,),
    ).fetchone()["count"]
    return raw_data


def raw_data_file_row(conn, file_id):
    record = row_dict(
        conn.execute("SELECT * FROM raw_data_files WHERE id = ?", (file_id,)).fetchone()
    )
    if record is None:
        raise LookupError("raw data file not found")
    return record


def raw_data_upload_file_path(record):
    target = resolve_data_path(record["file_path"])
    upload_root = (UPLOAD_DIR / "raw_data").resolve()
    try:
        target.relative_to(upload_root)
    except ValueError as exc:
        raise ValueError("invalid raw data file path") from exc
    if target == upload_root:
        raise ValueError("invalid raw data file path")
    return target


def output_paths_from_job_output(output_json):
    try:
        output = json.loads(output_json or "{}")
    except json.JSONDecodeError:
        return []

    if not isinstance(output, dict):
        return []

    candidates = []
    for key in ("chart_path", "report_path", "report_json_path"):
        value = output.get(key)
        if isinstance(value, str) and value:
            candidates.append(value)

    charts = output.get("charts")
    if isinstance(charts, list):
        for chart in charts:
            if isinstance(chart, dict):
                value = chart.get("chart_path")
                if isinstance(value, str) and value:
                    candidates.append(value)

    return candidates


def delete_output_files_for_jobs(job_rows):
    output_root = OUTPUT_DIR.resolve()
    deleted = []
    seen = set()
    for job in job_rows:
        for raw_path in output_paths_from_job_output(job["output_json"]):
            target = resolve_data_path(raw_path)
            if target in seen or not str(target).startswith(str(output_root)):
                continue
            seen.add(target)
            if target.is_file():
                target.unlink(missing_ok=True)
                deleted.append(str(target.relative_to(DATA_DIR)))

    for job in job_rows:
        job_dir = (OUTPUT_DIR / "visualizations" / "cd_violin" / str(job["id"])).resolve()
        if str(job_dir).startswith(str(output_root)) and job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)

    return deleted


def json_text(value, default_value):
    if value in (None, ""):
        return json.dumps(default_value, ensure_ascii=False)
    if isinstance(value, (dict, list)):
        if not isinstance(value, type(default_value)):
            raise ValueError("JSON field has invalid type")
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("JSON field must be valid JSON") from exc
        if not isinstance(parsed, type(default_value)):
            raise ValueError("JSON field has invalid type")
        return json.dumps(parsed, ensure_ascii=False)
    raise ValueError("JSON field has invalid type")


def parsed_data_row(conn, parsed_data_id):
    parsed = row_dict(
        conn.execute("SELECT * FROM parsed_data WHERE id = ?", (parsed_data_id,)).fetchone()
    )
    if parsed is None:
        raise LookupError("parsed data not found")
    return parsed


def get_parsed_data_list(query_params):
    raw_data_id = query_params.get("raw_data_id", [""])[0].strip()
    sample_id = query_params.get("sample_id", [""])[0].strip()
    data_type = query_params.get("data_type", [""])[0].strip()
    where = []
    args = []

    if raw_data_id:
        where.append("raw_data_id = ?")
        args.append(raw_data_id)
    if sample_id:
        where.append("sample_id = ?")
        args.append(sample_id)
    if data_type:
        where.append("data_type = ?")
        args.append(data_type)

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    with connect_db() as conn:
        return rows_dict(
            conn.execute(
                f"""
                SELECT *
                FROM parsed_data
                {where_sql}
                ORDER BY created_at DESC, id DESC
                LIMIT 500
                """,
                args,
            ).fetchall()
        )


def get_parsed_data_detail(parsed_data_id):
    with connect_db() as conn:
        return parsed_data_row(conn, parsed_data_id)


def parse_positive_int_param(query_params, name, default_value, max_value=None):
    raw_value = query_params.get(name, [""])[0]
    try:
        value = int(str(raw_value).strip())
    except (TypeError, ValueError):
        value = default_value
    if value < 1:
        value = 1
    if max_value is not None:
        value = min(value, max_value)
    return value


def parse_optional_bool_param(value):
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n"}:
        return False
    return None


def normalized_record_filter(field, value):
    text = str(value or "").strip()
    if field == "direction":
        direction_aliases = {
            "h": "Horizontal",
            "horizontal": "Horizontal",
            "v": "Vertical",
            "vertical": "Vertical",
        }
        text = direction_aliases.get(text.lower(), text)
    if field == "side":
        side_aliases = {
            "l": "Left",
            "left": "Left",
            "r": "Right",
            "right": "Right",
        }
        text = side_aliases.get(text.lower(), text)
    return text


def build_parsed_records_filters(parsed_data_id, query_params):
    where = ["parsed_data_id = ?"]
    args = [parsed_data_id]
    filters = {
        "parsed_data_id": parsed_data_id,
        "data_type": None,
        "die_id": None,
        "area": None,
        "is_outlier": None,
        "is_na": None,
        "row_group": None,
        "side": None,
        "direction": None,
        "dose": None,
        "location": None,
        "q": None,
    }

    text_fields = [
        "data_type",
        "die_id",
        "area",
        "row_group",
        "side",
        "direction",
        "dose",
        "location",
    ]
    for field in text_fields:
        value = normalized_record_filter(field, query_params.get(field, [""])[0])
        if value:
            where.append(f"LOWER({field}) = LOWER(?)")
            args.append(value)
            filters[field] = value

    is_outlier_raw = query_params.get("is_outlier", [""])[0]
    if str(is_outlier_raw).strip() != "":
        is_outlier = parse_optional_bool_param(is_outlier_raw)
        if is_outlier is not None:
            where.append("is_outlier = ?")
            args.append(1 if is_outlier else 0)
            filters["is_outlier"] = is_outlier

    na_sql = """
    (
        cleaned_value IS NULL
        OR TRIM(cleaned_value) = ''
        OR LOWER(TRIM(cleaned_value)) IN ('na', 'n/a', 'nan', 'none', 'null')
        OR raw_value IS NULL
        OR TRIM(raw_value) = ''
        OR LOWER(TRIM(raw_value)) IN ('na', 'n/a', 'nan', 'none', 'null')
    )
    """
    is_na_raw = query_params.get("is_na", [""])[0]
    if str(is_na_raw).strip() != "":
        is_na = parse_optional_bool_param(is_na_raw)
        if is_na is not None:
            where.append(na_sql if is_na else f"NOT {na_sql}")
            filters["is_na"] = is_na

    q = query_params.get("q", [""])[0].strip()
    if q:
        search_fields = [
            "primary_key",
            "group_key",
            "die_id",
            "area",
            "row_header",
            "col_header",
            "row_group",
            "side",
            "direction",
            "dose",
            "location",
            "raw_value",
            "cleaned_value",
        ]
        where.append(
            "("
            + " OR ".join(f"LOWER(COALESCE({field}, '')) LIKE LOWER(?)" for field in search_fields)
            + ")"
        )
        args.extend([f"%{q}%"] * len(search_fields))
        filters["q"] = q

    return where, args, filters


def get_parsed_data_records(parsed_data_id, query_params):
    page = parse_positive_int_param(query_params, "page", 1)
    page_size = parse_positive_int_param(query_params, "page_size", 100, max_value=500)
    offset = (page - 1) * page_size

    with connect_db() as conn:
        parsed_data_row(conn, parsed_data_id)
        where, args, filters = build_parsed_records_filters(parsed_data_id, query_params)
        where_sql = "WHERE " + " AND ".join(where)
        total = conn.execute(
            f"SELECT COUNT(*) AS count FROM parsed_records {where_sql}",
            args,
        ).fetchone()["count"]
        items = rows_dict(
            conn.execute(
                f"""
                SELECT
                    id, parsed_data_id, raw_data_id, sample_id, sample_uid,
                    raw_data_code, data_type, record_index, primary_key, group_key,
                    x_value, y_value, numeric_value, raw_value, cleaned_value,
                    is_outlier, outlier_reason, die_id, area, row_index, col_index,
                    row_header, col_header, row_group, side, direction, dose,
                    location, extra_json, created_at
                FROM parsed_records
                {where_sql}
                ORDER BY record_index IS NULL ASC, record_index ASC, id ASC
                LIMIT ? OFFSET ?
                """,
                [*args, page_size, offset],
            ).fetchall()
        )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if total else 0,
        "filters": filters,
    }


def parsed_record_option_value(field, value):
    text = normalized_record_filter(field, value)
    return text if text else None


def parsed_record_option_sort_key(value):
    text = str(value)
    return (
        re.sub(r"\d+", "", text).lower(),
        [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", text)],
    )


def get_parsed_record_options(parsed_data_id):
    option_fields = [
        "die_id",
        "area",
        "row_group",
        "side",
        "direction",
        "dose",
        "location",
    ]

    with connect_db() as conn:
        parsed = parsed_data_row(conn, parsed_data_id)
        options = {}
        for field in option_fields:
            rows = conn.execute(
                f"""
                SELECT DISTINCT {field} AS value
                FROM parsed_records
                WHERE parsed_data_id = ?
                  AND {field} IS NOT NULL
                  AND TRIM({field}) != ''
                """,
                (parsed_data_id,),
            ).fetchall()
            values = {
                value
                for row in rows
                if (value := parsed_record_option_value(field, row["value"])) is not None
            }
            options[field] = sorted(values, key=parsed_record_option_sort_key)

        total = conn.execute(
            "SELECT COUNT(*) AS count FROM parsed_records WHERE parsed_data_id = ?",
            (parsed_data_id,),
        ).fetchone()["count"]
        outlier_values = rows_dict(
            conn.execute(
                """
                SELECT DISTINCT is_outlier AS value
                FROM parsed_records
                WHERE parsed_data_id = ? AND is_outlier IS NOT NULL
                ORDER BY is_outlier ASC
                """,
                (parsed_data_id,),
            ).fetchall()
        )
        na_sql = """
        (
            cleaned_value IS NULL
            OR TRIM(cleaned_value) = ''
            OR LOWER(TRIM(cleaned_value)) IN ('na', 'n/a', 'nan', 'none', 'null')
            OR raw_value IS NULL
            OR TRIM(raw_value) = ''
            OR LOWER(TRIM(raw_value)) IN ('na', 'n/a', 'nan', 'none', 'null')
        )
        """
        na_count = conn.execute(
            f"SELECT COUNT(*) AS count FROM parsed_records WHERE parsed_data_id = ? AND {na_sql}",
            (parsed_data_id,),
        ).fetchone()["count"]
        non_na_count = conn.execute(
            f"SELECT COUNT(*) AS count FROM parsed_records WHERE parsed_data_id = ? AND NOT {na_sql}",
            (parsed_data_id,),
        ).fetchone()["count"]

    options["is_outlier"] = [int(row["value"]) for row in outlier_values if row["value"] is not None]
    options["is_na"] = [value for value, count in ((0, non_na_count), (1, na_count)) if count > 0]
    return {
        "parsed_data_id": parsed_data_id,
        "data_type": parsed["data_type"],
        "options": options,
        "counts": {
            "total": total,
        },
    }


def parse_resistance_summary_request(payload):
    payload = payload or {}
    if not isinstance(payload, dict):
        raise ValueError("request body must be a JSON object")

    config = payload.get("cleaning_config")
    if config is None:
        config = {}
    if not isinstance(config, dict):
        raise ValueError("cleaning_config must be an object")

    lower_raw = config.get("lower", config.get("lower_limit"))
    upper_raw = config.get("upper", config.get("upper_limit"))
    lower = parse_float(lower_raw, "lower")
    upper = parse_float(upper_raw, "upper")
    if lower is not None and upper is not None and lower > upper:
        raise ValueError("lower cannot be greater than upper")

    metric = str(payload.get("metric") or "cleaned_value").strip() or "cleaned_value"
    if metric not in {"numeric_value", "cleaned_value", "raw_value"}:
        raise ValueError("metric must be numeric_value, cleaned_value or raw_value")

    area = str(payload.get("area") or "").strip().upper() or None
    if area is not None and area not in {"A", "B", "C", "D"}:
        raise ValueError("area must be A, B, C or D")
    die_id = str(payload.get("die_id") or "").strip().upper() or None

    return {
        "cleaning_config": {"lower": lower, "upper": upper},
        "metric": metric,
        "area": area,
        "die_id": die_id,
    }


def is_na_value(value):
    if value is None:
        return True
    text = str(value).strip()
    return text == "" or text.lower() in {"na", "n/a", "nan", "none", "null"}


def to_float_or_none(value):
    if is_na_value(value):
        return None
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def clean_resistance_record(row, metric, cleaning_config):
    value = to_float_or_none(row.get(metric))
    raw_number = to_float_or_none(row.get("raw_value"))
    cleaned_number = to_float_or_none(row.get("cleaned_value"))
    numeric_number = to_float_or_none(row.get("numeric_value"))
    is_na = value is None
    is_outlier = False
    outlier_reason = None
    cleaned_value = value

    if value is not None:
        lower = cleaning_config["lower"]
        upper = cleaning_config["upper"]
        if lower is not None and value < lower:
            is_outlier = True
            outlier_reason = "below_lower_limit"
            cleaned_value = None
        elif upper is not None and value > upper:
            is_outlier = True
            outlier_reason = "above_upper_limit"
            cleaned_value = None

    return {
        **row,
        "value": value,
        "raw_number": raw_number,
        "cleaned_number": cleaned_number,
        "numeric_number": numeric_number,
        "dynamic_cleaned_value": cleaned_value,
        "is_na": is_na,
        "is_outlier": is_outlier,
        "outlier_reason": outlier_reason,
    }


def calculate_resistance_stats(records, base=None):
    base = base or {}
    count_total = len(records)
    valid_values = [record["value"] for record in records if record["value"] is not None]
    normal_values = [
        record["value"]
        for record in records
        if record["value"] is not None and not record["is_outlier"]
    ]
    count_valid = len(valid_values)
    count_outlier = sum(1 for record in records if record["is_outlier"])
    count_normal = len(normal_values)
    count_na = sum(1 for record in records if record["is_na"])
    maximum = max(normal_values) if normal_values else None
    minimum = min(normal_values) if normal_values else None
    value_range = maximum - minimum if maximum is not None and minimum is not None else None
    average = statistics.mean(normal_values) if normal_values else None
    std = statistics.stdev(normal_values) if len(normal_values) > 1 else (0 if len(normal_values) == 1 else None)
    three_sigma = 3 * std if std is not None else None
    uniformity = (
        value_range / (2 * average)
        if value_range is not None and average not in (None, 0)
        else None
    )

    return {
        **base,
        "count_total": count_total,
        "count_valid": count_valid,
        "count_na": count_na,
        "count_normal": count_normal,
        "count_outlier": count_outlier,
        "yield_rate": count_normal / count_total if count_total else None,
        "max": maximum,
        "min": minimum,
        "range": value_range,
        "average": average,
        "std": std,
        "three_sigma": three_sigma,
        "uniformity": uniformity,
    }


def build_resistance_layout_values(records):
    return [
        {
            "id": record["id"],
            "die_id": record.get("die_id"),
            "area": record.get("area"),
            "row_index": record.get("row_index"),
            "col_index": record.get("col_index"),
            "row_header": record.get("row_header"),
            "col_header": record.get("col_header"),
            "raw_value": record.get("raw_value"),
            "cleaned_value": record.get("cleaned_value"),
            "numeric_value": record.get("numeric_value"),
            "value": record["value"],
            "is_na": record["is_na"],
            "is_outlier": record["is_outlier"],
            "outlier_reason": record["outlier_reason"],
        }
        for record in records
    ]


def get_resistance_summary(parsed_data_id, payload=None):
    request = parse_resistance_summary_request(payload)
    area_filter = request["area"]
    die_filter = request["die_id"]

    with connect_db() as conn:
        parsed = parsed_data_row(conn, parsed_data_id)
        if "resistance" not in str(parsed.get("data_type") or "").lower():
            raise ValueError("parsed data is not resistance data")

        where = ["parsed_data_id = ?", "LOWER(data_type) LIKE ?"]
        args = [parsed_data_id, "%resistance%"]
        if area_filter:
            where.append("area = ?")
            args.append(area_filter)
        if die_filter:
            where.append("UPPER(die_id) = ?")
            args.append(die_filter)
        records = rows_dict(
            conn.execute(
                f"""
                SELECT
                    id, parsed_data_id, raw_data_id, sample_id, sample_uid,
                    raw_data_code, data_type, record_index, primary_key, group_key,
                    x_value, y_value, numeric_value, raw_value, cleaned_value,
                    is_outlier, outlier_reason, die_id, area, row_index, col_index,
                    row_header, col_header, row_group, side, direction, dose,
                    location, extra_json, created_at
                FROM parsed_records
                WHERE {" AND ".join(where)}
                ORDER BY record_index IS NULL ASC, record_index ASC, id ASC
                """,
                args,
            ).fetchall()
        )

    cleaned_records = [
        clean_resistance_record(record, request["metric"], request["cleaning_config"])
        for record in records
    ]
    die_ids = sorted(
        {record.get("die_id") for record in cleaned_records if record.get("die_id")},
        key=lambda value: (str(value)[0], int(str(value)[1:]) if str(value)[1:].isdigit() else str(value)[1:]),
    )
    die_summary = [
        calculate_resistance_stats(
            [record for record in cleaned_records if record.get("die_id") == die_id],
            {"die_id": die_id},
        )
        for die_id in die_ids
    ]

    area_summary = []
    for die_id in die_ids:
        for area in ("A", "B", "C", "D"):
            area_records = [
                record
                for record in cleaned_records
                if record.get("die_id") == die_id and record.get("area") == area
            ]
            if area_filter and area != area_filter:
                continue
            area_summary.append(calculate_resistance_stats(area_records, {"die_id": die_id, "area": area}))

    return {
        "parsed_data_id": parsed_data_id,
        "cleaning_config": request["cleaning_config"],
        "metric": request["metric"],
        "filters": {
            "die_id": die_filter,
            "area": area_filter,
        },
        "overall_summary": calculate_resistance_stats(cleaned_records),
        "die_summary": die_summary,
        "area_summary": area_summary,
        "layout_values": build_resistance_layout_values(cleaned_records),
    }


def parsed_data_with_context(conn, parsed_data_id):
    parsed = parsed_data_row(conn, parsed_data_id)
    raw_data = row_dict(
        conn.execute("SELECT * FROM raw_data WHERE id = ?", (parsed["raw_data_id"],)).fetchone()
    )
    if raw_data is None:
        raise LookupError("raw data not found")
    return parsed, raw_data


def json_object(value):
    try:
        parsed = json.loads(value or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def normalize_cd_sem_side(value):
    text = str(value or "").strip()
    lower = text.lower()
    if lower == "left":
        return "Left"
    if lower == "right":
        return "Right"
    return text


def normalize_cd_sem_direction(value):
    text = str(value or "").strip()
    lower = text.lower()
    if lower in {"h", "horizontal"}:
        return "Horizontal"
    if lower in {"v", "vertical"}:
        return "Vertical"
    return text


def cd_sem_record_for_visualization(record):
    extra = json_object(record.get("extra_json"))
    return {
        "id": record.get("id"),
        "record_index": record.get("record_index"),
        "row_group": record.get("row_group") or "",
        "side": normalize_cd_sem_side(record.get("side")),
        "direction": normalize_cd_sem_direction(record.get("direction")),
        "die_no": record.get("die_id") or "",
        "die_id": record.get("die_id") or "",
        "dose": record.get("dose") or "",
        "location": record.get("location") or "",
        "cd_value": record.get("numeric_value"),
        "numeric_value": record.get("numeric_value"),
        "raw_value": record.get("raw_value") or "",
        "cleaned_value": record.get("cleaned_value") or "",
        "unit": extra.get("unit") or "nm",
        "sample_display_code": extra.get("sample_display_code") or record.get("sample_uid") or "",
        "source_file": extra.get("source_file") or "",
        "raw_data_id": record.get("raw_data_id"),
        "raw_data_code": record.get("raw_data_code") or "",
        "sample_id": record.get("sample_id"),
        "sample_uid": record.get("sample_uid") or "",
    }


def get_cd_sem_records_for_visualization(conn, parsed_data_id):
    records = rows_dict(
        conn.execute(
            """
            SELECT
                id, parsed_data_id, raw_data_id, sample_id, sample_uid,
                raw_data_code, data_type, record_index, primary_key, group_key,
                x_value, y_value, numeric_value, raw_value, cleaned_value,
                is_outlier, outlier_reason, die_id, area, row_index, col_index,
                row_header, col_header, row_group, side, direction, dose,
                location, extra_json, created_at
            FROM parsed_records
            WHERE parsed_data_id = ? AND data_type = ?
            ORDER BY record_index IS NULL ASC, record_index ASC, id ASC
            """,
            (parsed_data_id, "cd_sem"),
        ).fetchall()
    )
    return [cd_sem_record_for_visualization(record) for record in records]


def relative_output_path(path):
    target = Path(path).resolve()
    output_root = OUTPUT_DIR.resolve()
    if not str(target).startswith(str(output_root)):
        raise ValueError("invalid output path")
    return str(target.relative_to(DATA_DIR))


def output_url_for(relative_path):
    return f"/api/outputs/{relative_path.replace(os.sep, '/')}"


def write_json_output(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def write_summary_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = rows if isinstance(rows, list) else []
    columns = [
        "die_id",
        "area",
        "max",
        "min",
        "range",
        "average",
        "uniformity",
        "count_total",
        "count_valid",
        "count_na",
        "count_normal",
        "count_outlier",
        "yield_rate",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row if isinstance(row, dict) else {})


def create_resistance_visualization_job(parsed, payload):
    if payload.get("chart_type") != "resistance_wafer_heatmap":
        raise ValueError("resistance parsed_data only supports resistance_wafer_heatmap")

    summary = payload.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("summary is required")
    overall_summary = summary.get("overall_summary")
    die_summary = summary.get("die_summary")
    area_summary = summary.get("area_summary")
    if not isinstance(overall_summary, dict) or not isinstance(die_summary, list) or not isinstance(area_summary, list):
        raise ValueError("summary must include overall_summary, die_summary and area_summary")

    layout_values = payload.get("layout_values")
    if not isinstance(layout_values, list):
        raise ValueError("layout_values is required")

    started_at = now_iso()
    input_payload = {
        "parsed_data_id": parsed["id"],
        "chart_type": "resistance_wafer_heatmap",
        "metric": payload.get("metric", ""),
        "area": payload.get("area", ""),
        "cleaning_config": payload.get("cleaning_config", {}),
        "display": payload.get("display", {}),
    }
    job_payload = {
        "job_type": "visualization",
        "job_name": f"Resistance wafer heatmap {parsed['raw_data_code']}",
        "raw_data_id": parsed["raw_data_id"],
        "parsed_data_id": parsed["id"],
        "sample_id": parsed["sample_id"],
        "sample_uid": parsed["sample_uid"],
        "data_type": parsed["data_type"],
        "script_name": RESISTANCE_HEATMAP_SCRIPT_NAME,
        "script_version": RESISTANCE_HEATMAP_SCRIPT_VERSION,
        "input_json": json.dumps(input_payload, ensure_ascii=False),
        "output_json": "{}",
        "status": "running",
        "error_message": "",
        "started_at": started_at,
        "finished_at": "",
    }

    with connect_db() as conn:
        job_id = insert_processing_job(conn, job_payload)
        conn.commit()

    output_dir = OUTPUT_DIR / "visualizations" / "resistance_heatmap" / str(job_id)
    try:
        payload_output = {
            "data_type": "resistance",
            "chart_type": "resistance_wafer_heatmap",
            "metric": payload.get("metric", ""),
            "area": payload.get("area", ""),
            "cleaning_config": payload.get("cleaning_config", {}),
            "display": payload.get("display", {}),
            "summary": summary,
            "layout_values": layout_values,
        }
        payload_path = output_dir / "resistance_heatmap_payload.json"
        die_summary_path = output_dir / "resistance_die_summary.csv"
        area_summary_path = output_dir / "resistance_area_summary.csv"
        overall_summary_path = output_dir / "resistance_overall_summary.json"

        write_json_output(payload_path, payload_output)
        write_summary_csv(die_summary_path, die_summary)
        write_summary_csv(area_summary_path, area_summary)
        write_json_output(overall_summary_path, overall_summary)
        chart_output = generate_resistance_heatmap_visualization(payload_output, output_dir)

        payload_relative = relative_output_path(payload_path)
        die_relative = relative_output_path(die_summary_path)
        area_relative = relative_output_path(area_summary_path)
        overall_relative = relative_output_path(overall_summary_path)
        chart_relative = relative_output_path(chart_output["chart_path"])
        output_json = {
            "data_type": "resistance",
            "chart_type": "resistance_wafer_heatmap",
            "metric": payload_output["metric"],
            "area": payload_output["area"],
            "chart_path": chart_relative,
            "chart_url": output_url_for(chart_relative),
            "cleaning_config": payload_output["cleaning_config"],
            "display": payload_output["display"],
            "outputs": {
                "chart": output_url_for(chart_relative),
                "json": output_url_for(payload_relative),
                "die_summary_csv": output_url_for(die_relative),
                "area_summary_csv": output_url_for(area_relative),
                "overall_summary_json": output_url_for(overall_relative),
            },
            "output_paths": {
                "chart": chart_relative,
                "json": payload_relative,
                "die_summary_csv": die_relative,
                "area_summary_csv": area_relative,
                "overall_summary_json": overall_relative,
            },
        }
        finished_at = now_iso()
        with connect_db() as conn:
            conn.execute(
                """
                UPDATE processing_jobs
                SET output_json = ?, status = 'success', finished_at = ?
                WHERE id = ?
                """,
                (json.dumps(output_json, ensure_ascii=False), finished_at, job_id),
            )
            conn.commit()
            return row_dict(conn.execute("SELECT * FROM processing_jobs WHERE id = ?", (job_id,)).fetchone())
    except Exception as exc:
        finished_at = now_iso()
        with connect_db() as conn:
            conn.execute(
                """
                UPDATE processing_jobs
                SET status = 'failed', error_message = ?, finished_at = ?
                WHERE id = ?
                """,
                (str(exc), finished_at, job_id),
            )
            conn.commit()
        raise


def visualize_parsed_data(parsed_data_id, payload=None):
    payload = payload or {}
    with connect_db() as conn:
        parsed, raw_data = parsed_data_with_context(conn, parsed_data_id)

    if parsed["data_type"] == "resistance":
        return create_resistance_visualization_job(parsed, payload)
    if parsed["data_type"] != "cd_sem":
        raise ValueError("当前标准化数据暂无可视化支持")

    parameters = {
        "chart_type": payload.get("chart_type", "violin"),
        "x_field": payload.get("x_field", "dose"),
        "y_field": payload.get("y_field", "cd_value"),
        "hue_field": payload.get("hue_field", "side"),
        "facet_field": payload.get("facet_field", payload.get("facet_fields", ["direction"])[0] if isinstance(payload.get("facet_fields"), list) and payload.get("facet_fields") else "direction"),
        "filters": payload.get("filters", {}),
        "include_overall": bool(payload.get("include_overall", False)),
        "output_format": payload.get("output_format", "png"),
        "title": payload.get("title", "CD Distribution by Dose"),
        "unit": payload.get("unit", "nm"),
        "split_field": payload.get("split_field", "direction"),
        "series_field": payload.get("series_field", "side"),
        "merge_field": payload.get("merge_field", "side"),
        "merge_rule": payload.get("merge_rule", {"label": "Overall", "source_values": ["Left", "Right"]}),
        "output_mode": payload.get("output_mode", "single_chart"),
        "x_order": payload.get("x_order", []),
        "inspect_schema": bool(payload.get("inspect_schema", False)),
        "title_prefix": payload.get("title_prefix", ""),
        "wafer_label": payload.get("wafer_label", ""),
        "chart_overrides": payload.get("chart_overrides", {}),
    }
    if parameters["chart_type"] != "violin":
        raise ValueError("only violin chart_type is supported")

    started_at = now_iso()
    with connect_db() as conn:
        job_payload = {
            "job_type": "visualization",
            "job_name": f"CD violin visualization {parsed['raw_data_code']}",
            "raw_data_id": parsed["raw_data_id"],
            "parsed_data_id": parsed["id"],
            "sample_id": parsed["sample_id"],
            "sample_uid": parsed["sample_uid"],
            "data_type": parsed["data_type"],
            "script_name": CD_VIOLIN_SCRIPT_NAME,
            "script_version": CD_VIOLIN_SCRIPT_VERSION,
            "input_json": json.dumps({"parsed_data_id": parsed_data_id, **parameters}, ensure_ascii=False),
            "output_json": "{}",
            "status": "running",
            "error_message": "",
            "started_at": started_at,
            "finished_at": "",
        }
        job_id = insert_processing_job(conn, job_payload)
        conn.commit()

    output_dir = OUTPUT_DIR / "visualizations" / "cd_violin" / str(job_id)
    try:
        with connect_db() as conn:
            cd_sem_records = get_cd_sem_records_for_visualization(conn, parsed_data_id)
        if not cd_sem_records:
            raise ValueError("No CD/SEM parsed_records found for visualization")
        output = generate_cd_violin_visualization({**dict(parsed), "records": cd_sem_records}, output_dir, parameters)
        charts = []
        for chart in output.get("charts", []):
            chart_path = relative_output_path(chart["chart_path"])
            charts.append(
                {
                    **chart,
                    "chart_path": chart_path,
                    "chart_url": f"/api/outputs/{chart_path.replace(os.sep, '/')}",
                }
            )
        output_json = {
            "chart_path": relative_output_path(output["chart_path"]),
            "report_path": relative_output_path(output["report_path"]),
            "report_json_path": relative_output_path(output["report_json_path"]),
            "chart_url": f"/api/outputs/{relative_output_path(output['chart_path']).replace(os.sep, '/')}",
            "report_url": f"/api/outputs/{relative_output_path(output['report_path']).replace(os.sep, '/')}",
            "report_json_url": f"/api/outputs/{relative_output_path(output['report_json_path']).replace(os.sep, '/')}",
            "chart_type": output["chart_type"],
            "group_count": output["group_count"],
            "point_count": output["point_count"],
            "charts": charts,
            "schema": output.get("schema"),
            "warnings": output["warnings"],
        }
        finished_at = now_iso()
        with connect_db() as conn:
            conn.execute(
                """
                UPDATE processing_jobs
                SET output_json = ?, status = 'success', finished_at = ?
                WHERE id = ?
                """,
                (json.dumps(output_json, ensure_ascii=False), finished_at, job_id),
            )
            conn.commit()
            return row_dict(conn.execute("SELECT * FROM processing_jobs WHERE id = ?", (job_id,)).fetchone())
    except Exception as exc:
        finished_at = now_iso()
        with connect_db() as conn:
            conn.execute(
                """
                UPDATE processing_jobs
                SET status = 'failed', error_message = ?, finished_at = ?
                WHERE id = ?
                """,
                (str(exc), finished_at, job_id),
            )
            conn.commit()
            raise


def safe_download_name(value):
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip())
    safe = safe.strip("._")
    return safe or "chart"


def get_visualization_chart_archive(job_id, chart_keys):
    selected_keys = [str(key).strip() for key in chart_keys if str(key).strip()]
    if not selected_keys:
        raise ValueError("请先选择要保存的图表")

    with connect_db() as conn:
        job = row_dict(conn.execute("SELECT * FROM processing_jobs WHERE id = ?", (job_id,)).fetchone())
    if job is None:
        raise LookupError("visualization job not found")
    if job["job_type"] != "visualization" or job["status"] != "success":
        raise ValueError("只能保存已成功生成的可视化图表")

    try:
        output = json.loads(job["output_json"] or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError("visualization output is invalid") from exc

    charts = output.get("charts")
    if not isinstance(charts, list):
        raise ValueError("当前可视化结果没有可保存的多图结果")

    chart_by_key = {
        str(chart.get("key")): chart
        for chart in charts
        if isinstance(chart, dict) and chart.get("key")
    }
    missing_keys = [key for key in selected_keys if key not in chart_by_key]
    if missing_keys:
        raise ValueError(f"未找到选中的图表：{', '.join(missing_keys)}")

    output_root = OUTPUT_DIR.resolve()
    archive_dir = OUTPUT_DIR / "downloads"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_name = f"CD_Violin_Selected_{job_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.zip"
    archive_path = archive_dir / archive_name

    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for key in selected_keys:
            chart = chart_by_key[key]
            relative_path = chart.get("chart_path")
            if not isinstance(relative_path, str) or not relative_path:
                raise ValueError(f"{key} 缺少图表文件路径")
            target = resolve_data_path(relative_path)
            if not str(target).startswith(str(output_root)) or not target.is_file():
                raise LookupError(f"{key} 图表文件不存在")
            title = chart.get("title") or key
            archive.writestr(f"{safe_download_name(title)}.png", target.read_bytes())

    return archive_path, archive_name


def create_mock_parsed_data(payload):
    try:
        raw_data_id = int(payload.get("raw_data_id", ""))
    except (TypeError, ValueError):
        raise ValueError("raw_data_id must be numeric")

    parser_name = optional_text(payload, "parser_name") or "mock_parser"
    parser_version = optional_text(payload, "parser_version") or "0.1.0"
    records = payload.get("records")
    if not isinstance(records, list):
        records = []
    records_json = "[]"
    summary_json = json_text(payload.get("summary"), {})
    warnings_json = json_text(payload.get("warnings"), [])
    errors_json = json_text(payload.get("errors"), [])
    plots_json = json_text(payload.get("plots"), [])
    timestamp = now_iso()

    with connect_db() as conn:
        raw_data = conn.execute("SELECT * FROM raw_data WHERE id = ?", (raw_data_id,)).fetchone()
        if raw_data is None:
            raise LookupError("raw data not found")

        job_payload = {
            "job_type": "parse",
            "job_name": f"Mock parse {raw_data['raw_data_code']}",
            "raw_data_id": raw_data_id,
            "parsed_data_id": None,
            "sample_id": raw_data["sample_id"],
            "sample_uid": raw_data["sample_uid"],
            "data_type": raw_data["data_type"],
            "script_name": parser_name,
            "script_version": parser_version,
            "input_json": json.dumps({"raw_data_id": raw_data_id}, ensure_ascii=False),
            "output_json": "{}",
            "status": "running",
            "error_message": "",
            "started_at": timestamp,
            "finished_at": "",
        }
        job_cursor = conn.execute(
            """
            INSERT INTO processing_jobs (
                job_type, job_name, raw_data_id, parsed_data_id, sample_id,
                sample_uid, data_type, script_name, script_version, input_json,
                output_json, status, error_message, started_at, finished_at
            )
            VALUES (
                :job_type, :job_name, :raw_data_id, :parsed_data_id, :sample_id,
                :sample_uid, :data_type, :script_name, :script_version, :input_json,
                :output_json, :status, :error_message, :started_at, :finished_at
            )
            """,
            job_payload,
        )

        parsed_payload = {
            "raw_data_id": raw_data_id,
            "sample_id": raw_data["sample_id"],
            "sample_uid": raw_data["sample_uid"],
            "sample_display_code": raw_data["sample_display_code"],
            "raw_data_code": raw_data["raw_data_code"],
            "data_type": raw_data["data_type"],
            "parser_name": parser_name,
            "parser_version": parser_version,
            "parsed_status": "success",
            "schema_version": "1.0",
            "records_json": records_json,
            "summary_json": summary_json,
            "record_count": len(records),
            "plots_json": plots_json,
            "warnings_json": warnings_json,
            "errors_json": errors_json,
            "output_file_path": "",
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        parsed_cursor = conn.execute(
            """
            INSERT INTO parsed_data (
                raw_data_id, sample_id, sample_uid, sample_display_code,
                raw_data_code, data_type, parser_name, parser_version,
                parsed_status, schema_version, records_json, summary_json,
                record_count, plots_json, warnings_json, errors_json,
                output_file_path, created_at, updated_at
            )
            VALUES (
                :raw_data_id, :sample_id, :sample_uid, :sample_display_code,
                :raw_data_code, :data_type, :parser_name, :parser_version,
                :parsed_status, :schema_version, :records_json, :summary_json,
                :record_count, :plots_json, :warnings_json, :errors_json,
                :output_file_path, :created_at, :updated_at
            )
            """,
            parsed_payload,
        )
        parsed_id = parsed_cursor.lastrowid
        insert_parsed_records(
            conn,
            parsed_id,
            {
                "raw_data_id": raw_data_id,
                "sample_id": raw_data["sample_id"],
                "sample_uid": raw_data["sample_uid"],
                "raw_data_code": raw_data["raw_data_code"],
                "data_type": raw_data["data_type"],
            },
            records,
            timestamp,
        )
        output_json = json.dumps(
            {
                "parsed_data_id": parsed_id,
                "schema_version": "1.0",
                "parser_name": parser_name,
                "parser_version": parser_version,
            },
            ensure_ascii=False,
        )
        conn.execute(
            """
            UPDATE processing_jobs
            SET parsed_data_id = ?, output_json = ?, status = 'success', finished_at = ?
            WHERE id = ?
            """,
            (parsed_id, output_json, timestamp, job_cursor.lastrowid),
        )
        conn.execute(
            "UPDATE raw_data SET parser_status = 'parsed', updated_at = ? WHERE id = ?",
            (timestamp, raw_data_id),
        )
        return parsed_data_row(conn, parsed_id)


def insert_processing_job(conn, payload):
    cursor = conn.execute(
        """
        INSERT INTO processing_jobs (
            job_type, job_name, raw_data_id, parsed_data_id, sample_id,
            sample_uid, data_type, script_name, script_version, input_json,
            output_json, status, error_message, started_at, finished_at
        )
        VALUES (
            :job_type, :job_name, :raw_data_id, :parsed_data_id, :sample_id,
            :sample_uid, :data_type, :script_name, :script_version, :input_json,
            :output_json, :status, :error_message, :started_at, :finished_at
        )
        """,
        payload,
    )
    return cursor.lastrowid


PARSED_RECORD_INSERT_COLUMNS = [
    "parsed_data_id",
    "raw_data_id",
    "sample_id",
    "sample_uid",
    "raw_data_code",
    "data_type",
    "record_index",
    "primary_key",
    "group_key",
    "x_value",
    "y_value",
    "numeric_value",
    "raw_value",
    "cleaned_value",
    "is_outlier",
    "outlier_reason",
    "die_id",
    "area",
    "row_index",
    "col_index",
    "row_header",
    "col_header",
    "row_group",
    "side",
    "direction",
    "dose",
    "location",
    "extra_json",
    "created_at",
]

PARSED_RECORD_MAPPED_KEYS = {
    "parsed_data_id",
    "raw_data_id",
    "sample_id",
    "sample_uid",
    "raw_data_code",
    "data_type",
    "record_index",
    "primary_key",
    "group_key",
    "x_value",
    "y_value",
    "numeric_value",
    "raw_value",
    "cleaned_value",
    "is_outlier",
    "outlier_reason",
    "die_id",
    "die_no",
    "area",
    "row_index",
    "col_index",
    "row_header",
    "col_header",
    "row_group",
    "side",
    "direction",
    "dose",
    "location",
    "cd_value",
}


def first_present(record, keys, default=None):
    for key in keys:
        if key in record:
            return record.get(key)
    return default


def text_or_none(value):
    if value is None:
        return None
    return str(value)


def finite_float_or_none(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def int_or_none(value):
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def bool_to_int(value):
    if isinstance(value, str):
        return 1 if value.strip().lower() in {"1", "true", "yes", "y"} else 0
    return 1 if bool(value) else 0


def map_parsed_record(record, context, record_index, created_at):
    if not isinstance(record, dict):
        record = {"raw_value": record}

    raw_value = first_present(record, ["raw_value", "cd_value"])
    cleaned_value = first_present(record, ["cleaned_value", "cd_value", "raw_value"])
    numeric_value = first_present(record, ["numeric_value", "cleaned_value", "raw_value", "cd_value"])
    die_id = first_present(record, ["die_id", "die_no"])

    extra = {
        key: value
        for key, value in record.items()
        if key not in PARSED_RECORD_MAPPED_KEYS
    }

    return {
        "parsed_data_id": context["parsed_data_id"],
        "raw_data_id": record.get("raw_data_id", context["raw_data_id"]),
        "sample_id": record.get("sample_id", context["sample_id"]),
        "sample_uid": record.get("sample_uid", context["sample_uid"]),
        "raw_data_code": record.get("raw_data_code", context["raw_data_code"]),
        "data_type": record.get("data_type", context["data_type"]),
        "record_index": int_or_none(record.get("record_index")) or record_index,
        "primary_key": text_or_none(record.get("primary_key")),
        "group_key": text_or_none(record.get("group_key")),
        "x_value": finite_float_or_none(record.get("x_value")),
        "y_value": finite_float_or_none(record.get("y_value")),
        "numeric_value": finite_float_or_none(numeric_value),
        "raw_value": text_or_none(raw_value),
        "cleaned_value": text_or_none(cleaned_value),
        "is_outlier": bool_to_int(record.get("is_outlier", False)),
        "outlier_reason": text_or_none(record.get("outlier_reason")),
        "die_id": text_or_none(die_id),
        "area": text_or_none(record.get("area")),
        "row_index": int_or_none(record.get("row_index")),
        "col_index": int_or_none(record.get("col_index")),
        "row_header": text_or_none(record.get("row_header")),
        "col_header": text_or_none(record.get("col_header")),
        "row_group": text_or_none(record.get("row_group")),
        "side": text_or_none(record.get("side")),
        "direction": text_or_none(record.get("direction")),
        "dose": text_or_none(record.get("dose")),
        "location": text_or_none(record.get("location")),
        "extra_json": json.dumps(extra, ensure_ascii=False),
        "created_at": created_at,
    }


def insert_parsed_records(conn, parsed_data_id, parsed_output, records, created_at):
    if not records:
        return 0

    context = {
        "parsed_data_id": parsed_data_id,
        "raw_data_id": parsed_output["raw_data_id"],
        "sample_id": parsed_output["sample_id"],
        "sample_uid": parsed_output.get("sample_uid", ""),
        "raw_data_code": parsed_output.get("raw_data_code", ""),
        "data_type": parsed_output["data_type"],
    }
    rows = [
        map_parsed_record(record, context, index, created_at)
        for index, record in enumerate(records, start=1)
    ]
    columns_sql = ", ".join(PARSED_RECORD_INSERT_COLUMNS)
    placeholders_sql = ", ".join(f":{column}" for column in PARSED_RECORD_INSERT_COLUMNS)
    conn.executemany(
        f"""
        INSERT INTO parsed_records ({columns_sql})
        VALUES ({placeholders_sql})
        """,
        rows,
    )
    return len(rows)


def insert_parsed_data(conn, parsed_output):
    timestamp = now_iso()
    records = parsed_output.get("records", [])
    if not isinstance(records, list):
        records = []
    payload = {
        "raw_data_id": parsed_output["raw_data_id"],
        "sample_id": parsed_output["sample_id"],
        "sample_uid": parsed_output.get("sample_uid", ""),
        "sample_display_code": parsed_output.get("sample_display_code", ""),
        "raw_data_code": parsed_output.get("raw_data_code", ""),
        "data_type": parsed_output["data_type"],
        "parser_name": parsed_output.get("parser_name", ""),
        "parser_version": parsed_output.get("parser_version", ""),
        "parsed_status": "success" if not parsed_output.get("errors") else "failed",
        "schema_version": parsed_output.get("schema_version", "1.0"),
        "records_json": "[]",
        "summary_json": json.dumps(parsed_output.get("summary", {}), ensure_ascii=False),
        "record_count": len(records),
        "plots_json": json.dumps(parsed_output.get("plots", []), ensure_ascii=False),
        "warnings_json": json.dumps(parsed_output.get("warnings", []), ensure_ascii=False),
        "errors_json": json.dumps(parsed_output.get("errors", []), ensure_ascii=False),
        "output_file_path": parsed_output.get("output_file_path", ""),
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    cursor = conn.execute(
        """
        INSERT INTO parsed_data (
            raw_data_id, sample_id, sample_uid, sample_display_code,
            raw_data_code, data_type, parser_name, parser_version,
            parsed_status, schema_version, records_json, summary_json,
            record_count, plots_json, warnings_json, errors_json,
            output_file_path, created_at, updated_at
        )
        VALUES (
            :raw_data_id, :sample_id, :sample_uid, :sample_display_code,
            :raw_data_code, :data_type, :parser_name, :parser_version,
            :parsed_status, :schema_version, :records_json, :summary_json,
            :record_count, :plots_json, :warnings_json, :errors_json,
            :output_file_path, :created_at, :updated_at
        )
        """,
        payload,
    )
    parsed_data_id = cursor.lastrowid
    insert_parsed_records(conn, parsed_data_id, parsed_output, records, timestamp)
    return parsed_data_id


def raw_data_file_path(row):
    target = resolve_data_path(row["file_path"])
    raw_root = (UPLOAD_DIR / "raw_data").resolve()
    if not str(target).startswith(str(raw_root)):
        raise ValueError("invalid raw data file path")
    return target


def parse_raw_data(raw_data_id, payload=None):
    payload = payload or {}
    requested_parser_name = optional_text(payload, "parser_name")

    timestamp = now_iso()
    with connect_db() as conn:
        raw_data = conn.execute("SELECT * FROM raw_data WHERE id = ?", (raw_data_id,)).fetchone()
        if raw_data is None:
            raise LookupError("raw data not found")

        if raw_data["data_type"] == "resistance":
            parser_name = requested_parser_name or "resistance_csv_parser"
            parser_version = "0.1.0"
            parse_func = parse_resistance_csv
            if parser_name != "resistance_csv_parser":
                raise ValueError("resistance raw data only supports resistance_csv_parser")
        elif raw_data["data_type"] == "cd_sem":
            parser_name = requested_parser_name or "cd_template_parser"
            parser_version = "0.1.0"
            parse_func = parse_cd_template_csv
            if parser_name != "cd_template_parser":
                raise ValueError("cd_sem raw data only supports cd_template_parser")
        else:
            raise ValueError("当前数据类型暂无 parser")

        conn.execute(
            "UPDATE raw_data SET parser_status = 'parsing', updated_at = ? WHERE id = ?",
            (timestamp, raw_data_id),
        )
        job_payload = {
            "job_type": "parse",
            "job_name": f"Parse {raw_data['raw_data_code']}",
            "raw_data_id": raw_data_id,
            "parsed_data_id": None,
            "sample_id": raw_data["sample_id"],
            "sample_uid": raw_data["sample_uid"],
            "data_type": raw_data["data_type"],
            "script_name": parser_name,
            "script_version": parser_version,
            "input_json": json.dumps({"raw_data_id": raw_data_id}, ensure_ascii=False),
            "output_json": "{}",
            "status": "running",
            "error_message": "",
            "started_at": timestamp,
            "finished_at": "",
        }
        if raw_data["data_type"] == "resistance":
            parser_files = conn.execute(
                """
                SELECT *,
                       CASE
                         WHEN LOWER(file_ext) = 'xlsx'
                           OR LOWER(original_filename) LIKE '%.xlsx'
                           OR LOWER(stored_filename) LIKE '%.xlsx' THEN 1
                         WHEN LOWER(file_ext) = 'csv'
                           OR LOWER(original_filename) LIKE '%.csv'
                           OR LOWER(stored_filename) LIKE '%.csv' THEN 2
                         ELSE 9
                       END AS parser_priority
                FROM raw_data_files
                WHERE raw_data_id = ?
                  AND (
                    LOWER(file_ext) IN ('xlsx', 'csv')
                    OR LOWER(original_filename) LIKE '%.xlsx'
                    OR LOWER(original_filename) LIKE '%.csv'
                    OR LOWER(stored_filename) LIKE '%.xlsx'
                    OR LOWER(stored_filename) LIKE '%.csv'
                  )
                ORDER BY parser_priority ASC, created_at DESC, id DESC
                """,
                (raw_data_id,),
            ).fetchall()
            xls_count = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM raw_data_files
                WHERE raw_data_id = ?
                  AND (
                    LOWER(file_ext) = 'xls'
                    OR LOWER(original_filename) LIKE '%.xls'
                    OR LOWER(stored_filename) LIKE '%.xls'
                  )
                """,
                (raw_data_id,),
            ).fetchone()["count"]
            missing_message = (
                "Current Resistance parser supports CSV/XLSX; no parseable file was found. "
                "XLS is not supported in this environment; please convert XLS to XLSX or CSV."
                if xls_count
                else "Current Resistance parser supports CSV/XLSX; no parseable file was found."
            )
            supported_format = "csv/xlsx"
        else:
            parser_files = conn.execute(
                """
                SELECT *
                FROM raw_data_files
                WHERE raw_data_id = ?
                  AND (
                    LOWER(file_ext) = 'csv'
                    OR LOWER(original_filename) LIKE '%.csv'
                    OR LOWER(stored_filename) LIKE '%.csv'
                  )
                ORDER BY created_at DESC, id DESC
                """,
                (raw_data_id,),
            ).fetchall()
            missing_message = "\u5f53\u524d Raw Data \u672a\u627e\u5230\u53ef\u89e3\u6790\u7684 CSV \u6587\u4ef6"
            supported_format = "csv"

        parser_file = parser_files[0] if parser_files else None
        if parser_file is None:
            finished_at = now_iso()
            job_payload["status"] = "failed"
            job_payload["error_message"] = missing_message
            job_payload["finished_at"] = finished_at
            insert_processing_job(conn, job_payload)
            conn.execute(
                "UPDATE raw_data SET parser_status = 'parse_failed', updated_at = ? WHERE id = ?",
                (finished_at, raw_data_id),
            )
            conn.commit()
            raise ValueError(missing_message)

        job_payload["input_json"] = json.dumps(
            {
                "raw_data_id": raw_data_id,
                "file_id": parser_file["id"],
                "original_filename": parser_file["original_filename"],
                "file_size": parser_file["file_size"],
                "sha256": parser_file["sha256"],
                "created_at": parser_file["created_at"],
                "parseable_file_count": len(parser_files),
                "parser_name": parser_name,
                "supported_format": supported_format,
                "strict_mode": False,
            },
            ensure_ascii=False,
        )
        job_id = insert_processing_job(conn, job_payload)

    try:
        parsed_output = parse_func(
            raw_data_file_path(parser_file),
            raw_data_id=raw_data["id"],
            sample_id=raw_data["sample_id"],
            sample_uid=raw_data["sample_uid"],
            raw_data_code=raw_data["raw_data_code"],
            sample_display_code=raw_data["sample_display_code"],
            data_type=raw_data["data_type"],
            source_file_info={
                "file_id": parser_file["id"],
                "original_filename": parser_file["original_filename"],
                "stored_filename": parser_file["stored_filename"],
                "file_size": parser_file["file_size"],
                "sha256": parser_file["sha256"],
                "created_at": parser_file["created_at"],
            },
        )
        parsed_output.setdefault("summary", {})["source_file"] = {
            "file_id": parser_file["id"],
            "original_filename": parser_file["original_filename"],
            "file_size": parser_file["file_size"],
            "sha256": parser_file["sha256"],
            "created_at": parser_file["created_at"],
        }
        if len(parser_files) > 1:
            parsed_output.setdefault("warnings", []).append(
                {
                    "row": None,
                    "field": "source_file",
                    "message": "Multiple parseable source files were found; the parser selected the highest-priority latest file.",
                    "value": parser_file["original_filename"],
                }
            )
    except Exception as exc:
        finished_at = now_iso()
        with connect_db() as conn:
            conn.execute(
                """
                UPDATE processing_jobs
                SET status = 'failed', error_message = ?, finished_at = ?
                WHERE id = ?
                """,
                (str(exc), finished_at, job_id),
            )
            conn.execute(
                "UPDATE raw_data SET parser_status = 'parse_failed', updated_at = ? WHERE id = ?",
                (finished_at, raw_data_id),
            )
        raise

    finished_at = now_iso()
    with connect_db() as conn:
        parsed_id = insert_parsed_data(conn, parsed_output)
        output_json = json.dumps(
            {
                "parsed_data_id": parsed_id,
                "summary": parsed_output.get("summary", {}),
                "warnings": parsed_output.get("warnings", []),
            },
            ensure_ascii=False,
        )
        conn.execute(
            """
            UPDATE processing_jobs
            SET parsed_data_id = ?, output_json = ?, status = 'success', finished_at = ?
            WHERE id = ?
            """,
            (parsed_id, output_json, finished_at, job_id),
        )
        conn.execute(
            "UPDATE raw_data SET parser_status = 'parsed', updated_at = ? WHERE id = ?",
            (finished_at, raw_data_id),
        )
        return raw_data_row_with_files(conn, raw_data_id)


def get_processing_jobs(query_params):
    raw_data_id = query_params.get("raw_data_id", [""])[0].strip()
    sample_id = query_params.get("sample_id", [""])[0].strip()
    job_type = query_params.get("job_type", [""])[0].strip()
    status = query_params.get("status", [""])[0].strip()
    where = []
    args = []

    if raw_data_id:
        where.append("raw_data_id = ?")
        args.append(raw_data_id)
    if sample_id:
        where.append("sample_id = ?")
        args.append(sample_id)
    if job_type:
        where.append("job_type = ?")
        args.append(job_type)
    if status:
        where.append("status = ?")
        args.append(status)

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    with connect_db() as conn:
        return rows_dict(
            conn.execute(
                f"""
                SELECT *
                FROM processing_jobs
                {where_sql}
                ORDER BY COALESCE(started_at, finished_at) DESC, id DESC
                LIMIT 500
                """,
                args,
            ).fetchall()
        )


def get_raw_data_list(query_params):
    sample_id = query_params.get("sample_id", [""])[0].strip()
    data_type = query_params.get("data_type", [""])[0].strip()
    parser_status = query_params.get("parser_status", [""])[0].strip()
    status = query_params.get("status", [""])[0].strip()
    query = query_params.get("query", [""])[0].strip()
    where = []
    args = []

    if sample_id:
        where.append("rd.sample_id = ?")
        args.append(sample_id)
    if data_type:
        where.append("rd.data_type = ?")
        args.append(data_type)
    if parser_status:
        where.append("rd.parser_status = ?")
        args.append(parser_status)
    if status:
        where.append("rd.status = ?")
        args.append(status)
    if query:
        like = f"%{query}%"
        where.append(
            "(rd.raw_data_code LIKE ? OR rd.raw_data_name LIKE ? OR rd.sample_display_code LIKE ? OR rd.sample_uid LIKE ? OR rd.instrument LIKE ? OR rd.operator LIKE ? OR rd.notes LIKE ?)"
        )
        args.extend([like, like, like, like, like, like, like])

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    with connect_db() as conn:
        return rows_dict(
            conn.execute(
                f"""
                SELECT rd.*
                FROM raw_data rd
                {where_sql}
                ORDER BY rd.created_at DESC, rd.id DESC
                LIMIT 500
                """,
                args,
            ).fetchall()
        )


def create_raw_data(payload):
    try:
        sample_id = int(payload.get("sample_id", ""))
    except (TypeError, ValueError):
        raise ValueError("sample_id must be numeric")

    raw_data_name = require_text(payload, "raw_data_name")
    data_type = normalize_raw_data_type(payload.get("data_type"))
    measured_at = optional_text(payload, "measured_at")
    timestamp = now_iso()

    metadata_value = payload.get("metadata_json", "")
    if isinstance(metadata_value, (dict, list)):
        metadata_json = json.dumps(metadata_value, ensure_ascii=False)
    else:
        metadata_json = optional_text(payload, "metadata_json")
        if metadata_json:
            try:
                json.loads(metadata_json)
            except json.JSONDecodeError as exc:
                raise ValueError("metadata_json must be valid JSON") from exc

    with connect_db() as conn:
        sample = get_sample_row(conn, sample_id)
        sample_uid = sample["sample_uid"] or generate_sample_uid(conn)
        sample_display_code = sample["sample_display_code"] or build_sample_display_code(sample)
        raw_data_code = generate_raw_data_code(conn, sample_uid, data_type, measured_at)
        target_dir = UPLOAD_DIR / "raw_data" / safe_path_part(raw_data_code, "raw-data")
        payload_to_insert = {
            "sample_id": sample_id,
            "sample_uid": sample_uid,
            "sample_display_code": sample_display_code,
            "raw_data_code": raw_data_code,
            "raw_data_name": raw_data_name,
            "data_type": data_type,
            "data_category": raw_data_category_for(data_type),
            "source_type": optional_text(payload, "source_type"),
            "instrument": optional_text(payload, "instrument"),
            "operator": optional_text(payload, "operator"),
            "measured_at": measured_at,
            "parser_status": "not_parsed",
            "status": "imported",
            "file_count": 0,
            "total_size": 0,
            "storage_path": storage_path_for(target_dir),
            "metadata_json": metadata_json,
            "notes": optional_text(payload, "notes"),
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        cursor = conn.execute(
            """
            INSERT INTO raw_data (
                sample_id, sample_uid, sample_display_code, raw_data_code,
                raw_data_name, data_type, data_category, source_type, instrument,
                operator, measured_at, parser_status, status, file_count,
                total_size, storage_path, metadata_json, notes, created_at, updated_at
            )
            VALUES (
                :sample_id, :sample_uid, :sample_display_code, :raw_data_code,
                :raw_data_name, :data_type, :data_category, :source_type, :instrument,
                :operator, :measured_at, :parser_status, :status, :file_count,
                :total_size, :storage_path, :metadata_json, :notes, :created_at, :updated_at
            )
            """,
            payload_to_insert,
        )
        return raw_data_row_with_files(conn, cursor.lastrowid)


def get_raw_data_detail(raw_data_id):
    with connect_db() as conn:
        return raw_data_row_with_files(conn, raw_data_id)


def save_raw_data_file(file_item, target_dir, raw_data_code):
    ensure_upload_root()
    original_name = Path(file_item.get("filename") or "upload.bin").name or "upload.bin"
    safe_name = safe_path_part(original_name, "upload.bin")
    stored_filename = f"{uuid.uuid4().hex}-{safe_name}"
    target = target_dir / stored_filename
    target.parent.mkdir(parents=True, exist_ok=True)

    with target.open("wb") as handle:
        handle.write(file_item["content"])

    file_ext = Path(original_name).suffix.lower().lstrip(".")
    mime_type = file_item.get("mime_type") or mimetypes.guess_type(original_name)[0] or ""
    return {
        "original_filename": original_name,
        "stored_filename": stored_filename,
        "relative_path": f"{raw_data_code}/{stored_filename}",
        "file_path": storage_path_for(target),
        "file_ext": file_ext,
        "mime_type": mime_type,
        "file_size": target.stat().st_size,
        "sha256": file_sha256(target),
        "preview_supported": 1 if preview_type_for_file({"mime_type": mime_type, "original_filename": original_name}) != "download" else 0,
    }


def upload_raw_data_files(raw_data_id, files):
    if not files:
        raise ValueError("at least one file is required")

    timestamp = now_iso()
    with connect_db() as conn:
        raw_data = conn.execute("SELECT * FROM raw_data WHERE id = ?", (raw_data_id,)).fetchone()
        if raw_data is None:
            raise LookupError("raw data not found")

        raw_root = (UPLOAD_DIR / "raw_data").resolve()
        target_dir = (UPLOAD_DIR / "raw_data" / safe_path_part(raw_data["raw_data_code"], "raw-data")).resolve()
        if not str(target_dir).startswith(str(raw_root)):
            raise ValueError("invalid raw data storage path")

        for file_item in files:
            stored = save_raw_data_file(file_item, target_dir, raw_data["raw_data_code"])
            payload = {
                "raw_data_id": raw_data_id,
                "created_at": timestamp,
                **stored,
            }
            conn.execute(
                """
                INSERT INTO raw_data_files (
                    raw_data_id, original_filename, stored_filename, relative_path,
                    file_path, file_ext, mime_type, file_size, sha256,
                    preview_supported, created_at
                )
                VALUES (
                    :raw_data_id, :original_filename, :stored_filename, :relative_path,
                    :file_path, :file_ext, :mime_type, :file_size, :sha256,
                    :preview_supported, :created_at
                )
                """,
                payload,
            )

        totals = conn.execute(
            """
            SELECT COUNT(*) AS file_count, COALESCE(SUM(file_size), 0) AS total_size
            FROM raw_data_files
            WHERE raw_data_id = ?
            """,
            (raw_data_id,),
        ).fetchone()
        conn.execute(
            """
            UPDATE raw_data
            SET file_count = ?, total_size = ?, updated_at = ?
            WHERE id = ?
            """,
            (totals["file_count"], totals["total_size"], timestamp, raw_data_id),
        )
        return raw_data_row_with_files(conn, raw_data_id)


def delete_raw_data(raw_data_id):
    with connect_db() as conn:
        raw_data = conn.execute("SELECT storage_path FROM raw_data WHERE id = ?", (raw_data_id,)).fetchone()
        if raw_data is None:
            raise LookupError("raw data not found")
        file_rows = conn.execute(
            "SELECT file_path FROM raw_data_files WHERE raw_data_id = ?",
            (raw_data_id,),
        ).fetchall()
        conn.execute("DELETE FROM processing_jobs WHERE raw_data_id = ?", (raw_data_id,))
        conn.execute("DELETE FROM parsed_records WHERE raw_data_id = ?", (raw_data_id,))
        conn.execute("DELETE FROM parsed_data WHERE raw_data_id = ?", (raw_data_id,))
        conn.execute("DELETE FROM raw_data WHERE id = ?", (raw_data_id,))

    raw_root = (UPLOAD_DIR / "raw_data").resolve()
    for row in file_rows:
        target = resolve_data_path(row["file_path"])
        if str(target).startswith(str(raw_root)) and target.is_file():
            target.unlink(missing_ok=True)

    storage_dir = resolve_data_path(raw_data["storage_path"]) if raw_data["storage_path"] else None
    if storage_dir and str(storage_dir).startswith(str(raw_root)) and storage_dir.exists():
        shutil.rmtree(storage_dir, ignore_errors=True)
    return {"deleted": raw_data_id}


def delete_raw_data_file(file_id):
    timestamp = now_iso()
    with connect_db() as conn:
        file_record = raw_data_file_row(conn, file_id)
        raw_data_id = file_record["raw_data_id"]
        file_count = conn.execute(
            "SELECT COUNT(*) AS count FROM raw_data_files WHERE raw_data_id = ?",
            (raw_data_id,),
        ).fetchone()["count"]

        if file_count > 1:
            raise ConflictError(
                "当前 Raw Data 下存在多个源文件，系统暂不能安全判断该文件对应的全部派生结果。"
                "请先使用整条 Raw Data 删除，或后续补充 raw_file_id 关系后再支持精确删除。"
            )

        target = raw_data_upload_file_path(file_record)

        parsed_rows = conn.execute(
            "SELECT id FROM parsed_data WHERE raw_data_id = ?",
            (raw_data_id,),
        ).fetchall()
        job_rows = conn.execute(
            "SELECT id, output_json FROM processing_jobs WHERE raw_data_id = ?",
            (raw_data_id,),
        ).fetchall()
        deleted_parsed_data_ids = [row["id"] for row in parsed_rows]
        deleted_processing_job_ids = [row["id"] for row in job_rows]

        conn.execute("DELETE FROM processing_jobs WHERE raw_data_id = ?", (raw_data_id,))
        conn.execute("DELETE FROM parsed_records WHERE raw_data_id = ?", (raw_data_id,))
        conn.execute("DELETE FROM parsed_data WHERE raw_data_id = ?", (raw_data_id,))
        conn.execute("DELETE FROM raw_data_files WHERE id = ?", (file_id,))
        conn.execute(
            """
            UPDATE raw_data
            SET file_count = 0,
                total_size = 0,
                parser_status = 'not_parsed',
                updated_at = ?
            WHERE id = ?
            """,
            (timestamp, raw_data_id),
        )
        detail = raw_data_row_with_files(conn, raw_data_id)

    if target.is_file():
        target.unlink(missing_ok=True)

    deleted_output_paths = delete_output_files_for_jobs(job_rows)

    return {
        "deleted_file_id": file_id,
        "raw_data_id": raw_data_id,
        "deleted_parsed_data_ids": deleted_parsed_data_ids,
        "deleted_processing_job_ids": deleted_processing_job_ids,
        "deleted_output_paths": deleted_output_paths,
        "strategy": "single_file_raw_data_cascade",
        "raw_data": detail,
    }


def get_characterization_files(query_params):
    sample_id = query_params.get("sample_id", [""])[0].strip()
    category = query_params.get("category", [""])[0].strip()
    query = query_params.get("query", [""])[0].strip()
    where = []
    args = []
    if sample_id:
        where.append("cf.sample_id = ?")
        args.append(sample_id)
    if category:
        where.append("cf.category = ?")
        args.append(category)
    if query:
        like = f"%{query}%"
        where.append(
            "(s.sample_code LIKE ? OR s.name LIKE ? OR cf.category LIKE ? OR cf.technique LIKE ? OR cf.title LIKE ? OR cf.original_filename LIKE ?)"
        )
        args.extend([like, like, like, like, like, like])

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    with connect_db() as conn:
        return rows_dict(
            conn.execute(
                f"""
                SELECT cf.*, s.sample_code, s.name AS sample_name,
                       cc.name AS collection_name, cc.storage_dir AS collection_storage_dir
                FROM characterization_files cf
                JOIN samples s ON s.id = cf.sample_id
                LEFT JOIN characterization_collections cc ON cc.id = cf.collection_id
                {where_sql}
                ORDER BY cf.created_at DESC, cf.id DESC
                LIMIT 1000
                """,
                args,
            ).fetchall()
        )


def characterization_file_record(row):
    item = row_dict(row)
    if item:
        item["preview_type"] = preview_type_for_file(item)
        item["is_previewable"] = item["preview_type"] != "download"
    return item


def collection_storage_dir(sample, collection_id, collection_name):
    sample_part = f"sample-{sample['id']}_{safe_path_part(sample['sample_code'], 'sample')}"
    collection_part = f"collection-{collection_id}_{safe_path_part(collection_name, 'collection')}"
    return UPLOAD_DIR / "characterization" / sample_part / collection_part


def create_characterization_collection_record(conn, fields):
    try:
        sample_id = int(fields.get("sample_id", ""))
    except (TypeError, ValueError):
        raise ValueError("sample_id must be numeric")

    sample = get_sample_row(conn, sample_id)
    timestamp = now_iso()
    category = optional_text(fields, "category") or "未分类"
    name = optional_text(fields, "collection_name") or optional_text(fields, "name")
    if not name:
        technique = optional_text(fields, "technique")
        captured_at = optional_text(fields, "captured_at")
        name = " / ".join([part for part in (technique, category, captured_at) if part]) or "未命名表征数据包"

    cursor = conn.execute(
        """
        INSERT INTO characterization_collections (
            sample_id, category, name, technique, instrument, captured_at,
            operator, notes, storage_dir, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sample_id,
            category,
            name,
            optional_text(fields, "technique"),
            optional_text(fields, "instrument"),
            optional_text(fields, "captured_at"),
            optional_text(fields, "operator"),
            optional_text(fields, "notes"),
            "",
            timestamp,
            timestamp,
        ),
    )
    collection_id = cursor.lastrowid
    target_dir = collection_storage_dir(sample, collection_id, name)
    conn.execute(
        "UPDATE characterization_collections SET storage_dir = ? WHERE id = ?",
        (storage_path_for(target_dir), collection_id),
    )
    return collection_id


def get_or_create_characterization_collection(conn, fields):
    collection_id = fields.get("collection_id")
    if collection_id not in ("", None):
        try:
            collection_id = int(collection_id)
        except (TypeError, ValueError):
            raise ValueError("collection_id must be numeric")
        row = conn.execute(
            "SELECT * FROM characterization_collections WHERE id = ?",
            (collection_id,),
        ).fetchone()
        if row is None:
            raise ValueError("collection_id not found")
        return row

    collection_id = create_characterization_collection_record(conn, fields)
    return conn.execute(
        "SELECT * FROM characterization_collections WHERE id = ?",
        (collection_id,),
    ).fetchone()


def create_characterization_collection(payload):
    with connect_db() as conn:
        collection_id = create_characterization_collection_record(conn, payload)
        return get_characterization_collection(collection_id, conn=conn)


def get_characterization_collection(collection_id, conn=None):
    own_conn = conn is None
    if own_conn:
        conn = connect_db()
    try:
        row = conn.execute(
            """
            SELECT cc.*, s.sample_code, s.name AS sample_name,
                   COUNT(cf.id) AS file_count,
                   COALESCE(SUM(cf.file_size), 0) AS total_bytes,
                   MAX(cf.created_at) AS latest_file_at
            FROM characterization_collections cc
            JOIN samples s ON s.id = cc.sample_id
            LEFT JOIN characterization_files cf ON cf.collection_id = cc.id
            WHERE cc.id = ?
            GROUP BY cc.id
            """,
            (collection_id,),
        ).fetchone()
        if row is None:
            raise LookupError("characterization collection not found")
        return row_dict(row)
    finally:
        if own_conn:
            conn.close()


def get_characterization_samples(query_params):
    query = query_params.get("query", [""])[0].strip()
    where = []
    args = []
    if query:
        like = f"%{query}%"
        where.append("(s.sample_code LIKE ? OR s.name LIKE ? OR s.category LIKE ? OR s.batch LIKE ? OR s.owner LIKE ?)")
        args.extend([like, like, like, like, like])
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    with connect_db() as conn:
        return rows_dict(
            conn.execute(
                f"""
                SELECT
                    s.*,
                    COUNT(DISTINCT cc.id) AS collection_count,
                    COUNT(cf.id) AS characterization_file_count,
                    COUNT(DISTINCT cc.category) AS characterization_category_count,
                    MAX(COALESCE(cf.created_at, cc.created_at)) AS latest_characterization_at
                FROM samples s
                LEFT JOIN characterization_collections cc ON cc.sample_id = s.id
                LEFT JOIN characterization_files cf ON cf.collection_id = cc.id
                {where_sql}
                GROUP BY s.id
                ORDER BY latest_characterization_at DESC, s.created_at DESC, s.id DESC
                """,
                args,
            ).fetchall()
        )


def get_characterization_tree(sample_id, query_params):
    query = query_params.get("query", [""])[0].strip()
    with connect_db() as conn:
        sample = row_dict(conn.execute("SELECT * FROM samples WHERE id = ?", (sample_id,)).fetchone())
        if sample is None:
            raise LookupError("sample not found")

        collection_where = ["cc.sample_id = ?"]
        collection_args = [sample_id]
        if query:
            like = f"%{query}%"
            collection_where.append(
                """
                (
                    cc.category LIKE ? OR cc.name LIKE ? OR cc.technique LIKE ? OR cc.instrument LIKE ?
                    OR cc.operator LIKE ? OR cc.notes LIKE ? OR cf.original_filename LIKE ? OR cf.title LIKE ?
                )
                """
            )
            collection_args.extend([like, like, like, like, like, like, like, like])

        where_sql = f"WHERE {' AND '.join(collection_where)}"
        collection_rows = rows_dict(
            conn.execute(
                f"""
                SELECT
                    cc.*,
                    COUNT(cf.id) AS file_count,
                    COALESCE(SUM(cf.file_size), 0) AS total_bytes,
                    MAX(cf.created_at) AS latest_file_at
                FROM characterization_collections cc
                LEFT JOIN characterization_files cf ON cf.collection_id = cc.id
                {where_sql}
                GROUP BY cc.id
                ORDER BY cc.category, cc.created_at DESC, cc.id DESC
                """,
                collection_args,
            ).fetchall()
        )

        collection_ids = [row["id"] for row in collection_rows]
        files_by_collection = {collection_id: [] for collection_id in collection_ids}
        if collection_ids:
            placeholders = ",".join("?" for _ in collection_ids)
            file_where = [f"cf.collection_id IN ({placeholders})"]
            file_args = list(collection_ids)
            if query:
                like = f"%{query}%"
                file_where.append(
                    "(cf.original_filename LIKE ? OR cf.title LIKE ? OR cf.category LIKE ? OR cf.technique LIKE ? OR cf.notes LIKE ?)"
                )
                file_args.extend([like, like, like, like, like])
            file_rows = conn.execute(
                f"""
                SELECT cf.*
                FROM characterization_files cf
                WHERE {' AND '.join(file_where)}
                ORDER BY cf.relative_path, cf.created_at DESC, cf.id DESC
                """,
                file_args,
            ).fetchall()
            for row in file_rows:
                item = characterization_file_record(row)
                files_by_collection.setdefault(item["collection_id"], []).append(item)

        categories = []
        category_map = {}
        for collection in collection_rows:
            category_name = collection["category"] or "未分类"
            if category_name not in category_map:
                category_map[category_name] = {"name": category_name, "collections": [], "file_count": 0}
                categories.append(category_map[category_name])
            collection["files"] = files_by_collection.get(collection["id"], [])
            category_map[category_name]["file_count"] += len(collection["files"])
            category_map[category_name]["collections"].append(collection)

    return {"sample": sample, "categories": categories}


def create_characterization_files(fields, files):
    if not files:
        raise ValueError("at least one file is required")

    timestamp = now_iso()
    created = []
    with connect_db() as conn:
        collection = get_or_create_characterization_collection(conn, fields)
        sample_id = collection["sample_id"]
        category = collection["category"] or optional_text(fields, "category") or "未分类"
        technique = collection["technique"] or optional_text(fields, "technique")
        target_dir = resolve_data_path(collection["storage_dir"]) if collection["storage_dir"] else UPLOAD_DIR / "characterization" / f"collection-{collection['id']}"

        for file_item in files:
            stored = save_uploaded_file(file_item, target_dir)
            payload = {
                "collection_id": collection["id"],
                "sample_id": sample_id,
                "category": category,
                "technique": technique,
                "title": optional_text(fields, "title") or stored["original_filename"],
                "original_filename": stored["original_filename"],
                "stored_filename": stored["stored_filename"],
                "storage_path": stored["storage_path"],
                "mime_type": stored["mime_type"],
                "file_size": stored["file_size"],
                "relative_path": stored["relative_path"],
                "thumbnail_path": "",
                "captured_at": optional_text(fields, "captured_at"),
                "operator": optional_text(fields, "operator"),
                "notes": optional_text(fields, "notes"),
                "created_at": timestamp,
            }
            cursor = conn.execute(
                """
                INSERT INTO characterization_files (
                    collection_id, sample_id, category, technique, title, original_filename,
                    stored_filename, storage_path, mime_type, file_size, relative_path,
                    thumbnail_path, captured_at, operator, notes, created_at
                )
                VALUES (
                    :collection_id, :sample_id, :category, :technique, :title, :original_filename,
                    :stored_filename, :storage_path, :mime_type, :file_size, :relative_path,
                    :thumbnail_path, :captured_at, :operator, :notes, :created_at
                )
                """,
                payload,
            )
            created.append(cursor.lastrowid)

        conn.execute(
            "UPDATE characterization_collections SET updated_at = ? WHERE id = ?",
            (timestamp, collection["id"]),
        )

    return {"inserted": len(created), "ids": created, "collection_id": collection["id"]}


def delete_characterization_file(file_id):
    with connect_db() as conn:
        row = conn.execute("SELECT storage_path FROM characterization_files WHERE id = ?", (file_id,)).fetchone()
        if row is None:
            raise LookupError("characterization file not found")
        conn.execute("DELETE FROM characterization_files WHERE id = ?", (file_id,))
    remove_stored_path(row["storage_path"])
    return {"deleted": file_id}


def get_characterization_file(file_id):
    with connect_db() as conn:
        row = conn.execute(
            """
            SELECT cf.*, s.sample_code, s.name AS sample_name,
                   cc.name AS collection_name, cc.storage_dir AS collection_storage_dir,
                   cc.instrument AS collection_instrument
            FROM characterization_files cf
            JOIN samples s ON s.id = cf.sample_id
            LEFT JOIN characterization_collections cc ON cc.id = cf.collection_id
            WHERE cf.id = ?
            """,
            (file_id,),
        ).fetchone()
    if row is None:
        raise LookupError("characterization file not found")
    return characterization_file_record(row)


def characterization_file_path(file_record):
    target = resolve_data_path(file_record["storage_path"])
    upload_root = UPLOAD_DIR.resolve()
    if not str(target).startswith(str(upload_root)) or not target.is_file():
        raise LookupError("stored file not found")
    return target


def preview_type_for_file(file_record):
    mime_type = file_record.get("mime_type") or mimetypes.guess_type(file_record.get("original_filename", ""))[0] or ""
    suffix = Path(file_record.get("original_filename", "")).suffix.lower()
    if mime_type.startswith("image/"):
        return "image"
    if mime_type == "application/pdf" or suffix == ".pdf":
        return "pdf"
    if mime_type.startswith("text/") or suffix in {".csv", ".txt", ".json", ".md", ".log", ".dat"}:
        return "text"
    return "download"


def get_performance_datasets(query_params):
    sample_id = query_params.get("sample_id", [""])[0].strip()
    query = query_params.get("query", [""])[0].strip()
    where = []
    args = []
    if sample_id:
        where.append("pd.sample_id = ?")
        args.append(sample_id)
    if query:
        like = f"%{query}%"
        where.append(
            "(s.sample_display_code LIKE ? OR s.sample_uid LIKE ? OR s.sample_code LIKE ? OR s.name LIKE ? OR pd.aliquot_code LIKE ? OR pd.dataset_name LIKE ? OR pd.test_type LIKE ? OR pd.data_format LIKE ?)"
        )
        args.extend([like, like, like, like, like, like, like, like])

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    with connect_db() as conn:
        return rows_dict(
            conn.execute(
                f"""
                SELECT pd.*, s.sample_uid, s.sample_display_code, s.sample_code, s.name AS sample_name
                FROM performance_datasets pd
                JOIN samples s ON s.id = pd.sample_id
                {where_sql}
                ORDER BY pd.created_at DESC, pd.id DESC
                LIMIT 500
                """,
                args,
            ).fetchall()
        )


def get_performance_dataset_files(dataset_id):
    with connect_db() as conn:
        dataset = conn.execute("SELECT id FROM performance_datasets WHERE id = ?", (dataset_id,)).fetchone()
        if dataset is None:
            raise LookupError("performance dataset not found")
        return rows_dict(
            conn.execute(
                """
                SELECT *
                FROM performance_dataset_files
                WHERE dataset_id = ?
                ORDER BY relative_path, id
                """,
                (dataset_id,),
            ).fetchall()
        )


def create_performance_dataset(fields, files):
    if not files:
        raise ValueError("at least one file is required")

    try:
        sample_id = int(fields.get("sample_id", ""))
    except (TypeError, ValueError):
        raise ValueError("sample_id must be numeric")

    dataset_name = require_text(fields, "dataset_name")
    timestamp = now_iso()
    dataset_token = uuid.uuid4().hex

    with connect_db() as conn:
        sample = get_sample_row(conn, sample_id)
        target_dir = UPLOAD_DIR / "performance" / safe_path_part(sample["sample_code"], "sample") / safe_path_part(dataset_name, "dataset")
        target_dir = target_dir / dataset_token
        dataset_payload = {
            "sample_id": sample_id,
            "aliquot_code": optional_text(fields, "aliquot_code"),
            "dataset_name": dataset_name,
            "test_type": optional_text(fields, "test_type"),
            "data_format": optional_text(fields, "data_format"),
            "source_folder_name": optional_text(fields, "source_folder_name"),
            "storage_dir": storage_path_for(target_dir),
            "file_count": 0,
            "total_bytes": 0,
            "collected_at": optional_text(fields, "collected_at"),
            "operator": optional_text(fields, "operator"),
            "status": optional_text(fields, "status") or "待处理",
            "notes": optional_text(fields, "notes"),
            "created_at": timestamp,
        }
        cursor = conn.execute(
            """
            INSERT INTO performance_datasets (
                sample_id, aliquot_code, dataset_name, test_type, data_format,
                source_folder_name, storage_dir, file_count, total_bytes,
                collected_at, operator, status, notes, created_at
            )
            VALUES (
                :sample_id, :aliquot_code, :dataset_name, :test_type, :data_format,
                :source_folder_name, :storage_dir, :file_count, :total_bytes,
                :collected_at, :operator, :status, :notes, :created_at
            )
            """,
            dataset_payload,
        )
        dataset_id = cursor.lastrowid

        file_count = 0
        total_bytes = 0
        for file_item in files:
            relative_name = file_item.get("filename") or "upload.bin"
            stored = save_uploaded_file(file_item, target_dir, relative_name=relative_name)
            file_payload = {
                "dataset_id": dataset_id,
                "relative_path": stored["relative_path"],
                "original_filename": stored["original_filename"],
                "stored_filename": stored["stored_filename"],
                "storage_path": stored["storage_path"],
                "mime_type": stored["mime_type"],
                "file_size": stored["file_size"],
                "created_at": timestamp,
            }
            conn.execute(
                """
                INSERT INTO performance_dataset_files (
                    dataset_id, relative_path, original_filename, stored_filename,
                    storage_path, mime_type, file_size, created_at
                )
                VALUES (
                    :dataset_id, :relative_path, :original_filename, :stored_filename,
                    :storage_path, :mime_type, :file_size, :created_at
                )
                """,
                file_payload,
            )
            file_count += 1
            total_bytes += stored["file_size"]

        conn.execute(
            """
            UPDATE performance_datasets
            SET file_count = ?, total_bytes = ?
            WHERE id = ?
            """,
            (file_count, total_bytes, dataset_id),
        )
        return row_dict(
            conn.execute(
                """
                SELECT pd.*, s.sample_uid, s.sample_display_code, s.sample_code, s.name AS sample_name
                FROM performance_datasets pd
                JOIN samples s ON s.id = pd.sample_id
                WHERE pd.id = ?
                """,
                (dataset_id,),
            ).fetchone()
        )


def delete_performance_dataset(dataset_id):
    with connect_db() as conn:
        row = conn.execute("SELECT storage_dir FROM performance_datasets WHERE id = ?", (dataset_id,)).fetchone()
        if row is None:
            raise LookupError("performance dataset not found")
        conn.execute("DELETE FROM performance_datasets WHERE id = ?", (dataset_id,))
    remove_stored_path(row["storage_dir"])
    return {"deleted": dataset_id}


def fetch_processing_source(conn, sample_id=None, metric_name=None):
    where = []
    args = []
    if sample_id:
        where.append("td.sample_id = ?")
        args.append(sample_id)
    if metric_name:
        where.append("td.metric_name = ?")
        args.append(metric_name)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    return rows_dict(
        conn.execute(
            f"""
            SELECT
                td.*,
                s.sample_uid,
                s.sample_display_code,
                s.sample_code,
                s.name AS sample_name
            FROM test_data td
            JOIN samples s ON s.id = td.sample_id
            {where_sql}
            ORDER BY td.metric_name, td.measured_at, td.id
            """,
            args,
        ).fetchall()
    )


def summarize_values(values):
    count = len(values)
    total = sum(values)
    mean = total / count
    sorted_values = sorted(values)
    if count % 2:
        median = sorted_values[count // 2]
    else:
        median = (sorted_values[count // 2 - 1] + sorted_values[count // 2]) / 2
    variance = sum((value - mean) ** 2 for value in values) / (count - 1) if count > 1 else 0.0
    sd = math.sqrt(variance)
    cv = sd / mean * 100 if mean else None
    return {
        "count": count,
        "min": min(values),
        "max": max(values),
        "mean": mean,
        "median": median,
        "stddev": sd,
        "cv_percent": cv,
    }


def run_stats(rows):
    groups = {}
    for row in rows:
        key = (row["metric_name"], row["unit"])
        groups.setdefault(key, []).append(row["numeric_value"])
    return {
        "type": "stats",
        "groups": [
            {"metric_name": metric, "unit": unit, **summarize_values(values)}
            for (metric, unit), values in sorted(groups.items())
        ],
    }


def run_qc(rows, parameters):
    metric_name = optional_text(parameters, "metric_name")
    lower = parse_float(parameters.get("lower_limit"), "lower_limit")
    upper = parse_float(parameters.get("upper_limit"), "upper_limit")
    source = [row for row in rows if not metric_name or row["metric_name"] == metric_name]
    if not source:
        return {"type": "qc", "count": 0, "passed": 0, "failed": 0, "failures": [], "limits": {}}

    values = [row["numeric_value"] for row in source]
    stats = summarize_values(values)
    if lower is None:
        lower = stats["mean"] - 3 * stats["stddev"]
    if upper is None:
        upper = stats["mean"] + 3 * stats["stddev"]

    failures = []
    for row in source:
        value = row["numeric_value"]
        if value < lower or value > upper:
            failures.append(
                {
                    "id": row["id"],
                    "sample_uid": row["sample_uid"],
                    "sample_display_code": row["sample_display_code"],
                    "sample_code": row["sample_code"],
                    "sample_name": row["sample_name"],
                    "metric_name": row["metric_name"],
                    "value": value,
                    "unit": row["unit"],
                    "measured_at": row["measured_at"],
                    "status": "below" if value < lower else "above",
                }
            )

    passed = len(source) - len(failures)
    return {
        "type": "qc",
        "count": len(source),
        "passed": passed,
        "failed": len(failures),
        "pass_rate": passed / len(source) * 100,
        "limits": {"lower": lower, "upper": upper, "metric_name": metric_name or "全部指标"},
        "failures": failures,
    }


def run_normalize(rows):
    groups = {}
    for row in rows:
        groups.setdefault(row["metric_name"], []).append(row)

    normalized = []
    for metric_name, metric_rows in sorted(groups.items()):
        values = [row["numeric_value"] for row in metric_rows]
        low = min(values)
        high = max(values)
        span = high - low
        for row in metric_rows:
            normalized.append(
                {
                    "id": row["id"],
                    "sample_uid": row["sample_uid"],
                    "sample_display_code": row["sample_display_code"],
                    "sample_code": row["sample_code"],
                    "sample_name": row["sample_name"],
                    "metric_name": metric_name,
                    "raw_value": row["numeric_value"],
                    "normalized_value": 0.0 if span == 0 else (row["numeric_value"] - low) / span,
                    "measured_at": row["measured_at"],
                }
            )
    return {"type": "normalize", "points": normalized[:500], "count": len(normalized)}


def run_processing(payload):
    method = optional_text(payload, "method") or "stats"
    job_name = optional_text(payload, "job_name") or "未命名处理"
    parameters = payload.get("parameters") or {}
    if not isinstance(parameters, dict):
        raise ValueError("parameters must be an object")

    sample_id = payload.get("sample_id")
    if sample_id in ("", None):
        sample_id = None
    else:
        try:
            sample_id = int(sample_id)
        except (TypeError, ValueError):
            raise ValueError("sample_id must be numeric")

    metric_name = optional_text(parameters, "metric_name")

    with connect_db() as conn:
        if sample_id and not sample_exists(conn, sample_id):
            raise ValueError("sample_id not found")
        rows = fetch_processing_source(conn, sample_id=sample_id, metric_name=None if method == "qc" else metric_name)
        if not rows:
            raise ValueError("no test data available for processing")

        if method == "stats":
            result = run_stats(rows)
        elif method == "qc":
            result = run_qc(rows, parameters)
        elif method == "normalize":
            result = run_normalize(rows)
        else:
            raise ValueError("unsupported processing method")

        result["source_count"] = len(rows)
        result["scope"] = {"sample_id": sample_id, "metric_name": metric_name or ""}

        cursor = conn.execute(
            """
            INSERT INTO processing_results (
                job_name, method, sample_id, parameters_json, result_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (job_name, method, sample_id, json.dumps(parameters, ensure_ascii=False), json.dumps(result, ensure_ascii=False), now_iso()),
        )
        return row_dict(
            conn.execute("SELECT * FROM processing_results WHERE id = ?", (cursor.lastrowid,)).fetchone()
        )


def get_processing_results():
    with connect_db() as conn:
        return rows_dict(
            conn.execute(
                """
                SELECT pr.*, s.sample_uid, s.sample_display_code, s.sample_code, s.name AS sample_name
                FROM processing_results pr
                LEFT JOIN samples s ON s.id = pr.sample_id
                ORDER BY pr.created_at DESC, pr.id DESC
                LIMIT 100
                """
            ).fetchall()
        )


def get_summary():
    with connect_db() as conn:
        sample_count = conn.execute("SELECT COUNT(*) AS count FROM samples").fetchone()["count"]
        data_count = conn.execute("SELECT COUNT(*) AS count FROM test_data").fetchone()["count"]
        result_count = conn.execute("SELECT COUNT(*) AS count FROM processing_results").fetchone()["count"]
        metric_count = conn.execute("SELECT COUNT(DISTINCT metric_name) AS count FROM test_data").fetchone()["count"]
        status_counts = rows_dict(
            conn.execute(
                """
                SELECT status, COUNT(*) AS count
                FROM samples
                GROUP BY status
                ORDER BY count DESC, status
                """
            ).fetchall()
        )
        recent_data = rows_dict(
            conn.execute(
                """
                SELECT td.id, td.test_name, td.metric_name, td.numeric_value, td.unit,
                       td.measured_at, s.sample_uid, s.sample_display_code, s.sample_code, s.name AS sample_name
                FROM test_data td
                JOIN samples s ON s.id = td.sample_id
                ORDER BY td.measured_at DESC, td.id DESC
                LIMIT 8
                """
            ).fetchall()
        )
        latest_result = row_dict(
            conn.execute(
                """
                SELECT id, job_name, method, created_at
                FROM processing_results
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """
            ).fetchone()
        )
    return {
        "sample_count": sample_count,
        "data_count": data_count,
        "result_count": result_count,
        "metric_count": metric_count,
        "status_counts": status_counts,
        "recent_data": recent_data,
        "latest_result": latest_result,
    }


class AppHandler(BaseHTTPRequestHandler):
    server_version = "SampleTestingCenter/1.0"

    def do_GET(self):
        self.route("GET")

    def do_POST(self):
        self.route("POST")

    def do_PUT(self):
        self.route("PUT")

    def do_PATCH(self):
        self.route("PATCH")

    def do_DELETE(self):
        self.route("DELETE")

    def route(self, method):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        try:
            if path.startswith("/api/"):
                self.handle_api(method, path, query)
            else:
                self.serve_static(path)
        except ValueError as exc:
            self.send_json({"error": str(exc)}, status=400)
        except LookupError as exc:
            self.send_json({"error": str(exc)}, status=404)
        except ConflictError as exc:
            self.send_json({"error": str(exc)}, status=409)
        except Exception as exc:
            self.send_json({"error": "internal server error", "detail": str(exc)}, status=500)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("request body must be valid JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("request body must be a JSON object")
        return payload

    def read_multipart(self):
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            raise ValueError("request body must be multipart/form-data")

        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": self.command,
                "CONTENT_TYPE": content_type,
                "CONTENT_LENGTH": self.headers.get("Content-Length", "0"),
            },
            keep_blank_values=True,
        )
        fields = {}
        files = []
        for item in form.list or []:
            if item.filename:
                files.append(
                    {
                        "name": item.name,
                        "filename": item.filename,
                        "mime_type": item.type or "",
                        "content": item.file.read(),
                    }
                )
            else:
                fields[item.name] = item.value
        return fields, files

    def handle_api(self, method, path, query):
        if method == "GET" and path == "/api/summary":
            return self.send_json(get_summary())
        if method == "GET" and path == "/api/samples":
            return self.send_json(get_samples(query))
        if method == "POST" and path == "/api/samples":
            return self.send_json(create_sample(self.read_json()), status=201)
        if method == "GET" and path == "/api/mes-route-templates":
            return self.send_json(get_mes_route_templates(query))
        if method == "POST" and path == "/api/mes-route-templates":
            return self.send_json(create_mes_route_template(self.read_json()), status=201)
        if method == "GET" and path == "/api/mes-route-templates/by-project":
            return self.send_json(get_mes_route_template_by_project(query))
        if path.startswith("/api/mes-route-templates/") and path.endswith("/layers") and method == "POST":
            template_id = int(path.replace("/api/mes-route-templates/", "", 1).replace("/layers", "").strip("/"))
            return self.send_json(create_mes_route_layer(template_id, self.read_json()), status=201)
        if path.startswith("/api/mes-route-templates/") and method == "GET":
            template_id = self.path_id(path, "/api/mes-route-templates/")
            return self.send_json(get_mes_route_template_detail(template_id))
        if path.startswith("/api/mes-route-layers/") and path.endswith("/steps") and method == "POST":
            layer_id = int(path.replace("/api/mes-route-layers/", "", 1).replace("/steps", "").strip("/"))
            return self.send_json(create_mes_route_step(layer_id, self.read_json()), status=201)
        if path.startswith("/api/mes-route-steps/") and method == "PATCH":
            step_id = self.path_id(path, "/api/mes-route-steps/")
            return self.send_json(update_mes_route_step(step_id, self.read_json()))
        if path.startswith("/api/mes-route-steps/") and method == "DELETE":
            step_id = self.path_id(path, "/api/mes-route-steps/")
            return self.send_json(delete_mes_route_step(step_id))
        if method == "POST" and path == "/api/mes-sample-routes":
            return self.send_json(create_mes_sample_route(self.read_json()), status=201)
        if path.startswith("/api/mes-sample-routes/") and path.endswith("/advance") and method == "POST":
            sample_route_id = int(path.replace("/api/mes-sample-routes/", "", 1).replace("/advance", "").strip("/"))
            return self.send_json(advance_mes_sample_route(sample_route_id, self.read_json()))
        if path.startswith("/api/samples/") and path.endswith("/mes-route") and method == "GET":
            sample_id = int(path.replace("/api/samples/", "", 1).replace("/mes-route", "").strip("/"))
            return self.send_json(get_mes_sample_route_by_sample(sample_id))
        if path.startswith("/api/samples/") and path.endswith("/characterization-tree") and method == "GET":
            sample_id = int(path.replace("/api/samples/", "", 1).replace("/characterization-tree", "").strip("/"))
            return self.send_json(get_characterization_tree(sample_id, query))
        if path.startswith("/api/samples/"):
            sample_id = self.path_id(path, "/api/samples/")
            if method == "PUT":
                return self.send_json(update_sample(sample_id, self.read_json()))
            if method == "DELETE":
                return self.send_json(delete_sample(sample_id))

        if method == "GET" and path == "/api/process-records/sample-lookup":
            if query.get("mode", [""])[0] == "suggestions":
                if query.get("field", [""])[0]:
                    return self.send_json(search_process_field_suggestions(query))
                return self.send_json(search_process_samples(query))
            if query.get("mode", [""])[0] == "field-suggestions":
                return self.send_json(search_process_field_suggestions(query))
            return self.send_json(lookup_process_sample(query))
        if method == "GET" and path == "/api/process-records/field-suggestions":
            return self.send_json(search_process_field_suggestions(query))
        if method == "GET" and path == "/api/process-records/layers":
            return self.send_json(search_process_layers(query))
        if method == "GET" and path == "/api/process-records/sample-suggestions":
            return self.send_json(search_process_samples(query))
        if method in {"POST", "PUT"} and path == "/api/process-records":
            status = 201 if method == "POST" else 200
            return self.send_json(save_process_record(self.read_json()), status=status)

        if method == "GET" and path == "/api/test-data":
            return self.send_json(get_test_data(query))
        if method == "POST" and path == "/api/test-data":
            return self.send_json(create_test_data(self.read_json()), status=201)
        if method == "POST" and path == "/api/test-data/bulk":
            return self.send_json(bulk_create_test_data(self.read_json()), status=201)
        if path.startswith("/api/test-data/") and method == "DELETE":
            record_id = self.path_id(path, "/api/test-data/")
            return self.send_json(delete_test_data(record_id))

        raw_data_path = path.rstrip("/") if path != "/" else path
        if method == "GET" and raw_data_path == "/api/raw-data":
            return self.send_json(get_raw_data_list(query))
        if method == "POST" and raw_data_path == "/api/raw-data":
            return self.send_json(create_raw_data(self.read_json()), status=201)
        if raw_data_path.startswith("/api/raw-data/"):
            suffix = raw_data_path.replace("/api/raw-data/", "", 1).strip("/")
            parts = [part for part in suffix.split("/") if part]
            if not parts:
                raise ValueError("raw_data_id must be numeric")
            try:
                raw_data_id = int(parts[0])
            except ValueError as exc:
                raise ValueError("raw_data_id must be numeric") from exc

            if method == "POST" and len(parts) == 2 and parts[1] == "files":
                _fields, files = self.read_multipart()
                return self.send_json(upload_raw_data_files(raw_data_id, files), status=201)
            if method == "POST" and len(parts) == 2 and parts[1] == "parse":
                return self.send_json(parse_raw_data(raw_data_id, self.read_json()))
            if method == "GET" and len(parts) == 1:
                return self.send_json(get_raw_data_detail(raw_data_id))
            if method == "DELETE" and len(parts) == 1:
                return self.send_json(delete_raw_data(raw_data_id))

        if path.startswith("/api/raw-data-files/"):
            suffix = path.replace("/api/raw-data-files/", "", 1).strip("/")
            if method == "GET" and suffix.endswith("/download"):
                file_id = int(suffix.replace("/download", "").strip("/"))
                return self.send_raw_data_file(file_id)
            if method == "DELETE":
                file_id = self.path_id(path, "/api/raw-data-files/")
                return self.send_json(delete_raw_data_file(file_id))

        if path.startswith("/api/outputs/") and method == "GET":
            return self.serve_output(path)
        if path.startswith("/api/templates/") and method == "GET":
            return self.serve_template(path)
        if method == "GET" and path == "/api/parsed-data":
            return self.send_json(get_parsed_data_list(query))
        if method == "POST" and path == "/api/parsed-data/mock":
            return self.send_json(create_mock_parsed_data(self.read_json()), status=201)
        if path.startswith("/api/parsed-data/") and method == "POST" and path.endswith("/visualize"):
            parsed_data_id = self.path_id(path[:-len("/visualize")], "/api/parsed-data/")
            return self.send_json(visualize_parsed_data(parsed_data_id, self.read_json()), status=201)
        if path.startswith("/api/parsed-data/") and method == "POST" and path.endswith("/resistance-summary"):
            parsed_data_id = self.path_id(path[:-len("/resistance-summary")], "/api/parsed-data/")
            return self.send_json(get_resistance_summary(parsed_data_id, self.read_json()))
        if path.startswith("/api/processing-jobs/") and method == "GET" and path.endswith("/charts/download"):
            job_id = self.path_id(path[:-len("/charts/download")], "/api/processing-jobs/")
            return self.send_visualization_chart_archive(job_id, query)
        if path.startswith("/api/parsed-data/") and method == "GET" and path.endswith("/records"):
            parsed_data_id = self.path_id(path[:-len("/records")], "/api/parsed-data/")
            return self.send_json(get_parsed_data_records(parsed_data_id, query))
        if path.startswith("/api/parsed-data/") and method == "GET" and path.endswith("/record-options"):
            parsed_data_id = self.path_id(path[:-len("/record-options")], "/api/parsed-data/")
            return self.send_json(get_parsed_record_options(parsed_data_id))
        if path.startswith("/api/parsed-data/") and method == "GET":
            parsed_data_id = self.path_id(path, "/api/parsed-data/")
            return self.send_json(get_parsed_data_detail(parsed_data_id))
        if method == "GET" and path == "/api/processing-jobs":
            return self.send_json(get_processing_jobs(query))

        if method == "GET" and path == "/api/characterization-files":
            return self.send_json(get_characterization_files(query))
        if method == "POST" and path == "/api/characterization-files":
            fields, files = self.read_multipart()
            return self.send_json(create_characterization_files(fields, files), status=201)
        if method == "GET" and path == "/api/characterization/samples":
            return self.send_json(get_characterization_samples(query))
        if method == "POST" and path == "/api/characterization-collections":
            return self.send_json(create_characterization_collection(self.read_json()), status=201)
        if path.startswith("/api/characterization-collections/") and method == "GET":
            collection_id = self.path_id(path, "/api/characterization-collections/")
            return self.send_json(get_characterization_collection(collection_id))
        if path.startswith("/api/characterization-files/"):
            suffix = path.replace("/api/characterization-files/", "", 1).strip("/")
            if method == "GET" and suffix.endswith("/preview"):
                file_id = int(suffix.replace("/preview", "").strip("/"))
                return self.send_characterization_file(file_id, inline=True)
            if method == "GET" and suffix.endswith("/download"):
                file_id = int(suffix.replace("/download", "").strip("/"))
                return self.send_characterization_file(file_id, inline=False)
            if method == "GET":
                file_id = self.path_id(path, "/api/characterization-files/")
                return self.send_json(get_characterization_file(file_id))
            if method == "DELETE":
                file_id = self.path_id(path, "/api/characterization-files/")
                return self.send_json(delete_characterization_file(file_id))

        if method == "GET" and path == "/api/performance-datasets":
            return self.send_json(get_performance_datasets(query))
        if method == "POST" and path == "/api/performance-datasets":
            fields, files = self.read_multipart()
            return self.send_json(create_performance_dataset(fields, files), status=201)
        if path.startswith("/api/performance-datasets/"):
            suffix = path.replace("/api/performance-datasets/", "", 1).strip("/")
            if method == "GET" and suffix.endswith("/files"):
                dataset_id = int(suffix.replace("/files", "").strip("/"))
                return self.send_json(get_performance_dataset_files(dataset_id))
            if method == "DELETE":
                dataset_id = self.path_id(path, "/api/performance-datasets/")
                return self.send_json(delete_performance_dataset(dataset_id))

        if method == "GET" and path == "/api/process-results":
            return self.send_json(get_processing_results())
        if method == "POST" and path == "/api/process":
            return self.send_json(run_processing(self.read_json()), status=201)

        self.send_json({"error": "not found"}, status=404)

    def path_id(self, path, prefix):
        raw = path.replace(prefix, "", 1).strip("/")
        try:
            return int(raw)
        except ValueError as exc:
            raise ValueError("invalid id") from exc

    def send_characterization_file(self, file_id, inline):
        record = get_characterization_file(file_id)
        target = characterization_file_path(record)
        preview_type = record["preview_type"]
        if inline and preview_type == "download":
            return self.send_json({"error": "file type is not previewable"}, status=415)

        content_type = record.get("mime_type") or mimetypes.guess_type(record["original_filename"])[0] or "application/octet-stream"
        if preview_type == "text":
            content_type = content_type if content_type.startswith("text/") else "text/plain"
        disposition_type = "inline" if inline else "attachment"
        filename = record["original_filename"]
        quoted_filename = quote(filename)
        safe_filename = filename.replace("\\", "_").replace('"', "'")

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(target.stat().st_size))
        self.send_header(
            "Content-Disposition",
            f"{disposition_type}; filename=\"{safe_filename}\"; filename*=UTF-8''{quoted_filename}",
        )
        self.end_headers()
        with target.open("rb") as handle:
            shutil.copyfileobj(handle, self.wfile)

    def serve_static(self, path):
        if path in ("", "/"):
            path = "/index.html"
        static_root = STATIC_DIR.resolve()
        requested_target = (STATIC_DIR / path.lstrip("/")).resolve()

        if str(requested_target).startswith(str(static_root)) and requested_target.is_file():
            target = requested_target
        else:
            suffix = Path(path).suffix.lower()
            if suffix:
                self.send_error(404)
                return
            target = (STATIC_DIR / "index.html").resolve()
            if not target.is_file():
                self.send_error(404)
                return

        content_type = self.guess_content_type(target)
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(target.stat().st_size))
        self.end_headers()
        with target.open("rb") as handle:
            self.wfile.write(handle.read())

    def serve_output(self, path):
        relative = path.replace("/api/outputs/", "", 1).strip("/")
        target = resolve_data_path(relative)
        output_root = OUTPUT_DIR.resolve()
        if not str(target).startswith(str(output_root)) or not target.is_file():
            self.send_json({"error": "output file not found"}, status=404)
            return

        content_type = self.guess_content_type(target)
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(target.stat().st_size))
        self.end_headers()
        with target.open("rb") as handle:
            shutil.copyfileobj(handle, self.wfile)

    def send_visualization_chart_archive(self, job_id, query):
        archive_path, archive_name = get_visualization_chart_archive(job_id, query.get("chart_key", []))
        quoted_filename = quote(archive_name)
        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Length", str(archive_path.stat().st_size))
        self.send_header(
            "Content-Disposition",
            f"attachment; filename=\"{archive_name}\"; filename*=UTF-8''{quoted_filename}",
        )
        self.end_headers()
        with archive_path.open("rb") as handle:
            shutil.copyfileobj(handle, self.wfile)

    def send_raw_data_file(self, file_id):
        with connect_db() as conn:
            record = raw_data_file_row(conn, file_id)
        target = raw_data_upload_file_path(record)
        if not target.is_file():
            raise LookupError("raw data file not found on disk")

        content_type = record.get("mime_type") or self.guess_content_type(target)
        filename = record["original_filename"]
        quoted_filename = quote(filename)
        safe_filename = filename.replace("\\", "_").replace('"', "'")

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(target.stat().st_size))
        self.send_header(
            "Content-Disposition",
            f"attachment; filename=\"{safe_filename}\"; filename*=UTF-8''{quoted_filename}",
        )
        self.end_headers()
        with target.open("rb") as handle:
            shutil.copyfileobj(handle, self.wfile)

    def serve_template(self, path):
        template_name = path.replace("/api/templates/", "", 1).strip("/")
        if "/" in template_name or "\\" in template_name or template_name not in ALLOWED_TEMPLATE_FILES:
            self.send_json({"error": "template not found"}, status=404)
            return

        template_root = TEMPLATE_DIR.resolve()
        target = (TEMPLATE_DIR / template_name).resolve()
        if not str(target).startswith(str(template_root)) or not target.is_file():
            self.send_json({"error": "template not found"}, status=404)
            return

        quoted_filename = quote(template_name)
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Length", str(target.stat().st_size))
        self.send_header(
            "Content-Disposition",
            f"attachment; filename=\"{template_name}\"; filename*=UTF-8''{quoted_filename}",
        )
        self.end_headers()
        with target.open("rb") as handle:
            shutil.copyfileobj(handle, self.wfile)

    def guess_content_type(self, target):
        overrides = {
            ".html": "text/html; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".md": "text/markdown; charset=utf-8",
            ".txt": "text/plain; charset=utf-8",
            ".svg": "image/svg+xml",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".ico": "image/x-icon",
        }
        suffix = target.suffix.lower()
        if suffix in overrides:
            return overrides[suffix]
        return mimetypes.guess_type(str(target))[0] or "application/octet-stream"

    def send_json(self, payload, status=200):
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, format, *args):
        print("[%s] %s" % (self.log_date_time_string(), format % args))


def main():
    parser = argparse.ArgumentParser(description="Sample testing information management center")
    parser.add_argument("--host", default=os.environ.get("JIQT_HOST", "0.0.0.0"))
    parser.add_argument("--port", default=int(os.environ.get("PORT", "8000")), type=int)
    parser.add_argument("--data-dir", default=os.environ.get("JIQT_DATA_DIR"), help="Directory for database, uploads, outputs, backups and logs")
    args = parser.parse_args()

    configure_paths(args.data_dir)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    init_db()
    run_migrations()
    server = ThreadingHTTPServer((args.host, args.port), AppHandler)
    print(f"Serving sample testing center at http://{args.host}:{args.port}")
    print(f"SQLite database: {DB_PATH}")
    server.serve_forever()


if __name__ == "__main__":
    main()
