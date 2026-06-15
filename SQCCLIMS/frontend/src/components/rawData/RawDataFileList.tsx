import { useEffect, useRef, useState } from "react";
import type { RawDataFile } from "../../types/rawData";
import { formatDateTime } from "../../utils/formatDate";
import { formatFileSize } from "../../utils/fileSize";

type RawDataFileListProps = {
  files?: RawDataFile[];
  onDownload: (fileId: number) => void;
  onDelete: (file: RawDataFile) => void;
};

function valueOrDash(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }

  return String(value);
}

export function RawDataFileList({ files = [], onDownload, onDelete }: RawDataFileListProps) {
  const [pageState, setPageState] = useState({ filesKey: "", page: 1 });
  const [openMenuId, setOpenMenuId] = useState<number | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const pageSize = 5;
  const filesKey = files.map((file) => file.id).join(",");
  const currentPage = pageState.filesKey === filesKey ? pageState.page : 1;
  const totalPages = Math.max(1, Math.ceil(files.length / pageSize));
  const safeCurrentPage = Math.min(currentPage, totalPages);
  const startIndex = (safeCurrentPage - 1) * pageSize;
  const visibleFiles = files.slice(startIndex, startIndex + pageSize);

  useEffect(() => {
    function handleMouseDown(event: MouseEvent) {
      if (!menuRef.current?.contains(event.target as Node)) {
        setOpenMenuId(null);
      }
    }

    document.addEventListener("mousedown", handleMouseDown);
    return () => document.removeEventListener("mousedown", handleMouseDown);
  }, []);

  function handleDelete(file: RawDataFile) {
    setOpenMenuId(null);
    onDelete(file);
  }

  if (files.length === 0) {
    return <div className="empty-row">暂无文件，请先上传原始数据文件</div>;
  }

  return (
    <div className="raw-file-table-wrap">
      <table className="raw-file-table">
        <thead>
          <tr>
            <th>原始文件名</th>
            <th>大小</th>
            <th>扩展名</th>
            <th>SHA256</th>
            <th>上传时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {visibleFiles.map((file) => (
            <tr key={file.id}>
              <td title={file.original_filename}>{valueOrDash(file.original_filename)}</td>
              <td>{formatFileSize(file.file_size)}</td>
              <td>{valueOrDash(file.file_ext)}</td>
              <td title={file.sha256}>{file.sha256 ? file.sha256.slice(0, 12) : "-"}</td>
              <td>{formatDateTime(file.created_at)}</td>
              <td>
                <div className="raw-file-action-menu" ref={openMenuId === file.id ? menuRef : null}>
                  <button
                    className="ghost-button raw-file-more-button"
                    type="button"
                    aria-expanded={openMenuId === file.id}
                    onClick={() => setOpenMenuId((current) => (current === file.id ? null : file.id))}
                  >
                    更多
                  </button>
                  {openMenuId === file.id ? (
                    <div className="raw-file-action-dropdown">
                      <button
                        type="button"
                        onClick={() => {
                          setOpenMenuId(null);
                          onDownload(file.id);
                        }}
                      >
                        下载
                      </button>
                      <button
                        className="raw-file-delete-menu-item"
                        type="button"
                        onClick={() => handleDelete(file)}
                      >
                        删除
                      </button>
                    </div>
                  ) : null}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {files.length > pageSize ? (
        <div className="raw-file-list-toggle">
          <span>
            当前显示第 {startIndex + 1}-{Math.min(startIndex + visibleFiles.length, files.length)} 条，共{" "}
            {files.length} 条
          </span>
          <button
            className="ghost-button"
            type="button"
            disabled={safeCurrentPage <= 1}
            onClick={() => setPageState({ filesKey, page: Math.max(1, safeCurrentPage - 1) })}
          >
            上一页
          </button>
          <span>
            第 {safeCurrentPage} / {totalPages} 页
          </span>
          <button
            className="ghost-button"
            type="button"
            disabled={safeCurrentPage >= totalPages}
            onClick={() => setPageState({ filesKey, page: Math.min(totalPages, safeCurrentPage + 1) })}
          >
            下一页
          </button>
        </div>
      ) : null}
    </div>
  );
}
