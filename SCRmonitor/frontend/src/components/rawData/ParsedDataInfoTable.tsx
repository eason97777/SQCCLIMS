import { useMemo, useState } from "react";
import type { ParsedDataRecord } from "../../types/rawData";

type ParsedDataInfoTableProps = {
  parsedData: ParsedDataRecord[];
  selectedParsedData: ParsedDataRecord | null;
  onSelect: (parsedData: ParsedDataRecord) => void;
};

type ParsedInfoRow = {
  data: ParsedDataRecord;
  fileName: string;
  recordCount: string;
  status: string;
  version: string;
};

const INFO_PAGE_SIZE = 10;
const INFO_COLUMN_SIZE = 5;

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

function getParsedInfoRow(item: ParsedDataRecord): ParsedInfoRow {
  const summary = parseJsonObject(item.summary_json);
  const sourceFile = asRecord(summary.source_file);
  const diagnostics = asRecord(summary.diagnostics);
  const overall = item.data_type === "cd_sem" ? asRecord(summary.overall) : summary;

  return {
    data: item,
    fileName: valueOrDash(sourceFile.original_filename),
    recordCount: valueOrDash(diagnostics.valid_record_count ?? overall.count),
    status: valueOrDash(item.parsed_status),
    version: valueOrDash(item.parser_version),
  };
}

function StatusBadge({ status }: { status: string }) {
  const normalizedStatus = status.toLowerCase();
  const className = normalizedStatus === "success" || normalizedStatus === "parsed"
    ? "raw-parsed-status-badge success"
    : "raw-parsed-status-badge";

  return <span className={className}>{status}</span>;
}

export function ParsedDataInfoTable({
  parsedData,
  selectedParsedData,
  onSelect,
}: ParsedDataInfoTableProps) {
  const [page, setPage] = useState(1);
  const totalPages = Math.max(1, Math.ceil(parsedData.length / INFO_PAGE_SIZE));
  const currentPage = Math.min(Math.max(page, 1), totalPages);
  const pageStart = (currentPage - 1) * INFO_PAGE_SIZE;
  const rows = useMemo(
    () => parsedData.map((item) => getParsedInfoRow(item)),
    [parsedData],
  );
  const pageRows = rows.slice(pageStart, pageStart + INFO_PAGE_SIZE);
  const leftRows = pageRows.slice(0, INFO_COLUMN_SIZE);
  const rightRows = pageRows.slice(INFO_COLUMN_SIZE, INFO_PAGE_SIZE);
  const selectedId = selectedParsedData?.id ?? null;
  const leftCount = leftRows.length;
  const rightCount = rightRows.length;

  function updatePage(nextPage: number) {
    setPage(Math.min(Math.max(nextPage, 1), totalPages));
  }

  function renderInfoCells(row: ParsedInfoRow | undefined) {
    if (!row) {
      return (
        <>
          <td aria-hidden="true" />
          <td aria-hidden="true" />
          <td aria-hidden="true" />
          <td aria-hidden="true" />
        </>
      );
    }

    const selected = row.data.id === selectedId;
    const cellClassName = `raw-parsed-info-clickable-cell ${selected ? "selected" : ""}`;

    return (
      <>
        <td className={cellClassName} onClick={() => onSelect(row.data)}>
          <button
            className={`raw-parsed-info-row-button ${selected ? "selected" : ""}`}
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              onSelect(row.data);
            }}
            title={row.fileName}
          >
            {row.fileName}
          </button>
        </td>
        <td className={`numeric-cell ${cellClassName}`} onClick={() => onSelect(row.data)}>
          {row.recordCount}
        </td>
        <td className={cellClassName} onClick={() => onSelect(row.data)}>
          <StatusBadge status={row.status} />
        </td>
        <td className={cellClassName} onClick={() => onSelect(row.data)}>
          {row.version}
        </td>
      </>
    );
  }

  return (
    <section className="raw-parsed-section raw-parsed-info-section">
      <h5>解析信息</h5>
      {parsedData.length === 0 ? (
        <div className="empty-row">暂无标准化结果</div>
      ) : (
        <>
          <div className="raw-parsed-info-table-wrap">
            <table className="raw-parsed-info-table">
              <colgroup>
                <col className="raw-parsed-info-file-col" />
                <col className="raw-parsed-info-compact-col" />
                <col className="raw-parsed-info-compact-col" />
                <col className="raw-parsed-info-compact-col" />
                <col className="raw-parsed-info-file-col" />
                <col className="raw-parsed-info-compact-col" />
                <col className="raw-parsed-info-compact-col" />
                <col className="raw-parsed-info-compact-col" />
              </colgroup>
              <thead>
                <tr>
                  <th>文件名称</th>
                  <th>数据数量</th>
                  <th>解析状态</th>
                  <th>版本号</th>
                  <th className="raw-parsed-info-split">文件名称</th>
                  <th>数据数量</th>
                  <th>解析状态</th>
                  <th>版本号</th>
                </tr>
              </thead>
              <tbody>
                {Array.from({ length: INFO_COLUMN_SIZE }, (_, index) => (
                  <tr key={index}>
                    {renderInfoCells(leftRows[index])}
                    {renderInfoCells(rightRows[index])}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="raw-parsed-section-footer">
            <span>共 {parsedData.length} 条（左侧 {leftCount} 条，右侧 {rightCount} 条）</span>
            <div className="raw-parsed-pagination">
              <button type="button" onClick={() => updatePage(currentPage - 1)} disabled={currentPage <= 1}>
                上一页
              </button>
              <span>{currentPage} / {totalPages}</span>
              <button type="button" onClick={() => updatePage(currentPage + 1)} disabled={currentPage >= totalPages}>
                下一页
              </button>
            </div>
          </div>
        </>
      )}
    </section>
  );
}
