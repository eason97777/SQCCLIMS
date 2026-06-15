"""Centralized deletion helpers (Data_Flow.md "Deletion & Data-Safety Policy").

The DB cascade removes child *rows* but cannot touch files on disk, so file
cleanup is centralized here (Principle 2): collect an entity's file paths (and
its descendants') BEFORE the row delete, then remove them from the live store
AFTER the row delete succeeds. The append-only archive (Principle 4) already
holds immutable copies, so removing live files is safe.

This module also provides read-only cascade-preview helpers (Principle 3) that
report a delete's blast radius without deleting anything.

Paths are read from ``app.config`` at call time.
"""
import app.config as config
from app.storage import resolve_data_path


def _live_store_roots():
    return (config.UPLOAD_DIR.resolve(), config.OUTPUT_DIR.resolve())


def _is_under_live_store(target):
    target_str = str(target)
    for root in _live_store_roots():
        if target_str == str(root) or target_str.startswith(str(root) + "/"):
            return True
    return False


def collect_sample_file_paths(conn, sample_id):
    """Return resolved live-store file paths owned by the sample and its
    descendants (raw data files, characterization files, performance dataset
    files, and parsed-data generated outputs)."""
    storage_values = []

    for row in conn.execute(
        """
        SELECT rdf.file_path AS storage
        FROM raw_data_files rdf
        JOIN raw_data rd ON rd.id = rdf.raw_data_id
        WHERE rd.sample_id = ?
        """,
        (sample_id,),
    ).fetchall():
        storage_values.append(row["storage"])

    for row in conn.execute(
        "SELECT storage_path AS storage FROM characterization_files WHERE sample_id = ?",
        (sample_id,),
    ).fetchall():
        storage_values.append(row["storage"])

    for row in conn.execute(
        """
        SELECT pdf.storage_path AS storage
        FROM performance_dataset_files pdf
        JOIN performance_datasets pd ON pd.id = pdf.dataset_id
        WHERE pd.sample_id = ?
        """,
        (sample_id,),
    ).fetchall():
        storage_values.append(row["storage"])

    for row in conn.execute(
        """
        SELECT output_file_path AS storage
        FROM parsed_data
        WHERE sample_id = ? AND output_file_path != ''
        """,
        (sample_id,),
    ).fetchall():
        storage_values.append(row["storage"])

    paths = []
    for value in storage_values:
        if not value:
            continue
        paths.append(resolve_data_path(value))
    return paths


def remove_files(paths):
    """Unlink each existing path, guarded by root confinement: only paths under
    the upload/output dirs are removed."""
    removed = 0
    for target in paths:
        resolved = target if hasattr(target, "is_file") else resolve_data_path(target)
        if not _is_under_live_store(resolved):
            continue
        if resolved.is_file():
            resolved.unlink(missing_ok=True)
            removed += 1
    return removed


def _count(conn, sql, args):
    return conn.execute(sql, args).fetchone()["count"]


def sample_delete_preview(sample_id):
    from app.db import connect_db

    with connect_db() as conn:
        sample = conn.execute(
            "SELECT id, sample_display_code FROM samples WHERE id = ?",
            (sample_id,),
        ).fetchone()
        if sample is None:
            raise LookupError("sample not found")

        files_total = len(collect_sample_file_paths(conn, sample_id))
        return {
            "sample_display_code": sample["sample_display_code"],
            "test_data": _count(
                conn, "SELECT COUNT(*) AS count FROM test_data WHERE sample_id = ?", (sample_id,)
            ),
            "process_records": _count(
                conn, "SELECT COUNT(*) AS count FROM process_records WHERE sample_id = ?", (sample_id,)
            ),
            "raw_data": _count(
                conn, "SELECT COUNT(*) AS count FROM raw_data WHERE sample_id = ?", (sample_id,)
            ),
            "raw_data_files": _count(
                conn,
                """
                SELECT COUNT(*) AS count
                FROM raw_data_files rdf
                JOIN raw_data rd ON rd.id = rdf.raw_data_id
                WHERE rd.sample_id = ?
                """,
                (sample_id,),
            ),
            "parsed_data": _count(
                conn, "SELECT COUNT(*) AS count FROM parsed_data WHERE sample_id = ?", (sample_id,)
            ),
            "parsed_records": _count(
                conn, "SELECT COUNT(*) AS count FROM parsed_records WHERE sample_id = ?", (sample_id,)
            ),
            "characterization_files": _count(
                conn, "SELECT COUNT(*) AS count FROM characterization_files WHERE sample_id = ?", (sample_id,)
            ),
            "performance_datasets": _count(
                conn, "SELECT COUNT(*) AS count FROM performance_datasets WHERE sample_id = ?", (sample_id,)
            ),
            "files_total": files_total,
        }


def raw_data_delete_preview(raw_data_id):
    from app.db import connect_db

    with connect_db() as conn:
        raw_data = conn.execute(
            "SELECT id, raw_data_code FROM raw_data WHERE id = ?",
            (raw_data_id,),
        ).fetchone()
        if raw_data is None:
            raise LookupError("raw data not found")

        file_rows = conn.execute(
            "SELECT file_path FROM raw_data_files WHERE raw_data_id = ?",
            (raw_data_id,),
        ).fetchall()
        output_rows = conn.execute(
            """
            SELECT output_file_path
            FROM parsed_data
            WHERE raw_data_id = ? AND output_file_path != ''
            """,
            (raw_data_id,),
        ).fetchall()

        paths = []
        for row in file_rows:
            if row["file_path"]:
                paths.append(resolve_data_path(row["file_path"]))
        for row in output_rows:
            if row["output_file_path"]:
                paths.append(resolve_data_path(row["output_file_path"]))
        files_total = sum(
            1 for p in paths if _is_under_live_store(p) and p.is_file()
        )

        return {
            "raw_data_code": raw_data["raw_data_code"],
            "raw_data_files": len(file_rows),
            "parsed_data": _count(
                conn, "SELECT COUNT(*) AS count FROM parsed_data WHERE raw_data_id = ?", (raw_data_id,)
            ),
            "parsed_records": _count(
                conn, "SELECT COUNT(*) AS count FROM parsed_records WHERE raw_data_id = ?", (raw_data_id,)
            ),
            "files_total": files_total,
        }
