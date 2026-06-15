import { apiClient } from "./apiClient";
import type {
  PerformanceDataset,
  PerformanceDatasetDeletePreview,
  PerformanceDatasetFields,
  PerformanceDatasetFile,
  PerformanceDatasetListParams,
} from "../types/performance";
import type { DeleteResponse } from "../types/sample";

export function getPerformanceDatasets(params: PerformanceDatasetListParams = {}) {
  return apiClient.get<PerformanceDataset[]>("/api/performance-datasets", params);
}

export function getPerformanceDatasetFiles(datasetId: string | number) {
  return apiClient.get<PerformanceDatasetFile[]>(
    `/api/performance-datasets/${datasetId}/files`,
  );
}

export function uploadPerformanceDataset(
  fields: PerformanceDatasetFields,
  files: File[],
) {
  const formData = new FormData();

  for (const [key, value] of Object.entries(fields)) {
    if (value !== undefined && value !== null && value !== "") {
      formData.append(key, String(value));
    }
  }

  for (const file of files) {
    const fileName =
      "webkitRelativePath" in file &&
      typeof file.webkitRelativePath === "string" &&
      file.webkitRelativePath
        ? file.webkitRelativePath
        : file.name;

    formData.append("files", file, fileName);
  }

  return apiClient.postFormData<PerformanceDataset>(
    "/api/performance-datasets",
    formData,
  );
}

export function deletePerformanceDataset(datasetId: string | number) {
  return apiClient.delete<DeleteResponse>(`/api/performance-datasets/${datasetId}`);
}

export function getPerformanceDatasetDeletePreview(datasetId: string | number) {
  return apiClient.get<PerformanceDatasetDeletePreview>(
    `/api/performance-datasets/${datasetId}/delete-preview`,
  );
}
