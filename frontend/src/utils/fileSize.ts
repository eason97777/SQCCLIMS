export function formatFileSize(value?: number | null) {
  const size = Number(value ?? 0);
  if (!Number.isFinite(size) || size <= 0) {
    return "0 B";
  }

  const units = ["B", "KB", "MB", "GB", "TB"];
  let nextSize = size;
  let unitIndex = 0;

  while (nextSize >= 1024 && unitIndex < units.length - 1) {
    nextSize /= 1024;
    unitIndex += 1;
  }

  const digits = nextSize >= 10 || unitIndex === 0 ? 0 : 1;
  return `${nextSize.toFixed(digits)} ${units[unitIndex]}`;
}
