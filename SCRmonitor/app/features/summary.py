
from app.db import connect_db
from app.validation import row_dict, rows_dict


def get_summary():
    with connect_db() as conn:
        sample_count = conn.execute("SELECT COUNT(*) AS count FROM samples").fetchone()["count"]
        data_count = conn.execute("SELECT COUNT(*) AS count FROM test_data").fetchone()["count"]
        result_count = conn.execute("SELECT COUNT(*) AS count FROM processing_results").fetchone()["count"]
        metric_count = conn.execute("SELECT COUNT(DISTINCT metric_name) AS count FROM test_data").fetchone()["count"]
        status_counts = rows_dict(
            conn.execute(
                """
                SELECT status, COUNT(*) AS count
                FROM samples
                GROUP BY status
                ORDER BY count DESC, status
                """
            ).fetchall()
        )
        recent_data = rows_dict(
            conn.execute(
                """
                SELECT td.id, td.test_name, td.metric_name, td.numeric_value, td.unit,
                       td.measured_at, s.sample_uid, s.sample_display_code, s.sample_code, s.name AS sample_name
                FROM test_data td
                JOIN samples s ON s.id = td.sample_id
                ORDER BY td.measured_at DESC, td.id DESC
                LIMIT 8
                """
            ).fetchall()
        )
        latest_result = row_dict(
            conn.execute(
                """
                SELECT id, job_name, method, created_at
                FROM processing_results
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """
            ).fetchone()
        )
    return {
        "sample_count": sample_count,
        "data_count": data_count,
        "result_count": result_count,
        "metric_count": metric_count,
        "status_counts": status_counts,
        "recent_data": recent_data,
        "latest_result": latest_result,
    }
