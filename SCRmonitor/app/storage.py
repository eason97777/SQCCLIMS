import hashlib
import json
import mimetypes
import os
import shutil
import uuid
from pathlib import Path

import app.config as config
from app.validation import safe_path_parts


def storage_path_for(path):
    target = path.resolve()
    try:
        return str(target.relative_to(config.DATA_DIR))
    except ValueError:
        try:
            return str(target.relative_to(config.ROOT))
        except ValueError:
            return str(target)

def resolve_data_path(storage_path):
    raw_path = Path(str(storage_path or ""))
    if raw_path.is_absolute():
        return raw_path.resolve()

    parts = raw_path.parts
    if parts and parts[0] == config.DATA_DIR.name:
        raw_path = Path(*parts[1:]) if len(parts) > 1 else Path()

    data_target = (config.DATA_DIR / raw_path).resolve()
    if str(data_target).startswith(str(config.DATA_DIR.resolve())):
        return data_target
    return (config.ROOT / raw_path).resolve()

def ensure_upload_root():
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

def file_sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def save_uploaded_file(file_item, target_dir, relative_name=None):
    ensure_upload_root()
    parts = safe_path_parts(relative_name or file_item.get("filename"), fallback="upload.bin")
    original_filename = parts[-1]
    stored_filename = f"{uuid.uuid4().hex}-{original_filename}"
    target = target_dir.joinpath(*parts[:-1], stored_filename)
    target.parent.mkdir(parents=True, exist_ok=True)

    with target.open("wb") as handle:
        handle.write(file_item["content"])

    return {
        "original_filename": original_filename,
        "relative_path": "/".join(parts),
        "stored_filename": stored_filename,
        "storage_path": storage_path_for(target),
        "mime_type": file_item.get("mime_type") or mimetypes.guess_type(original_filename)[0] or "",
        "file_size": target.stat().st_size,
    }

def remove_stored_path(storage_path):
    target = resolve_data_path(storage_path)
    upload_root = config.UPLOAD_DIR.resolve()
    if str(target).startswith(str(upload_root)):
        if target.is_file():
            target.unlink(missing_ok=True)
        elif target.is_dir():
            shutil.rmtree(target, ignore_errors=True)

def raw_data_upload_file_path(record):
    target = resolve_data_path(record["file_path"])
    upload_root = (config.UPLOAD_DIR / "raw_data").resolve()
    try:
        target.relative_to(upload_root)
    except ValueError as exc:
        raise ValueError("invalid raw data file path") from exc
    if target == upload_root:
        raise ValueError("invalid raw data file path")
    return target

def raw_data_file_path(row):
    target = resolve_data_path(row["file_path"])
    raw_root = (config.UPLOAD_DIR / "raw_data").resolve()
    if not str(target).startswith(str(raw_root)):
        raise ValueError("invalid raw data file path")
    return target

def output_paths_from_job_output(output_json):
    try:
        output = json.loads(output_json or "{}")
    except json.JSONDecodeError:
        return []

    if not isinstance(output, dict):
        return []

    candidates = []
    for key in ("chart_path", "report_path", "report_json_path"):
        value = output.get(key)
        if isinstance(value, str) and value:
            candidates.append(value)

    charts = output.get("charts")
    if isinstance(charts, list):
        for chart in charts:
            if isinstance(chart, dict):
                value = chart.get("chart_path")
                if isinstance(value, str) and value:
                    candidates.append(value)

    return candidates

def relative_output_path(path):
    target = Path(path).resolve()
    output_root = config.OUTPUT_DIR.resolve()
    if not str(target).startswith(str(output_root)):
        raise ValueError("invalid output path")
    return str(target.relative_to(config.DATA_DIR))

def output_url_for(relative_path):
    return f"/api/outputs/{relative_path.replace(os.sep, '/')}"
