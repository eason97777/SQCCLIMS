import type { ProcessingResultRecord } from "../../types/processing";
import { formatDateTime } from "../../utils/formatDate";
import { getSampleDisplayCode } from "../../utils/sampleFields";

type ProcessingHistoryTableProps = {
  results: ProcessingResultRecord[];
  onSelect: (result: ProcessingResultRecord) => void;
};

export function ProcessingHistoryTable({
  results,
  onSelect,
}: ProcessingHistoryTableProps) {
  if (!results.length) {
    return <div className="empty-row">暂无分析历史</div>;
  }

  return (
    <div className="history-list">
      {results.map((item) => (
        <button
          key={item.id}
          className="history-item ghost-button"
          type="button"
          onClick={() => onSelect(item)}
        >
          <span>
            <strong>{item.job_name}</strong>
            <span>
              {item.sample_id
                ? getSampleDisplayCode({
                    sample_uid: item.sample_uid ?? undefined,
                    sample_display_code: item.sample_display_code ?? undefined,
                    sample_code: item.sample_code ?? "",
                    name: item.sample_name ?? "",
                  })
                : "全部样品"}{" "}
              / {item.method}
            </span>
          </span>
          <span>{formatDateTime(item.created_at)}</span>
          <span className="tag">{item.method}</span>
        </button>
      ))}
    </div>
  );
}
