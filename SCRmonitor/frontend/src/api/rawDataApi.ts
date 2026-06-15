import { apiClient } from "./apiClient";
import type {
  RawDataListParams,
  RawDataPayload,
  RawDataRecord,
  MockParsedDataPayload,
  ParsedDataRecord,
  ParsedRecordOptionsResponse,
  ParsedRecordsParams,
  ParsedRecordsResponse,
  ProcessingJobRecord,
  ResistanceSummaryRequest,
  ResistanceSummaryResponse,
  VisualizationPayload,
  DeleteRawDataFileResponse,
} from "../types/rawData";
import type { DeleteResponse } from "../types/sample";

export function getRawData(params: RawDataListParams = {}) {
  return apiClient.get<RawDataRecord[]>("/api/raw-data", params);
}

export function createRawData(payload: RawDataPayload) {
  return apiClient.postJson<RawDataRecord, RawDataPayload>("/api/raw-data", payload);
}

export function getRawDataDetail(rawDataId: string | number) {
  return apiClient.get<RawDataRecord>(`/api/raw-data/${rawDataId}`);
}

export function uploadRawDataFiles(rawDataId: string | number, files: File[]) {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file, file.name);
  }
  return apiClient.postFormData<RawDataRecord>(
    `/api/raw-data/${rawDataId}/files`,
    formData,
  );
}

export function parseRawData(rawDataId: string | number, parserName = "resistance_csv_parser") {
  return apiClient.postJson<RawDataRecord, { parser_name: string }>(
    `/api/raw-data/${rawDataId}/parse`,
    { parser_name: parserName },
  );
}

export function deleteRawData(rawDataId: string | number) {
  return apiClient.delete<DeleteResponse>(`/api/raw-data/${rawDataId}`);
}

export function rawDataFileDownloadUrl(fileId: string | number) {
  return apiClient.buildUrl(`/api/raw-data-files/${fileId}/download`);
}

export function deleteRawDataFile(fileId: string | number) {
  return apiClient.delete<DeleteRawDataFileResponse>(`/api/raw-data-files/${fileId}`);
}

export function getParsedData(params: RawDataListParams = {}) {
  return apiClient.get<ParsedDataRecord[]>("/api/parsed-data", params);
}

export function getParsedDataDetail(parsedDataId: string | number) {
  return apiClient.get<ParsedDataRecord>(`/api/parsed-data/${parsedDataId}`);
}

export function getParsedDataRecords(
  parsedDataId: string | number,
  params: ParsedRecordsParams = {},
) {
  return apiClient.get<ParsedRecordsResponse>(`/api/parsed-data/${parsedDataId}/records`, params);
}

export function getParsedRecordOptions(parsedDataId: string | number) {
  return apiClient.get<ParsedRecordOptionsResponse>(`/api/parsed-data/${parsedDataId}/record-options`);
}

export function getResistanceSummary(
  parsedDataId: string | number,
  payload: ResistanceSummaryRequest = {},
) {
  return apiClient.postJson<ResistanceSummaryResponse, ResistanceSummaryRequest>(
    `/api/parsed-data/${parsedDataId}/resistance-summary`,
    payload,
  );
}

export function createMockParsedData(payload: MockParsedDataPayload) {
  return apiClient.postJson<ParsedDataRecord, MockParsedDataPayload>(
    "/api/parsed-data/mock",
    payload,
  );
}

export function visualizeParsedData(
  parsedDataId: string | number,
  payload: VisualizationPayload = { chart_type: "violin" },
) {
  return apiClient.postJson<ProcessingJobRecord, VisualizationPayload>(
    `/api/parsed-data/${parsedDataId}/visualize`,
    payload,
  );
}

export function getProcessingJobs(params: RawDataListParams = {}) {
  return apiClient.get<ProcessingJobRecord[]>("/api/processing-jobs", params);
}

export function visualizationChartsDownloadUrl(jobId: string | number, chartKeys: string[]) {
  return apiClient.buildUrl(`/api/processing-jobs/${jobId}/charts/download`, {
    chart_key: chartKeys,
  });
}
