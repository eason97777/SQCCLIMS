import { useMemo, useState } from "react";
import type { ProcessingJobRecord } from "../../types/rawData";
import { formatDateTime } from "../../utils/formatDate";

type ProcessingJobsTableProps = {
  jobs: ProcessingJobRecord[];
};

const PAGE_SIZE = 5;

function valueOrDash(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }

  return String(value);
}

function parseOutputLinks(value: string) {
  try {
    const parsed = JSON.parse(value || "{}") as {
      chart_url?: string;
      report_url?: string;
      report_json_url?: string;
      outputs?: Record<string, string>;
    };
    return parsed;
  } catch {
    return {};
  }
}

function outputLinkEntries(outputJson: string) {
  const links = parseOutputLinks(outputJson);
  const entries: Array<{ label: string; url: string }> = [];
  if (links.chart_url) {
    entries.push({ label: "chart", url: links.chart_url });
  }
  if (links.report_url) {
    entries.push({ label: "report", url: links.report_url });
  }
  if (links.report_json_url) {
    entries.push({ label: "json", url: links.report_json_url });
  }
  if (links.outputs && typeof links.outputs === "object") {
    for (const [label, url] of Object.entries(links.outputs)) {
      if (typeof url === "string" && url) {
        entries.push({ label, url });
      }
    }
  }
  return entries;
}

export function ProcessingJobsTable({ jobs }: ProcessingJobsTableProps) {
  const jobsSignature = useMemo(() => jobs.map((job) => job.id).join("|"), [jobs]);
  const [pageState, setPageState] = useState({ page: 1, signature: "" });
  const totalPages = Math.max(1, Math.ceil(jobs.length / PAGE_SIZE));
  const currentPage = pageState.signature === jobsSignature ? pageState.page : 1;
  const safePage = Math.min(currentPage, totalPages);
  const rangeStart = jobs.length === 0 ? 0 : (safePage - 1) * PAGE_SIZE + 1;
  const rangeEnd = Math.min(jobs.length, safePage * PAGE_SIZE);
  const pagedJobs = useMemo(
    () => jobs.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE),
    [jobs, safePage],
  );

  if (jobs.length === 0) {
    return <div className="empty-row">暂无处理历史</div>;
  }

  return (
    <div className="processing-jobs-panel">
      <div className="table-wrap">
        <table className="raw-jobs-table">
          <thead>
            <tr>
              <th>job_type</th>
              <th>script_name</th>
              <th>script_version</th>
              <th>status</th>
              <th>started_at</th>
              <th>finished_at</th>
              <th>error_message</th>
              <th>output</th>
            </tr>
          </thead>
          <tbody>
            {pagedJobs.map((job) => (
              <tr key={job.id}>
                <td>{valueOrDash(job.job_type)}</td>
                <td>{valueOrDash(job.script_name)}</td>
                <td>{valueOrDash(job.script_version)}</td>
                <td>
                  <span className="tag">{valueOrDash(job.status)}</span>
                </td>
                <td>{formatDateTime(job.started_at)}</td>
                <td>{formatDateTime(job.finished_at)}</td>
                <td title={job.error_message}>{valueOrDash(job.error_message)}</td>
                <td>
                  {(() => {
                    const links = outputLinkEntries(job.output_json);
                    return links.length > 0 ? (
                      <div className="job-output-links">
                        {links.map((link) => (
                          <a href={link.url} key={`${job.id}-${link.label}`} target="_blank" rel="noreferrer">
                            {link.label}
                          </a>
                        ))}
                      </div>
                    ) : "-";
                  })()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {jobs.length > PAGE_SIZE ? (
        <div className="processing-jobs-pagination">
          <span>当前显示第 {rangeStart}-{rangeEnd} 条 / 共 {jobs.length} 条</span>
          <div className="processing-jobs-pagination-controls">
            <button
              type="button"
              disabled={safePage <= 1}
              onClick={() =>
                setPageState({
                  page: Math.max(1, safePage - 1),
                  signature: jobsSignature,
                })
              }
            >
              上一页
            </button>
            <span>第 {safePage} / {totalPages} 页</span>
            <button
              type="button"
              disabled={safePage >= totalPages}
              onClick={() =>
                setPageState({
                  page: Math.min(totalPages, safePage + 1),
                  signature: jobsSignature,
                })
              }
            >
              下一页
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
