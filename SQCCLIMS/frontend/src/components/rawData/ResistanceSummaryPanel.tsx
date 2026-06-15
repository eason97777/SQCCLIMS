import { useEffect, useMemo, useState } from "react";
import { getResistanceSummary } from "../../api/rawDataApi";
import type {
  ParsedDataRecord,
  ResistanceLayoutValue,
  ResistanceStats,
  ResistanceSummaryResponse,
} from "../../types/rawData";

type ResistanceSummaryPanelProps = {
  parsedData: ParsedDataRecord;
};

type DetailFilter = "all" | "outlier" | "na" | "normal";

const PAGE_SIZE = 100;
const AREA_OPTIONS = ["A", "B", "C", "D"];

const DIE_SUMMARY_COLUMNS: Array<{ key: keyof ResistanceStats; label: string; kind?: "number" | "percent" }> = [
  { key: "die_id", label: "Die" },
  { key: "max", label: "Max", kind: "number" },
  { key: "min", label: "Min", kind: "number" },
  { key: "range", label: "Range", kind: "number" },
  { key: "average", label: "Average", kind: "number" },
  { key: "std", label: "Std", kind: "number" },
  { key: "three_sigma", label: "3 Sigma", kind: "number" },
  { key: "uniformity", label: "Uniformity", kind: "percent" },
  { key: "count_total", label: "Total" },
  { key: "count_valid", label: "Valid" },
  { key: "count_na", label: "NA" },
  { key: "count_normal", label: "Normal" },
  { key: "count_outlier", label: "Outlier" },
  { key: "yield_rate", label: "Yield Rate", kind: "percent" },
];

const AREA_SUMMARY_COLUMNS: Array<{ key: keyof ResistanceStats; label: string; kind?: "number" | "percent" }> = [
  { key: "die_id", label: "Die" },
  { key: "area", label: "Area" },
  ...DIE_SUMMARY_COLUMNS.slice(1),
];

function isNil(value: unknown) {
  return value === null || value === undefined || value === "";
}

function valueOrDash(value: unknown) {
  return isNil(value) ? "-" : String(value);
}

function formatNumber(value: unknown) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return valueOrDash(value);
  }
  return Number.isInteger(value) ? String(value) : value.toFixed(4);
}

function formatPercent(value: unknown) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "-";
  }
  return `${(value * 100).toFixed(2)}%`;
}

function formatStatValue(value: unknown, kind?: "number" | "percent") {
  if (kind === "percent") {
    return formatPercent(value);
  }
  if (kind === "number") {
    return formatNumber(value);
  }
  return valueOrDash(value);
}

function optionalLimit(value: string) {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const number = Number(trimmed);
  return Number.isFinite(number) ? number : null;
}

function uniqueSorted(values: Array<string | null | undefined>) {
  return [...new Set(values.filter(Boolean) as string[])]
    .sort((left, right) => left.localeCompare(right, undefined, { numeric: true }));
}

function matchesQuery(record: ResistanceLayoutValue, query: string) {
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    return true;
  }
  return [
    record.die_id,
    record.area,
    record.row_header,
    record.col_header,
    record.raw_value,
    record.cleaned_value,
    record.outlier_reason,
  ].some((value) => String(value ?? "").toLowerCase().includes(normalized));
}

export function ResistanceSummaryPanel({ parsedData }: ResistanceSummaryPanelProps) {
  const [dieFilter, setDieFilter] = useState("");
  const [areaFilter, setAreaFilter] = useState("");
  const [detailFilter, setDetailFilter] = useState<DetailFilter>("all");
  const [query, setQuery] = useState("");
  const [lowerLimit, setLowerLimit] = useState("0");
  const [upperLimit, setUpperLimit] = useState("100");
  const [currentPage, setCurrentPage] = useState(1);
  const [summary, setSummary] = useState<ResistanceSummaryResponse | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState("");

  const lowerLimitNumber = optionalLimit(lowerLimit);
  const upperLimitNumber = optionalLimit(upperLimit);
  const hasLimitError = lowerLimitNumber !== null && upperLimitNumber !== null && lowerLimitNumber > upperLimitNumber;

  useEffect(() => {
    if (hasLimitError) {
      setSummaryLoading(false);
      setSummaryError("异常值下限不能大于上限");
      return;
    }

    let cancelled = false;
    setSummaryLoading(true);
    setSummaryError("");
    getResistanceSummary(parsedData.id, {
      cleaning_config: { lower: lowerLimitNumber, upper: upperLimitNumber },
      metric: "cleaned_value",
    })
      .then((result) => {
        if (!cancelled) {
          setSummary(result);
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setSummaryError(error instanceof Error ? error.message : "加载 Resistance 汇总失败");
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
  }, [hasLimitError, lowerLimitNumber, parsedData.id, upperLimitNumber]);

  const overall = summary?.overall_summary || {};
  const dieOptions = useMemo(
    () => uniqueSorted(summary?.die_summary.map((item) => item.die_id) || []),
    [summary?.die_summary],
  );
  const filteredRecords = useMemo(() => (
    (summary?.layout_values || []).filter((record) => {
      if (dieFilter && record.die_id !== dieFilter) {
        return false;
      }
      if (areaFilter && record.area !== areaFilter) {
        return false;
      }
      if (detailFilter === "outlier" && !record.is_outlier) {
        return false;
      }
      if (detailFilter === "na" && !record.is_na) {
        return false;
      }
      if (detailFilter === "normal" && (record.is_na || record.is_outlier)) {
        return false;
      }
      return matchesQuery(record, query);
    })
  ), [areaFilter, detailFilter, dieFilter, query, summary?.layout_values]);
  const totalPages = Math.max(1, Math.ceil(filteredRecords.length / PAGE_SIZE));
  const safeCurrentPage = Math.min(Math.max(currentPage, 1), totalPages);
  const visibleRecords = filteredRecords.slice(
    (safeCurrentPage - 1) * PAGE_SIZE,
    safeCurrentPage * PAGE_SIZE,
  );

  function resetToFirstPage() {
    setCurrentPage(1);
  }

  function updateDieFilter(value: string) {
    setDieFilter(value);
    resetToFirstPage();
  }

  function updateAreaFilter(value: string) {
    setAreaFilter(value);
    resetToFirstPage();
  }

  function updateDetailFilter(value: DetailFilter) {
    setDetailFilter(value);
    resetToFirstPage();
  }

  function updateQuery(value: string) {
    setQuery(value);
    resetToFirstPage();
  }

  function updateLowerLimit(value: string) {
    setLowerLimit(value);
    resetToFirstPage();
  }

  function updateUpperLimit(value: string) {
    setUpperLimit(value);
    resetToFirstPage();
  }

  return (
    <div className="resistance-summary-panel">
      <section className="raw-parsed-section">
        <h5>数据概览</h5>
        <div className="resistance-filter-bar">
          <label>
            下限
            <input
              type="number"
              value={lowerLimit}
              onChange={(event) => updateLowerLimit(event.target.value)}
            />
          </label>
          <label>
            上限
            <input
              type="number"
              value={upperLimit}
              onChange={(event) => updateUpperLimit(event.target.value)}
            />
          </label>
        </div>
        {summaryLoading ? <div className="empty-row">加载 Resistance 汇总中...</div> : null}
        {summaryError ? <div className="empty-row">{summaryError}</div> : null}
        {!summaryLoading && !summaryError ? (
          <div className="resistance-overview-grid">
            <div className="raw-summary-card">
              <span>Die 数量</span>
              <strong>{valueOrDash(summary?.die_summary.length)}</strong>
            </div>
            <div className="raw-summary-card">
              <span>总点数</span>
              <strong>{valueOrDash(overall.count_total)}</strong>
            </div>
            <div className="raw-summary-card">
              <span>有效点数</span>
              <strong>{valueOrDash(overall.count_valid)}</strong>
            </div>
            <div className="raw-summary-card">
              <span>NA 点数</span>
              <strong>{valueOrDash(overall.count_na)}</strong>
            </div>
            <div className="raw-summary-card">
              <span>正常点数</span>
              <strong>{valueOrDash(overall.count_normal)}</strong>
            </div>
            <div className="raw-summary-card">
              <span>异常点数</span>
              <strong>{valueOrDash(overall.count_outlier)}</strong>
            </div>
            <div className="raw-summary-card">
              <span>良率</span>
              <strong>{formatPercent(overall.yield_rate)}</strong>
            </div>
          </div>
        ) : null}
      </section>

      <section className="raw-parsed-section">
        <h5>Die 统计表</h5>
        <div className="resistance-table-wrap">
          <table className="raw-records-table resistance-stats-table">
            <thead>
              <tr>
                {DIE_SUMMARY_COLUMNS.map((column) => (
                  <th key={column.key}>{column.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(summary?.die_summary || []).map((row) => (
                <tr key={row.die_id || JSON.stringify(row)}>
                  {DIE_SUMMARY_COLUMNS.map((column) => (
                    <td key={column.key} className={column.kind ? "numeric-cell" : "text-cell"}>
                      {formatStatValue(row[column.key], column.kind)}
                    </td>
                  ))}
                </tr>
              ))}
              {!summaryLoading && !summary?.die_summary.length ? (
                <tr><td className="empty-row" colSpan={DIE_SUMMARY_COLUMNS.length}>暂无数据</td></tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>

      <section className="raw-parsed-section">
        <h5>Area 统计表</h5>
        <div className="resistance-table-wrap">
          <table className="raw-records-table resistance-stats-table">
            <thead>
              <tr>
                {AREA_SUMMARY_COLUMNS.map((column) => (
                  <th key={column.key}>{column.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(summary?.area_summary || []).map((row) => (
                <tr key={`${row.die_id || "die"}-${row.area || "area"}`}>
                  {AREA_SUMMARY_COLUMNS.map((column) => (
                    <td key={column.key} className={column.kind ? "numeric-cell" : "text-cell"}>
                      {formatStatValue(row[column.key], column.kind)}
                    </td>
                  ))}
                </tr>
              ))}
              {!summaryLoading && !summary?.area_summary.length ? (
                <tr><td className="empty-row" colSpan={AREA_SUMMARY_COLUMNS.length}>暂无数据</td></tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>

      <section className="raw-parsed-section raw-parsed-records-section">
        <h5>点位明细表</h5>
        <div className="resistance-filter-bar">
          <label>
            Die
            <select value={dieFilter} onChange={(event) => updateDieFilter(event.target.value)}>
              <option value="">全部</option>
              {dieOptions.map((dieId) => (
                <option key={dieId} value={dieId}>{dieId}</option>
              ))}
            </select>
          </label>
          <label>
            Area
            <select value={areaFilter} onChange={(event) => updateAreaFilter(event.target.value)}>
              <option value="">全部</option>
              {AREA_OPTIONS.map((area) => (
                <option key={area} value={area}>{area}</option>
              ))}
            </select>
          </label>
          <label>
            状态
            <select value={detailFilter} onChange={(event) => updateDetailFilter(event.target.value as DetailFilter)}>
              <option value="all">全部</option>
              <option value="outlier">只看异常</option>
              <option value="na">只看 NA</option>
              <option value="normal">只看正常</option>
            </select>
          </label>
          <label>
            搜索
            <input value={query} onChange={(event) => updateQuery(event.target.value)} placeholder="Die / Area / 数值" />
          </label>
        </div>

        {summaryLoading ? <div className="empty-row">加载 Resistance 明细中...</div> : null}
        {!summaryLoading ? (
          <>
            <div className="parsed-records-table-wrap">
              <table className="raw-records-table resistance-detail-table">
                <thead>
                  <tr>
                    <th>Die</th>
                    <th>Row</th>
                    <th>Col</th>
                    <th>Row Header</th>
                    <th>Col Header</th>
                    <th>Area</th>
                    <th>Raw Value</th>
                    <th>Cleaned Value</th>
                    <th>Is NA</th>
                    <th>Is Outlier</th>
                    <th>Outlier Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleRecords.map((record) => (
                    <tr key={record.id}>
                      <td className="text-cell">{valueOrDash(record.die_id)}</td>
                      <td className="numeric-cell">{valueOrDash(record.row_index)}</td>
                      <td className="numeric-cell">{valueOrDash(record.col_index)}</td>
                      <td className="text-cell">{valueOrDash(record.row_header)}</td>
                      <td className="text-cell">{valueOrDash(record.col_header)}</td>
                      <td className="text-cell">{valueOrDash(record.area)}</td>
                      <td className="numeric-cell">{valueOrDash(record.raw_value)}</td>
                      <td className="numeric-cell">{valueOrDash(record.cleaned_value)}</td>
                      <td className="text-cell">{record.is_na ? "是" : "否"}</td>
                      <td className="text-cell">{record.is_outlier ? "是" : "否"}</td>
                      <td className="text-cell">{valueOrDash(record.outlier_reason)}</td>
                    </tr>
                  ))}
                  {!visibleRecords.length ? (
                    <tr><td className="empty-row" colSpan={11}>暂无数据</td></tr>
                  ) : null}
                </tbody>
              </table>
            </div>
            <div className="parsed-records-toolbar">
              <span>共 {filteredRecords.length} 条，当前显示 {visibleRecords.length} 条</span>
              <div className="parsed-records-pagination">
                <button type="button" onClick={() => setCurrentPage(safeCurrentPage - 1)} disabled={safeCurrentPage <= 1}>
                  上一页
                </button>
                <span>{safeCurrentPage} / {totalPages}</span>
                <button type="button" onClick={() => setCurrentPage(safeCurrentPage + 1)} disabled={safeCurrentPage >= totalPages}>
                  下一页
                </button>
              </div>
            </div>
          </>
        ) : null}
      </section>
    </div>
  );
}
