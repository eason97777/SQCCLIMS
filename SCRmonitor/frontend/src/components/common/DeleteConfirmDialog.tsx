export type DeletePreviewLine = {
  label: string;
  count: number;
};

type DeleteConfirmDialogProps = {
  open: boolean;
  title: string;
  /** Leading sentence, e.g. "确认删除样品 SCR-001？" */
  message: string;
  /**
   * Strong tier only: the cascade preview lines. Only non-zero lines should be
   * passed in by the caller. When empty (or undefined) the dialog renders as a
   * plain confirm (simple tier).
   */
  previewLines?: DeletePreviewLine[];
  /** Strong tier: whether the preview request is still loading. */
  loading?: boolean;
  /** Error from fetching the preview (delete is still allowed). */
  error?: string;
  /** Whether the actual delete request is running. */
  deleting?: boolean;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
};

export function DeleteConfirmDialog({
  open,
  title,
  message,
  previewLines = [],
  loading = false,
  error = "",
  deleting = false,
  confirmLabel = "确认删除",
  cancelLabel = "取消",
  onConfirm,
  onCancel,
}: DeleteConfirmDialogProps) {
  if (!open) {
    return null;
  }

  const hasPreview = previewLines.length > 0;

  return (
    <div className="modal show" aria-hidden="false">
      <div className="modal-backdrop" onClick={deleting ? undefined : onCancel} />
      <section
        className="modal-panel delete-confirm-panel"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="delete-confirm-title"
      >
        <header className="modal-header">
          <div>
            <p className="eyebrow">删除确认</p>
            <h3 id="delete-confirm-title">{title}</h3>
          </div>
        </header>

        <div className="delete-confirm-body">
          <p className="delete-confirm-message">{message}</p>

          {loading ? (
            <p className="delete-confirm-loading">正在统计将要删除的关联数据…</p>
          ) : null}

          {error ? (
            <p className="delete-confirm-error">
              无法获取删除影响范围：{error}。仍可继续删除。
            </p>
          ) : null}

          {!loading && hasPreview ? (
            <>
              <p className="delete-confirm-subtitle">此操作还将一并永久删除：</p>
              <ul className="delete-confirm-list">
                {previewLines.map((line) => (
                  <li key={line.label}>
                    <strong>{line.count}</strong> {line.label}
                  </li>
                ))}
              </ul>
              <p className="delete-confirm-note">
                已上传的原始文件会保留在归档区，必要时可恢复。
              </p>
            </>
          ) : null}
        </div>

        <footer className="modal-footer delete-confirm-footer">
          <button
            type="button"
            className="ghost-button"
            onClick={onCancel}
            disabled={deleting}
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            className="danger-button"
            onClick={onConfirm}
            disabled={deleting || loading}
          >
            {deleting ? "删除中…" : confirmLabel}
          </button>
        </footer>
      </section>
    </div>
  );
}
