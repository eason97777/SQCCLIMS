import type { ParsedDataRecord } from "../../types/rawData";
import { formatDateTime } from "../../utils/formatDate";

type ParsedDataListProps = {
  parsedData: ParsedDataRecord[];
  selectedParsedDataId?: number | null;
  onSelect: (parsedData: ParsedDataRecord) => void;
};

export function ParsedDataList({
  parsedData,
  selectedParsedDataId,
  onSelect,
}: ParsedDataListProps) {
  if (parsedData.length === 0) {
    return <div className="empty-row">暂无标准化结果，请先运行解析</div>;
  }

  return (
    <div className="raw-parsed-list">
      {parsedData.map((item) => (
        <button
          className={`raw-parsed-item ${selectedParsedDataId === item.id ? "active" : ""}`}
          key={item.id}
          type="button"
          onClick={() => onSelect(item)}
        >
          <strong>{item.parser_name || "-"}</strong>
          <span>{item.parser_version || "-"}</span>
          <span>{item.parsed_status || "-"}</span>
          <small>{formatDateTime(item.created_at)}</small>
        </button>
      ))}
    </div>
  );
}
