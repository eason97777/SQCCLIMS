import json
import math

from app.db import db_session
from app.features.samples import sample_exists
from app.validation import now_iso, optional_text, parse_float, row_dict, rows_dict


def fetch_processing_source(conn, sample_id=None, metric_name=None):
    where = []
    args = []
    if sample_id:
        where.append("td.sample_id = ?")
        args.append(sample_id)
    if metric_name:
        where.append("td.metric_name = ?")
        args.append(metric_name)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    return rows_dict(
        conn.execute(
            f"""
            SELECT
                td.*,
                s.sample_uid,
                s.sample_display_code,
                s.sample_code,
                s.name AS sample_name
            FROM test_data td
            JOIN samples s ON s.id = td.sample_id
            {where_sql}
            ORDER BY td.metric_name, td.measured_at, td.id
            """,
            args,
        ).fetchall()
    )

def summarize_values(values):
    count = len(values)
    total = sum(values)
    mean = total / count
    sorted_values = sorted(values)
    if count % 2:
        median = sorted_values[count // 2]
    else:
        median = (sorted_values[count // 2 - 1] + sorted_values[count // 2]) / 2
    variance = sum((value - mean) ** 2 for value in values) / (count - 1) if count > 1 else 0.0
    sd = math.sqrt(variance)
    cv = sd / mean * 100 if mean else None
    return {
        "count": count,
        "min": min(values),
        "max": max(values),
        "mean": mean,
        "median": median,
        "stddev": sd,
        "cv_percent": cv,
    }

def run_stats(rows):
    groups = {}
    for row in rows:
        key = (row["metric_name"], row["unit"])
        groups.setdefault(key, []).append(row["numeric_value"])
    return {
        "type": "stats",
        "groups": [
            {"metric_name": metric, "unit": unit, **summarize_values(values)}
            for (metric, unit), values in sorted(groups.items())
        ],
    }

def run_qc(rows, parameters):
    metric_name = optional_text(parameters, "metric_name")
    lower = parse_float(parameters.get("lower_limit"), "lower_limit")
    upper = parse_float(parameters.get("upper_limit"), "upper_limit")
    source = [row for row in rows if not metric_name or row["metric_name"] == metric_name]
    if not source:
        return {"type": "qc", "count": 0, "passed": 0, "failed": 0, "failures": [], "limits": {}}

    values = [row["numeric_value"] for row in source]
    stats = summarize_values(values)
    if lower is None:
        lower = stats["mean"] - 3 * stats["stddev"]
    if upper is None:
        upper = stats["mean"] + 3 * stats["stddev"]

    failures = []
    for row in source:
        value = row["numeric_value"]
        if value < lower or value > upper:
            failures.append(
                {
                    "id": row["id"],
                    "sample_uid": row["sample_uid"],
                    "sample_display_code": row["sample_display_code"],
                    "sample_code": row["sample_code"],
                    "sample_name": row["sample_name"],
                    "metric_name": row["metric_name"],
                    "value": value,
                    "unit": row["unit"],
                    "measured_at": row["measured_at"],
                    "status": "below" if value < lower else "above",
                }
            )

    passed = len(source) - len(failures)
    return {
        "type": "qc",
        "count": len(source),
        "passed": passed,
        "failed": len(failures),
        "pass_rate": passed / len(source) * 100,
        "limits": {"lower": lower, "upper": upper, "metric_name": metric_name or "全部指标"},
        "failures": failures,
    }

def run_normalize(rows):
    groups = {}
    for row in rows:
        groups.setdefault(row["metric_name"], []).append(row)

    normalized = []
    for metric_name, metric_rows in sorted(groups.items()):
        values = [row["numeric_value"] for row in metric_rows]
        low = min(values)
        high = max(values)
        span = high - low
        for row in metric_rows:
            normalized.append(
                {
                    "id": row["id"],
                    "sample_uid": row["sample_uid"],
                    "sample_display_code": row["sample_display_code"],
                    "sample_code": row["sample_code"],
                    "sample_name": row["sample_name"],
                    "metric_name": metric_name,
                    "raw_value": row["numeric_value"],
                    "normalized_value": 0.0 if span == 0 else (row["numeric_value"] - low) / span,
                    "measured_at": row["measured_at"],
                }
            )
    return {"type": "normalize", "points": normalized[:500], "count": len(normalized)}

def run_processing(payload):
    method = optional_text(payload, "method") or "stats"
    job_name = optional_text(payload, "job_name") or "未命名处理"
    parameters = payload.get("parameters") or {}
    if not isinstance(parameters, dict):
        raise ValueError("parameters must be an object")

    sample_id = payload.get("sample_id")
    if sample_id in ("", None):
        sample_id = None
    else:
        try:
            sample_id = int(sample_id)
        except (TypeError, ValueError):
            raise ValueError("sample_id must be numeric")

    metric_name = optional_text(parameters, "metric_name")

    with db_session() as conn:
        if sample_id and not sample_exists(conn, sample_id):
            raise ValueError("sample_id not found")
        rows = fetch_processing_source(conn, sample_id=sample_id, metric_name=None if method == "qc" else metric_name)
        if not rows:
            raise ValueError("no test data available for processing")

        if method == "stats":
            result = run_stats(rows)
        elif method == "qc":
            result = run_qc(rows, parameters)
        elif method == "normalize":
            result = run_normalize(rows)
        else:
            raise ValueError("unsupported processing method")

        result["source_count"] = len(rows)
        result["scope"] = {"sample_id": sample_id, "metric_name": metric_name or ""}

        cursor = conn.execute(
            """
            INSERT INTO processing_results (
                job_name, method, sample_id, parameters_json, result_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (job_name, method, sample_id, json.dumps(parameters, ensure_ascii=False), json.dumps(result, ensure_ascii=False), now_iso()),
        )
        return row_dict(
            conn.execute("SELECT * FROM processing_results WHERE id = ?", (cursor.lastrowid,)).fetchone()
        )

def get_processing_results():
    with db_session() as conn:
        return rows_dict(
            conn.execute(
                """
                SELECT pr.*, s.sample_uid, s.sample_display_code, s.sample_code, s.name AS sample_name
                FROM processing_results pr
                LEFT JOIN samples s ON s.id = pr.sample_id
                ORDER BY pr.created_at DESC, pr.id DESC
                LIMIT 100
                """
            ).fetchall()
        )
