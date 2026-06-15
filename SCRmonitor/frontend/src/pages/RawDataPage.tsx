import { useEffect, useMemo, useState } from "react";
import { getParsedData, getProcessingJobs } from "../api/rawDataApi";
import { getSamples } from "../api/samplesApi";
import { RawDataDetailPanel } from "../components/rawData/RawDataDetailPanel";
import { RawDataFilter } from "../components/rawData/RawDataFilter";
import { RawDataForm } from "../components/rawData/RawDataForm";
import { RawDataTable } from "../components/rawData/RawDataTable";
import { useRawDataStore } from "../stores/rawDataStore";
import type { Sample } from "../types/sample";
import type {
  ParsedDataRecord,
  ProcessingJobRecord,
  RawDataPayload,
  RawDataRecord,
  VisualizationPayload,
} from "../types/rawData";
import { RAW_DATA_TYPE_OPTIONS } from "../utils/constants";
import { formatDateTime } from "../utils/formatDate";
import { formatFileSize } from "../utils/fileSize";

type RawDataMainTab = "list" | "detail" | "create";

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
              <dt>处理任务</dt>
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

  const pageError = useMemo(
    () => localError || error || samplesError,
    [error, localError, samplesError],
  );

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
      if (!selectedRawData?.id) {
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
  }, [selectedRawData?.id]);

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

  async function handleSelect(record: RawDataRecord) {
    setLocalError("");

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

  async function handleDeleteRawDataFile(fileId: number, rawDataId: number) {
    setLocalError("");

    try {
      await deleteRawDataFile(fileId, rawDataId);
      await refreshRawDataResults(rawDataId);
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "删除 Raw Data 源文件失败");
    }
  }

  async function handleDelete(record: RawDataRecord) {
    const confirmed = window.confirm(`确认删除 Raw Data：${record.raw_data_code}？`);
    if (!confirmed) {
      return;
    }

    setLocalError("");

    try {
      await deleteRawData(record.id);
      if (selectedRawData?.id === record.id) {
        setParsedData([]);
        setSelectedParsedData(null);
        setProcessingJobs([]);
        setActiveMainTab("list");
      }
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "删除 Raw Data 失败");
    }
  }

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
                onSelect={(record) => void handleSelect(record)}
                onDelete={(record) => void handleDelete(record)}
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
          <RawDataDetailPanel
            rawData={selectedRawData}
            parsedData={parsedData}
            selectedParsedData={selectedParsedData}
            processingJobs={processingJobs}
            uploading={uploading}
            parsing={parsing}
            onUpload={(rawDataId, files) => void handleUpload(rawDataId, files)}
            onDownloadFile={downloadRawDataFile}
            onDeleteFile={(fileId, rawDataId) => void handleDeleteRawDataFile(fileId, rawDataId)}
            onParse={(rawDataId) => void handleParse(rawDataId)}
            onVisualize={(parsedDataId, payload) => void handleVisualize(parsedDataId, payload)}
            onSelectParsedData={setSelectedParsedData}
          />
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
    </section>
  );
}
