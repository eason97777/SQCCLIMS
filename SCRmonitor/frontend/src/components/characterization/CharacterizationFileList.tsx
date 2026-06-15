import type { CharacterizationFile } from "../../types/characterization";

type CharacterizationFileListProps = {
  files: CharacterizationFile[];
  onPreview: (file: CharacterizationFile) => void;
  onDelete: (file: CharacterizationFile) => void;
  buildDownloadUrl: (fileId: number) => string;
};

function fileKindLabel(file: CharacterizationFile) {
  if (file.preview_type === "image") {
    return "图像";
  }
  if (file.preview_type === "pdf") {
    return "PDF";
  }
  if (file.preview_type === "text") {
    return "文本";
  }
  return file.original_filename.split(".").pop()?.toUpperCase() || "文件";
}

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

export function CharacterizationFileList({
  files,
  onPreview,
  onDelete,
  buildDownloadUrl,
}: CharacterizationFileListProps) {
  if (!files.length) {
    return <div className="empty-row">该数据包暂无文件</div>;
  }

  return (
    <div className="file-card-grid">
      {files.map((file) => {
        const kind = fileKindLabel(file);
        const preview =
          file.preview_type === "image" ? (
            <img
              src={`/api/characterization-files/${file.id}/preview`}
              alt={file.original_filename}
            />
          ) : (
            <div className="file-type-icon">{kind}</div>
          );

        return (
          <article key={file.id} className="file-card">
            <button
              className="file-open"
              type="button"
              title={`查看 ${file.original_filename}`}
              onClick={() => onPreview(file)}
            >
              <div className="file-thumb">{preview}</div>
              <strong title={file.original_filename}>{file.original_filename}</strong>
            </button>
            <span>{file.relative_path || file.original_filename}</span>
            <small>
              {formatBytes(file.file_size)} / {kind}
            </small>
            <div className="file-card-actions file-card-actions-three">
              <button className="ghost-button" type="button" onClick={() => onPreview(file)}>
                查看
              </button>
              <a
                className="ghost-link"
                href={buildDownloadUrl(file.id)}
                download={file.original_filename}
              >
                下载
              </a>
              <button
                className="danger-button"
                type="button"
                onClick={() => onDelete(file)}
              >
                删除
              </button>
            </div>
          </article>
        );
      })}
    </div>
  );
}
