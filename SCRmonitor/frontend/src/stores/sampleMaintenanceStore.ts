import { useCallback, useEffect, useMemo, useState } from "react";
import type { Sample } from "../types/sample";
import {
  getSampleName,
  getSampleOwner,
  getSampleProcessType,
  getSampleProjectCode,
  getSampleSeq,
} from "../utils/sampleFields";
import {
  normalizeCodeText,
  normalizeWhitespace,
} from "../utils/textNormalize";

export type SampleMaintenanceOptions = {
  sampleCodes: string[];
  sampleNames: string[];
  processTypes: string[];
  sampleSeqs: string[];
  owners: string[];
};

type MaintenanceField = keyof SampleMaintenanceOptions;

const STORAGE_KEY = "scrmonitor.sampleMaintenanceOptions.v3";

const EMPTY_OPTIONS: SampleMaintenanceOptions = {
  sampleCodes: [],
  sampleNames: [],
  processTypes: [],
  sampleSeqs: [],
  owners: [],
};

function uniqueSorted(values: Array<string | null | undefined>) {
  return Array.from(
    new Set(values.map((value) => normalizeWhitespace(value)).filter(Boolean)),
  ).sort((a, b) => a.localeCompare(b, "zh-Hans-CN"));
}

function readStoredOptions(): SampleMaintenanceOptions {
  if (typeof window === "undefined") {
    return EMPTY_OPTIONS;
  }

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return EMPTY_OPTIONS;
    }

    const parsed = JSON.parse(raw) as Partial<SampleMaintenanceOptions>;
    return {
      sampleCodes: uniqueSorted(parsed.sampleCodes ?? []),
      sampleNames: uniqueSorted(parsed.sampleNames ?? []),
      processTypes: uniqueSorted(parsed.processTypes ?? []),
      sampleSeqs: uniqueSorted(parsed.sampleSeqs ?? []),
      owners: uniqueSorted(parsed.owners ?? []),
    };
  } catch {
    return EMPTY_OPTIONS;
  }
}

function saveStoredOptions(options: SampleMaintenanceOptions) {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(options));
}

function mergeOptions(
  maintained: SampleMaintenanceOptions,
  samples: Sample[],
): SampleMaintenanceOptions {
  return {
    sampleCodes: uniqueSorted([
      ...maintained.sampleCodes,
      ...samples.map((sample) => normalizeCodeText(getSampleProjectCode(sample))),
    ]),
    sampleNames: uniqueSorted([
      ...maintained.sampleNames,
      ...samples.map((sample) => getSampleName(sample)),
    ]),
    processTypes: uniqueSorted([
      ...maintained.processTypes,
      ...samples.map((sample) => getSampleProcessType(sample)),
    ]),
    sampleSeqs: uniqueSorted([
      ...maintained.sampleSeqs,
      ...samples.map((sample) => normalizeCodeText(getSampleSeq(sample))),
    ]),
    owners: uniqueSorted([
      ...maintained.owners,
      ...samples.map((sample) => getSampleOwner(sample)),
    ]),
  };
}

export function useSampleMaintenanceStore(samples: Sample[]) {
  const [maintainedOptions, setMaintainedOptions] =
    useState<SampleMaintenanceOptions>(() => readStoredOptions());

  useEffect(() => {
    saveStoredOptions(maintainedOptions);
  }, [maintainedOptions]);

  const options = useMemo(
    () => mergeOptions(maintainedOptions, samples),
    [maintainedOptions, samples],
  );

  const addOption = useCallback((field: MaintenanceField, value: string) => {
    const normalized =
      field === "sampleCodes" || field === "sampleSeqs"
        ? normalizeCodeText(value)
        : normalizeWhitespace(value);

    if (!normalized) {
      return;
    }

    setMaintainedOptions((current) => ({
      ...current,
      [field]: uniqueSorted([...current[field], normalized]),
    }));
  }, []);

  const removeOption = useCallback((field: MaintenanceField, value: string) => {
    setMaintainedOptions((current) => ({
      ...current,
      [field]: current[field].filter((item) => item !== value),
    }));
  }, []);

  return {
    options,
    addOption,
    removeOption,
  };
}
