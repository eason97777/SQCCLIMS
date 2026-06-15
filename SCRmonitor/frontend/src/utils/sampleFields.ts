import type { Sample, SamplePayload } from "../types/sample";

const SAMPLE_STATUS_PRIORITY = new Map([
  ["待测试", 0],
  ["测试中", 1],
  ["已完成", 2],
  ["已归档", 3],
]);

function valueOrEmpty(value: unknown) {
  if (value === null || value === undefined) {
    return "";
  }

  return String(value);
}

export function getSampleProjectCode(sample: Partial<Sample>) {
  return valueOrEmpty(
    sample.projectCode || sample.sample_code || sample.code || sample.sampleNo || sample.id,
  );
}

export function getSampleUid(sample: Partial<Sample>) {
  return valueOrEmpty(sample.sample_uid);
}

export function getSampleName(sample: Partial<Sample>) {
  return valueOrEmpty(sample.sampleName || sample.name);
}

export function getSampleProcessType(sample: Partial<Sample>) {
  return valueOrEmpty(sample.processType || sample.category);
}

export function getSampleSeq(sample: Partial<Sample>) {
  return valueOrEmpty(sample.sampleSeq || sample.batch);
}

export function getSampleOwner(sample: Partial<Sample>) {
  return valueOrEmpty(
    sample.responsiblePerson ||
      sample.owner ||
      sample.manager ||
      sample.leader ||
      sample.assignee,
  );
}

export function getSampleRemark(sample: Partial<Sample>) {
  return valueOrEmpty(sample.remark || sample.notes || sample.comment);
}

export function getSampleStatus(sample: Partial<Sample>) {
  return valueOrEmpty(sample.status);
}

export function buildSampleDisplayCode(sample: Partial<Sample>) {
  return [
    getSampleProjectCode(sample),
    getSampleName(sample),
    getSampleProcessType(sample),
    getSampleSeq(sample),
  ]
    .map((value) => value || "-")
    .join("-");
}

export function getSampleDisplayCode(sample: Partial<Sample>) {
  return valueOrEmpty(sample.sample_display_code) || buildSampleDisplayCode(sample);
}

export function getSampleDisplayLabel(sample: Partial<Sample>) {
  const displayCode = getSampleDisplayCode(sample);
  const uid = getSampleUid(sample);
  return uid ? `${displayCode} (${uid})` : displayCode;
}

export function valueOrDash(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }

  return String(value);
}

function compareText(a: string, b: string) {
  if (!a && !b) {
    return 0;
  }
  if (!a) {
    return 1;
  }
  if (!b) {
    return -1;
  }
  return a.localeCompare(b, "zh-Hans-CN", {
    numeric: true,
    sensitivity: "base",
  });
}

function compareSampleSeq(a: string, b: string) {
  const aNumber = Number(a);
  const bNumber = Number(b);
  const aIsNumeric = a.trim() !== "" && Number.isInteger(aNumber);
  const bIsNumeric = b.trim() !== "" && Number.isInteger(bNumber);

  if (aIsNumeric && bIsNumeric) {
    return aNumber - bNumber;
  }

  return compareText(a, b);
}

export function sortSamplesByBusinessRule(samples: Sample[]) {
  return [...samples].sort((a, b) => {
    const statusDiff =
      (SAMPLE_STATUS_PRIORITY.get(getSampleStatus(a)) ?? 99) -
      (SAMPLE_STATUS_PRIORITY.get(getSampleStatus(b)) ?? 99);
    if (statusDiff !== 0) {
      return statusDiff;
    }

    const projectDiff = compareText(getSampleProjectCode(a), getSampleProjectCode(b));
    if (projectDiff !== 0) {
      return projectDiff;
    }

    const nameDiff = compareText(getSampleName(a), getSampleName(b));
    if (nameDiff !== 0) {
      return nameDiff;
    }

    const seqDiff = compareSampleSeq(getSampleSeq(a), getSampleSeq(b));
    if (seqDiff !== 0) {
      return seqDiff;
    }

    return a.id - b.id;
  });
}

type BuildSamplePayloadInput = {
  projectCode: string;
  sampleName: string;
  processType: string;
  sampleSeq: string;
  responsiblePerson?: string;
  status: string;
  remark?: string;
};

export function buildCompatibleSamplePayload(
  input: BuildSamplePayloadInput,
  previousSample?: Partial<Sample> | null,
): SamplePayload {
  return {
    projectCode: input.projectCode,
    sampleName: input.sampleName,
    processType: input.processType,
    sampleSeq: input.sampleSeq,
    responsiblePerson: input.responsiblePerson,
    remark: input.remark,
    sample_code: input.projectCode,
    name: input.sampleName,
    category: input.processType,
    batch: input.sampleSeq,
    owner: input.responsiblePerson ?? previousSample?.owner ?? "",
    received_at: previousSample?.received_at || "",
    notes: input.remark ?? previousSample?.notes ?? "",
    status: input.status,
  };
}
