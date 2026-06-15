import type { PerformanceDataset } from "../../types/performance";
import { formatDateTime } from "../../utils/formatDate";
import { getSampleDisplayCode } from "../../utils/sampleFields";

type DatasetSummaryCardProps = {
  dataset: PerformanceDataset | null;
};

function formatBytes(value: number) {
  if (value < 1024) {
    return `${value} B`;
  }
  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1).replace(/\.0$/, "")} KB`;
  }
  if (value < 1024 * 1024 * 1024) {
    return `${(value / 1024 / 1024).toFixed(1).replace(/\.0$/, "")} MB`;
  }
  return `${(value / 1024 / 1024 / 1024).toFixed(1).replace(/\.0$/, "")} GB`;
}

export function DatasetSummaryCard({ dataset }: DatasetSummaryCardProps) {
  if (!dataset) {
    return <div className="empty-row">选择一个数据集以查看概览</div>;
  }

  return (
    <div className="status-list">
      <div className="status-item">
        <span>样品</span>
        <strong>{getSampleDisplayCode(dataset)}</strong>
      </div>
      <div className="status-item">
        <span>取样编号</span>
        <strong>{dataset.aliquot_code || "-"}</strong>
      </div>
      <div className="status-item">
        <span>数据集</span>
        <strong>{dataset.dataset_name}</strong>
      </div>
      <div className="status-item">
        <span>状态</span>
        <strong>{dataset.status || "-"}</strong>
      </div>
      <div className="status-item">
        <span>总大小</span>
        <strong>{formatBytes(dataset.total_bytes || 0)}</strong>
      </div>
      <div className="status-item">
        <span>导入时间</span>
        <strong>{formatDateTime(dataset.created_at)}</strong>
      </div>
    </div>
  );
}
