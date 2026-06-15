#!/usr/bin/env python3
import csv
import math
import re
import statistics
from collections import defaultdict
from pathlib import Path


PARSER_NAME = "cd_template_parser"
PARSER_VERSION = "0.1.0"
SCHEMA_VERSION = "1.0"

REQUIRED_FIELDS = {"row_group", "side", "direction", "die_no", "dose", "cd_value"}
OPTIONAL_FIELDS = {"unit", "location"}


def normalize_header(value):
    return str(value or "").replace("\ufeff", "").strip().lower()


def clean_text(value):
    return str(value or "").strip()


def normalize_row_group(value):
    text = clean_text(value)
    compact = text.replace(" ", "").replace("_", "").replace("-", "").lower()
    if text in {"第一行", "第1行"} or compact in {"row1", "1"}:
        return "row_1"
    if text in {"第二行", "第2行"} or compact in {"row2", "2"}:
        return "row_2"
    return None


def normalize_side(value):
    text = clean_text(value)
    compact = text.replace(" ", "").lower()
    if compact in {"left", "l"} or text in {"左", "左侧"}:
        return "Left"
    if compact in {"right", "r"} or text in {"右", "右侧"}:
        return "Right"
    return None


def normalize_direction(value):
    text = clean_text(value)
    compact = text.replace(" ", "").lower()
    if compact in {"vertical", "v"} or text in {"垂直", "纵向"}:
        return "Vertical"
    if compact in {"horizontal", "h"} or text in {"水平", "横向"}:
        return "Horizontal"
    return None


def parse_die_no(value):
    text = clean_text(value)
    match = re.search(r"\d+", text)
    if not match:
        return None
    number = int(match.group(0))
    return number if 1 <= number <= 12 else None


def parse_number(value):
    text = clean_text(value)
    if not text:
        return None
    normalized = (
        text.replace(",", "")
        .replace("，", "")
        .replace("．", ".")
        .replace("－", "-")
    )
    try:
        number = float(normalized)
    except ValueError:
        return None
    if not math.isfinite(number):
        return None
    return number


def stats(values):
    if not values:
        return {"count": 0, "mean": None, "std": None, "min": None, "max": None}
    return {
        "count": len(values),
        "mean": round(statistics.mean(values), 4),
        "std": round(statistics.stdev(values), 4) if len(values) > 1 else 0,
        "min": min(values),
        "max": max(values),
    }


def grouped_stats(records, keys):
    grouped = defaultdict(list)
    for record in records:
        group_key = tuple(record.get(key, "") for key in keys)
        grouped[group_key].append(record["cd_value"])

    result = []
    for group_key, values in sorted(grouped.items()):
        item = {key: group_key[index] for index, key in enumerate(keys)}
        item.update(stats(values))
        result.append(item)
    return result


def normalize_headers(fieldnames):
    return {normalize_header(header): header for header in fieldnames or []}


def make_error(row, field, message, value):
    return {
        "row": row,
        "field": field,
        "message": message,
        "value": value,
    }


def parse_cd_template_csv(
    csv_path,
    *,
    raw_data_id,
    sample_id,
    sample_uid,
    raw_data_code,
    sample_display_code="",
    data_type="cd_sem",
    source_file_info=None,
):
    path = Path(csv_path)
    warnings = []
    errors = []
    records = []
    values = []
    csv_total_rows = 0
    seen_keys = set()
    duplicate_keys = set()
    missing_unit_rows = 0
    invalid_cd_rows = 0
    invalid_position_rows = 0

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise ValueError("CSV header cannot be empty")

            header_map = normalize_headers(reader.fieldnames)
            missing_fields = sorted(field for field in REQUIRED_FIELDS if field not in header_map)
            if missing_fields:
                raise ValueError(f"CSV is missing required fields: {', '.join(missing_fields)}")

            for row_number, row in enumerate(reader, start=2):
                if not any(clean_text(value) for value in row.values()):
                    continue
                csv_total_rows += 1

                row_group_raw = row.get(header_map["row_group"], "")
                side_raw = row.get(header_map["side"], "")
                direction_raw = row.get(header_map["direction"], "")
                die_no_raw = row.get(header_map["die_no"], "")
                dose = clean_text(row.get(header_map["dose"], ""))
                cd_value_raw = row.get(header_map["cd_value"], "")

                row_group = normalize_row_group(row_group_raw)
                side = normalize_side(side_raw)
                direction = normalize_direction(direction_raw)
                die_no = parse_die_no(die_no_raw)
                cd_value = parse_number(cd_value_raw)

                row_errors = []
                if row_group is None:
                    invalid_position_rows += 1
                    row_errors.append(make_error(row_number, "row_group", "row_group must be row_1 or row_2", row_group_raw))
                if side is None:
                    invalid_position_rows += 1
                    row_errors.append(make_error(row_number, "side", "side must be Left or Right", side_raw))
                if direction is None:
                    invalid_position_rows += 1
                    row_errors.append(make_error(row_number, "direction", "direction must be Vertical or Horizontal", direction_raw))
                if die_no is None:
                    row_errors.append(make_error(row_number, "die_no", "die_no must be an integer from 1 to 12", die_no_raw))
                if not dose:
                    row_errors.append(make_error(row_number, "dose", "dose cannot be empty", dose))
                if cd_value is None:
                    invalid_cd_rows += 1
                    row_errors.append(make_error(row_number, "cd_value", "cd_value is invalid; row skipped", cd_value_raw))

                if row_errors:
                    errors.extend(row_errors)
                    continue

                unit = clean_text(row.get(header_map.get("unit", ""), "")) if "unit" in header_map else ""
                if not unit:
                    unit = "nm"
                    missing_unit_rows += 1

                location = clean_text(row.get(header_map.get("location", ""), "")) if "location" in header_map else ""

                duplicate_key = (row_group, side, direction, die_no, dose, location)
                if duplicate_key in seen_keys:
                    duplicate_keys.add(duplicate_key)
                seen_keys.add(duplicate_key)

                if cd_value > 10000:
                    warnings.append(make_error(row_number, "cd_value", "cd_value is greater than 10000 nm; please confirm", cd_value_raw))

                values.append(cd_value)
                records.append(
                    {
                        "row_group": row_group,
                        "side": side,
                        "direction": direction,
                        "die_no": die_no,
                        "dose": dose,
                        "cd_value": cd_value,
                        "unit": unit,
                        "location": location,
                        "data_type": data_type,
                        "raw_data_id": raw_data_id,
                        "raw_data_code": raw_data_code,
                        "sample_id": sample_id,
                        "sample_uid": sample_uid,
                        "sample_display_code": sample_display_code,
                        "source_file": path.name,
                    }
                )
    except UnicodeDecodeError as exc:
        raise ValueError("CSV is not UTF-8. Please convert the CSV to UTF-8 before importing.") from exc

    if not records:
        if invalid_cd_rows:
            raise ValueError("CSV contains no valid CD values")
        if invalid_position_rows:
            raise ValueError("CSV row_group / side / direction values cannot be recognized")
        raise ValueError("CSV contains no valid CD records")

    if missing_unit_rows:
        warnings.append(
            {
                "row": None,
                "field": "unit",
                "message": f"{missing_unit_rows} rows had empty unit values; defaulted to nm",
                "value": "",
            }
        )

    for key in sorted(duplicate_keys):
        warnings.append(
            {
                "row": None,
                "field": "duplicate",
                "message": "Duplicate combination: row_group + side + direction + die_no + dose + location",
                "value": " | ".join(str(part) for part in key),
            }
        )

    completeness_groups = defaultdict(set)
    for record in records:
        group_key = (record["dose"], record["location"])
        die_key = (record["row_group"], record["side"], record["direction"], record["die_no"])
        completeness_groups[group_key].add(die_key)

    for group_key, die_keys in sorted(completeness_groups.items()):
        if len(die_keys) < 96:
            warnings.append(
                {
                    "row": None,
                    "field": "completeness",
                    "message": "This dose/location group has fewer than the theoretical 96 records; please confirm this is a partial measurement",
                    "value": {
                        "dose": group_key[0],
                        "location": group_key[1],
                        "count": len(die_keys),
                    },
                }
            )

    first_unit = records[0].get("unit", "nm") if records else "nm"
    overall = stats(values)
    overall["unit"] = first_unit
    unique_doses = sorted({record["dose"] for record in records if record.get("dose")})
    summary = {
        "overall": overall,
        "by_dose": grouped_stats(records, ["dose"]),
        "by_position": grouped_stats(records, ["row_group", "side", "direction"]),
        "by_dose_and_direction": grouped_stats(records, ["dose", "direction"]),
        "by_dose_side_direction": grouped_stats(records, ["dose", "side", "direction"]),
        "source_file": source_file_info or {
            "file_id": None,
            "original_filename": path.name,
            "file_size": None,
            "sha256": "",
            "created_at": "",
        },
        "diagnostics": {
            "csv_total_rows": csv_total_rows,
            "valid_record_count": len(records),
            "skipped_row_count": csv_total_rows - len(records),
            "unique_doses": unique_doses,
        },
    }

    if len(records) < 10:
        warnings.append(
            {
                "row": None,
                "field": "record_count",
                "message": "Current CD record count is low; this may be a template example rather than a complete test dataset.",
                "value": len(records),
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "data_type": data_type,
        "raw_data_id": raw_data_id,
        "sample_id": sample_id,
        "sample_uid": sample_uid,
        "sample_display_code": sample_display_code,
        "raw_data_code": raw_data_code,
        "parser_name": PARSER_NAME,
        "parser_version": PARSER_VERSION,
        "records": records,
        "summary": summary,
        "plots": [],
        "warnings": warnings,
        "errors": errors,
    }
