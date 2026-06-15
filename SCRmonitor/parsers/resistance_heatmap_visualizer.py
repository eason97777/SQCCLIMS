#!/usr/bin/env python3
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Rectangle


SCRIPT_NAME = "resistance_wafer_heatmap"
SCRIPT_VERSION = "0.1.0"

FULL_DIE_LAYOUT = [
    [None, None, None, None, "A1", "A2", "A3", "A4", "A5", None, None, None, None],
    [None, None, None, "B1", "B2", "B3", "B4", "B5", "B6", "B7", None, None, None],
    [None, None, "C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9", None, None],
    [None, "D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9", "D10", "D11", None],
    ["E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8", "E9", "E10", "E11", "E12", "E13"],
    ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12", "F13"],
    ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "G9", "G10", "G11", "G12", "G13"],
    ["H1", "H2", "H3", "H4", "H5", "H6", "H7", "H8", "H9", "H10", "H11", "H12", "H13"],
    ["I1", "I2", "I3", "I4", "I5", "I6", "I7", "I8", "I9", "I10", "I11", "I12", "I13"],
    [None, "J1", "J2", "J3", "J4", "J5", "J6", "J7", "J8", "J9", "J10", "J11", None],
    [None, None, "K1", "K2", "K3", "K4", "K5", "K6", "K7", "K8", "K9", None, None],
    [None, None, None, "L1", "L2", "L3", "L4", "L5", "L6", "L7", None, None, None],
    [None, None, None, None, "M1", "M2", "M3", "M4", "M5", None, None, None, None],
]

METRIC_LABELS = {
    "average": "Average",
    "max": "Max",
    "min": "Min",
    "range": "Range",
    "uniformity": "Uniformity",
    "yield_rate": "Yield Rate",
}

AREA_LABELS = {
    "all": "All Die",
    "A": "Area A",
    "B": "Area B",
    "C": "Area C",
    "D": "Area D",
}

EXCEL_RED_WHITE_BLUE_CMAP = LinearSegmentedColormap.from_list(
    "excel_red_white_blue",
    ["#5B9BD5", "#FFFFFF", "#F8696B"],
)


def is_number(value):
    return isinstance(value, (int, float)) and math.isfinite(value)


def flatten_layout_values(layout_values):
    values = {}
    if not isinstance(layout_values, list):
        return values
    for row in layout_values:
        if not isinstance(row, list):
            continue
        for cell in row:
            if isinstance(cell, dict) and cell.get("die_id"):
                values[str(cell["die_id"])] = cell
    return values


def format_value(value, metric, decimal_places):
    if not is_number(value):
        return "-"
    if metric in {"uniformity", "yield_rate"}:
        return f"{value * 100:.{decimal_places}f}%"
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.{decimal_places}f}"


def cleaning_label(config):
    if not isinstance(config, dict) or not config.get("enabled"):
        return "Filter off"
    lower = config.get("lower_limit")
    upper = config.get("upper_limit")
    lower_text = f"< {lower}" if is_number(lower) else "no lower limit"
    upper_text = f"> {upper}" if is_number(upper) else "no upper limit"
    return f"{lower_text} or {upper_text} marked as outlier"


def cell_color(value, value_min, value_max, cmap):
    if not is_number(value):
        return "#eef1f1"
    ratio = 0.5 if value_max == value_min else (value - value_min) / (value_max - value_min)
    ratio = min(1, max(0, ratio))
    return cmap(ratio)


def generate_resistance_heatmap_visualization(payload, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    chart_path = output_dir / "resistance_wafer_heatmap.png"

    metric = str(payload.get("metric") or "average")
    area = str(payload.get("area") or "all")
    display = payload.get("display") if isinstance(payload.get("display"), dict) else {}
    cleaning_config = payload.get("cleaning_config") if isinstance(payload.get("cleaning_config"), dict) else {}
    show_die_label = bool(display.get("show_die_label", True))
    show_value = bool(display.get("show_value", True))
    decimal_places = display.get("decimal_places", 2)
    try:
        decimal_places = max(0, min(6, int(decimal_places)))
    except (TypeError, ValueError):
        decimal_places = 2

    values_by_die = flatten_layout_values(payload.get("layout_values", []))
    numeric_values = [
        cell.get("value")
        for cell in values_by_die.values()
        if is_number(cell.get("value"))
    ]
    value_min = min(numeric_values) if numeric_values else 0
    value_max = max(numeric_values) if numeric_values else 0
    cmap = EXCEL_RED_WHITE_BLUE_CMAP

    row_count = len(FULL_DIE_LAYOUT)
    col_count = max(len(row) for row in FULL_DIE_LAYOUT)
    fig, ax = plt.subplots(figsize=(14.8, 13.4), dpi=160)
    ax.set_xlim(0, col_count)
    ax.set_ylim(row_count, 0)
    ax.set_aspect("equal")
    ax.axis("off")

    for row_index, row in enumerate(FULL_DIE_LAYOUT):
        for col_index, die_id in enumerate(row):
            if die_id is None:
                continue
            cell = values_by_die.get(die_id, {})
            value = cell.get("value")
            has_data = is_number(value)
            face_color = cell_color(value, value_min, value_max, cmap)
            edge_color = "#2f5752" if has_data else "#cbd2d0"
            rect = Rectangle(
                (col_index + 0.06, row_index + 0.08),
                0.88,
                0.78,
                linewidth=1.2,
                edgecolor=edge_color,
                facecolor=face_color,
            )
            ax.add_patch(rect)

            lines = []
            if show_die_label:
                lines.append(die_id)
            if show_value:
                lines.append(format_value(value, metric, decimal_places))
            if lines:
                ax.text(
                    col_index + 0.5,
                    row_index + 0.47,
                    "\n".join(lines),
                    ha="center",
                    va="center",
                    fontsize=8.5,
                    fontweight="bold" if show_die_label else "normal",
                    color="#17211f" if has_data else "#8a9693",
                )

    metric_label = METRIC_LABELS.get(metric, metric)
    area_label = AREA_LABELS.get(area, area)
    title = f"Resistance Wafer Heatmap - {metric_label} - {area_label}"
    subtitle = cleaning_label(cleaning_config)
    fig.suptitle(title, fontsize=15, fontweight="bold", y=0.965)
    ax.set_title(subtitle, fontsize=10, color="#60706c", pad=8)

    if numeric_values:
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=value_min, vmax=value_max))
        sm.set_array([])
        colorbar = fig.colorbar(sm, ax=ax, fraction=0.036, pad=0.04)
        colorbar.set_label(metric_label, fontsize=9)

    fig.savefig(chart_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    return {
        "chart_path": chart_path,
        "chart_type": "resistance_wafer_heatmap",
        "metric": metric,
        "area": area,
        "point_count": len([die_id for row in FULL_DIE_LAYOUT for die_id in row if die_id]),
        "value_min": value_min if numeric_values else None,
        "value_max": value_max if numeric_values else None,
    }
