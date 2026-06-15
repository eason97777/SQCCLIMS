import { apiClient } from "./apiClient";
import type {
  BulkCreateResult,
  CsvImportRecord,
  TestDataListParams,
  TestDataPayload,
  TestDataRecord,
} from "../types/testData";
import type { DeleteResponse } from "../types/sample";

export function getTestData(params: TestDataListParams = {}) {
  return apiClient.get<TestDataRecord[]>("/api/test-data", params);
}

export function createTestData(payload: TestDataPayload) {
  return apiClient.postJson<TestDataRecord, TestDataPayload>("/api/test-data", payload);
}

export function importTestDataCsv(records: CsvImportRecord[]) {
  return apiClient.postJson<BulkCreateResult, { records: CsvImportRecord[] }>(
    "/api/test-data/bulk",
    { records },
  );
}

export function deleteTestData(recordId: string | number) {
  return apiClient.delete<DeleteResponse>(`/api/test-data/${recordId}`);
}
