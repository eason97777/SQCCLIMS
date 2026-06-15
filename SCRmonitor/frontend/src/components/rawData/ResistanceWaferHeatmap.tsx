import { useState } from "react";

export type ResistanceMetric = "average" | "max" | "min" | "range" | "uniformity" | "yield_rate";

export type ResistanceHeatmapCell = {
  dieId: string;
  value: number | null;
  label: string;
  hasData: boolean;
};

export type ResistanceDiePoint = {
  die_id: string | null;
  area: string | null;
  row_index: number | null;
  col_index: number | null;
  row_header: string | null;
  col_header: string | null;
  value: number | null;
  numeric_value: number | null;
  cleaned_value: string | null;
  raw_value: string | null;
  is_na: boolean;
  is_outlier: boolean;
};

type ResistanceWaferHeatmapProps = {
  valuesByDie: Map<string, ResistanceHeatmapCell>;
  selectedDieId?: string;
  showDieLabel: boolean;
  showValue: boolean;
  zoom: number;
  onSelectDie: (dieId: string) => void;
};

export const RESISTANCE_FULL_DIE_LAYOUT: Array<Array<string | null>> = [
  [null, null, null, null, "A1", "A2", "A3", "A4", "A5", null, null, null, null],
  [null, null, null, "B1", "B2", "B3", "B4", "B5", "B6", "B7", null, null, null],
  [null, null, "C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9", null, null],
  [null, "D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9", "D10", "D11", null],
  ["E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8", "E9", "E10", "E11", "E12", "E13"],
  ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12", "F13"],
  ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "G9", "G10", "G11", "G12", "G13"],
  ["H1", "H2", "H3", "H4", "H5", "H6", "H7", "H8", "H9", "H10", "H11", "H12", "H13"],
  ["I1", "I2", "I3", "I4", "I5", "I6", "I7", "I8", "I9", "I10", "I11", "I12", "I13"],
  [null, "J1", "J2", "J3", "J4", "J5", "J6", "J7", "J8", "J9", "J10", "J11", null],
  [null, null, "K1", "K2", "K3", "K4", "K5", "K6", "K7", "K8", "K9", null, null],
  [null, null, null, "L1", "L2", "L3", "L4", "L5", "L6", "L7", null, null, null],
  [null, null, null, null, "M1", "M2", "M3", "M4", "M5", null, null, null, null],
];

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

const EXCEL_BLUE = [91, 155, 213];
const EXCEL_WHITE = [255, 255, 255];
const EXCEL_RED = [248, 105, 107];

function interpolateColor(start: number[], end: number[], ratio: number) {
  const [r, g, b] = start.map((channel, index) => (
    Math.round(channel + (end[index] - channel) * ratio)
  ));
  return `rgb(${r}, ${g}, ${b})`;
}

export function heatColor(value: number, min: number, max: number) {
  const ratio = max === min ? 0.5 : Math.min(1, Math.max(0, (value - min) / (max - min)));
  if (ratio <= 0.5) {
    return interpolateColor(EXCEL_BLUE, EXCEL_WHITE, ratio * 2);
  }
  return interpolateColor(EXCEL_WHITE, EXCEL_RED, (ratio - 0.5) * 2);
}

function formatPointLabel(point: ResistanceDiePoint | undefined, decimalPlaces: number) {
  if (!point) {
    return "-";
  }
  if (isFiniteNumber(point.value)) {
    return Number.isInteger(point.value) ? String(point.value) : point.value.toFixed(decimalPlaces);
  }
  return point.cleaned_value || point.raw_value || "-";
}

export function ResistanceWaferHeatmap({
  valuesByDie,
  selectedDieId = "",
  showDieLabel,
  showValue,
  zoom,
  onSelectDie,
}: ResistanceWaferHeatmapProps) {
  const numericValues = [...valuesByDie.values()]
    .map((cell) => cell.value)
    .filter(isFiniteNumber);
  const min = numericValues.length ? Math.min(...numericValues) : 0;
  const max = numericValues.length ? Math.max(...numericValues) : 0;
  const zoomStyle = {
    "--wafer-cell-size": `${58 * zoom}px`,
    "--wafer-die-font-size": `${11 * zoom}px`,
    "--wafer-value-font-size": `${11 * zoom}px`,
    "--wafer-grid-gap": `${Math.max(3, 4 * zoom)}px`,
  } as Record<string, string>;

  return (
    <div className="resistance-wafer-map" role="grid" aria-label="Resistance wafer heatmap" style={zoomStyle}>
      {RESISTANCE_FULL_DIE_LAYOUT.map((row, rowIndex) => (
        <div className="resistance-wafer-row" role="row" key={`row-${rowIndex}`}>
          {row.map((dieId, colIndex) => {
            if (!dieId) {
              return (
                <div
                  className="resistance-wafer-slot empty"
                  role="presentation"
                  key={`empty-${rowIndex}-${colIndex}`}
                />
              );
            }

            const cell = valuesByDie.get(dieId);
            const cellValue = cell?.value;
            const hasData = Boolean(cell?.hasData && isFiniteNumber(cellValue));
            const isSelected = selectedDieId === dieId;
            const style = hasData
              ? { backgroundColor: heatColor(cellValue as number, min, max) }
              : undefined;

            return (
              <button
                className={`resistance-wafer-cell ${hasData ? "has-data" : "no-data"} ${isSelected ? "selected" : ""}`}
                key={dieId}
                type="button"
                role="gridcell"
                style={style}
                title={`${dieId}: ${cell?.label || "-"}`}
                disabled={!hasData}
                onClick={() => onSelectDie(dieId)}
              >
                {showDieLabel ? <span className="resistance-wafer-die">{dieId}</span> : null}
                {showValue ? <strong>{cell?.label || "-"}</strong> : null}
              </button>
            );
          })}
        </div>
      ))}
    </div>
  );
}

type ResistanceSingleDieHeatmapProps = {
  dieId: string;
  points: ResistanceDiePoint[];
  decimalPlaces: number;
};

const DIE_AREA_OPTIONS = ["A", "B", "C", "D"] as const;
type DieArea = typeof DIE_AREA_OPTIONS[number];

export function ResistanceSingleDieHeatmap({
  dieId,
  points,
  decimalPlaces,
}: ResistanceSingleDieHeatmapProps) {
  const [selectedArea, setSelectedArea] = useState<DieArea | null>(null);
  const pointsByPosition = new Map(
    points
      .filter((point) => point.die_id === dieId && point.row_index && point.col_index)
      .map((point) => [`${point.row_index}:${point.col_index}`, point]),
  );
  const numericValues = points
    .filter((point) => point.die_id === dieId && isFiniteNumber(point.value) && !point.is_outlier)
    .map((point) => point.value as number);
  const min = numericValues.length ? Math.min(...numericValues) : 0;
  const max = numericValues.length ? Math.max(...numericValues) : 0;

  return (
    <div className="resistance-single-die" aria-label={`${dieId} 12 by 12 die heatmap`}>
      <div className="resistance-single-die-grid" role="grid">
        {Array.from({ length: 12 }, (_, rowOffset) => (
          Array.from({ length: 12 }, (__, colOffset) => {
            const rowIndex = rowOffset + 1;
            const colIndex = colOffset + 1;
            const point = pointsByPosition.get(`${rowIndex}:${colIndex}`);
            const hasValue = isFiniteNumber(point?.value);
            const label = formatPointLabel(point, decimalPlaces);
            const isDimmed = Boolean(selectedArea && point?.area !== selectedArea);
            const style = hasValue && !point?.is_outlier
              ? { backgroundColor: heatColor(point.value as number, min, max) }
              : undefined;

            return (
              <div
                className={`resistance-single-die-cell area-${point?.area || "none"} ${hasValue ? "has-data" : "no-data"} ${point?.is_outlier ? "outlier" : ""} ${isDimmed ? "dimmed" : ""}`}
                key={`${rowIndex}-${colIndex}`}
                role="gridcell"
                style={style}
                title={`${dieId} R${rowIndex} C${colIndex} 鍖哄煙 ${point?.area || "-"}: ${label}`}
              >
                <span>{label}</span>
              </div>
            );
          })
        ))}
      </div>
      <div className="resistance-single-die-legend" aria-label="单 Die 区域筛选">
        {DIE_AREA_OPTIONS.map((areaName) => (
          <button
            className={selectedArea === areaName ? "active" : ""}
            key={areaName}
            type="button"
            aria-pressed={selectedArea === areaName}
            onClick={() => setSelectedArea((currentArea) => (currentArea === areaName ? null : areaName))}
          >
            {areaName} 区
          </button>
        ))}
      </div>
    </div>
  );
}
