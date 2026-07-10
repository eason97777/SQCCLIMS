import { useMemo, useState } from "react";
import type { RawDataRecord } from "../../types/rawData";
import { ARTIFACT_TYPE_OPTIONS } from "../../utils/constants";
import { formatDateTime } from "../../utils/formatDate";

const PAGE_SIZE = 10;
const TABLE_FILLER_ROWS = Array.from({ length: PAGE_SIZE });

type RawDataTableProps = {
  rawData: RawDataRecord[];
  loading?: boolean;
  selectedRawDataId?: number | null;
  selectedSource?: string | null;
  onSelect: (record: RawDataRecord) => void;
  onDelete: (record: RawDataRecord) => void;
};

function valueOrDash(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }

  return String(value);
}

function typeLabel(value: string) {
  return ARTIFACT_TYPE_OPTIONS.find((option) => option.value === value)?.label || value;
}

function parserStatusClass(status: string) {
  if (status === "parsed") return "tag good";
  if (status === "parsing") return "tag done";
  if (status === "parse_failed") return "tag warn";
  return "tag";
}

function parserStatusLabel(status: string) {
  if (status === "parsed") return "已解析";
  if (status === "parse_failed") return "解析失败";
  if (status === "parsing") return "解析中";
  if (status === "not_parsed") return "未解析";
  return valueOrDash(status);
}

export function RawDataTable({
  rawData,
  loading = false,
  selectedRawDataId = null,
  selectedSource = null,
  onSelect,
  onDelete,
}: RawDataTableProps) {
  const [page, setPage] = useState(1);
  const pageCount = Math.max(1, Math.ceil(rawData.length / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);

  const pageRawData = useMemo(() => {
    const start = (currentPage - 1) * PAGE_SIZE;
    return rawData.slice(start, start + PAGE_SIZE);
  }, [currentPage, rawData]);

  const fillerRows = Math.max(0, PAGE_SIZE - pageRawData.length);

  function goToPage(nextPage: number) {
    setPage(Math.min(Math.max(nextPage, 1), pageCount));
  }

  return (
    <div className="raw-data-table-shell">
      <div className="table-wrap raw-data-list-table-wrap">
        <table className="raw-data-table raw-data-list-table">
          <thead>
            <tr>
              <th>样品</th>
              <th>类型</th>
              <th>解析状态</th>
              <th>创建时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {!loading && rawData.length === 0 ? (
              <tr className="raw-data-empty-table-row">
                <td className="empty-row" colSpan={5}>
                  暂无 Raw Data
                </td>
              </tr>
            ) : null}

            {pageRawData.map((record) => (
              <tr
                className={
                  selectedRawDataId === record.id &&
                  (selectedSource ?? "raw_data") === (record.source ?? "raw_data")
                    ? "raw-data-selected-row"
                    : undefined
                }
                key={`${record.source ?? "raw_data"}:${record.id}`}
              >
                <td title={record.sample_display_code}>
                  <strong>{valueOrDash(record.sample_display_code)}</strong>
                </td>
                <td title={typeLabel(record.data_type)}>{typeLabel(record.data_type)}</td>
                <td>
                  <span className={parserStatusClass(record.parser_status)}>
                    {parserStatusLabel(record.parser_status)}
                  </span>
                </td>
                <td>{formatDateTime(record.created_at)}</td>
                <td>
                  <div className="row-actions raw-data-row-actions">
                    <button className="ghost-button" type="button" onClick={() => onSelect(record)}>
                      详情
                    </button>
                    {(record.source ?? "raw_data") !== "performance" ? (
                      <button
                        className="danger-button"
                        type="button"
                        onClick={() => onDelete(record)}
                      >
                        删除
                      </button>
                    ) : null}
                  </div>
                </td>
              </tr>
            ))}

            {rawData.length > 0
              ? TABLE_FILLER_ROWS.slice(0, fillerRows).map((_, index) => (
                  <tr className="raw-data-filler-row" key={`filler-${index}`}>
                    <td colSpan={5}>&nbsp;</td>
                  </tr>
                ))
              : null}
          </tbody>
        </table>
      </div>

      <div className="table-pagination raw-data-list-pagination">
        <span>共 {rawData.length} 条</span>
        {rawData.length > PAGE_SIZE ? (
          <div className="row-actions">
            <button
              className="ghost-button"
              type="button"
              disabled={currentPage <= 1}
              onClick={() => goToPage(currentPage - 1)}
            >
              上一页
            </button>
            <span className="hint-text">
              第 {currentPage} / {pageCount} 页
            </span>
            <button
              className="ghost-button"
              type="button"
              disabled={currentPage >= pageCount}
              onClick={() => goToPage(currentPage + 1)}
            >
              下一页
            </button>
          </div>
        ) : null}
      </div>
    </div>
  );
}
