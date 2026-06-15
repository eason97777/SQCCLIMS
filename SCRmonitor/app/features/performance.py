import uuid

import app.config as config
from app.archive import archive_file
from app.db import connect_db, record_deletion
from app.features.samples import get_sample_row
from app.storage import remove_stored_path, resolve_data_path, save_uploaded_file, storage_path_for
from app.validation import now_iso, optional_text, require_text, row_dict, rows_dict, safe_path_part


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
        target_dir = config.UPLOAD_DIR / "performance" / safe_path_part(sample["sample_code"], "sample") / safe_path_part(dataset_name, "dataset")
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
            archive_file(
                resolve_data_path(stored["storage_path"]),
                original_filename=stored.get("original_filename"),
                source="performance",
            )
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
        row = conn.execute("SELECT * FROM performance_datasets WHERE id = ?", (dataset_id,)).fetchone()
        if row is None:
            raise LookupError("performance dataset not found")
        record_deletion(conn, "performance_datasets", row)
        conn.execute("DELETE FROM performance_datasets WHERE id = ?", (dataset_id,))
    remove_stored_path(row["storage_dir"])
    return {"deleted": dataset_id}
