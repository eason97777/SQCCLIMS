import json

from app.db import connect_db
from app.features.mes import complete_mes_step_from_process_record, sync_mes_route_from_submitted_process_records
from app.migrations import extract_process_layer_name, normalize_process_layer_name
from app.validation import normalize_sample_text, now_iso, optional_text, row_dict, rows_dict


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

def sample_available_for_process_stage(conn, sample_id, stage):
    sync_mes_route_from_submitted_process_records(conn, sample_id)
    active_step = get_active_mes_step_for_sample(conn, sample_id)
    return bool(active_step and active_step["step_name"] == stage)

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
