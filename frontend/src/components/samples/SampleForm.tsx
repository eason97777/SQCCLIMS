import { useEffect, useMemo, useState } from "react";
import type { SampleMaintenanceOptions } from "../../stores/sampleMaintenanceStore";
import type { Sample, SamplePayload } from "../../types/sample";
import {
  buildCompatibleSamplePayload,
  getSampleName,
  getSampleProcessType,
  getSampleProjectCode,
  getSampleSeq,
} from "../../utils/sampleFields";
import {
  sampleToNamingInput,
  validateSampleNamingFields,
} from "../../utils/sampleNaming";
import { SAMPLE_STATUS_OPTIONS } from "../../utils/constants";
import {
  normalizeCodeText,
  normalizeNoteText,
  normalizeWhitespace,
} from "../../utils/textNormalize";
import { CandidateCombobox } from "./CandidateCombobox";
import { SelectCombobox } from "./SelectCombobox";

type SampleFormProps = {
  initialValue?: Partial<Sample> | null;
  maintenanceOptions?: SampleMaintenanceOptions;
  samples?: Sample[];
  submitting?: boolean;
  onDraftChange?: (draft: SamplePayload) => void;
  onSubmit: (payload: SamplePayload) => Promise<void> | void;
  onCancel?: () => void;
};

type SampleFormState = {
  projectCode: string;
  sampleName: string;
  processType: string;
  sampleSeq: string;
  responsiblePerson: string;
  status: string;
  remark: string;
};

function buildFormState(sample?: Partial<Sample> | null): SampleFormState {
  const input = sampleToNamingInput(sample ?? {});
  return {
    projectCode: input.projectCode,
    sampleName: input.sampleName,
    processType: input.processType,
    sampleSeq: input.sampleSeq,
    responsiblePerson: input.responsiblePerson ?? "",
    status: input.status || "待测试",
    remark: input.remark ?? "",
  };
}

function getNextSuggestedSeq(samples: Sample[], state: SampleFormState, editingId?: number) {
  const projectCode = normalizeCodeText(state.projectCode);
  const sampleName = normalizeWhitespace(state.sampleName);
  const processType = normalizeWhitespace(state.processType);

  if (!projectCode || !sampleName || !processType) {
    return "";
  }

  const numericSeqs = samples
    .filter((sample) => {
      if (editingId && sample.id === editingId) {
        return false;
      }
      return (
        getSampleProjectCode(sample) === projectCode &&
        getSampleName(sample) === sampleName &&
        getSampleProcessType(sample) === processType
      );
    })
    .map((sample) => Number(getSampleSeq(sample)))
    .filter((value) => Number.isInteger(value) && value > 0);

  if (numericSeqs.length === 0) {
    return "1";
  }

  return String(Math.max(...numericSeqs) + 1);
}

export function SampleForm({
  initialValue,
  maintenanceOptions,
  samples = [],
  submitting = false,
  onDraftChange,
  onSubmit,
  onCancel,
}: SampleFormProps) {
  const [formState, setFormState] = useState<SampleFormState>(() =>
    buildFormState(initialValue),
  );
  const [formError, setFormError] = useState("");

  const suggestedSeq = useMemo(
    () => getNextSuggestedSeq(samples, formState, initialValue?.id),
    [formState, initialValue?.id, samples],
  );
  const draftPayload = useMemo(
    () =>
      buildCompatibleSamplePayload(
        {
          projectCode: normalizeCodeText(formState.projectCode),
          sampleName: normalizeWhitespace(formState.sampleName),
          processType: normalizeWhitespace(formState.processType),
          sampleSeq: normalizeWhitespace(formState.sampleSeq),
          responsiblePerson: normalizeWhitespace(formState.responsiblePerson),
          status: formState.status,
          remark: normalizeNoteText(formState.remark),
        },
        initialValue,
      ),
    [formState, initialValue],
  );

  useEffect(() => {
    onDraftChange?.(draftPayload);
  }, [draftPayload, onDraftChange]);

  function updateField(field: keyof SampleFormState, value: string) {
    setFormError("");
    setFormState((current) => ({
      ...current,
      [field]: value,
    }));
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError("");

    const validation = validateSampleNamingFields(
      formState,
      samples,
      initialValue?.id,
    );

    if (validation.errors.length > 0) {
      setFormError(validation.errors[0]);
      return;
    }

    const { normalized } = validation;

    if (suggestedSeq && normalized.sampleSeq !== suggestedSeq) {
      const confirmed = window.confirm(
        `当前建议样品序号为 ${suggestedSeq}，确认使用自定义序号 ${normalized.sampleSeq} 吗？`,
      );
      if (!confirmed) {
        return;
      }
    }

    await onSubmit(
      buildCompatibleSamplePayload(
        {
          projectCode: normalized.projectCode,
          sampleName: normalized.sampleName,
          processType: normalized.processType,
          sampleSeq: normalized.sampleSeq,
          responsiblePerson: normalized.responsiblePerson,
          status: normalized.status,
          remark: normalizeNoteText(normalized.remark),
        },
        initialValue,
      ),
    );
  }

  function handleReset() {
    setFormError("");
    setFormState(buildFormState(initialValue));
    onCancel?.();
  }

  return (
    <>
      <div className="panel-header">
        <h3>当前样品</h3>
      </div>
      <form className="form-grid current-sample-form" onSubmit={handleSubmit}>
        {formError ? <div className="form-error full">{formError}</div> : null}
        <label>
          项目编号
          <CandidateCombobox
            fieldKey="projectCode"
            required
            value={formState.projectCode}
            options={maintenanceOptions?.sampleCodes ?? []}
            onChange={(value) => updateField("projectCode", value)}
          />
        </label>
        <label>
          样品名称
          <CandidateCombobox
            fieldKey="sampleName"
            required
            value={formState.sampleName}
            options={maintenanceOptions?.sampleNames ?? []}
            onChange={(value) => updateField("sampleName", value)}
          />
        </label>
        <label>
          工艺类型
          <CandidateCombobox
            fieldKey="processType"
            required
            value={formState.processType}
            options={maintenanceOptions?.processTypes ?? []}
            onChange={(value) => updateField("processType", value)}
          />
        </label>
        <label>
          样品序号
          <CandidateCombobox
            fieldKey="sampleSeq"
            required
            value={formState.sampleSeq}
            options={maintenanceOptions?.sampleSeqs ?? []}
            onChange={(value) => updateField("sampleSeq", value)}
          />
        </label>
        <label>
          负责人
          <CandidateCombobox
            fieldKey="responsiblePerson"
            value={formState.responsiblePerson}
            placeholder="请输入负责人"
            options={maintenanceOptions?.owners ?? []}
            onChange={(value) => updateField("responsiblePerson", value)}
          />
        </label>
        <label>
          状态
          <SelectCombobox
            name="status"
            value={formState.status}
            options={SAMPLE_STATUS_OPTIONS}
            onChange={(value) => updateField("status", value)}
          />
        </label>
        <label className="full">
          备注
          <textarea
            name="remark"
            rows={3}
            placeholder="请输入备注信息。"
            value={formState.remark}
            onChange={(event) => updateField("remark", event.target.value)}
          />
        </label>
        <div className="form-actions full">
          <button type="submit" disabled={submitting}>
            {submitting ? "保存中..." : "保存"}
          </button>
          <button
            className="ghost-button"
            type="button"
            onClick={handleReset}
            disabled={submitting}
          >
            清空
          </button>
        </div>
      </form>
    </>
  );
}
