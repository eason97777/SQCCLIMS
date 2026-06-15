import type { CharacterizationFile } from "../../types/characterization";
import { getSampleDisplayCode } from "../../utils/sampleFields";
import { formatDateTime } from "../../utils/formatDate";

type FilePreviewModalProps = {
  file: CharacterizationFile | null;
  textContent: string;
  previewUrl: string;
  downloadUrl: string;
  onClose: () => void;
  onToggleImageFit: () => void;
  imageFit: boolean;
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

export function FilePreviewModal({
  file,
  textContent,
  previewUrl,
  downloadUrl,
  onClose,
  onToggleImageFit,
  imageFit,
}: FilePreviewModalProps) {
  if (!file) {
    return null;
  }

  return (
    <div className="modal show" aria-hidden="false">
      <div className="modal-backdrop" onClick={onClose} />
      <section
        className="modal-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="file-preview-title"
      >
        <header className="modal-header">
          <div>
            <p className="eyebrow">Characterization File</p>
            <h3 id="file-preview-title">{file.title || file.original_filename}</h3>
          </div>
          <div className="modal-actions">
            <a
              className="download-button"
              href={downloadUrl}
              download={file.original_filename}
            >
              下载原始文件
            </a>
            <button className="ghost-button" type="button" onClick={onClose}>
              关闭
            </button>
          </div>
        </header>
        <div className="file-metadata">
          <div>
            <span>样品</span>
            <strong>
              {getSampleDisplayCode(file)}
            </strong>
          </div>
          <div>
            <span>分类</span>
            <strong>{file.category || "-"}</strong>
          </div>
          <div>
            <span>技术/设备</span>
            <strong>{file.technique || "-"}</strong>
          </div>
          <div>
            <span>文件名</span>
            <strong>{file.original_filename}</strong>
          </div>
          <div>
            <span>大小</span>
            <strong>{formatBytes(file.file_size)}</strong>
          </div>
          <div>
            <span>上传时间</span>
            <strong>{formatDateTime(file.created_at)}</strong>
          </div>
          <div>
            <span>存储路径</span>
            <strong>{file.storage_path}</strong>
          </div>
          <div>
            <span>备注</span>
            <strong>{file.notes || "-"}</strong>
          </div>
        </div>
        <div className="file-preview-content">
          {file.preview_type === "image" ? (
            <>
              <div className="preview-toolbar">
                <button className="ghost-button" type="button" onClick={onToggleImageFit}>
                  切换适配/原始大小
                </button>
              </div>
              <img
                className={`preview-image ${imageFit ? "fit" : ""}`}
                src={previewUrl}
                alt={file.original_filename}
              />
            </>
          ) : null}
          {file.preview_type === "pdf" ? (
            <iframe
              className="preview-frame"
              src={previewUrl}
              title={file.original_filename}
            />
          ) : null}
          {file.preview_type === "text" ? (
            <pre className="preview-text">{textContent}</pre>
          ) : null}
          {file.preview_type === "download" ? (
            <div className="unsupported-preview">
              <strong>此文件类型暂不支持浏览器内预览</strong>
              <p>可以查看上方元数据，或下载原始文件后使用对应软件打开。</p>
            </div>
          ) : null}
        </div>
      </section>
    </div>
  );
}
