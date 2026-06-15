#!/usr/bin/env python3
import json
import math
import re
import shutil
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FormatStrFormatter, MultipleLocator  # noqa: E402


SCRIPT_NAME = "cd_violin_visualizer"
SCRIPT_VERSION = "0.1.0"

DEFAULT_PARAMETERS = {
    "chart_type": "violin",
    "x_field": "dose",
    "y_field": "cd_value",
    "hue_field": "side",
    "facet_field": "direction",
    "facet_fields": ["direction"],
    "include_overall": False,
    "output_format": "png",
    "title": "CD Distribution by Dose",
    "unit": "nm",
}

ALLOWED_FIELDS = {
    "dose",
    "side",
    "side_display",
    "source_side",
    "direction",
    "row_group",
    "die_no",
    "location",
    "cd_value",
}
FILTER_FIELDS = {"row_group", "side", "direction", "dose", "location"}
NUMERIC_FIELD_HINTS = {"cd_value"}
CATEGORICAL_FIELD_HINTS = {"row_group", "side", "direction", "die_no", "dose", "unit", "location"}
SCHEMA_VALUE_LIMIT = 50
NATURAL_SORT_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")


def natural_sort_key(value):
    text = value_or_empty(value)
    parts = []
    last_index = 0
    for match in NATURAL_SORT_NUMBER_RE.finditer(text):
        if match.start() > last_index:
            parts.append(text[last_index:match.start()].lower())
        parts.append(float(match.group()))
        last_index = match.end()
    if last_index < len(text):
        parts.append(text[last_index:].lower())
    return parts


def sort_schema_values(values):
    try:
        return sorted(values, key=natural_sort_key)
    except (TypeError, ValueError):
        return sorted(values, key=lambda value: value.lower())


def value_or_empty(value):
    return "" if value is None else str(value).strip()


def to_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def stats(values):
    if not values:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "std": None,
            "min": None,
            "max": None,
            "values": [],
        }
    return {
        "count": len(values),
        "mean": round(statistics.mean(values), 4),
        "median": round(statistics.median(values), 4),
        "std": round(statistics.stdev(values), 4) if len(values) > 1 else 0,
        "min": min(values),
        "max": max(values),
        "values": [round(value, 4) for value in values],
    }


def recommended_roles(field_name, kind):
    roles = []
    if field_name == "dose":
        roles.extend(["x", "filter"])
    elif field_name == "cd_value":
        roles.append("y")
    elif field_name == "direction":
        roles.extend(["split", "filter"])
    elif field_name == "side":
        roles.extend(["series", "filter", "merge"])
    elif field_name in FILTER_FIELDS:
        roles.append("filter")
    elif kind == "numeric":
        roles.append("y")
    elif kind == "categorical":
        roles.append("filter")
    else:
        roles.append("metadata")
    return roles


def inspect_records_schema(records):
    warnings = []
    if not isinstance(records, list):
        return {
            "fields": [],
            "defaults": {
                "x_field": "dose",
                "y_field": "cd_value",
                "split_field": "direction",
                "series_field": "side",
                "merge_field": "side",
                "merge_rule": {"label": "Overall", "source_values": ["Left", "Right"]},
                "output_mode": "single_chart",
                "x_order": [],
            },
            "numeric_fields": [],
            "categorical_fields": [],
            "filterable_fields": [],
            "warnings": ["records is not a list"],
        }

    field_names = []
    seen_fields = set()
    for record in records:
        if not isinstance(record, dict):
            warnings.append("Non-object records were ignored during schema inspection.")
            continue
        for field_name in record.keys():
            if field_name not in seen_fields:
                field_names.append(field_name)
                seen_fields.add(field_name)

    fields = []
    numeric_fields = []
    categorical_fields = []
    filterable_fields = []

    for field_name in field_names:
        raw_values = [record.get(field_name) for record in records if isinstance(record, dict)]
        values = [value for value in raw_values if value_or_empty(value)]
        empty_count = len(raw_values) - len(values)
        numeric_values = [to_number(value) for value in values]
        valid_numeric_values = [value for value in numeric_values if value is not None]
        string_values = sort_schema_values({value_or_empty(value) for value in values})
        unique_count = len(string_values)

        if field_name in NUMERIC_FIELD_HINTS:
            kind = "numeric"
        elif field_name in CATEGORICAL_FIELD_HINTS:
            kind = "categorical"
        elif values and len(valid_numeric_values) == len(values):
            kind = "numeric"
        else:
            kind = "categorical"

        field = {
            "name": field_name,
            "kind": kind,
            "non_empty_count": len(values),
            "empty_count": empty_count,
            "unique_count": unique_count,
            "sample_values": string_values[:5],
            "recommended_roles": recommended_roles(field_name, kind),
        }

        if kind == "numeric":
            numeric_fields.append(field_name)
            if valid_numeric_values:
                field["min"] = min(valid_numeric_values)
                field["max"] = max(valid_numeric_values)
                field["sample_values"] = valid_numeric_values[:5]
        else:
            categorical_fields.append(field_name)
            field["values"] = string_values[:SCHEMA_VALUE_LIMIT]
            if unique_count > SCHEMA_VALUE_LIMIT:
                field["values_truncated"] = True

        if kind == "categorical" and field_name in FILTER_FIELDS:
            filterable_fields.append(field_name)
        fields.append(field)

    dose_values = []
    for field in fields:
        if field["name"] == "dose":
            dose_values = field.get("values", [])
            break

    return {
        "fields": fields,
        "defaults": {
            "x_field": "dose",
            "y_field": "cd_value",
            "split_field": "direction",
            "series_field": "side",
            "merge_field": "side",
            "merge_rule": {"label": "Overall", "source_values": ["Left", "Right"]},
            "output_mode": "single_chart",
            "x_order": dose_values,
        },
        "numeric_fields": numeric_fields,
        "categorical_fields": categorical_fields,
        "filterable_fields": filterable_fields,
        "warnings": sorted(set(warnings)),
    }


def normalize_parameters(parameters):
    merged = {**DEFAULT_PARAMETERS, **(parameters or {})}
    merged["chart_type"] = "violin"
    merged["y_field"] = "cd_value"
    merged["x_field"] = merged.get("x_field") or "dose"
    merged["hue_field"] = merged.get("hue_field") or "side"
    if merged["hue_field"] == "none":
        merged["hue_field"] = ""

    facet_field = merged.get("facet_field")
    if not facet_field:
        facet_fields = merged.get("facet_fields")
        facet_field = facet_fields[0] if isinstance(facet_fields, list) and facet_fields else "direction"
    if facet_field == "none":
        facet_field = ""
    merged["facet_field"] = facet_field
    merged["facet_fields"] = [facet_field] if facet_field else []
    merged["filters"] = merged.get("filters") if isinstance(merged.get("filters"), dict) else {}
    merged["include_overall"] = bool(merged.get("include_overall", False))
    merged["title"] = value_or_empty(merged.get("title")) or "CD Distribution"
    merged["chart_overrides"] = merged.get("chart_overrides") if isinstance(merged.get("chart_overrides"), dict) else {}
    return merged


def chart_override_for(parameters, chart_key):
    overrides = parameters.get("chart_overrides")
    if not isinstance(overrides, dict):
        return {}

    if value_or_empty(overrides.get("chart_key")) == chart_key:
        return overrides

    chart_overrides = overrides.get(chart_key)
    return chart_overrides if isinstance(chart_overrides, dict) else {}


def optional_number(value):
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def optional_int(value, default=None):
    if value in (None, ""):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def validate_parameters(parameters, records):
    fields = set()
    for record in records:
        fields.update(record.keys())
    fields.update(ALLOWED_FIELDS)
    if parameters.get("include_overall"):
        fields.update({"side_display", "source_side"})

    for key in ("x_field", "y_field"):
        if parameters[key] not in fields:
            raise ValueError(f"{key} does not exist: {parameters[key]}")

    if parameters["hue_field"] and parameters["hue_field"] not in fields:
        raise ValueError(f"hue_field does not exist: {parameters['hue_field']}")

    if parameters["facet_field"] and parameters["facet_field"] not in fields:
        raise ValueError(f"facet_field does not exist: {parameters['facet_field']}")

    for field in parameters["filters"].keys():
        if field not in FILTER_FIELDS:
            raise ValueError(f"Unsupported filter field: {field}")
        if field not in fields:
            raise ValueError(f"Filter field does not exist: {field}")


def apply_filters(records, filters):
    if not filters:
        return records

    result = []
    for record in records:
        matched = True
        for field, allowed_values in filters.items():
            if allowed_values in (None, "", []):
                continue
            allowed = allowed_values if isinstance(allowed_values, list) else [allowed_values]
            allowed = {value_or_empty(value) for value in allowed}
            if value_or_empty(record.get(field)) not in allowed:
                matched = False
                break
        if matched:
            result.append(record)
    return result


def prepare_records(records, parameters):
    warnings = []
    y_field = parameters["y_field"]
    prepared = []
    skipped_missing_y = 0
    unexpected_side = set()
    unexpected_direction = set()

    for record in records:
        value = to_number(record.get(y_field))
        if value is None:
            skipped_missing_y += 1
            continue
        next_record = dict(record)
        next_record[y_field] = value
        next_record["dose"] = value_or_empty(next_record.get("dose")) or "-"
        next_record["location"] = value_or_empty(next_record.get("location")) or "-"
        next_record["side"] = value_or_empty(next_record.get("side")) or "-"
        next_record["direction"] = value_or_empty(next_record.get("direction")) or "-"
        if next_record["side"] not in {"Left", "Right"}:
            unexpected_side.add(next_record["side"])
        if next_record["direction"] not in {"Vertical", "Horizontal"}:
            unexpected_direction.add(next_record["direction"])
        prepared.append(next_record)

    if skipped_missing_y:
        warnings.append(f"{skipped_missing_y} records were skipped because {y_field} was missing or invalid.")
    if unexpected_side:
        warnings.append(f"Unexpected side values found: {', '.join(sorted(unexpected_side))}.")
    if unexpected_direction:
        warnings.append(f"Unexpected direction values found: {', '.join(sorted(unexpected_direction))}.")

    return prepared, warnings


def derive_overall_records(records, parameters, warnings):
    if not parameters.get("include_overall"):
        return records

    source_sides = [value_or_empty(record.get("side")) for record in records]
    has_left = "Left" in source_sides
    has_right = "Right" in source_sides
    if not has_left and not has_right:
        raise ValueError("include_overall requires Left or Right side records")
    if has_left and not has_right:
        warnings.append("include_overall enabled, but only Left records were found.")
    if has_right and not has_left:
        warnings.append("include_overall enabled, but only Right records were found.")

    derived = []
    side_counts = defaultdict(int)
    for record in records:
        source_side = value_or_empty(record.get("side")) or "-"
        if source_side not in {"Left", "Right"}:
            continue
        next_record = dict(record)
        next_record["source_side"] = source_side
        next_record["side_display"] = "Overall"
        next_record["side"] = "Overall"
        derived.append(next_record)
        side_counts[source_side] += 1

    if not derived:
        raise ValueError("include_overall did not produce any Overall records")
    if side_counts.get("Left", 0) and side_counts.get("Right", 0) and side_counts["Left"] != side_counts["Right"]:
        warnings.append(
            f"include_overall source side counts are imbalanced: Left={side_counts['Left']}, Right={side_counts['Right']}."
        )

    return derived


def build_groups(records, parameters):
    x_field = parameters["x_field"]
    hue_field = parameters["hue_field"]
    facet_field = parameters["facet_field"]
    y_field = parameters["y_field"]

    grouped_records = defaultdict(list)
    for record in records:
        group_key_values = {
            x_field: value_or_empty(record.get(x_field)) or "-",
        }
        if facet_field:
            group_key_values[facet_field] = value_or_empty(record.get(facet_field)) or "-"
        if hue_field:
            group_key_values[hue_field] = value_or_empty(record.get(hue_field)) or "-"
        group_key = (
            group_key_values.get(facet_field, ""),
            group_key_values[x_field],
            group_key_values.get(hue_field, ""),
        )
        grouped_records[group_key].append(record)

    groups = []
    for (facet, x_value, hue), group_records in sorted(grouped_records.items()):
        values = [record[y_field] for record in group_records]
        group = {x_field: x_value}
        if facet_field:
            group[facet_field] = facet
        if hue_field:
            group[hue_field] = hue
        item = {"group": group}
        item.update(stats(values))
        if parameters.get("include_overall"):
            breakdown = defaultdict(int)
            for record in group_records:
                breakdown[value_or_empty(record.get("source_side")) or "-"] += 1
            item["source_side_breakdown"] = dict(sorted(breakdown.items()))
        groups.append(item)

    return groups


def write_report_md(path, context, parameters, groups, warnings):
    lines = [
        "# CD violin data check report",
        "",
        "## Basic information",
        f"- parsed_data_id: {context.get('parsed_data_id')}",
        f"- raw_data_id: {context.get('raw_data_id')}",
        f"- raw_data_code: {context.get('raw_data_code')}",
        f"- sample_display_code: {context.get('sample_display_code')}",
        f"- script_name: {SCRIPT_NAME}",
        f"- script_version: {SCRIPT_VERSION}",
        f"- generated_at: {datetime.now(timezone.utc).replace(microsecond=0).isoformat()}",
        "",
        "## Chart parameters",
        f"- chart_type: {parameters.get('chart_type')}",
        f"- x_field: {parameters.get('x_field')}",
        f"- y_field: {parameters.get('y_field')}",
        f"- hue_field: {parameters.get('hue_field')}",
        f"- facet_field: {parameters.get('facet_field')}",
        f"- facet_fields: {parameters.get('facet_fields')}",
        f"- include_overall: {parameters.get('include_overall')}",
        f"- filters: {json.dumps(parameters.get('filters', {}), ensure_ascii=False)}",
        "",
    ]
    if parameters.get("include_overall"):
        lines.extend(
            [
                "## Overall",
                "- Overall is a visualization-only derived grouping from Left + Right records.",
                "- parsed_records is used as the visualization data source.",
                "- source_side keeps the original Left / Right value for traceability.",
                "",
            ]
        )

    lines.extend(
        [
            "## Group statistics",
            "| group | count | mean | median | std | min | max | source_side_breakdown |",
            "|---|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for group in groups:
        group_name = " / ".join(f"{key}={value}" for key, value in group["group"].items())
        breakdown = json.dumps(group.get("source_side_breakdown", {}), ensure_ascii=False)
        lines.append(
            f"| {group_name} | {group['count']} | {group['mean']} | {group['median']} | "
            f"{group['std']} | {group['min']} | {group['max']} | {breakdown} |"
        )

    lines.extend(["", "## Raw CD value lists"])
    for group in groups:
        group_name = " / ".join(f"{key}={value}" for key, value in group["group"].items())
        values = ", ".join(str(value) for value in group["values"])
        lines.extend([f"### {group_name}", values or "-", ""])

    lines.extend(["## Warnings"])
    if warnings:
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("- None")

    path.write_text("\n".join(lines), encoding="utf-8")


def plot_chart(path, records, parameters, warnings):
    x_field = parameters["x_field"]
    hue_field = parameters["hue_field"]
    facet_field = parameters["facet_field"]
    y_field = parameters["y_field"]
    title = parameters.get("title") or DEFAULT_PARAMETERS["title"]
    unit = parameters.get("unit") or "nm"

    facets = sorted({value_or_empty(record.get(facet_field)) or "-" for record in records}) if facet_field else ["All"]
    x_values = sorted({value_or_empty(record.get(x_field)) or "-" for record in records})
    hue_values = sorted({value_or_empty(record.get(hue_field)) or "-" for record in records}) if hue_field else ["All"]

    if len(x_values) > 12:
        warnings.append(f"x_field has many categories ({len(x_values)}), chart may be dense.")
    if len(hue_values) > 6:
        warnings.append(f"hue_field has many categories ({len(hue_values)}), legend may be dense.")

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    fig, axes = plt.subplots(
        1,
        len(facets),
        figsize=(max(8, len(x_values) * max(1, len(hue_values)) * len(facets) * 1.2), 6),
        dpi=160,
        squeeze=False,
    )
    colors = ["#2f7d73", "#d97757", "#5f7fbf", "#b980c5", "#d8a13d", "#789262"]

    for facet_index, facet in enumerate(facets):
        ax = axes[0][facet_index]
        base_positions = list(range(1, len(x_values) + 1))
        width = 0.7 / max(1, len(hue_values))

        for hue_index, hue in enumerate(hue_values):
            data = []
            positions = []
            offset = (hue_index - (len(hue_values) - 1) / 2) * width
            for x_index, x_value in enumerate(x_values):
                values = [
                    record[y_field]
                    for record in records
                    if (not facet_field or (value_or_empty(record.get(facet_field)) or "-") == facet)
                    and (value_or_empty(record.get(x_field)) or "-") == x_value
                    and (not hue_field or (value_or_empty(record.get(hue_field)) or "-") == hue)
                ]
                if values:
                    if len(values) < 3:
                        warnings.append(f"Group {facet}/{x_value}/{hue} has fewer than 3 data points.")
                    data.append(values)
                    positions.append(base_positions[x_index] + offset)

            if not data:
                continue

            violin = ax.violinplot(data, positions=positions, widths=width * 0.9, showmedians=True, showextrema=True)
            color = colors[hue_index % len(colors)]
            for body in violin["bodies"]:
                body.set_facecolor(color)
                body.set_edgecolor(color)
                body.set_alpha(0.35)
            for key in ("cmedians", "cmins", "cmaxes", "cbars"):
                if key in violin:
                    violin[key].set_color(color)

            for pos, values in zip(positions, data):
                label = hue if hue_field and pos == positions[0] else None
                ax.scatter([pos] * len(values), values, s=12, alpha=0.65, color=color, label=label)

        ax.set_title(str(facet) if facet_field else title)
        ax.set_xticks(base_positions)
        ax.set_xticklabels(x_values, rotation=20, ha="right")
        ax.set_xlabel(x_field)
        ax.set_ylabel(f"CD Value ({unit})")
        ax.grid(axis="y", linestyle="--", alpha=0.25)
        handles, labels = ax.get_legend_handles_labels()
        unique = dict(zip(labels, handles))
        if unique and hue_field:
            ax.legend(unique.values(), unique.keys(), loc="best")

    fig.suptitle(title, fontweight="bold")
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def unique_ordered_values(records, field, preferred_order=None):
    values = {value_or_empty(record.get(field)) or "-" for record in records}
    normalized_lookup = {normalize_display_value(field, value): value for value in values}
    ordered = []
    for value in preferred_order or []:
        text = value_or_empty(value)
        source_value = text if text in values else normalized_lookup.get(normalize_display_value(field, text))
        if source_value in values and source_value not in ordered:
            ordered.append(source_value)
    ordered.extend(value for value in sorted(values, key=natural_sort_key) if value not in ordered)
    return ordered


def normalize_dose_label(value):
    text = value_or_empty(value)
    compact = text.replace(" ", "")
    if compact.lower().startswith("dose") and len(compact) > 4:
        return f"Dose{compact[4:]}"
    return text


def normalize_display_value(field, value):
    if field == "dose":
        return normalize_dose_label(value)
    return value_or_empty(value)


def group_values_by_x(records, x_field, y_field, x_values):
    grouped = {x_value: [] for x_value in x_values}
    for record in records:
        x_value = value_or_empty(record.get(x_field)) or "-"
        if x_value in grouped:
            grouped[x_value].append(record[y_field])
    return grouped


def jitter_positions(position, count):
    if count <= 1:
        return [position] * count
    span = 0.14
    step = span / max(1, count - 1)
    start = position - span / 2
    return [start + index * step for index in range(count)]


def plot_notebook_violin_chart(path, records, parameters, title, is_overall, x_values, warnings, chart_override=None):
    x_field = parameters["x_field"]
    y_field = parameters["y_field"]
    unit = parameters.get("unit") or "nm"
    override = chart_override if isinstance(chart_override, dict) else {}
    chart_title = value_or_empty(override.get("title")) or f"{title} 结线宽分布"
    x_label = value_or_empty(override.get("x_label")) or ""
    y_label = value_or_empty(override.get("y_label")) or f"结线宽 ({unit})"
    y_min = optional_number(override.get("y_min"))
    y_max = optional_number(override.get("y_max"))
    y_step = optional_number(override.get("y_step"))
    decimal_places = max(0, optional_int(override.get("decimal_places"), 0) or 0)
    grouped = group_values_by_x(records, x_field, y_field, x_values)
    x_labels = [x_value for x_value in x_values if grouped.get(x_value)]
    display_labels = [normalize_display_value(x_field, x_value) for x_value in x_labels]
    plot_data = [grouped[x_value] for x_value in x_labels]
    positions = list(range(1, len(x_labels) + 1))

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, ax = plt.subplots(figsize=(10, 6), dpi=300)

    if not plot_data:
        ax.text(0.5, 0.5, "No valid data", ha="center", va="center", transform=ax.transAxes)
        ax.set_xticks([])
        warnings.append(f"{title} has no valid data.")
    else:
        violin = ax.violinplot(plot_data, positions=positions, widths=0.6, showmedians=True, showextrema=True)
        for body in violin["bodies"]:
            body.set_facecolor("#FFF2E8")
            body.set_edgecolor("#E67E22")
            body.set_alpha(0.9)
        violin["cmedians"].set_color("#D35400")
        violin["cmedians"].set_linewidth(3)
        for key in ("cmins", "cmaxes"):
            if key in violin:
                violin[key].set_color("#E74C3C")
        if "cbars" in violin:
            violin["cbars"].set_color("#1f77b4")

        if is_overall:
            source_colors = {"Left": "#3498DB", "Right": "#E74C3C"}
            for index, x_value in enumerate(x_labels):
                position = positions[index]
                for source_side, color in source_colors.items():
                    values = [
                        record[y_field]
                        for record in records
                        if (value_or_empty(record.get(x_field)) or "-") == x_value
                        and value_or_empty(record.get("source_side")) == source_side
                    ]
                    if values:
                        x_positions = jitter_positions(position, len(values))
                        label = source_side if index == 0 else None
                        ax.scatter(x_positions, values, c=color, s=10, alpha=0.6, label=label)
            handles, labels_for_legend = ax.get_legend_handles_labels()
            unique = dict(zip(labels_for_legend, handles))
            if unique:
                ax.legend(unique.values(), unique.keys(), loc="upper right", bbox_to_anchor=(1.15, 1))
        else:
            for position, values in zip(positions, plot_data):
                ax.scatter(jitter_positions(position, len(values)), values, c="#E67E22", s=10, alpha=0.6)

        ax.set_xticks(positions)
        ax.set_xticklabels(display_labels)

    ax.set_title(chart_title, fontweight="bold", fontsize=14)
    if x_label:
        ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    if y_min is not None or y_max is not None:
        ax.set_ylim(bottom=y_min, top=y_max)
    if y_step is not None and y_step > 0:
        ax.yaxis.set_major_locator(MultipleLocator(y_step))
    ax.yaxis.set_major_formatter(FormatStrFormatter(f"%.{decimal_places}f"))
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def build_notebook_chart_records(records, direction, side, parameters, warnings):
    split_field = parameters.get("split_field") or "direction"
    series_field = parameters.get("series_field") or "side"
    merge_rule = parameters.get("merge_rule") if isinstance(parameters.get("merge_rule"), dict) else {}
    source_values = merge_rule.get("source_values") if isinstance(merge_rule.get("source_values"), list) else ["Left", "Right"]
    source_values = {value_or_empty(value) for value in source_values}

    direction_records = [
        record for record in records if value_or_empty(record.get(split_field)) == direction
    ]
    if side != "Overall":
        return [
            record for record in direction_records if value_or_empty(record.get(series_field)) == side
        ]

    overall_records = []
    side_counts = defaultdict(int)
    for record in direction_records:
        source_side = value_or_empty(record.get(series_field))
        if source_side not in source_values:
            continue
        next_record = dict(record)
        next_record["source_side"] = source_side
        next_record["side_display"] = "Overall"
        overall_records.append(next_record)
        side_counts[source_side] += 1

    if len(side_counts) == 1:
        warnings.append(f"{direction}_Overall only contains {next(iter(side_counts))} source records.")
    if side_counts.get("Left", 0) and side_counts.get("Right", 0) and side_counts["Left"] != side_counts["Right"]:
        warnings.append(
            f"{direction}_Overall source side counts are imbalanced: Left={side_counts['Left']}, Right={side_counts['Right']}."
        )
    return overall_records


def generate_notebook_six_pack(records, output_path, parameters):
    x_field = parameters["x_field"]
    y_field = parameters["y_field"]
    x_values = unique_ordered_values(records, x_field, parameters.get("x_order"))
    charts = []
    all_warnings = []
    directions = ["Horizontal", "Vertical"]
    sides = ["Left", "Right", "Overall"]
    title_prefix = value_or_empty(parameters.get("title_prefix")) or value_or_empty(parameters.get("wafer_label"))

    for direction in directions:
        for side in sides:
            key = f"{direction}_{side}"
            title = f"{title_prefix}_{key}" if title_prefix else key
            chart_warnings = []
            chart_records = build_notebook_chart_records(records, direction, side, parameters, chart_warnings)
            chart_override = chart_override_for(parameters, key)
            chart_path = output_path / f"{key}.png"
            plot_notebook_violin_chart(
                chart_path,
                chart_records,
                parameters,
                title,
                side == "Overall",
                x_values,
                chart_warnings,
                chart_override,
            )
            grouped = group_values_by_x(chart_records, x_field, y_field, x_values)
            group_count = sum(1 for values in grouped.values() if values)
            charts.append(
                {
                    "key": key,
                    "title": title,
                    "chart_path": str(chart_path),
                    "direction": direction,
                    "side": side,
                    "point_count": len(chart_records),
                    "group_count": group_count,
                    "warnings": chart_warnings,
                }
            )
            all_warnings.extend(chart_warnings)

    return charts, all_warnings


def generate_cd_violin_visualization(parsed_data, output_dir, parameters=None):
    if parsed_data.get("data_type") != "cd_sem":
        raise ValueError("cd_violin_visualizer only supports cd_sem parsed_data")

    params = normalize_parameters(parameters)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    raw_records = parsed_data.get("records")
    if not isinstance(raw_records, list) or not raw_records:
        raise ValueError("parsed_records is empty")

    schema = inspect_records_schema(raw_records)
    validate_parameters(params, raw_records)
    filtered_records = apply_filters(raw_records, params["filters"])
    prepared_records, warnings = prepare_records(filtered_records, params)
    if not prepared_records:
        raise ValueError("No valid cd_value data after filtering")

    output_mode = value_or_empty(params.get("output_mode")) or "single_chart"
    use_notebook_six_pack = output_mode == "notebook_six_pack"
    visualization_records = prepared_records if use_notebook_six_pack else derive_overall_records(prepared_records, params, warnings)
    groups = build_groups(visualization_records, params)
    chart_path = output_path / "chart.png"
    report_md_path = output_path / "report.md"
    report_json_path = output_path / "report.json"
    charts = []

    if use_notebook_six_pack:
        charts, chart_warnings = generate_notebook_six_pack(visualization_records, output_path, params)
        warnings.extend(chart_warnings)
        if charts:
            chart_path = Path(charts[0]["chart_path"])
            compatibility_chart_path = output_path / "chart.png"
            if chart_path != compatibility_chart_path:
                shutil.copyfile(chart_path, compatibility_chart_path)
                chart_path = compatibility_chart_path
    else:
        plot_chart(chart_path, visualization_records, params, warnings)
    context = {
        "parsed_data_id": parsed_data.get("id"),
        "raw_data_id": parsed_data.get("raw_data_id"),
        "raw_data_code": parsed_data.get("raw_data_code"),
        "sample_display_code": parsed_data.get("sample_display_code"),
    }
    write_report_md(report_md_path, context, params, groups, warnings)

    report = {
        "chart_title": params.get("title"),
        "parsed_data_id": parsed_data.get("id"),
        "raw_data_id": parsed_data.get("raw_data_id"),
        "sample_display_code": parsed_data.get("sample_display_code"),
        "parameters": params,
        "schema": schema,
        "charts": charts,
        "groups": groups,
        "warnings": warnings,
    }
    report_json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "chart_path": str(chart_path),
        "report_path": str(report_md_path),
        "report_json_path": str(report_json_path),
        "chart_type": "violin",
        "group_count": len(groups),
        "point_count": len(visualization_records),
        "charts": charts,
        "schema": schema,
        "warnings": warnings,
    }
