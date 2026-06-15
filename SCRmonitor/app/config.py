"""Application paths and shared constants.

``configure_paths()`` reassigns the runtime path globals (DATA_DIR, DB_PATH,
UPLOAD_DIR, OUTPUT_DIR, LOG_DIR) at startup. Other modules MUST therefore
reference these as attributes at call time (``import app.config as config``
then ``config.DB_PATH``) rather than binding the value at import time.
"""
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = Path(os.environ.get("JIQT_DATA_DIR", ROOT / "data")).expanduser().resolve()

DB_PATH = DATA_DIR / "sample_testing.db"

STATIC_DIR = ROOT / "frontend" / "dist"

UPLOAD_DIR = DATA_DIR / "uploads"

OUTPUT_DIR = DATA_DIR / "outputs"

LOG_DIR = DATA_DIR / "logs"

TEMPLATE_DIR = ROOT / "templates"

MIGRATIONS_DIR = ROOT / "migrations"

ALLOWED_TEMPLATE_FILES = {"cd_sem_template.csv"}

RAW_DATA_TYPES = {
    "resistance": {"label": "电阻测试数据", "category": "electrical"},
    "cd_sem": {"label": "CD / SEM 数据", "category": "metrology"},
    "sem_image": {"label": "SEM / 图片类数据", "category": "image"},
    "xps": {"label": "XPS / 光谱类数据", "category": "spectrum"},
    "xrd": {"label": "XRD 数据", "category": "spectrum"},
    "afm": {"label": "AFM 数据", "category": "metrology"},
    "report": {"label": "报告文件", "category": "report"},
    "instrument_folder": {"label": "仪器原始目录", "category": "folder"},
    "generic_file": {"label": "通用文件", "category": "other"},
}

GARBLED_TEXT_MARKERS = ("�", "锟", "鎬", "鏍", "����")

PARSED_RECORD_INSERT_COLUMNS = [
    "parsed_data_id",
    "raw_data_id",
    "sample_id",
    "sample_uid",
    "raw_data_code",
    "data_type",
    "record_index",
    "primary_key",
    "group_key",
    "x_value",
    "y_value",
    "numeric_value",
    "raw_value",
    "cleaned_value",
    "is_outlier",
    "outlier_reason",
    "die_id",
    "area",
    "row_index",
    "col_index",
    "row_header",
    "col_header",
    "row_group",
    "side",
    "direction",
    "dose",
    "location",
    "extra_json",
    "created_at",
]

PARSED_RECORD_MAPPED_KEYS = {
    "parsed_data_id",
    "raw_data_id",
    "sample_id",
    "sample_uid",
    "raw_data_code",
    "data_type",
    "record_index",
    "primary_key",
    "group_key",
    "x_value",
    "y_value",
    "numeric_value",
    "raw_value",
    "cleaned_value",
    "is_outlier",
    "outlier_reason",
    "die_id",
    "die_no",
    "area",
    "row_index",
    "col_index",
    "row_header",
    "col_header",
    "row_group",
    "side",
    "direction",
    "dose",
    "location",
    "cd_value",
}

def configure_paths(data_dir=None):
    global DATA_DIR, DB_PATH, UPLOAD_DIR, OUTPUT_DIR, LOG_DIR
    if data_dir:
        DATA_DIR = Path(data_dir).expanduser().resolve()
    DB_PATH = DATA_DIR / "sample_testing.db"
    UPLOAD_DIR = DATA_DIR / "uploads"
    OUTPUT_DIR = DATA_DIR / "outputs"
    LOG_DIR = DATA_DIR / "logs"
