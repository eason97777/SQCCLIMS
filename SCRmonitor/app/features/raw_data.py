import json
import mimetypes
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path

import app.config as config
from app.archive import archive_file
from app.backup import backup_database
from app.errors import ConflictError
from app.db import connect_db, record_deletion
from app.features.characterization import preview_type_for_file
from app.features.samples import build_sample_display_code, generate_sample_uid, get_sample_row
from app.storage import ensure_upload_root, file_sha256, raw_data_upload_file_path, resolve_data_path, storage_path_for
from app.validation import now_iso, optional_text, require_text, row_dict, rows_dict, safe_path_part


def normalize_raw_data_type(value):
    data_type = re.sub(r"[^a-z0-9_]+", "_", str(value or "").strip().lower()).strip("_")
    if not data_type:
        raise ValueError("data_type is required")
    if data_type not in config.RAW_DATA_TYPES:
        raise ValueError("unsupported data_type")
    return data_type

def raw_data_category_for(data_type):
    return config.RAW_DATA_TYPES.get(data_type, config.RAW_DATA_TYPES["generic_file"])["category"]

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
        target_dir = config.UPLOAD_DIR / "raw_data" / safe_path_part(raw_data_code, "raw-data")
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

        raw_root = (config.UPLOAD_DIR / "raw_data").resolve()
        target_dir = (config.UPLOAD_DIR / "raw_data" / safe_path_part(raw_data["raw_data_code"], "raw-data")).resolve()
        if not str(target_dir).startswith(str(raw_root)):
            raise ValueError("invalid raw data storage path")

        for file_item in files:
            stored = save_raw_data_file(file_item, target_dir, raw_data["raw_data_code"])
            archive_file(
                resolve_data_path(stored["file_path"]),
                sha256=stored.get("sha256"),
                original_filename=stored.get("original_filename"),
                source="raw_data",
            )
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
    # Strong-tier delete: snapshot the DB before opening the delete transaction.
    backup_database()
    with connect_db() as conn:
        raw_data = conn.execute("SELECT storage_path FROM raw_data WHERE id = ?", (raw_data_id,)).fetchone()
        if raw_data is None:
            raise LookupError("raw data not found")
        file_rows = conn.execute(
            "SELECT file_path FROM raw_data_files WHERE raw_data_id = ?",
            (raw_data_id,),
        ).fetchall()
        raw_data_full = conn.execute("SELECT * FROM raw_data WHERE id = ?", (raw_data_id,)).fetchone()
        record_deletion(conn, "raw_data", raw_data_full)
        conn.execute("DELETE FROM processing_jobs WHERE raw_data_id = ?", (raw_data_id,))
        conn.execute("DELETE FROM parsed_records WHERE raw_data_id = ?", (raw_data_id,))
        conn.execute("DELETE FROM parsed_data WHERE raw_data_id = ?", (raw_data_id,))
        conn.execute("DELETE FROM raw_data WHERE id = ?", (raw_data_id,))

    raw_root = (config.UPLOAD_DIR / "raw_data").resolve()
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
        record_deletion(conn, "raw_data_files", file_record)
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

    from app.features.visualization import delete_output_files_for_jobs

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
