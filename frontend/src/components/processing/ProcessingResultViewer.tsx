import type { ProcessingResultRecord } from "../../types/processing";
import { formatDateTime } from "../../utils/formatDate";

type ProcessingResultViewerProps = {
  result: ProcessingResultRecord | null;
};

type StatsGroup = {
  metric_name?: string;
  unit?: string;
  count?: number;
  mean?: number;
  stddev?: number;
  min?: number;
  max?: number;
  cv_percent?: number | null;
};

type QcFailure = {
  sample_display_code?: string;
  sample_code?: string;
  metric_name?: string;
  value?: number;
  unit?: string;
  status?: string;
  measured_at?: string;
};

type StatsResult = {
  type: "stats";
  groups?: StatsGroup[];
};

type QcResult = {
  type: "qc";
  count?: number;
  pass_rate?: number;
  failed?: number;
  failures?: QcFailure[];
};

type NormalizePoint = {
  sample_display_code?: string;
  sample_code?: string;
  metric_name?: string;
  raw_value?: number;
  normalized_value?: number;
  measured_at?: string;
};

type NormalizeResult = {
  type: "normalize";
  points?: NormalizePoint[];
};

type UnknownResult = Record<string, unknown>;

function tryParseResult(resultJson: string): UnknownResult | string {
  try {
    return JSON.parse(resultJson) as UnknownResult;
  } catch {
    return resultJson;
  }
}

function formatNumber(value: unknown, digits = 3) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  const number = Number(value);
  if (Number.isNaN(number)) {
    return String(value);
  }
  return Number.isInteger(number)
    ? String(number)
    : number.toFixed(digits).replace(/0+$/, "").replace(/\.$/, "");
}

function renderTable(headers: string[], rows: Array<Array<string | number>>) {
  return (
    <div className="table-wrap compact">
      <table>
        <thead>
          <tr>
            {headers.map((header) => (
              <th key={header}>{header}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length ? (
            rows.map((row, rowIndex) => (
              <tr key={rowIndex}>
                {row.map((cell, cellIndex) => (
                  <td key={`${rowIndex}-${cellIndex}`}>{String(cell)}</td>
                ))}
              </tr>
            ))
          ) : (
            <tr>
              <td className="empty-row" colSpan={headers.length}>
                暂无数据
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

export function ProcessingResultViewer({ result }: ProcessingResultViewerProps) {
  if (!result) {
    return <div className="empty-row">暂无分析结果</div>;
  }

  const parsed = tryParseResult(result.result_json);
  const isObject = typeof parsed === "object" && parsed !== null;
  const type =
    isObject && "type" in parsed && typeof parsed.type === "string" ? parsed.type : "";

  if (type === "stats") {
    const statsResult = parsed as StatsResult;
    return (
      <div className="result-view">
        <div className="result-title">
          <h4>{result.job_name}</h4>
          <span className="tag">{result.method}</span>
        </div>
        {renderTable(
          ["指标", "数量", "均值", "标准差", "最小值", "最大值", "CV%"],
          (statsResult.groups || []).map((row) => [
            row.unit ? `${row.metric_name || "-"} (${row.unit})` : row.metric_name || "-",
            formatNumber(row.count),
            formatNumber(row.mean),
            formatNumber(row.stddev),
            formatNumber(row.min),
            formatNumber(row.max),
            row.cv_percent == null ? "-" : formatNumber(row.cv_percent, 2),
          ]),
        )}
      </div>
    );
  }

  if (type === "qc") {
    const qcResult = parsed as QcResult;
    return (
      <div className="result-view">
        <div className="result-title">
          <h4>{result.job_name}</h4>
          <span className="tag">{result.method}</span>
        </div>
        <div className="result-grid">
          <div className="result-metric">
            <span>判定总数</span>
            <strong>{formatNumber(qcResult.count || 0)}</strong>
          </div>
          <div className="result-metric">
            <span>通过率</span>
            <strong>{formatNumber(qcResult.pass_rate || 0, 2)}%</strong>
          </div>
          <div className="result-metric">
            <span>异常数</span>
            <strong>{formatNumber(qcResult.failed || 0)}</strong>
          </div>
        </div>
        {Array.isArray(qcResult.failures)
          ? renderTable(
              ["样品", "指标", "数值", "状态", "时间"],
              qcResult.failures.map((row) => [
                row.sample_display_code || row.sample_code || "-",
                row.metric_name || "-",
                `${formatNumber(row.value)} ${row.unit || ""}`,
                row.status === "below" ? "低于下限" : "高于上限",
                formatDateTime(row.measured_at),
              ]),
            )
          : (
            <div className="empty-row">结果结构暂不支持完整展示</div>
          )}
      </div>
    );
  }

  if (type === "normalize") {
    const normalizeResult = parsed as NormalizeResult;
    return (
      <div className="result-view">
        <div className="result-title">
          <h4>{result.job_name}</h4>
          <span className="tag">{result.method}</span>
        </div>
        {renderTable(
          ["样品", "指标", "原始值", "归一化值", "时间"],
          (normalizeResult.points || []).slice(0, 80).map((row) => [
            row.sample_display_code || row.sample_code || "-",
            row.metric_name || "-",
            formatNumber(row.raw_value),
            formatNumber(row.normalized_value),
            formatDateTime(row.measured_at),
          ]),
        )}
      </div>
    );
  }

  return (
    <div className="result-view">
      <div className="result-title">
        <h4>{result.job_name}</h4>
        <span className="tag">{result.method}</span>
      </div>
      {type ? <div className="empty-row">结果结构暂不支持完整展示</div> : null}
      <pre>{typeof parsed === "string" ? parsed : JSON.stringify(parsed, null, 2)}</pre>
    </div>
  );
}
