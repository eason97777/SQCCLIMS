import { apiClient } from "./apiClient";
import type { ProcessingRequest, ProcessingResultRecord } from "../types/processing";

export function getProcessingResults() {
  return apiClient.get<ProcessingResultRecord[]>("/api/process-results");
}

export function runProcessing(payload: ProcessingRequest) {
  return apiClient.postJson<ProcessingResultRecord, ProcessingRequest>(
    "/api/process",
    payload,
  );
}

// TODO: backend currently has no GET /api/process-results/:id route; detail reads depend on list payload.
