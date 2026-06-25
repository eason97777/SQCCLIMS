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
from app.storage import output_paths_from_job_output, resolve_data_path


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


def collect_job_output_paths(job_rows):
    """Return resolved live-store paths for the visualization outputs referenced
    by the given ``processing_jobs`` rows (each must expose ``output_json``).
    Mirrors the extraction used by ``delete_output_files_for_jobs`` so sample /
    raw-data deletes don't orphan generated chart/report files."""
    paths = []
    seen = set()
    for job in job_rows:
        for raw_path in output_paths_from_job_output(job["output_json"]):
            target = resolve_data_path(raw_path)
            if target in seen:
                continue
            seen.add(target)
            paths.append(target)
    return paths


def collect_sample_job_output_paths(conn, sample_id):
    """Return resolved live-store paths for visualization outputs owned by the
    sample's ``processing_jobs`` rows."""
    job_rows = conn.execute(
        "SELECT output_json FROM processing_jobs WHERE sample_id = ?",
        (sample_id,),
    ).fetchall()
    return collect_job_output_paths(job_rows)


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
    from app.db import db_session

    with db_session() as conn:
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
    from app.db import db_session

    with db_session() as conn:
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


def performance_dataset_delete_preview(dataset_id):
    """Read-only cascade preview for a performance dataset delete. Does not
    delete anything. ``files`` is the number of dataset files that will be
    removed."""
    from app.db import db_session

    with db_session() as conn:
        dataset = conn.execute(
            "SELECT id, dataset_name FROM performance_datasets WHERE id = ?",
            (dataset_id,),
        ).fetchone()
        if dataset is None:
            raise LookupError("performance dataset not found")

        files = _count(
            conn,
            "SELECT COUNT(*) AS count FROM performance_dataset_files WHERE dataset_id = ?",
            (dataset_id,),
        )
        return {
            "dataset_name": dataset["dataset_name"],
            "files": files,
        }


def raw_data_file_delete_preview(file_id):
    """Read-only cascade preview for a single raw-data-file delete. Does not
    delete anything. Reports what ``delete_raw_data_file`` would cascade-remove
    for the file's parent raw_data (parsed_data, parsed_records, and files on
    disk: the source file plus the parent's visualization outputs)."""
    from app.db import db_session

    with db_session() as conn:
        file_record = conn.execute(
            "SELECT id, raw_data_id, original_filename, file_path FROM raw_data_files WHERE id = ?",
            (file_id,),
        ).fetchone()
        if file_record is None:
            raise LookupError("raw data file not found")
        raw_data_id = file_record["raw_data_id"]

        paths = []
        if file_record["file_path"]:
            paths.append(resolve_data_path(file_record["file_path"]))

        job_rows = conn.execute(
            "SELECT output_json FROM processing_jobs WHERE raw_data_id = ?",
            (raw_data_id,),
        ).fetchall()
        paths.extend(collect_job_output_paths(job_rows))

        files_total = sum(
            1 for p in paths if _is_under_live_store(p) and p.is_file()
        )
        return {
            "original_filename": file_record["original_filename"],
            "parsed_data": _count(
                conn, "SELECT COUNT(*) AS count FROM parsed_data WHERE raw_data_id = ?", (raw_data_id,)
            ),
            "parsed_records": _count(
                conn, "SELECT COUNT(*) AS count FROM parsed_records WHERE raw_data_id = ?", (raw_data_id,)
            ),
            "files_total": files_total,
        }
