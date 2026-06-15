import { useEffect, useMemo, useState } from "react";
import { getResistanceSummary } from "../../api/rawDataApi";
import type {
  ParsedDataRecord,
  ResistanceStats,
  ResistanceSummaryResponse,
  VisualizationPayload,
} from "../../types/rawData";
import {
  RESISTANCE_FULL_DIE_LAYOUT,
  ResistanceSingleDieHeatmap,
  ResistanceWaferHeatmap,
  type ResistanceHeatmapCell,
  type ResistanceMetric,
} from "./ResistanceWaferHeatmap";

type ResistanceVisualizationPanelProps = {
  selectedParsedData: ParsedDataRecord;
  onVisualize: (parsedDataId: number, payload?: VisualizationPayload) => Promise<void> | void;
};

type ResistanceArea = "all" | "A" | "B" | "C" | "D";

type MetricOption = {
  value: ResistanceMetric;
  label: string;
  percent?: boolean;
};

const WAFER_ZOOM_MIN = 0.7;
const WAFER_ZOOM_MAX = 1.8;
const WAFER_ZOOM_STEP = 0.1;

const METRIC_OPTIONS: MetricOption[] = [
  { value: "average", label: "Average" },
  { value: "max", label: "Max" },
  { value: "min", label: "Min" },
  { value: "range", label: "Range" },
  { value: "uniformity", label: "Uniformity", percent: true },
  { value: "yield_rate", label: "Yield Rate", percent: true },
];

const AREA_OPTIONS: Array<{ value: ResistanceArea; label: string }> = [
  { value: "all", label: "全 Die" },
  { value: "A", label: "A 区" },
  { value: "B", label: "B 区" },
  { value: "C", label: "C 区" },
  { value: "D", label: "D 区" },
];

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function optionalLimit(value: string) {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const number = Number(trimmed);
  return Number.isFinite(number) ? number : null;
}

function formatNumber(value: unknown, decimalPlaces: number) {
  if (!isFiniteNumber(value)) {
    return "-";
  }
  return Number.isInteger(value) ? String(value) : value.toFixed(decimalPlaces);
}

function formatMetricValue(value: unknown, metric: ResistanceMetric, decimalPlaces: number) {
  if (!isFiniteNumber(value)) {
    return "-";
  }
  if (metric === "uniformity" || metric === "yield_rate") {
    return `${(value * 100).toFixed(decimalPlaces)}%`;
  }
  return formatNumber(value, decimalPlaces);
}

function statValue(stat: ResistanceStats | undefined, metric: ResistanceMetric) {
  const value = stat?.[metric];
  return isFiniteNumber(value) ? value : null;
}

function statsByDie(stats: ResistanceStats[]) {
  return new Map(stats.filter((stat) => stat.die_id).map((stat) => [stat.die_id as string, stat]));
}

function areaKey(dieId: string, area: string) {
  return `${dieId}:${area}`;
}

function statsByDieArea(stats: ResistanceStats[]) {
  return new Map(
    stats
      .filter((stat) => stat.die_id && stat.area)
      .map((stat) => [areaKey(stat.die_id as string, stat.area as string), stat]),
  );
}

function formatStat(value: unknown, kind: "number" | "percent", decimalPlaces = 2) {
  if (!isFiniteNumber(value)) {
    return "-";
  }
  if (kind === "percent") {
    return `${(value * 100).toFixed(decimalPlaces)}%`;
  }
  return formatNumber(value, decimalPlaces);
}

function StatRow({ label, value, kind = "number" }: { label: string; value: unknown; kind?: "number" | "percent" }) {
  return (
    <div className="resistance-die-stat">
      <span>{label}</span>
      <strong>{formatStat(value, kind)}</strong>
    </div>
  );
}

export function ResistanceVisualizationPanel({ selectedParsedData, onVisualize }: ResistanceVisualizationPanelProps) {
  const [metric, setMetric] = useState<ResistanceMetric>("average");
  const [area, setArea] = useState<ResistanceArea>("all");
  const [showDieLabel, setShowDieLabel] = useState(true);
  const [showValue, setShowValue] = useState(true);
  const [decimalPlaces, setDecimalPlaces] = useState(2);
  const [waferZoom, setWaferZoom] = useState(1);
  const [selectedDieId, setSelectedDieId] = useState("");
  const [enableOutlierFilter, setEnableOutlierFilter] = useState(true);
  const [lowerLimit, setLowerLimit] = useState("0");
  const [upperLimit, setUpperLimit] = useState("100");
  const [summary, setSummary] = useState<ResistanceSummaryResponse | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState("");
  const [saveMessage, setSaveMessage] = useState("");
  const [savingAnalysis, setSavingAnalysis] = useState(false);

  const lowerLimitNumber = enableOutlierFilter ? optionalLimit(lowerLimit) : null;
  const upperLimitNumber = enableOutlierFilter ? optionalLimit(upperLimit) : null;
  const hasLimitError = lowerLimitNumber !== null && upperLimitNumber !== null && lowerLimitNumber > upperLimitNumber;
  const summaryArea = area === "all" ? null : area;

  useEffect(() => {
    if (hasLimitError) {
      setSummaryLoading(false);
      setSummaryError("异常值下限不能大于上限");
      return;
    }

    let cancelled = false;
    setSummaryLoading(true);
    setSummaryError("");
    getResistanceSummary(selectedParsedData.id, {
      cleaning_config: {
        lower: lowerLimitNumber,
        upper: upperLimitNumber,
      },
      metric: "cleaned_value",
      area: summaryArea,
      die_id: null,
    })
      .then((result) => {
        if (!cancelled) {
          setSummary(result);
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setSummaryError(error instanceof Error ? error.message : "加载 Resistance 动态汇总失败");
          setSummary(null);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setSummaryLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [area, hasLimitError, lowerLimitNumber, selectedParsedData.id, summaryArea, upperLimitNumber]);

  const dieSummary = summary?.die_summary || [];
  const areaSummary = summary?.area_summary || [];
  const dynamicOverallSummary = summary?.overall_summary || {};

  const { dieStats, areaStats, valuesByDie } = useMemo(() => {
    const dieStatsMap = statsByDie(dieSummary);
    const areaStatsMap = statsByDieArea(areaSummary);
    const nextValues = new Map<string, ResistanceHeatmapCell>();
    const sourceStats = area === "all"
      ? dieSummary
      : areaSummary.filter((stat) => stat.area === area);

    for (const stat of sourceStats) {
      if (!stat.die_id) {
        continue;
      }
      const value = statValue(stat, metric);
      nextValues.set(stat.die_id, {
        dieId: stat.die_id,
        value,
        label: formatMetricValue(value, metric, decimalPlaces),
        hasData: value !== null,
      });
    }

    return {
      dieStats: dieStatsMap,
      areaStats: areaStatsMap,
      valuesByDie: nextValues,
    };
  }, [area, areaSummary, decimalPlaces, dieSummary, metric]);

  const firstAvailableDie = valuesByDie.keys().next().value || dieSummary[0]?.die_id || "";
  const activeDieId = selectedDieId || firstAvailableDie;
  const selectedDieStats = activeDieId ? dieStats.get(activeDieId) : undefined;
  const selectedAreaStats = activeDieId
    ? ["A", "B", "C", "D"].map((areaName) => areaStats.get(areaKey(activeDieId, areaName))).filter(Boolean)
    : [];
  const selectedMetricValue = selectedDieId
    ? valuesByDie.get(selectedDieId)?.value
    : valuesByDie.get(activeDieId)?.value;
  const selectedDiePoints = useMemo(
    () => (summary?.layout_values || []).filter((point) => point.die_id === activeDieId),
    [activeDieId, summary?.layout_values],
  );

  function updateDecimalPlaces(value: number) {
    if (Number.isFinite(value)) {
      setDecimalPlaces(Math.min(6, Math.max(0, Math.trunc(value))));
    }
  }

  function updateWaferZoom(nextZoom: number) {
    if (Number.isFinite(nextZoom)) {
      setWaferZoom(Math.min(WAFER_ZOOM_MAX, Math.max(WAFER_ZOOM_MIN, Number(nextZoom.toFixed(2)))));
    }
  }

  const filterDescription = enableOutlierFilter && !hasLimitError
    ? `筛选：${lowerLimitNumber !== null ? `< ${lowerLimitNumber}` : "无下限"} 或 ${upperLimitNumber !== null ? `> ${upperLimitNumber}` : "无上限"} 计为异常`
    : "筛选：关闭";

  const layoutValues = useMemo(() => RESISTANCE_FULL_DIE_LAYOUT.map((row) => row.map((dieId) => {
    if (!dieId) {
      return null;
    }
    const cell = valuesByDie.get(dieId);
    return {
      die_id: dieId,
      value: cell?.value ?? null,
      label: cell?.label ?? "-",
      has_data: Boolean(cell?.hasData),
    };
  })), [valuesByDie]);

  async function handleSaveAnalysis() {
    setSaveMessage("");
    if (hasLimitError) {
      setSaveMessage("请先修正异常值阈值后再保存。");
      return;
    }
    if (!summary) {
      setSaveMessage("请等待动态汇总加载完成后再保存。");
      return;
    }

    setSavingAnalysis(true);
    try {
      await onVisualize(selectedParsedData.id, {
        chart_type: "resistance_wafer_heatmap",
        metric,
        area,
        cleaning_config: {
          enabled: enableOutlierFilter,
          lower_limit: lowerLimitNumber,
          upper_limit: upperLimitNumber,
        },
        display: {
          show_die_label: showDieLabel,
          show_value: showValue,
          decimal_places: decimalPlaces,
        },
        summary: {
          overall_summary: summary.overall_summary as Record<string, unknown>,
          die_summary: summary.die_summary as Array<Record<string, unknown>>,
          area_summary: summary.area_summary as Array<Record<string, unknown>>,
        },
        layout_values: layoutValues,
      });
      setSaveMessage("当前分析已保存，可在处理历史中查看输出。");
    } catch (err) {
      setSaveMessage(err instanceof Error ? err.message : "保存当前分析失败");
    } finally {
      setSavingAnalysis(false);
    }
  }

  return (
    <section className="resistance-visualization-panel">
      <div className="resistance-visualization-config">
        <label>
          热图指标
          <select value={metric} onChange={(event) => setMetric(event.target.value as ResistanceMetric)}>
            {METRIC_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
        <label>
          统计范围
          <select value={area} onChange={(event) => setArea(event.target.value as ResistanceArea)}>
            {AREA_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
        <label>
          小数位数
          <input
            min={0}
            max={6}
            type="number"
            value={decimalPlaces}
            onChange={(event) => updateDecimalPlaces(Number(event.target.value))}
          />
        </label>
        <label className="resistance-checkbox-row">
          <input
            type="checkbox"
            checked={showDieLabel}
            onChange={(event) => setShowDieLabel(event.target.checked)}
          />
          <span>显示 Die 编号</span>
        </label>
        <label className="resistance-checkbox-row">
          <input
            type="checkbox"
            checked={showValue}
            onChange={(event) => setShowValue(event.target.checked)}
          />
          <span>显示数值</span>
        </label>
        <div className="resistance-outlier-config">
          <label className="resistance-checkbox-row">
            <input
              type="checkbox"
              checked={enableOutlierFilter}
              onChange={(event) => setEnableOutlierFilter(event.target.checked)}
            />
            <span>启用异常值筛选</span>
          </label>
          <label>
            下限
            <input
              type="number"
              value={lowerLimit}
              onChange={(event) => setLowerLimit(event.target.value)}
            />
          </label>
          <label>
            上限
            <input
              type="number"
              value={upperLimit}
              onChange={(event) => setUpperLimit(event.target.value)}
            />
          </label>
          <p className={`resistance-filter-status ${hasLimitError || summaryError ? "error" : ""}`}>
            {summaryError || filterDescription}
            {!hasLimitError && !summaryError ? `；Normal ${dynamicOverallSummary.count_normal ?? "-"} / Total ${dynamicOverallSummary.count_total ?? "-"}，Yield ${formatStat(dynamicOverallSummary.yield_rate, "percent")}` : ""}
          </p>
        </div>
        <div className="resistance-save-actions">
          <button type="button" disabled={savingAnalysis || summaryLoading || hasLimitError || !summary} onClick={() => void handleSaveAnalysis()}>
            {savingAnalysis ? "保存中..." : "保存当前分析"}
          </button>
          {saveMessage ? (
            <span className={hasLimitError || saveMessage.includes("失败") ? "error" : ""}>{saveMessage}</span>
          ) : null}
        </div>
      </div>

      {summaryLoading ? <div className="empty-row">加载 Resistance 可视化数据中...</div> : null}
      {!summaryLoading && summaryError && !hasLimitError ? <div className="empty-row">{summaryError}</div> : null}

      <div className="resistance-visualization-layout">
        <div className="resistance-heatmap-section">
          <div className="resistance-heatmap-header">
            <h5>Wafer Die Heatmap</h5>
            <span>{METRIC_OPTIONS.find((option) => option.value === metric)?.label} · {AREA_OPTIONS.find((option) => option.value === area)?.label} · {hasLimitError ? "筛选配置错误，当前未应用筛选" : filterDescription}</span>
          </div>
          <div className="resistance-zoom-controls" aria-label="Wafer heatmap zoom controls">
            <button
              type="button"
              title="缩小热图"
              disabled={waferZoom <= WAFER_ZOOM_MIN}
              onClick={() => updateWaferZoom(waferZoom - WAFER_ZOOM_STEP)}
            >
              -
            </button>
            <strong>{Math.round(waferZoom * 100)}%</strong>
            <button
              type="button"
              title="放大热图"
              disabled={waferZoom >= WAFER_ZOOM_MAX}
              onClick={() => updateWaferZoom(waferZoom + WAFER_ZOOM_STEP)}
            >
              +
            </button>
            <button type="button" title="重置缩放" onClick={() => updateWaferZoom(1)}>
              重置
            </button>
          </div>
          <ResistanceWaferHeatmap
            valuesByDie={valuesByDie}
            selectedDieId={activeDieId}
            showDieLabel={showDieLabel}
            showValue={showValue}
            zoom={waferZoom}
            onSelectDie={setSelectedDieId}
          />
          {activeDieId ? (
            <div className="resistance-single-die-section">
              <div className="resistance-single-die-header">
                <h5>{activeDieId} 单 Die 12×12 热图</h5>
                <span>A/B/C/D 四区按 6×6 象限分隔</span>
              </div>
              <ResistanceSingleDieHeatmap
                dieId={activeDieId}
                points={selectedDiePoints}
                decimalPlaces={decimalPlaces}
              />
            </div>
          ) : null}
        </div>

        <aside className="resistance-die-detail">
          <h5>Die 详情</h5>
          {activeDieId ? (
            <>
              <div className="resistance-die-title">
                <strong>{activeDieId}</strong>
                <span>当前指标：{formatMetricValue(selectedMetricValue, metric, decimalPlaces)}</span>
              </div>
              <div className="resistance-die-stats-grid">
                <StatRow label="Max" value={selectedDieStats?.max} />
                <StatRow label="Min" value={selectedDieStats?.min} />
                <StatRow label="Range" value={selectedDieStats?.range} />
                <StatRow label="Average" value={selectedDieStats?.average} />
                <StatRow label="Std" value={selectedDieStats?.std} />
                <StatRow label="3 Sigma" value={selectedDieStats?.three_sigma} />
                <StatRow label="Uniformity" value={selectedDieStats?.uniformity} kind="percent" />
                <StatRow label="Yield Rate" value={selectedDieStats?.yield_rate} kind="percent" />
                <StatRow label="Total" value={selectedDieStats?.count_total} />
                <StatRow label="Valid" value={selectedDieStats?.count_valid} />
                <StatRow label="NA" value={selectedDieStats?.count_na} />
                <StatRow label="Normal" value={selectedDieStats?.count_normal} />
                <StatRow label="Outlier" value={selectedDieStats?.count_outlier} />
              </div>

              <div className="resistance-area-detail">
                <h6>A/B/C/D 区域摘要</h6>
                <div className="resistance-area-detail-list">
                  {selectedAreaStats.map((stat) => (
                    <div className="resistance-area-detail-card" key={`${activeDieId}-${stat?.area}`}>
                      <strong>{stat?.area}</strong>
                      <span>Avg {formatStat(stat?.average, "number")}</span>
                      <span>Range {formatStat(stat?.range, "number")}</span>
                      <span>Yield {formatStat(stat?.yield_rate, "percent")}</span>
                    </div>
                  ))}
                </div>
              </div>
            </>
          ) : (
            <div className="empty-row">暂无 Die 数据</div>
          )}
        </aside>
      </div>
    </section>
  );
}
