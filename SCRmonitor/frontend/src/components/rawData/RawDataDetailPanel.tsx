import { useState } from "react";
import type {
  ParsedDataRecord,
  ProcessingJobRecord,
  RawDataFile,
  RawDataRecord,
  VisualizationPayload,
} from "../../types/rawData";
import { ParsedDataInfoTable } from "./ParsedDataInfoTable";
import { ParsedDataRecordsTable } from "./ParsedDataRecordsTable";
import { ProcessingJobsTable } from "./ProcessingJobsTable";
import { RawDataFileList } from "./RawDataFileList";
import { ResistanceSummaryPanel } from "./ResistanceSummaryPanel";
import { ResistanceVisualizationPanel } from "./ResistanceVisualizationPanel";
import { VisualizationPreviewPanel } from "./VisualizationPreviewPanel";

type RawDataDetailPanelProps = {
  rawData: RawDataRecord | null;
  parsedData: ParsedDataRecord[];
  selectedParsedData: ParsedDataRecord | null;
  processingJobs: ProcessingJobRecord[];
  uploading?: boolean;
  parsing?: boolean;
  onUpload: (rawDataId: number, files: File[]) => Promise<void> | void;
  onDownloadFile: (fileId: number) => void;
  onDeleteFile: (file: RawDataFile, rawDataId: number) => void;
  onParse: (rawDataId: number) => Promise<void> | void;
  onVisualize: (parsedDataId: number, payload?: VisualizationPayload) => Promise<void> | void;
  onSelectParsedData: (parsedData: ParsedDataRecord) => void;
};

type DetailTab = "files" | "parsed" | "visualization" | "jobs";

function canParseRawData(dataType: string) {
  return dataType === "cd_sem" || dataType === "resistance";
}

function TemplateDownloadHint({ dataType }: { dataType: string }) {
  if (dataType === "cd_sem") {
    return (
      <a className="button-like raw-template-download-button" href="/api/templates/cd_sem_template.csv">
        下载 CD 数据模板
      </a>
    );
  }

  return null;
}

export function RawDataDetailPanel({
  rawData,
  parsedData,
  selectedParsedData,
  processingJobs,
  uploading = false,
  parsing = false,
  onUpload,
  onDownloadFile,
  onDeleteFile,
  onParse,
  onVisualize,
  onSelectParsedData,
}: RawDataDetailPanelProps) {
  const [files, setFiles] = useState<File[]>([]);
  const [activeDetailTab, setActiveDetailTab] = useState<DetailTab>("files");

  async function handleUpload() {
    if (!rawData || files.length === 0) {
      return;
    }

    await onUpload(rawData.id, files);
    setFiles([]);
  }

  async function handleParse() {
    if (!rawData) {
      return;
    }

    await onParse(rawData.id);
    setActiveDetailTab("parsed");
  }

  if (!rawData) {
    return (
      <>
        <div className="panel-header">
          <h3>Raw Data 详情</h3>
        </div>
        <div className="empty-row">请先在数据清单中选择一条 Raw Data。</div>
      </>
    );
  }

  return (
    <>
      <div className="panel-header">
        <h3>Raw Data 详情</h3>
      </div>

      <nav className="raw-data-detail-tabs" aria-label="Raw Data 详情分区">
        {[
          ["files", "原始文件"],
          ["parsed", "标准化结果"],
          ["visualization", "可视化结果"],
          ["jobs", "处理历史"],
        ].map(([tab, label]) => (
          <button
            key={tab}
            type="button"
            className={`raw-data-detail-tab ${activeDetailTab === tab ? "active" : ""}`}
            onClick={() => setActiveDetailTab(tab as DetailTab)}
          >
            {label}
          </button>
        ))}
      </nav>

      <div className="raw-detail-sections raw-data-detail-tab-panel">
        {activeDetailTab === "files" ? (
          <section className="raw-detail-section">
            <h4>原始文件</h4>
            <div className="raw-upload-panel">
              <input
                type="file"
                multiple
                onChange={(event) => setFiles(Array.from(event.target.files || []))}
              />
              <button type="button" disabled={uploading || files.length === 0} onClick={handleUpload}>
                {uploading ? "上传中..." : "上传文件"}
              </button>
              <div className="raw-file-inline-actions">
                <TemplateDownloadHint dataType={rawData.data_type} />
                {canParseRawData(rawData.data_type) ? (
                  <button
                    className="raw-template-parse-button"
                    type="button"
                    disabled={parsing || (rawData.files?.length ?? 0) === 0}
                    onClick={() => void handleParse()}
                  >
                    解析
                  </button>
                ) : null}
              </div>
            </div>
            <RawDataFileList
              files={rawData.files}
              onDownload={onDownloadFile}
              onDelete={(file) => onDeleteFile(file, rawData.id)}
            />
          </section>
        ) : null}

        {activeDetailTab === "parsed" ? (
          <div className="raw-parsed-tab-content">
            <h4>标准化结果</h4>
            <ParsedDataInfoTable
              parsedData={parsedData}
              selectedParsedData={selectedParsedData}
              onSelect={onSelectParsedData}
            />
            {selectedParsedData ? (
              selectedParsedData.data_type === "resistance" ? (
                <ResistanceSummaryPanel parsedData={selectedParsedData} />
              ) : (
                <>
                <ParsedDataRecordsTable parsedData={selectedParsedData} />
                <p className="raw-parsed-note">说明：标准化记录基于当前选中的解析信息展示</p>
                </>
              )
            ) : null}
          </div>
        ) : null}

        {activeDetailTab === "visualization" ? (
          <section className="raw-detail-section">
            <h4>可视化结果</h4>
            {selectedParsedData?.data_type === "cd_sem" ? (
              <VisualizationPreviewPanel
                selectedParsedData={selectedParsedData}
                processingJobs={processingJobs}
                onVisualize={onVisualize}
              />
            ) : selectedParsedData?.data_type === "resistance" ? (
              <ResistanceVisualizationPanel
                selectedParsedData={selectedParsedData}
                onVisualize={onVisualize}
              />
            ) : (
              <div className="empty-row">当前标准化结果暂无可视化面板。</div>
            )}
          </section>
        ) : null}

        {activeDetailTab === "jobs" ? (
          <section className="raw-detail-section">
            <h4>处理历史</h4>
            <ProcessingJobsTable jobs={processingJobs} />
          </section>
        ) : null}

      </div>
    </>
  );
}
