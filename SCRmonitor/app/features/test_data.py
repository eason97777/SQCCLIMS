
from app.db import connect_db
from app.features.samples import sample_exists
from app.validation import now_iso, optional_text, parse_float, require_text, row_dict, rows_dict


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
