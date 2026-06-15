import type { Sample } from "../../types/sample";
import { getSampleDisplayLabel } from "../../utils/sampleFields";
import { ProcessingTypeSelector } from "./ProcessingTypeSelector";

type ProcessingFormState = {
  job_name: string;
  sample_id: string;
  metric_name: string;
  method: "stats" | "qc" | "normalize";
  lower_limit: string;
  upper_limit: string;
};

type ProcessingParamFormProps = {
  samples: Sample[];
  metricOptions: string[];
  formState: ProcessingFormState;
  running?: boolean;
  onChange: (nextState: Partial<ProcessingFormState>) => void;
  onSubmit: () => Promise<void> | void;
};

export function ProcessingParamForm({
  samples,
  metricOptions,
  formState,
  running = false,
  onChange,
  onSubmit,
}: ProcessingParamFormProps) {
  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onSubmit();
  }

  return (
    <>
      <div className="panel-header">
        <h3>处理任务</h3>
      </div>
      <form className="form-grid" onSubmit={handleSubmit}>
        <label className="full">
          任务名称
          <input
            name="job_name"
            value={formState.job_name}
            onChange={(event) => onChange({ job_name: event.target.value })}
          />
        </label>
        <label className="full">
          样品范围
          <select
            name="sample_id"
            value={formState.sample_id}
            onChange={(event) => onChange({ sample_id: event.target.value })}
          >
            <option value="">全部样品</option>
            {samples.map((sample) => (
              <option key={sample.id} value={sample.id}>
                {getSampleDisplayLabel(sample)}
              </option>
            ))}
          </select>
        </label>
        <label className="full">
          指标筛选
          <input
            list="metric-options"
            name="metric_name"
            placeholder="留空为全部指标"
            value={formState.metric_name}
            onChange={(event) => onChange({ metric_name: event.target.value })}
          />
          <datalist id="metric-options">
            {metricOptions.map((metric) => (
              <option key={metric} value={metric} />
            ))}
          </datalist>
        </label>

        <ProcessingTypeSelector
          selectedType={formState.method}
          onChange={(method) => onChange({ method })}
        />

        <label>
          下限
          <input
            name="lower_limit"
            type="number"
            step="any"
            value={formState.lower_limit}
            onChange={(event) => onChange({ lower_limit: event.target.value })}
          />
        </label>
        <label>
          上限
          <input
            name="upper_limit"
            type="number"
            step="any"
            value={formState.upper_limit}
            onChange={(event) => onChange({ upper_limit: event.target.value })}
          />
        </label>
        <div className="form-actions full">
          <button type="submit" disabled={running}>
            {running ? "运行中..." : "运行处理"}
          </button>
        </div>
      </form>
    </>
  );
}
