type DataImportPanelProps = {
  importing?: boolean;
  onImport: (file: File) => Promise<void> | void;
};

export function DataImportPanel({
  importing = false,
  onImport,
}: DataImportPanelProps) {
  async function handleChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    await onImport(file);
    event.target.value = "";
  }

  return (
    <label className="file-button">
      {importing ? "导入中..." : "导入 CSV"}
      <input
        id="csv-input"
        type="file"
        accept=".csv,text/csv"
        disabled={importing}
        onChange={(event) => {
          void handleChange(event);
        }}
      />
    </label>
  );
}
