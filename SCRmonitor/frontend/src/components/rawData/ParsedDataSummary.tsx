import type { ParsedDataRecord } from "../../types/rawData";

type ParsedDataSummaryProps = {
  parsedData: ParsedDataRecord | null;
};

function parseJsonObject(value: string): Record<string, unknown> {
  try {
    const parsed = JSON.parse(value || "{}");
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
  } catch {
    return {};
  }
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function valueOrDash(value: unknown) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }

  return String(value);
}

export function ParsedDataSummary({ parsedData }: ParsedDataSummaryProps) {
  if (!parsedData) {
    return <div className="empty-row">请选择一条标准化结果</div>;
  }

  const summary = parseJsonObject(parsedData.summary_json);
  const sourceFile = asRecord(summary.source_file);
  const diagnostics = asRecord(summary.diagnostics);
  const uniqueDoses = Array.isArray(diagnostics.unique_doses)
    ? diagnostics.unique_doses.map((item) => String(item)).join(", ")
    : "";

  return (
    <>
      {parsedData.data_type === "cd_sem" ? (
        <div className="raw-summary-diagnostics">
          <div>
            <span>解析来源文件</span>
            <strong>{valueOrDash(sourceFile.original_filename)}</strong>
          </div>
          <div>
            <span>有效记录数</span>
            <strong>{valueOrDash(diagnostics.valid_record_count)}</strong>
          </div>
          <div>
            <span>CSV 数据行数</span>
            <strong>{valueOrDash(diagnostics.csv_total_rows)}</strong>
          </div>
          <div>
            <span>dose 集合</span>
            <strong title={uniqueDoses}>{valueOrDash(uniqueDoses)}</strong>
          </div>
        </div>
      ) : null}
    </>
  );
}
