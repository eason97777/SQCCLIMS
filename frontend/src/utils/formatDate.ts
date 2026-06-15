export function formatDateTime(value?: string | null) {
  if (!value) {
    return "-";
  }

  return String(value).replace("T", " ").replace("+00:00", "").slice(0, 16);
}
