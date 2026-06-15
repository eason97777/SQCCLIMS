import json
import math
import re
from datetime import datetime
from datetime import timezone

import app.config as config


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def row_dict(row):
    return dict(row) if row is not None else None

def rows_dict(rows):
    return [dict(row) for row in rows]

def require_text(payload, key):
    value = str(payload.get(key, "")).strip()
    if not value:
        raise ValueError(f"{key} is required")
    return value

def optional_text(payload, key):
    return str(payload.get(key, "") or "").strip()

def parse_float(value, field_name):
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be numeric")
    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be finite")
    return number

def has_garbled_text(value):
    text = str(value or "")
    return any(marker in text for marker in config.GARBLED_TEXT_MARKERS)

def has_only_punctuation(value):
    return re.search(r"[A-Za-z0-9\u4e00-\u9fff]", str(value or "")) is None

def normalize_sample_text(value):
    return re.sub(r"\s+", " ", str(value or "").strip())

def json_text(value, default_value):
    if value in (None, ""):
        return json.dumps(default_value, ensure_ascii=False)
    if isinstance(value, (dict, list)):
        if not isinstance(value, type(default_value)):
            raise ValueError("JSON field has invalid type")
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("JSON field must be valid JSON") from exc
        if not isinstance(parsed, type(default_value)):
            raise ValueError("JSON field has invalid type")
        return json.dumps(parsed, ensure_ascii=False)
    raise ValueError("JSON field has invalid type")

def json_object(value):
    try:
        parsed = json.loads(value or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}

def text_or_none(value):
    if value is None:
        return None
    return str(value)

def finite_float_or_none(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None

def int_or_none(value):
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

def bool_to_int(value):
    if isinstance(value, str):
        return 1 if value.strip().lower() in {"1", "true", "yes", "y"} else 0
    return 1 if bool(value) else 0

def is_na_value(value):
    if value is None:
        return True
    text = str(value).strip()
    return text == "" or text.lower() in {"na", "n/a", "nan", "none", "null"}

def to_float_or_none(value):
    if is_na_value(value):
        return None
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None

def safe_path_part(value, fallback="item"):
    return safe_path_parts(value, fallback=fallback)[0]

def safe_path_parts(value, fallback="file"):
    raw_parts = re.split(r"[\\/]+", str(value or ""))
    parts = []
    for raw in raw_parts:
        cleaned = re.sub(r"[^\w.\- \u4e00-\u9fff]+", "_", raw.strip(), flags=re.UNICODE)
        cleaned = cleaned.strip(" .")
        if cleaned and cleaned not in (".", ".."):
            parts.append(cleaned)
    return parts or [fallback]

def safe_download_name(value):
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip())
    safe = safe.strip("._")
    return safe or "chart"

def parse_positive_int_param(query_params, name, default_value, max_value=None):
    raw_value = query_params.get(name, [""])[0]
    try:
        value = int(str(raw_value).strip())
    except (TypeError, ValueError):
        value = default_value
    if value < 1:
        value = 1
    if max_value is not None:
        value = min(value, max_value)
    return value

def parse_optional_bool_param(value):
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n"}:
        return False
    return None

def first_present(record, keys, default=None):
    for key in keys:
        if key in record:
            return record.get(key)
    return default
