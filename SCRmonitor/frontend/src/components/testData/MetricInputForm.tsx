import { useState } from "react";
import type { Sample } from "../../types/sample";
import type { TestDataPayload } from "../../types/testData";
import { getSampleDisplayLabel } from "../../utils/sampleFields";
import {
  normalizeNoteText,
  normalizeNumericText,
  normalizeWhitespace,
  toNumberOrNull,
  trimText,
} from "../../utils/textNormalize";

type MetricInputFormProps = {
  samples: Sample[];
  saving?: boolean;
  onSubmit: (payload: TestDataPayload) => Promise<void> | void;
};

type MetricFormState = {
  sample_id: string;
  test_name: string;
  metric_name: string;
  numeric_value: string;
  unit: string;
  measured_at: string;
  operator: string;
  environment: string;
  raw_note: string;
};

function localDateTimeValue() {
  const date = new Date();
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
  return date.toISOString().slice(0, 16);
}

function buildInitialState(): MetricFormState {
  return {
    sample_id: "",
    test_name: "",
    metric_name: "",
    numeric_value: "",
    unit: "",
    measured_at: localDateTimeValue(),
    operator: "",
    environment: "",
    raw_note: "",
  };
}

export function MetricInputForm({
  samples,
  saving = false,
  onSubmit,
}: MetricInputFormProps) {
  const [formState, setFormState] = useState<MetricFormState>(buildInitialState);
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
    const testName = normalizeWhitespace(formState.test_name);
    const metricName = normalizeWhitespace(formState.metric_name);
    const numericText = normalizeNumericText(formState.numeric_value);
    const numericValue = toNumberOrNull(numericText);

    if (!sampleId || !testName || !metricName || numericValue === null) {
      setFormError("请选择样品编号，并填写测试项目、指标名称和有效数值。");
      return;
    }

    await onSubmit({
      sample_id: sampleId,
      test_name: testName,
      metric_name: metricName,
      numeric_value: numericText,
      unit: normalizeWhitespace(formState.unit),
      measured_at: trimText(formState.measured_at),
      operator: normalizeWhitespace(formState.operator),
      environment: normalizeWhitespace(formState.environment),
      raw_note: normalizeNoteText(formState.raw_note),
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
        <h3>数值数据录入</h3>
      </div>
      <form className="form-grid" onSubmit={handleSubmit}>
        {formError ? <div className="form-error full">{formError}</div> : null}
        <label className="full">
          样品编号
          <select
            name="sample_id"
            required
            value={formState.sample_id}
            onChange={handleChange}
          >
            <option value="">选择样品编号</option>
            {samples.map((sample) => (
              <option key={sample.id} value={sample.id}>
                {getSampleDisplayLabel(sample)}
              </option>
            ))}
          </select>
        </label>
        <label>
          测试项目
          <input
            name="test_name"
            required
            value={formState.test_name}
            onChange={handleChange}
          />
        </label>
        <label>
          指标名称
          <input
            name="metric_name"
            required
            value={formState.metric_name}
            onChange={handleChange}
          />
        </label>
        <label>
          数值
          <input
            name="numeric_value"
            inputMode="decimal"
            required
            value={formState.numeric_value}
            onChange={handleChange}
          />
        </label>
        <label>
          单位
          <input name="unit" value={formState.unit} onChange={handleChange} />
        </label>
        <label>
          测试时间
          <input
            name="measured_at"
            type="datetime-local"
            value={formState.measured_at}
            onChange={handleChange}
          />
        </label>
        <label>
          操作人员
          <input name="operator" value={formState.operator} onChange={handleChange} />
        </label>
        <label>
          环境条件
          <input
            name="environment"
            value={formState.environment}
            onChange={handleChange}
          />
        </label>
        <label className="full">
          原始备注
          <textarea
            name="raw_note"
            rows={3}
            value={formState.raw_note}
            onChange={handleChange}
          />
        </label>
        <div className="form-actions full">
          <button type="submit" disabled={saving}>
            {saving ? "保存中..." : "保存数据"}
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
