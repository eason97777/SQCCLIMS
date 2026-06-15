import { apiClient } from "./apiClient";
import type { DeleteResponse, Sample, SampleListParams, SamplePayload } from "../types/sample";

export function getSamples(params: SampleListParams = {}) {
  return apiClient.get<Sample[]>("/api/samples", params);
}

export function createSample(payload: SamplePayload) {
  return apiClient.postJson<Sample, SamplePayload>("/api/samples", payload);
}

export function updateSample(sampleId: string | number, payload: SamplePayload) {
  return apiClient.putJson<Sample, SamplePayload>(`/api/samples/${sampleId}`, payload);
}

export function deleteSample(sampleId: string | number) {
  return apiClient.delete<DeleteResponse>(`/api/samples/${sampleId}`);
}

// TODO: backend currently has no GET /api/samples/:id route; detail reads still depend on list data.
