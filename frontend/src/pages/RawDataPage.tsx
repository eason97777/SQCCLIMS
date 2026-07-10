import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  getParsedData,
  getProcessingJobs,
  getRawDataDeletePreview,
  getRawDataFileDeletePreview,
} from "../api/rawDataApi";
import { getSamples } from "../api/samplesApi";
import { RawDataDetailPanel } from "../components/rawData/RawDataDetailPanel";
import { PerformanceArtifactDetail } from "../components/rawData/PerformanceArtifactDetail";
import { DatasetImportPanel } from "../components/performance/DatasetImportPanel";
import { uploadPerformanceDataset } from "../api/performanceApi";
import type { PerformanceDatasetFields } from "../types/performance";
import { RawDataFilter } from "../components/rawData/RawDataFilter";
import { RawDataForm } from "../components/rawData/RawDataForm";
import { RawDataTable } from "../components/rawData/RawDataTable";
import {
  DeleteConfirmDialog,
  type DeletePreviewLine,
} from "../components/common/DeleteConfirmDialog";
import { useRawDataStore } from "../stores/rawDataStore";
import type { Sample } from "../types/sample";
import type {
  ParsedDataRecord,
  ProcessingJobRecord,
  RawDataDeletePreview,
  RawDataFile,
  RawDataFileDeletePreview,
  RawDataPayload,
  RawDataRecord,
  VisualizationPayload,
} from "../types/rawData";
import { RAW_DATA_TYPE_OPTIONS } from "../utils/constants";
import { formatDateTime } from "../utils/formatDate";
import { formatFileSize } from "../utils/fileSize";

type RawDataMainTab = "list" | "detail" | "create" | "perf-upload";

function valueOrDash(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }

  return String(value);
}

function dataTypeLabel(value: string) {
  return RAW_DATA_TYPE_OPTIONS.find((option) => option.value === value)?.label || value;
}

function parserStatusLabel(status: string) {
  if (status === "parsed") return "已解析";
  if (status === "parse_failed") return "解析失败";
  if (status === "parsing") return "解析中";
  if (status === "not_parsed") return "未解析";
  return valueOrDash(status);
}

function parserStatusClass(status: string) {
  if (status === "parsed") return "tag good";
  if (status === "parse_failed") return "tag warn";
  if (status === "parsing") return "tag done";
  return "tag";
}

function parseJsonObject(value: string): Record<string, unknown> {
  try {
    const parsed = JSON.parse(value || "{}");
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
  } catch {
    return {};
  }
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function latestSourceFile(parsedData: ParsedDataRecord | null) {
  if (!parsedData) {
    return "-";
  }

  const summary = parseJsonObject(parsedData.summary_json);
  const sourceFile = asRecord(summary.source_file);
  return valueOrDash(sourceFile.original_filename as string | undefined);
}

function validRecordCount(parsedData: ParsedDataRecord | null) {
  if (!parsedData) {
    return "-";
  }

  const summary = parseJsonObject(parsedData.summary_json);
  const diagnostics = asRecord(summary.diagnostics);
  const overall = asRecord(summary.overall);
  return valueOrDash(
    (diagnostics.valid_record_count as number | undefined)
      ?? (overall.count as number | undefined)
      ?? (summary.count as number | undefined),
  );
}

function RawDataSummarySide({
  rawData,
  parsedData,
  processingJobs,
}: {
  rawData: RawDataRecord | null;
  parsedData: ParsedDataRecord[];
  processingJobs: ProcessingJobRecord[];
}) {
  const selectedParsedData = parsedData[0] ?? null;

  if (!rawData) {
    return (
      <section className="panel raw-data-summary-side">
        <div className="panel-header">
          <h3>信息详情</h3>
        </div>
        <div className="raw-data-summary-empty">
          <span className="raw-data-summary-empty-icon">i</span>
          <strong>请选择一条 Raw Data 查看摘要</strong>
          <span>点击左侧列表中的“详情”，这里会展示关键识别与数据状态。</span>
        </div>
      </section>
    );
  }

  return (
    <section className="panel raw-data-summary-side">
      <div className="panel-header">
        <h3>信息详情</h3>
      </div>
      <div className="raw-data-summary-groups">
        <section className="raw-data-summary-group">
          <h4>基本识别</h4>
          <dl>
            <div>
              <dt>Raw Data 编号</dt>
              <dd title={rawData.raw_data_code}>{valueOrDash(rawData.raw_data_code)}</dd>
            </div>
            <div>
              <dt>样品</dt>
              <dd title={rawData.sample_display_code}>{valueOrDash(rawData.sample_display_code)}</dd>
            </div>
            <div>
              <dt>名称</dt>
              <dd title={rawData.raw_data_name}>{valueOrDash(rawData.raw_data_name)}</dd>
            </div>
            <div>
              <dt>类型</dt>
              <dd>{dataTypeLabel(rawData.data_type)}</dd>
            </div>
          </dl>
        </section>

        <section className="raw-data-summary-group">
          <h4>数据状态</h4>
          <dl>
            <div>
              <dt>解析状态</dt>
              <dd>
                <span className={parserStatusClass(rawData.parser_status)}>
                  {parserStatusLabel(rawData.parser_status)}
                </span>
              </dd>
            </div>
            <div>
              <dt>文件数量</dt>
              <dd>{rawData.file_count} 个 / {formatFileSize(rawData.total_size)}</dd>
            </div>
            <div>
              <dt>标准化结果</dt>
              <dd>{rawData.parsed_data_count ?? parsedData.length}</dd>
            </div>
            <div>
              <dt>解析 / 可视化任务</dt>
              <dd>{rawData.processing_job_count ?? processingJobs.length}</dd>
            </div>
            <div>
              <dt>有效记录</dt>
              <dd>{validRecordCount(selectedParsedData)}</dd>
            </div>
          </dl>
        </section>

        <section className="raw-data-summary-group">
          <h4>最近来源</h4>
          <dl>
            <div>
              <dt>最新源文件</dt>
              <dd title={latestSourceFile(selectedParsedData)}>{latestSourceFile(selectedParsedData)}</dd>
            </div>
            <div>
              <dt>创建时间</dt>
              <dd>{formatDateTime(rawData.created_at)}</dd>
            </div>
          </dl>
        </section>
      </div>
    </section>
  );
}

export function RawDataPage() {
  const {
    rawData,
    selectedRawData,
    filters,
    loading,
    saving,
    uploading,
    parsing,
    error,
    setFilters,
    refreshRawData,
    createRawData,
    loadRawDataDetail,
    uploadFiles,
    parseRawDataRecord,
    visualizeParsedDataRecord,
    deleteRawData,
    downloadRawDataFile,
    deleteRawDataFile,
    setSelectedRawData,
  } = useRawDataStore();

  const [samples, setSamples] = useState<Sample[]>([]);
  const [samplesLoading, setSamplesLoading] = useState(true);
  const [samplesError, setSamplesError] = useState("");
  const [localError, setLocalError] = useState("");
  const [parsedData, setParsedData] = useState<ParsedDataRecord[]>([]);
  const [selectedParsedData, setSelectedParsedData] = useState<ParsedDataRecord | null>(null);
  const [processingJobs, setProcessingJobs] = useState<ProcessingJobRecord[]>([]);
  const [activeMainTab, setActiveMainTab] = useState<RawDataMainTab>("list");
  const [pendingDelete, setPendingDelete] = useState<RawDataRecord | null>(null);
  const [preview, setPreview] = useState<RawDataDeletePreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [pendingFileDelete, setPendingFileDelete] = useState<
    { file: RawDataFile; rawDataId: number } | null
  >(null);
  const [filePreview, setFilePreview] = useState<RawDataFileDeletePreview | null>(null);
  const [filePreviewLoading, setFilePreviewLoading] = useState(false);
  const [filePreviewError, setFilePreviewError] = useState("");
  const [fileDeleting, setFileDeleting] = useState(false);
  const [perfUploading, setPerfUploading] = useState(false);
  const [searchParams] = useSearchParams();

  const pageError = useMemo(
    () => localError || error || samplesError,
    [error, localError, samplesError],
  );

  // Spec 004 Phase 2b: legacy /performance-datasets redirects here with
  // ?data_type=performance; apply it as a filter so the unified list opens scoped.
  useEffect(() => {
    const nextType = searchParams.get("data_type");
    if (nextType) {
      setFilters({ data_type: nextType });
    }
  }, [searchParams, setFilters]);

  useEffect(() => {
    let active = true;

    async function loadSamples() {
      setSamplesLoading(true);
      setSamplesError("");

      try {
        const nextSamples = await getSamples();
        if (active) {
          setSamples(nextSamples);
        }
      } catch (err) {
        if (active) {
          setSamplesError(err instanceof Error ? err.message : "加载样品选项失败");
        }
      } finally {
        if (active) {
          setSamplesLoading(false);
        }
      }
    }

    void loadSamples();

    return () => {
      active = false;
    };
  }, []);

  async function refreshRawDataResults(rawDataId: number) {
    const [nextParsedData, nextProcessingJobs] = await Promise.all([
      getParsedData({ raw_data_id: rawDataId }),
      getProcessingJobs({ raw_data_id: rawDataId }),
    ]);

    setParsedData(nextParsedData);
    setSelectedParsedData((current) => {
      if (current) {
        const matched = nextParsedData.find((item) => item.id === current.id);
        if (matched) {
          return matched;
        }
      }

      return null;
    });
    setProcessingJobs(nextProcessingJobs);
  }

  useEffect(() => {
    let active = true;

    async function loadResults() {
      if (!selectedRawData?.id || selectedRawData.source === "performance") {
        setParsedData([]);
        setSelectedParsedData(null);
        setProcessingJobs([]);
        return;
      }

      try {
        const [nextParsedData, nextProcessingJobs] = await Promise.all([
          getParsedData({ raw_data_id: selectedRawData.id }),
          getProcessingJobs({ raw_data_id: selectedRawData.id }),
        ]);

        if (active) {
          setParsedData(nextParsedData);
          setSelectedParsedData(null);
          setProcessingJobs(nextProcessingJobs);
        }
      } catch (err) {
        if (active) {
          setLocalError(err instanceof Error ? err.message : "加载 Raw Data 结果失败");
        }
      }
    }

    void loadResults();

    return () => {
      active = false;
    };
  }, [selectedRawData?.id, selectedRawData?.source]);

  async function handleCreate(payload: RawDataPayload) {
    setLocalError("");

    try {
      const created = await createRawData(payload);
      await refreshRawDataResults(created.id);
      setActiveMainTab("detail");
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "创建 Raw Data 失败");
    }
  }

  async function handlePerfImport(fields: PerformanceDatasetFields, files: File[]) {
    setLocalError("");
    setPerfUploading(true);
    try {
      // Spec 004 Phase 2b: performance upload lands via the existing endpoint
      // (writes performance_datasets); the artifacts view surfaces it in this
      // same unified list. (Reframing the write to raw_data is a later step.)
      await uploadPerformanceDataset(fields, files);
      await refreshRawData();
      setFilters({ data_type: "performance" });
      setActiveMainTab("list");
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "导入性能数据集失败");
    } finally {
      setPerfUploading(false);
    }
  }

  async function handleSelect(record: RawDataRecord) {
    setLocalError("");

    if ((record.source ?? "raw_data") === "performance") {
      // Performance-origin artifact: its detail + delete are self-contained in
      // PerformanceArtifactDetail (perf endpoints, keyed by source_row_id); no
      // raw-data fetch. Clear any raw-data results from a prior selection.
      setSelectedRawData(record);
      setParsedData([]);
      setSelectedParsedData(null);
      setProcessingJobs([]);
      setActiveMainTab("detail");
      return;
    }

    try {
      const detail = await loadRawDataDetail(record.id);
      await refreshRawDataResults(record.id);
      setSelectedRawData(detail ?? record);
      setActiveMainTab("detail");
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "加载 Raw Data 详情失败");
    }
  }

  async function handleUpload(rawDataId: number, files: File[]) {
    setLocalError("");

    try {
      await uploadFiles(rawDataId, files);
      await refreshRawDataResults(rawDataId);
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "上传 Raw Data 文件失败");
    }
  }

  function requestFileDelete(file: RawDataFile, rawDataId: number) {
    setPendingFileDelete({ file, rawDataId });
    setFilePreview(null);
    setFilePreviewError("");
    setFilePreviewLoading(true);
    getRawDataFileDeletePreview(file.id)
      .then((result) => setFilePreview(result))
      .catch((err) =>
        setFilePreviewError(err instanceof Error ? err.message : "获取删除影响范围失败"),
      )
      .finally(() => setFilePreviewLoading(false));
  }

  function cancelFileDelete() {
    setPendingFileDelete(null);
    setFilePreview(null);
    setFilePreviewError("");
    setFilePreviewLoading(false);
  }

  async function confirmFileDelete() {
    if (!pendingFileDelete) {
      return;
    }
    const { file, rawDataId } = pendingFileDelete;
    setLocalError("");
    setFileDeleting(true);
    try {
      await deleteRawDataFile(file.id, rawDataId);
      await refreshRawDataResults(rawDataId);
      cancelFileDelete();
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "删除 Raw Data 源文件失败");
    } finally {
      setFileDeleting(false);
    }
  }

  const fileDeletePreviewLines = useMemo<DeletePreviewLine[]>(() => {
    if (!filePreview) {
      return [];
    }
    const candidates: DeletePreviewLine[] = [
      { label: "条解析数据", count: filePreview.parsed_data },
      { label: "条解析记录", count: filePreview.parsed_records },
      { label: "个关联文件", count: filePreview.files_total },
    ];
    return candidates.filter((line) => line.count > 0);
  }, [filePreview]);

  function requestDelete(record: RawDataRecord) {
    setPendingDelete(record);
    setPreview(null);
    setPreviewError("");
    setPreviewLoading(true);
    getRawDataDeletePreview(record.id)
      .then((result) => setPreview(result))
      .catch((err) =>
        setPreviewError(err instanceof Error ? err.message : "获取删除影响范围失败"),
      )
      .finally(() => setPreviewLoading(false));
  }

  function cancelDelete() {
    setPendingDelete(null);
    setPreview(null);
    setPreviewError("");
    setPreviewLoading(false);
  }

  async function confirmDelete() {
    if (!pendingDelete) {
      return;
    }
    const record = pendingDelete;
    setLocalError("");
    setDeleting(true);
    try {
      await deleteRawData(record.id);
      if (selectedRawData?.id === record.id) {
        setParsedData([]);
        setSelectedParsedData(null);
        setProcessingJobs([]);
        setActiveMainTab("list");
      }
      cancelDelete();
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "删除 Raw Data 失败");
    } finally {
      setDeleting(false);
    }
  }

  const deletePreviewLines = useMemo<DeletePreviewLine[]>(() => {
    if (!preview) {
      return [];
    }
    const candidates: DeletePreviewLine[] = [
      { label: "个源文件", count: preview.raw_data_files },
      { label: "条解析数据", count: preview.parsed_data },
      { label: "条解析记录", count: preview.parsed_records },
      { label: "个关联文件", count: preview.files_total },
    ];
    return candidates.filter((line) => line.count > 0);
  }, [preview]);

  async function handleParse(rawDataId: number) {
    setLocalError("");

    try {
      await parseRawDataRecord(rawDataId);
      await refreshRawDataResults(rawDataId);
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "运行 Raw Data 解析失败");
    }
  }

  async function handleVisualize(parsedDataId: number, payload?: VisualizationPayload) {
    setLocalError("");

    try {
      await visualizeParsedDataRecord(parsedDataId, payload);
      if (selectedRawData?.id) {
        await refreshRawDataResults(selectedRawData.id);
      }
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "生成 CD 小提琴图失败");
    }
  }

  return (
    <section className="raw-data-workspace">
      {pageError ? (
        <section className="panel panel-section-spacing">
          <div className="empty-row">
            <div className="page-message">
              <strong>Raw Data 操作失败</strong>
              <span>{pageError}</span>
            </div>
          </div>
        </section>
      ) : null}

      <nav className="raw-data-main-tabs" aria-label="Raw Data 工作区">
        {[
          ["list", "数据清单"],
          ["detail", "数据详情"],
          ["create", "新建数据"],
          ["perf-upload", "性能上传"],
        ].map(([tab, label]) => (
          <button
            key={tab}
            type="button"
            className={`raw-data-main-tab ${activeMainTab === tab ? "raw-data-main-tab-active" : ""}`}
            onClick={() => setActiveMainTab(tab as RawDataMainTab)}
          >
            {label}
          </button>
        ))}
      </nav>

      {activeMainTab === "list" ? (
        <div className="raw-data-tab-panel raw-data-list-layout">
          <section className="panel raw-data-list-main">
            <div className="panel-header raw-data-list-card-header">
              <h3>信息列表</h3>
            </div>
            <RawDataFilter
              filters={filters}
              samples={samples}
              onChange={setFilters}
              onRefresh={() => void refreshRawData()}
            />
            {loading ? (
              <div className="empty-row">加载中...</div>
            ) : (
              <RawDataTable
                key={`${filters.sample_id ?? ""}-${filters.data_type ?? ""}-${filters.parser_status ?? ""}-${filters.status ?? ""}-${filters.query ?? ""}`}
                rawData={rawData}
                selectedRawDataId={selectedRawData?.id ?? null}
                selectedSource={selectedRawData?.source ?? null}
                onSelect={(record) => void handleSelect(record)}
                onDelete={(record) => requestDelete(record)}
              />
            )}
          </section>
          <RawDataSummarySide
            rawData={selectedRawData}
            parsedData={parsedData}
            processingJobs={processingJobs}
          />
        </div>
      ) : null}

      {activeMainTab === "detail" ? (
        <section className="panel raw-data-detail-panel raw-data-tab-panel">
          {selectedRawData?.source === "performance" ? (
            <PerformanceArtifactDetail
              key={selectedRawData.source_row_id ?? selectedRawData.id}
              record={selectedRawData}
              onDeleted={() => {
                setSelectedRawData(null);
                setActiveMainTab("list");
                void refreshRawData();
              }}
            />
          ) : (
            <RawDataDetailPanel
              rawData={selectedRawData}
              parsedData={parsedData}
              selectedParsedData={selectedParsedData}
              processingJobs={processingJobs}
              uploading={uploading}
              parsing={parsing}
              onUpload={(rawDataId, files) => void handleUpload(rawDataId, files)}
              onDownloadFile={downloadRawDataFile}
              onDeleteFile={(file, rawDataId) => requestFileDelete(file, rawDataId)}
              onParse={(rawDataId) => void handleParse(rawDataId)}
              onVisualize={(parsedDataId, payload) => void handleVisualize(parsedDataId, payload)}
              onSelectParsedData={setSelectedParsedData}
            />
          )}
        </section>
      ) : null}

      {activeMainTab === "create" ? (
        <section className="panel form-panel raw-data-create-panel raw-data-tab-panel">
          {samplesLoading ? (
            <div className="empty-row">加载样品选项中...</div>
          ) : (
            <>
              <RawDataForm samples={samples} saving={saving} onSubmit={handleCreate} />
              <div className="raw-data-create-hint">
                带 * 为必填字段，创建后将自动刷新 Raw Data 列表并跳转到数据详情页。
              </div>
            </>
          )}
        </section>
      ) : null}

      {activeMainTab === "perf-upload" ? (
        <section className="panel form-panel raw-data-tab-panel">
          <div className="panel-header">
            <h3>性能数据集上传</h3>
          </div>
          {samplesLoading ? (
            <div className="empty-row">加载样品选项中...</div>
          ) : (
            <div className="import-grid">
              <DatasetImportPanel
                samples={samples}
                uploading={perfUploading}
                onImport={(fields, files) => void handlePerfImport(fields, files)}
              />
            </div>
          )}
        </section>
      ) : null}

      <DeleteConfirmDialog
        open={pendingDelete !== null}
        title="删除 Raw Data"
        message={`确认删除 Raw Data：${pendingDelete?.raw_data_code ?? ""}？此操作不可撤销。`}
        previewLines={deletePreviewLines}
        loading={previewLoading}
        error={previewError}
        deleting={deleting}
        onConfirm={() => void confirmDelete()}
        onCancel={cancelDelete}
      />

      <DeleteConfirmDialog
        open={pendingFileDelete !== null}
        title="删除源文件"
        message={`确认删除源文件 ${pendingFileDelete?.file.original_filename ?? ""}？此操作不可撤销。`}
        previewLines={fileDeletePreviewLines}
        loading={filePreviewLoading}
        error={filePreviewError}
        deleting={fileDeleting}
        onConfirm={() => void confirmFileDelete()}
        onCancel={cancelFileDelete}
      />
    </section>
  );
}
