import type { TestDataRecord } from "../../types/testData";
import { formatDateTime } from "../../utils/formatDate";
import { getSampleDisplayCode } from "../../utils/sampleFields";

type TestDataTableProps = {
  testData: TestDataRecord[];
  loading?: boolean;
  onDelete: (record: TestDataRecord) => void;
};

function valueOrDash(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }

  return String(value);
}

export function TestDataTable({
  testData,
  loading = false,
  onDelete,
}: TestDataTableProps) {
  return (
    <div className="table-wrap">
      <table className="test-data-table">
        <thead>
          <tr>
            <th>样品编号</th>
            <th>测试项目</th>
            <th>指标名称</th>
            <th>数值</th>
            <th>测试时间</th>
            <th>操作人员</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {!loading && testData.length === 0 ? (
            <tr>
              <td className="empty-row" colSpan={7}>
                暂无测试数据
              </td>
            </tr>
          ) : null}

          {testData.map((row) => (
            <tr key={row.id}>
              <td>
                <strong>{valueOrDash(getSampleDisplayCode(row))}</strong>
              </td>
              <td>{valueOrDash(row.test_name)}</td>
              <td>{valueOrDash(row.metric_name)}</td>
              <td>
                {valueOrDash(row.numeric_value)}
                {row.unit ? ` ${row.unit}` : ""}
              </td>
              <td>{formatDateTime(row.measured_at) || "-"}</td>
              <td>{valueOrDash(row.operator)}</td>
              <td>
                <div className="row-actions">
                  <button
                    className="danger-button"
                    type="button"
                    onClick={() => onDelete(row)}
                  >
                    删除
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
