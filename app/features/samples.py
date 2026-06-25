import sqlite3
from datetime import datetime

from app.backup import backup_database
from app.db import connect_db, db_session, record_deletion
from app.deletion import collect_sample_file_paths, collect_sample_job_output_paths, remove_files
from app.validation import has_garbled_text, has_only_punctuation, normalize_sample_text, now_iso, optional_text, require_text, row_dict, rows_dict


# Bounded retries for the sample_uid uniqueness race: under contention a second
# creator may mint a UID another writer just committed. We regenerate and retry
# a small fixed number of times; beyond that an unresolved collision propagates
# (handler -> 409) rather than spinning.
MAX_UID_RETRIES = 5


def is_uid_collision(exc):
    """True iff the IntegrityError is specifically a sample_uid unique violation
    (the partial unique index idx_samples_uid_unique), not a display-code one."""
    message = str(exc).lower()
    return "idx_samples_uid_unique" in message or "samples.sample_uid" in message


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

def build_sample_display_code(sample):
    return "-".join(
        [
            normalize_sample_text(sample.get("sample_code")) or "-",
            normalize_sample_text(sample.get("name")) or "-",
            normalize_sample_text(sample.get("category")) or "-",
            normalize_sample_text(sample.get("batch")) or "-",
        ]
    )

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

def sample_exists(conn, sample_id):
    row = conn.execute("SELECT id FROM samples WHERE id = ?", (sample_id,)).fetchone()
    return row is not None

def get_sample_row(conn, sample_id):
    row = conn.execute("SELECT * FROM samples WHERE id = ?", (sample_id,)).fetchone()
    if row is None:
        raise ValueError("sample_id not found")
    return row

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
    with db_session() as conn:
        return rows_dict(conn.execute(sql, args).fetchall())

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
    # Take the write lock UP FRONT with BEGIN IMMEDIATE so the read-then-write
    # create path does not start a deferred transaction and then have to upgrade
    # its lock mid-flight (the classic busy/deadlock trigger). A manual BEGIN
    # cannot run inside Python sqlite3's implicit transaction management, so we
    # switch this connection to autocommit (isolation_level = None) and drive
    # BEGIN IMMEDIATE / COMMIT / ROLLBACK ourselves.
    conn = connect_db()
    conn.isolation_level = None
    try:
        for _ in range(MAX_UID_RETRIES):
            conn.execute("BEGIN IMMEDIATE")
            try:
                validate_sample_hierarchy(conn, sample)
                sample["sample_uid"] = generate_sample_uid(conn)
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
                row = conn.execute(
                    "SELECT * FROM samples WHERE id = ?", (cursor.lastrowid,)
                ).fetchone()
                conn.execute("COMMIT")
                return row_dict(row)
            except sqlite3.IntegrityError as exc:
                conn.execute("ROLLBACK")
                if is_uid_collision(exc):
                    # Another writer committed our UID first; regenerate (now
                    # seeing the committed row) and retry. The unique index is
                    # the last line of defense behind BEGIN IMMEDIATE.
                    continue
                # Display-code (or other) collision: preserve the existing 400.
                raise ValueError("当前样品显示编号已存在，请修改项目编号、样品名称、工艺类型或样品序号。") from exc
            except Exception:
                conn.execute("ROLLBACK")
                raise
        # Retries exhausted on a genuine, unresolvable UID collision: let the
        # integrity error reach the handler -> 409.
        raise sqlite3.IntegrityError("sample_uid collision could not be resolved")
    finally:
        conn.close()

def update_sample(sample_id, payload):
    with db_session() as conn:
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
    # Strong-tier delete: snapshot the DB before opening the delete transaction.
    backup_database()
    with db_session() as conn:
        row = conn.execute("SELECT * FROM samples WHERE id = ?", (sample_id,)).fetchone()
        if row is None:
            raise LookupError("sample not found")
        # Collect file paths BEFORE the row delete (the cascade would otherwise
        # remove the rows that point at them). processing_jobs.sample_id is
        # ON DELETE SET NULL, so its output files (and rows) would otherwise be
        # orphaned: collect those outputs and explicitly delete the rows here.
        file_paths = collect_sample_file_paths(conn, sample_id)
        job_output_paths = collect_sample_job_output_paths(conn, sample_id)
        record_deletion(conn, "samples", row)
        conn.execute("DELETE FROM processing_jobs WHERE sample_id = ?", (sample_id,))
        cursor = conn.execute("DELETE FROM samples WHERE id = ?", (sample_id,))
        if cursor.rowcount == 0:
            raise LookupError("sample not found")
    # Remove live-store files only after the row delete commits; the archive
    # still holds immutable copies.
    remove_files(file_paths)
    remove_files(job_output_paths)
    return {"deleted": sample_id}
