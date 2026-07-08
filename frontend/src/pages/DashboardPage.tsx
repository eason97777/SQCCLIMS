import { useDashboardStore } from "../stores/dashboardStore";
import { getSampleDisplayCode } from "../utils/sampleFields";
import { formatDateTime } from "../utils/formatDate";

export function DashboardPage() {
  const { summary, loading, error, refreshDashboardSummary } = useDashboardStore();

  const statusCounts = summary?.status_counts || [];
  const recentData = summary?.recent_data || [];
  const totalSamples = Math.max(1, summary?.sample_count || 0);

  return (
    <section>
      <div className="kpi-grid">
        <article className="kpi-card">
          <span>样品总数</span>
          <strong>{summary?.sample_count ?? 0}</strong>
        </article>
        <article className="kpi-card">
          <span>数据记录</span>
          <strong>{summary?.data_count ?? 0}</strong>
        </article>
        <article className="kpi-card">
          <span>指标类型</span>
          <strong>{summary?.metric_count ?? 0}</strong>
        </article>
        <article className="kpi-card">
          <span>分析结果</span>
          <strong>{summary?.result_count ?? 0}</strong>
        </article>
      </div>

      {error ? (
        <section className="panel panel-section-spacing">
          <div className="empty-row">
            <div className="page-message">
              <strong>总览数据加载失败</strong>
              <span>{error}</span>
              <button type="button" onClick={() => void refreshDashboardSummary()}>
                重试
              </button>
            </div>
          </div>
        </section>
      ) : null}

      <div className="two-column dashboard-two-column">
        <section className="panel">
          <div className="panel-header">
            <h3>样品状态</h3>
          </div>
          {loading ? (
            <div className="empty-row">加载中...</div>
          ) : statusCounts.length ? (
            <div className="status-list">
              {statusCounts.map((item) => (
                <div key={item.status} className="status-item">
                  <span>{item.status}</span>
                  <div className="bar">
                    <span style={{ width: `${(item.count / totalSamples) * 100}%` }} />
                  </div>
                  <strong>{item.count}</strong>
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-row">暂无样品</div>
          )}
        </section>

        <section className="panel">
          <div className="panel-header">
            <h3>最近数据</h3>
          </div>
          <div className="table-wrap compact">
            <table>
              <thead>
                <tr>
                  <th>样品</th>
                  <th>指标</th>
                  <th>数值</th>
                  <th>时间</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td className="empty-row" colSpan={4}>
                      加载中...
                    </td>
                  </tr>
                ) : recentData.length ? (
                  recentData.map((row) => (
                    <tr key={row.id}>
                      <td>{getSampleDisplayCode(row)}</td>
                      <td>{row.metric_name}</td>
                      <td>
                        {row.numeric_value} {row.unit || ""}
                      </td>
                      <td>{formatDateTime(row.measured_at)}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td className="empty-row" colSpan={4}>
                      暂无数据
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      <section className="panel history-panel">
        <div className="panel-header">
          <h3>最近分析结果</h3>
        </div>
        {loading ? (
          <div className="empty-row">加载中...</div>
        ) : summary?.latest_result ? (
          <div className="history-list">
            <div className="history-item">
              <span>
                <strong>{summary.latest_result.job_name}</strong>
                <span>{summary.latest_result.method}</span>
              </span>
              <span>{formatDateTime(summary.latest_result.created_at)}</span>
              <span className="tag">{summary.latest_result.method}</span>
            </div>
          </div>
        ) : (
          <div className="empty-row">暂无分析结果</div>
        )}
      </section>
    </section>
  );
}
