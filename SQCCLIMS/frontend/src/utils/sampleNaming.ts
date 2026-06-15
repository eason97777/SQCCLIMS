import type { Sample } from "../types/sample";
import {
  buildSampleDisplayCode as buildFallbackSampleDisplayCode,
  getSampleName,
  getSampleOwner,
  getSampleProcessType,
  getSampleProjectCode,
  getSampleRemark,
  getSampleSeq,
  getSampleStatus,
} from "./sampleFields";
import { normalizeCodeText, normalizeNoteText, normalizeWhitespace } from "./textNormalize";

export type SampleNamingInput = {
  projectCode: string;
  sampleName: string;
  processType: string;
  sampleSeq: string;
  responsiblePerson?: string;
  status: string;
  remark?: string;
};

export type NormalizedSampleNamingInput = Required<SampleNamingInput>;

const GARBLED_MARKERS = ["�", "锟", "鎬", "鏍", "����"];

function normalizeRequiredText(value: string) {
  return normalizeWhitespace(value);
}

export function normalizeSampleNamingInput(
  input: SampleNamingInput,
): NormalizedSampleNamingInput {
  return {
    projectCode: normalizeCodeText(input.projectCode),
    sampleName: normalizeRequiredText(input.sampleName),
    processType: normalizeRequiredText(input.processType),
    sampleSeq: normalizeCodeText(input.sampleSeq),
    responsiblePerson: normalizeWhitespace(input.responsiblePerson ?? ""),
    status: normalizeWhitespace(input.status),
    remark: normalizeNoteText(input.remark ?? ""),
  };
}

export function buildSampleDisplayCode(input: SampleNamingInput) {
  return buildFallbackSampleDisplayCode({
    projectCode: input.projectCode,
    sampleName: input.sampleName,
    processType: input.processType,
    sampleSeq: input.sampleSeq,
  });
}

export function hasGarbledText(value: string | null | undefined) {
  const source = String(value ?? "");
  return GARBLED_MARKERS.some((marker) => source.includes(marker));
}

function hasOnlyPunctuation(value: string) {
  return !/[A-Za-z0-9\u4e00-\u9fff]/.test(value);
}

function isSameSampleIdentity(sample: Sample, input: NormalizedSampleNamingInput) {
  return (
    normalizeCodeText(getSampleProjectCode(sample)) === input.projectCode &&
    normalizeWhitespace(getSampleName(sample)) === input.sampleName &&
    normalizeWhitespace(getSampleProcessType(sample)) === input.processType &&
    normalizeCodeText(getSampleSeq(sample)) === input.sampleSeq
  );
}

export function validateSampleNamingFields(
  input: SampleNamingInput,
  samples: Sample[] = [],
  editingId?: number,
) {
  const normalized = normalizeSampleNamingInput(input);
  const errors: string[] = [];

  if (!normalized.projectCode) {
    errors.push("项目编号不能为空");
  }
  if (!normalized.sampleName) {
    errors.push("样品名称不能为空");
  }
  if (!normalized.processType) {
    errors.push("工艺类型不能为空");
  }
  if (!normalized.sampleSeq) {
    errors.push("样品序号不能为空");
  }
  if (!normalized.status) {
    errors.push("样品状态不能为空");
  }

  const fieldsForGarbledCheck = [
    normalized.projectCode,
    normalized.sampleName,
    normalized.processType,
    normalized.sampleSeq,
    normalized.responsiblePerson,
    normalized.status,
    normalized.remark,
  ];

  if (fieldsForGarbledCheck.some(hasGarbledText)) {
    errors.push("检测到疑似乱码字符，请检查字段内容后再保存。");
  }

  if (
    normalized.sampleSeq &&
    (normalized.sampleSeq.length > 32 || hasOnlyPunctuation(normalized.sampleSeq))
  ) {
    errors.push("样品序号格式可能不规范，请检查。");
  }

  const duplicate = samples.find((sample) => {
    if (editingId && sample.id === editingId) {
      return false;
    }
    return isSameSampleIdentity(sample, normalized);
  });

  if (duplicate) {
    errors.push("当前样品命名组合已存在，请修改项目编号、样品名称、工艺类型或样品序号。");
  }

  return {
    errors,
    normalized,
    sampleDisplayCode: buildSampleDisplayCode(normalized),
  };
}

export function sampleToNamingInput(sample: Partial<Sample>): SampleNamingInput {
  return {
    projectCode: getSampleProjectCode(sample),
    sampleName: getSampleName(sample),
    processType: getSampleProcessType(sample),
    sampleSeq: getSampleSeq(sample),
    responsiblePerson: getSampleOwner(sample),
    status: getSampleStatus(sample),
    remark: getSampleRemark(sample),
  };
}
