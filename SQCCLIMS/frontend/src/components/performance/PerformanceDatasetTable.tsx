import type { PerformanceDataset } from "../../types/performance";
import { formatDateTime } from "../../utils/formatDate";
import { getSampleDisplayCode } from "../../utils/sampleFields";

type PerformanceDatasetTableProps = {
  datasets: PerformanceDataset[];
  onViewFiles: (dataset: PerformanceDataset) => void;
  onDelete: (dataset: PerformanceDataset) => void;
};

export function PerformanceDatasetTable({
  datasets,
  onViewFiles,
  onDelete,
}: PerformanceDatasetTableProps) {
  return (
    <div className="table-wrap compact">
      <table>
        <thead>
          <tr>
            <th>母样品</th>
            <th>取样编号</th>
            <th>数据集名称</th>
            <th>文件数量</th>
            <th>状态</th>
            <th>导入时间</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {datasets.length === 0 ? (
            <tr>
              <td className="empty-row" colSpan={7}>
                暂无性能数据集
              </td>
            </tr>
          ) : (
            datasets.map((dataset) => (
              <tr key={dataset.id}>
                <td>
                  <strong>{getSampleDisplayCode(dataset)}</strong>
                </td>
                <td>{dataset.aliquot_code || "-"}</td>
                <td>{dataset.dataset_name}</td>
                <td>{dataset.file_count || 0}</td>
                <td>{dataset.status || "-"}</td>
                <td>{formatDateTime(dataset.created_at)}</td>
                <td>
                  <div className="row-actions">
                    <button
                      className="ghost-button"
                      type="button"
                      onClick={() => onViewFiles(dataset)}
                    >
                      查看文件
                    </button>
                    <button
                      className="danger-button"
                      type="button"
                      onClick={() => onDelete(dataset)}
                    >
                      删除
                    </button>
                  </div>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
