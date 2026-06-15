import { useState } from "react";
import type {
  CharacterizationCollection,
  CharacterizationUploadFields,
} from "../../types/characterization";

type FileUploadPanelProps = {
  selectedCollection: CharacterizationCollection | null;
  uploading?: boolean;
  onUpload: (
    fields: CharacterizationUploadFields,
    files: File[],
  ) => Promise<void> | void;
};

type UploadState = {
  title: string;
  notes: string;
  captured_at: string;
  operator: string;
};

function todayDate() {
  return new Date().toISOString().slice(0, 10);
}

export function FileUploadPanel({
  selectedCollection,
  uploading = false,
  onUpload,
}: FileUploadPanelProps) {
  const [uploadState, setUploadState] = useState<UploadState>({
    title: "",
    notes: "",
    captured_at: todayDate(),
    operator: "",
  });
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);

  function handleChange(
    event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>,
  ) {
    const { name, value } = event.target;
    setUploadState((current) => ({
      ...current,
      [name]: value,
    }));
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedCollection || !selectedFiles.length) {
      return;
    }

    await onUpload(
      {
        sample_id: selectedCollection.sample_id,
        collection_id: selectedCollection.id,
        category: selectedCollection.category,
        technique: selectedCollection.technique,
        instrument: selectedCollection.instrument,
        captured_at: uploadState.captured_at,
        operator: uploadState.operator,
        title: uploadState.title,
        notes: uploadState.notes,
      },
      selectedFiles,
    );

    setUploadState({
      title: "",
      notes: "",
      captured_at: todayDate(),
      operator: "",
    });
    setSelectedFiles([]);

    const input = document.getElementById("characterization-files-input") as
      | HTMLInputElement
      | null;
    if (input) {
      input.value = "";
    }
  }

  return (
    <form className="form-grid" onSubmit={handleSubmit}>
      <label>
        当前数据包
        <input
          value={selectedCollection ? selectedCollection.name : "请先在右侧选择数据包"}
          readOnly
        />
      </label>
      <label>
        文件标题
        <input
          name="title"
          placeholder="留空则使用文件名"
          value={uploadState.title}
          onChange={handleChange}
        />
      </label>
      <label>
        采集日期
        <input
          name="captured_at"
          type="date"
          value={uploadState.captured_at}
          onChange={handleChange}
        />
      </label>
      <label>
        操作人
        <input name="operator" value={uploadState.operator} onChange={handleChange} />
      </label>
      <label className="full">
        备注
        <textarea
          name="notes"
          rows={2}
          value={uploadState.notes}
          onChange={handleChange}
        />
      </label>
      <label className="full">
        文件
        <input
          id="characterization-files-input"
          type="file"
          multiple
          required
          disabled={!selectedCollection || uploading}
          onChange={(event) => setSelectedFiles(Array.from(event.target.files || []))}
        />
      </label>
      <div className="form-actions full">
        <button type="submit" disabled={!selectedCollection || uploading || !selectedFiles.length}>
          {uploading ? "上传中..." : "上传表征文件"}
        </button>
      </div>
    </form>
  );
}
