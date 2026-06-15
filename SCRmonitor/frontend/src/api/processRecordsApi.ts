import { apiClient } from "./apiClient";
import type { Sample } from "../types/sample";
import type {
  ProcessRecord,
  ProcessRecordPayload,
  ProcessSampleLookupResponse,
  ProcessStage,
} from "../types/processRecord";

export function lookupProcessSample(
  query: string,
  stage: ProcessStage = "发料",
  scope?: { layer_name?: string; record_no?: number },
) {
  return apiClient.get<ProcessSampleLookupResponse>("/api/process-records/sample-lookup", {
    query,
    stage,
    ...scope,
  });
}

export function getProcessSampleSuggestions(query: string, stage?: ProcessStage) {
  return apiClient.get<Sample[]>("/api/process-records/sample-lookup", {
    query,
    mode: "suggestions",
    ...(stage ? { stage } : {}),
  });
}

export function getProcessFieldSuggestions(field: string, query: string) {
  return apiClient.get<string[]>("/api/process-records/field-suggestions", {
    field,
    query,
  });
}

export function getProcessLayerSuggestions(sampleId: number, query: string) {
  return apiClient.get<string[]>("/api/process-records/layers", {
    sample_id: sampleId,
    query,
  });
}

export function saveProcessRecord(payload: ProcessRecordPayload) {
  return apiClient.postJson<ProcessRecord, ProcessRecordPayload>("/api/process-records", payload);
}
