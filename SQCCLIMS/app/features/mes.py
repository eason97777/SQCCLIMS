
from app.db import connect_db, record_deletion
from app.validation import normalize_sample_text, now_iso, optional_text, row_dict, rows_dict


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

        step_row = conn.execute("SELECT * FROM mes_route_steps WHERE id = ?", (step_id,)).fetchone()
        record_deletion(conn, "mes_route_steps", step_row)
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

def advance_mes_sample_route(sample_route_id, payload):
    action = optional_text(payload, "action")
    if action != "skip":
        raise ValueError("样品建档页仅允许工程师跳过工步，完成状态由工艺记录提交触发")

    operator = optional_text(payload, "operator")
    note = optional_text(payload, "note")
    with connect_db() as conn:
        return advance_mes_sample_route_step(conn, sample_route_id, "skip", operator=operator, note=note)

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
