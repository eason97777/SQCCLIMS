import { useState } from "react";
import type { CharacterizationCollectionPayload } from "../../types/characterization";
import type { Sample } from "../../types/sample";
import { getSampleDisplayLabel } from "../../utils/sampleFields";
import {
  normalizeNoteText,
  normalizeWhitespace,
  trimText,
} from "../../utils/textNormalize";

type CollectionFormProps = {
  samples: Sample[];
  saving?: boolean;
  selectedSampleId?: string;
  onSubmit: (payload: CharacterizationCollectionPayload) => Promise<void> | void;
};

type FormState = {
  sample_id: string;
  collection_name: string;
  category: string;
  technique: string;
  instrument: string;
  captured_at: string;
  operator: string;
  notes: string;
};

function todayDate() {
  return new Date().toISOString().slice(0, 10);
}

function buildInitialState(selectedSampleId = ""): FormState {
  return {
    sample_id: selectedSampleId,
    collection_name: "",
    category: "结构表征",
    technique: "",
    instrument: "",
    captured_at: todayDate(),
    operator: "",
    notes: "",
  };
}

export function CollectionForm({
  samples,
  saving = false,
  selectedSampleId = "",
  onSubmit,
}: CollectionFormProps) {
  const [formState, setFormState] = useState<FormState>(() =>
    buildInitialState(selectedSampleId),
  );

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
    await onSubmit({
      sample_id: trimText(formState.sample_id),
      collection_name: normalizeWhitespace(formState.collection_name),
      category: normalizeWhitespace(formState.category),
      technique: normalizeWhitespace(formState.technique),
      instrument: normalizeWhitespace(formState.instrument),
      captured_at: trimText(formState.captured_at),
      operator: normalizeWhitespace(formState.operator),
      notes: normalizeNoteText(formState.notes),
    });
    setFormState(buildInitialState(formState.sample_id));
  }

  return (
    <form className="form-grid" onSubmit={handleSubmit}>
      <label>
        样品
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
        数据包名称
        <input
          name="collection_name"
          placeholder="例如 TEM report 2026-04-12"
          value={formState.collection_name}
          onChange={handleChange}
        />
      </label>
      <label>
        分类
        <select name="category" value={formState.category} onChange={handleChange}>
          <option>形貌图像</option>
          <option>结构表征</option>
          <option>成分分析</option>
          <option>光谱文件</option>
          <option>测试报告</option>
          <option>原始设备数据</option>
          <option>其他</option>
        </select>
      </label>
      <label>
        技术
        <input
          name="technique"
          placeholder="SEM / TEM / XRD / Raman"
          value={formState.technique}
          onChange={handleChange}
        />
      </label>
      <label>
        设备
        <input
          name="instrument"
          placeholder="设备型号或编号"
          value={formState.instrument}
          onChange={handleChange}
        />
      </label>
      <label>
        采集日期
        <input
          name="captured_at"
          type="date"
          value={formState.captured_at}
          onChange={handleChange}
        />
      </label>
      <label>
        操作人
        <input name="operator" value={formState.operator} onChange={handleChange} />
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
      <div className="form-actions full">
        <button type="submit" disabled={saving}>
          {saving ? "创建中..." : "创建数据包"}
        </button>
      </div>
    </form>
  );
}
