import { useState } from "react";
import type { PerformanceDatasetFields } from "../../types/performance";
import type { Sample } from "../../types/sample";
import { getSampleDisplayLabel } from "../../utils/sampleFields";
import {
  normalizeCodeText,
  normalizeNoteText,
  normalizeWhitespace,
  trimText,
} from "../../utils/textNormalize";

type DirectoryFile = File & {
  webkitRelativePath?: string;
};

type DirectoryInputProps = React.InputHTMLAttributes<HTMLInputElement> & {
  webkitdirectory?: string;
  directory?: string;
};

type DatasetImportPanelProps = {
  samples: Sample[];
  uploading?: boolean;
  onImport: (fields: PerformanceDatasetFields, files: DirectoryFile[]) => Promise<void> | void;
};

type FormState = {
  sample_id: string;
  aliquot_code: string;
  dataset_name: string;
  test_type: string;
  data_format: string;
  collected_at: string;
  operator: string;
  status: string;
  notes: string;
};

function todayDate() {
  return new Date().toISOString().slice(0, 10);
}

function buildInitialState(): FormState {
  return {
    sample_id: "",
    aliquot_code: "",
    dataset_name: "",
    test_type: "",
    data_format: "",
    collected_at: todayDate(),
    operator: "",
    status: "待处理",
    notes: "",
  };
}

export function DatasetImportPanel({
  samples,
  uploading = false,
  onImport,
}: DatasetImportPanelProps) {
  const [formState, setFormState] = useState<FormState>(buildInitialState);
  const [selectedFiles, setSelectedFiles] = useState<DirectoryFile[]>([]);
  const directoryInputProps: DirectoryInputProps = {
    id: "performance-folder-input",
    name: "files",
    type: "file",
    multiple: true,
    webkitdirectory: "true",
    directory: "",
    required: true,
    disabled: uploading,
    onChange: (event) =>
      setSelectedFiles(Array.from(event.target.files || []) as DirectoryFile[]),
  };

  function handleChange(
    event: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>,
  ) {
    const { name, value } = event.target;
    setFormState((current) => ({
      ...current,
      [name]: value,
    }));
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedFiles.length) {
      return;
    }

    const firstFile = selectedFiles[0];
    const sourceFolderName =
      firstFile?.webkitRelativePath?.split("/")[0] || "";

    await onImport(
      {
        sample_id: trimText(formState.sample_id),
        aliquot_code: normalizeCodeText(formState.aliquot_code),
        dataset_name: normalizeWhitespace(formState.dataset_name),
        test_type: normalizeWhitespace(formState.test_type),
        data_format: normalizeWhitespace(formState.data_format),
        source_folder_name: sourceFolderName,
        collected_at: trimText(formState.collected_at),
        operator: normalizeWhitespace(formState.operator),
        status: normalizeWhitespace(formState.status),
        notes: normalizeNoteText(formState.notes),
      },
      selectedFiles,
    );

    setFormState(buildInitialState());
    setSelectedFiles([]);
    const input = document.getElementById("performance-folder-input") as
      | HTMLInputElement
      | null;
    if (input) {
      input.value = "";
    }
  }

  return (
    <form className="import-card" onSubmit={handleSubmit}>
      <h4>取样性能数据集</h4>
      <p>样品取样后形成独立测试包，按文件夹导入，供后续处理模块调用。</p>
      <label>
        母样品
        <select
          name="sample_id"
          required
          value={formState.sample_id}
          onChange={handleChange}
        >
          <option value="">选择样品</option>
          {samples.map((sample) => (
            <option key={sample.id} value={sample.id}>
              {getSampleDisplayLabel(sample)}
            </option>
          ))}
        </select>
      </label>
      <label>
        取样编号
        <input
          name="aliquot_code"
          placeholder="例如 S01-A"
          value={formState.aliquot_code}
          onChange={handleChange}
        />
      </label>
      <label>
        数据集名称
        <input
          name="dataset_name"
          required
          placeholder="例如 循环伏安-第一批"
          value={formState.dataset_name}
          onChange={handleChange}
        />
      </label>
      <label>
        测试类型
        <input
          name="test_type"
          placeholder="IV / CV / EIS / 寿命"
          value={formState.test_type}
          onChange={handleChange}
        />
      </label>
      <label>
        数据格式
        <input
          name="data_format"
          placeholder="csv / txt / vendor"
          value={formState.data_format}
          onChange={handleChange}
        />
      </label>
      <label>
        采集日期
        <input
          name="collected_at"
          type="date"
          value={formState.collected_at}
          onChange={handleChange}
        />
      </label>
      <label>
        操作人
        <input
          name="operator"
          value={formState.operator}
          onChange={handleChange}
        />
      </label>
      <label>
        状态
        <select name="status" value={formState.status} onChange={handleChange}>
          <option>待处理</option>
          <option>处理中</option>
          <option>已处理</option>
          <option>已归档</option>
        </select>
      </label>
      <label className="full">
        备注
        <textarea
          name="notes"
          rows={2}
          value={formState.notes}
          onChange={handleChange}
        />
      </label>
      <label className="full">
        文件夹
        <input {...directoryInputProps} />
      </label>
      <button type="submit" disabled={uploading || !selectedFiles.length}>
        {uploading ? "导入中..." : "导入性能数据集"}
      </button>
    </form>
  );
}
