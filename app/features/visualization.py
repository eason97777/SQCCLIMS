import csv
import json
import os
import shutil
import statistics
import zipfile
from datetime import datetime

from parsers.cd_violin_visualizer import SCRIPT_NAME as CD_VIOLIN_SCRIPT_NAME
from parsers.cd_violin_visualizer import SCRIPT_VERSION as CD_VIOLIN_SCRIPT_VERSION
from parsers.cd_violin_visualizer import generate_cd_violin_visualization
from parsers.resistance_heatmap_visualizer import SCRIPT_NAME as RESISTANCE_HEATMAP_SCRIPT_NAME
from parsers.resistance_heatmap_visualizer import SCRIPT_VERSION as RESISTANCE_HEATMAP_SCRIPT_VERSION
from parsers.resistance_heatmap_visualizer import generate_resistance_heatmap_visualization

import app.config as config
from app.db import db_session
from app.features.parsing import insert_processing_job, parsed_data_row, parsed_data_with_context
from app.storage import output_paths_from_job_output, output_url_for, relative_output_path, resolve_data_path
from app.validation import json_object, now_iso, parse_float, row_dict, rows_dict, safe_download_name, to_float_or_none


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

    with db_session() as conn:
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

    with db_session() as conn:
        job_id = insert_processing_job(conn, job_payload)
        conn.commit()

    output_dir = config.OUTPUT_DIR / "visualizations" / "resistance_heatmap" / str(job_id)
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
        with db_session() as conn:
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
        with db_session() as conn:
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
    with db_session() as conn:
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
    with db_session() as conn:
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

    output_dir = config.OUTPUT_DIR / "visualizations" / "cd_violin" / str(job_id)
    try:
        with db_session() as conn:
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
        with db_session() as conn:
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
        with db_session() as conn:
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

def get_visualization_chart_archive(job_id, chart_keys):
    selected_keys = [str(key).strip() for key in chart_keys if str(key).strip()]
    if not selected_keys:
        raise ValueError("请先选择要保存的图表")

    with db_session() as conn:
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

    output_root = config.OUTPUT_DIR.resolve()
    archive_dir = config.OUTPUT_DIR / "downloads"
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
    with db_session() as conn:
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

def delete_output_files_for_jobs(job_rows):
    output_root = config.OUTPUT_DIR.resolve()
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
                deleted.append(str(target.relative_to(config.DATA_DIR)))

    for job in job_rows:
        job_dir = (config.OUTPUT_DIR / "visualizations" / "cd_violin" / str(job["id"])).resolve()
        if str(job_dir).startswith(str(output_root)) and job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)

    return deleted
