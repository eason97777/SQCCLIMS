import { useEffect, useMemo, useState } from "react";
import {
  deletePerformanceDataset,
  getPerformanceDatasetDeletePreview,
  getPerformanceDatasetFiles,
} from "../../api/performanceApi";
import type { PerformanceDatasetFile } from "../../types/performance";
import type { RawDataRecord } from "../../types/rawData";
import { formatDateTime } from "../../utils/formatDate";
import { formatFileSize } from "../../utils/fileSize";
import {
  DeleteConfirmDialog,
  type DeletePreviewLine,
} from "../common/DeleteConfirmDialog";
import { DatasetFileTree } from "../performance/DatasetFileTree";

// Spec 004 Phase 2b: a performance-origin artifact selected from the unified
// Raw Data / Artifacts list. Its detail + delete live on the performance
// endpoints (keyed by `source_row_id`), rendered in-place here so the operator
// never leaves the unified list.
type PerformanceArtifactDetailProps = {
  record: RawDataRecord;
  onDeleted: () => void;
};

function valueOrDash(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  return String(value);
}

function parseMetadata(value: string): Record<string, string> {
  try {
    const parsed = JSON.parse(value || "{}");
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as Record<string, string>;
    }
  } catch {
    // ignore malformed metadata
  }
  return {};
}

export function PerformanceArtifactDetail({ record, onDeleted }: PerformanceArtifactDetailProps) {
  const datasetId = record.source_row_id ?? record.id;
  const [files, setFiles] = useState<PerformanceDatasetFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [pendingDelete, setPendingDelete] = useState(false);
  const [preview, setPreview] = useState<{ dataset_name: string; files: number } | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState("");
  const [deleting, setDeleting] = useState(false);

  const meta = useMemo(() => parseMetadata(record.metadata_json), [record.metadata_json]);

  // loading/error start fresh from initial state on each mount; RawDataPage keys
  // this component by dataset id, so selecting a different artifact remounts it
  // (no setState-in-effect needed to reset the spinner).
  useEffect(() => {
    let active = true;
    getPerformanceDatasetFiles(datasetId)
      .then((result) => {
        if (active) {
          setFiles(result);
        }
      })
      .catch((err) => {
        if (active) {
          setError(err instanceof Error ? err.message : "加载数据集文件结构失败");
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [datasetId]);

  function requestDelete() {
    setPendingDelete(true);
    setPreview(null);
    setPreviewError("");
    setPreviewLoading(true);
    getPerformanceDatasetDeletePreview(datasetId)
      .then((result) => setPreview(result))
      .catch((err) =>
        setPreviewError(err instanceof Error ? err.message : "获取删除影响范围失败"),
      )
      .finally(() => setPreviewLoading(false));
  }

  function cancelDelete() {
    setPendingDelete(false);
    setPreview(null);
    setPreviewError("");
    setPreviewLoading(false);
  }

  async function confirmDelete() {
    setDeleting(true);
    try {
      await deletePerformanceDataset(datasetId);
      cancelDelete();
      onDeleted();
    } catch (err) {
      setPreviewError(err instanceof Error ? err.message : "删除性能数据集失败");
    } finally {
      setDeleting(false);
    }
  }

  const previewLines = useMemo<DeletePreviewLine[]>(() => {
    if (!preview) {
      return [];
    }
    return [{ label: "个数据集文件", count: preview.files }].filter((line) => line.count > 0);
  }, [preview]);

  return (
    <div className="raw-detail-sections">
      <div className="panel-header">
        <h3>{valueOrDash(record.raw_data_name)}（性能数据集）</h3>
        <button className="danger-button" type="button" onClick={requestDelete}>
          删除
        </button>
      </div>

      {error ? <div className="empty-row">{error}</div> : null}

      <section className="raw-detail-section">
        <h4>数据集概览</h4>
        <dl>
          <div>
            <dt>编号</dt>
            <dd title={record.raw_data_code}>{valueOrDash(record.raw_data_code)}</dd>
          </div>
          <div>
            <dt>样品</dt>
            <dd>{valueOrDash(record.sample_display_code)}</dd>
          </div>
          <div>
            <dt>取样编号</dt>
            <dd>{valueOrDash(meta.aliquot_code)}</dd>
          </div>
          <div>
            <dt>测试类型</dt>
            <dd>{valueOrDash(meta.test_type)}</dd>
          </div>
          <div>
            <dt>数据格式</dt>
            <dd>{valueOrDash(meta.data_format)}</dd>
          </div>
          <div>
            <dt>来源文件夹</dt>
            <dd>{valueOrDash(meta.source_folder_name)}</dd>
          </div>
          <div>
            <dt>操作人员</dt>
            <dd>{valueOrDash(record.operator)}</dd>
          </div>
          <div>
            <dt>采集时间</dt>
            <dd>{valueOrDash(record.measured_at)}</dd>
          </div>
          <div>
            <dt>文件数量</dt>
            <dd>
              {record.file_count} 个 / {formatFileSize(record.total_size)}
            </dd>
          </div>
          <div>
            <dt>状态</dt>
            <dd>{valueOrDash(record.status)}</dd>
          </div>
          <div>
            <dt>创建时间</dt>
            <dd>{formatDateTime(record.created_at)}</dd>
          </div>
          <div>
            <dt>备注</dt>
            <dd>{valueOrDash(record.notes)}</dd>
          </div>
        </dl>
      </section>

      <section className="raw-detail-section">
        <h4>文件结构</h4>
        {loading ? (
          <div className="empty-row">加载中...</div>
        ) : (
          <div className="table-wrap">
            <DatasetFileTree files={files} />
          </div>
        )}
      </section>

      <DeleteConfirmDialog
        open={pendingDelete}
        title="删除性能数据集"
        message={`确认删除性能数据集 ${record.raw_data_name}？此操作不可撤销。`}
        previewLines={previewLines}
        loading={previewLoading}
        error={previewError}
        deleting={deleting}
        onConfirm={() => void confirmDelete()}
        onCancel={cancelDelete}
      />
    </div>
  );
}
