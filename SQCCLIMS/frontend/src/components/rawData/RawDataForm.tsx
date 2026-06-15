import { useState } from "react";
import type { Sample } from "../../types/sample";
import type { RawDataPayload } from "../../types/rawData";
import { RAW_DATA_TYPE_OPTIONS } from "../../utils/constants";
import { getSampleDisplayLabel } from "../../utils/sampleFields";
import {
  normalizeNoteText,
  normalizeWhitespace,
  trimText,
} from "../../utils/textNormalize";

type RawDataFormProps = {
  samples: Sample[];
  saving?: boolean;
  onSubmit: (payload: RawDataPayload) => Promise<void> | void;
};

type RawDataFormState = {
  sample_id: string;
  raw_data_name: string;
  data_type: string;
  source_type: string;
  instrument: string;
  operator: string;
  measured_at: string;
  notes: string;
};

function localDateTimeValue() {
  const date = new Date();
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
  return date.toISOString().slice(0, 16);
}

function buildInitialState(): RawDataFormState {
  return {
    sample_id: "",
    raw_data_name: "",
    data_type: "generic_file",
    source_type: "",
    instrument: "",
    operator: "",
    measured_at: localDateTimeValue(),
    notes: "",
  };
}

export function RawDataForm({ samples, saving = false, onSubmit }: RawDataFormProps) {
  const [formState, setFormState] = useState<RawDataFormState>(buildInitialState);
  const [formError, setFormError] = useState("");

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
    setFormError("");

    const sampleId = trimText(formState.sample_id);
    const rawDataName = normalizeWhitespace(formState.raw_data_name);
    const dataType = trimText(formState.data_type);

    if (!sampleId || !rawDataName || !dataType) {
      setFormError("请选择样品，并填写 Raw Data 名称和数据类型。");
      return;
    }

    await onSubmit({
      sample_id: sampleId,
      raw_data_name: rawDataName,
      data_type: dataType,
      source_type: normalizeWhitespace(formState.source_type),
      instrument: normalizeWhitespace(formState.instrument),
      operator: normalizeWhitespace(formState.operator),
      measured_at: trimText(formState.measured_at),
      notes: normalizeNoteText(formState.notes),
    });

    setFormState(buildInitialState());
  }

  function handleReset() {
    setFormError("");
    setFormState(buildInitialState());
  }

  return (
    <>
      <div className="panel-header">
        <h3>新建 Raw Data</h3>
      </div>
      <form className="form-grid raw-data-form-grid" onSubmit={handleSubmit}>
        {formError ? <div className="form-error full">{formError}</div> : null}
        <label>
          样品 <span className="required-mark">*</span>
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
          Raw Data 名称 <span className="required-mark">*</span>
          <input
            name="raw_data_name"
            required
            placeholder="请输入 Raw Data 名称"
            value={formState.raw_data_name}
            onChange={handleChange}
          />
        </label>
        <label>
          数据类型 <span className="required-mark">*</span>
          <select
            name="data_type"
            required
            value={formState.data_type}
            onChange={handleChange}
          >
            {RAW_DATA_TYPE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          来源类型
          <input
            name="source_type"
            placeholder="请输入来源类型"
            value={formState.source_type}
            onChange={handleChange}
          />
        </label>
        <label>
          仪器
          <input
            name="instrument"
            placeholder="请输入仪器"
            value={formState.instrument}
            onChange={handleChange}
          />
        </label>
        <label>
          操作人员
          <input
            name="operator"
            placeholder="请输入操作人员"
            value={formState.operator}
            onChange={handleChange}
          />
        </label>
        <label>
          测量时间
          <input
            name="measured_at"
            type="datetime-local"
            value={formState.measured_at}
            onChange={handleChange}
          />
        </label>
        <label className="full">
          备注
          <textarea
            name="notes"
            rows={3}
            placeholder="请输入备注信息（可选）"
            value={formState.notes}
            onChange={handleChange}
          />
        </label>
        <div className="form-actions full">
          <button type="submit" disabled={saving}>
            {saving ? "创建中..." : "创建"}
          </button>
          <button
            className="ghost-button"
            type="button"
            onClick={handleReset}
            disabled={saving}
          >
            清空
          </button>
        </div>
      </form>
    </>
  );
}
