import { useMemo, useState } from "react";
import type { Sample } from "../../types/sample";
import {
  getSampleDisplayCode,
  getSampleOwner,
  getSampleUid,
  valueOrDash,
} from "../../utils/sampleFields";
import { SampleStatusBadge } from "./SampleStatusBadge";
import { SelectCombobox } from "./SelectCombobox";

type SampleTableProps = {
  samples: Sample[];
  loading?: boolean;
  readonly?: boolean;
  selectedSampleId?: number | null;
  onSelect?: (sample: Sample) => void;
  onEdit?: (sample: Sample) => void;
  onDelete?: (sample: Sample) => void;
};

export function SampleTable({
  samples,
  loading = false,
  readonly = false,
  selectedSampleId,
  onSelect,
  onEdit,
  onDelete,
}: SampleTableProps) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [uidQuery, setUidQuery] = useState("");
  const [displayQuery, setDisplayQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [dateFilter, setDateFilter] = useState("");
  const columnCount = readonly ? 4 : 5;
  const filteredSamples = useMemo(() => {
    return samples.filter((sample) => {
      const uid = getSampleUid(sample).toLowerCase();
      const displayCode = getSampleDisplayCode(sample).toLowerCase();
      const createdDate = sample.created_at ? sample.created_at.slice(0, 10) : "";
      return (
        (!uidQuery || uid.includes(uidQuery.trim().toLowerCase())) &&
        (!displayQuery || displayCode.includes(displayQuery.trim().toLowerCase())) &&
        (!statusFilter || sample.status === statusFilter) &&
        (!dateFilter || createdDate === dateFilter)
      );
    });
  }, [dateFilter, displayQuery, samples, statusFilter, uidQuery]);
  const pageCount = Math.max(1, Math.ceil(filteredSamples.length / pageSize));
  const currentPage = Math.min(page, pageCount);
  const statusOptions = useMemo(
    () => Array.from(new Set(samples.map((sample) => sample.status).filter(Boolean))),
    [samples],
  );

  const pageSamples = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filteredSamples.slice(start, start + pageSize);
  }, [currentPage, filteredSamples, pageSize]);

  function goToPage(nextPage: number) {
    setPage(Math.min(Math.max(nextPage, 1), pageCount));
  }

  function resetFilters() {
    setUidQuery("");
    setDisplayQuery("");
    setStatusFilter("");
    setDateFilter("");
    setPage(1);
  }

  return (
    <div className="sample-table-shell">
      {!readonly ? (
        <div className="sample-table-filters">
          <input
            value={uidQuery}
            placeholder="按样品 UID 搜索"
            onChange={(event) => {
              setUidQuery(event.target.value);
              setPage(1);
            }}
          />
          <input
            value={displayQuery}
            placeholder="按样品显示编号搜索"
            onChange={(event) => {
              setDisplayQuery(event.target.value);
              setPage(1);
            }}
          />
          <SelectCombobox
            value={statusFilter}
            placeholder="全部状态"
            options={[
              { label: "全部状态", value: "" },
              ...statusOptions.map((status) => ({ label: status, value: status })),
            ]}
            onChange={(value) => {
              setStatusFilter(value);
              setPage(1);
            }}
          />
          <input
            value={dateFilter}
            type="date"
            onChange={(event) => {
              setDateFilter(event.target.value);
              setPage(1);
            }}
          />
          <button className="ghost-button sample-refresh-button" type="button" onClick={resetFilters}>
            刷新
          </button>
        </div>
      ) : null}
      <div className="table-wrap sample-table-wrap">
        <table
          className={`sample-table ${
            readonly ? "readonly-sample-table" : "editable-sample-table"
          }`}
        >
          <thead>
            <tr>
              <th>样品 UID</th>
              <th>样品显示编号</th>
              <th>负责人</th>
              <th>状态</th>
              {!readonly ? <th>操作</th> : null}
            </tr>
          </thead>
          <tbody>
            {!loading && filteredSamples.length === 0 ? (
              <tr>
                <td className="empty-row" colSpan={columnCount}>
                  暂无样品
                </td>
              </tr>
            ) : null}

            {pageSamples.map((sample) => {
              const isSelected = selectedSampleId === sample.id;

              return (
                <tr
                  className={isSelected ? "selected-row" : ""}
                  key={sample.id}
                  onClick={() => onSelect?.(sample)}
                >
                  <td>{valueOrDash(getSampleUid(sample))}</td>
                  <td>
                    <strong>{valueOrDash(getSampleDisplayCode(sample))}</strong>
                  </td>
                  <td>{valueOrDash(getSampleOwner(sample))}</td>
                  <td>
                    <SampleStatusBadge status={sample.status} />
                  </td>
                  {!readonly ? (
                    <td>
                      <div className="row-actions">
                        <button
                          className="ghost-button"
                          type="button"
                          onClick={(event) => {
                            event.stopPropagation();
                            onEdit?.(sample);
                          }}
                        >
                          编辑
                        </button>
                        <button
                          className="danger-button"
                          type="button"
                          onClick={(event) => {
                            event.stopPropagation();
                            onDelete?.(sample);
                          }}
                        >
                          删除
                        </button>
                      </div>
                    </td>
                  ) : null}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="table-pagination sample-table-pagination">
        <span>共 {filteredSamples.length} 条</span>
        <div className="row-actions">
          <button
            className="ghost-button"
            type="button"
            disabled={currentPage <= 1}
            onClick={() => goToPage(currentPage - 1)}
          >
            ‹
          </button>
          <button className="ghost-button active-page-button" type="button">
            {currentPage}
          </button>
          <button
            className="ghost-button"
            type="button"
            disabled={currentPage >= pageCount}
            onClick={() => goToPage(currentPage + 1)}
          >
            ›
          </button>
          <SelectCombobox
            value={String(pageSize)}
            options={[5, 10, 20, 50].map((size) => ({ label: `${size} 条/页`, value: String(size) }))}
            onChange={(value) => {
              setPageSize(Number(value));
              setPage(1);
            }}
          />
        </div>
      </div>
    </div>
  );
}
