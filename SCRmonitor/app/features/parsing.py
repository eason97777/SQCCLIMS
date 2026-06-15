import json
import math
import re

from parsers.cd_template_parser import parse_cd_template_csv
from parsers.resistance_csv_parser import parse_resistance_csv

import app.config as config
from app.db import connect_db
from app.features.raw_data import raw_data_row_with_files
from app.storage import raw_data_file_path
from app.validation import bool_to_int, finite_float_or_none, first_present, int_or_none, json_text, now_iso, optional_text, parse_optional_bool_param, parse_positive_int_param, row_dict, rows_dict, text_or_none


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

def parsed_data_with_context(conn, parsed_data_id):
    parsed = parsed_data_row(conn, parsed_data_id)
    raw_data = row_dict(
        conn.execute("SELECT * FROM raw_data WHERE id = ?", (parsed["raw_data_id"],)).fetchone()
    )
    if raw_data is None:
        raise LookupError("raw data not found")
    return parsed, raw_data

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
        if key not in config.PARSED_RECORD_MAPPED_KEYS
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
    columns_sql = ", ".join(config.PARSED_RECORD_INSERT_COLUMNS)
    placeholders_sql = ", ".join(f":{column}" for column in config.PARSED_RECORD_INSERT_COLUMNS)
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
