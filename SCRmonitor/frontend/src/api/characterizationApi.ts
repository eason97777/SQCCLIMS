import { apiClient } from "./apiClient";
import type {
  CharacterizationCollection,
  CharacterizationCollectionPayload,
  CharacterizationFile,
  CharacterizationFilesParams,
  CharacterizationSampleListItem,
  CharacterizationTree,
  CharacterizationUploadFields,
  CharacterizationUploadResult,
} from "../types/characterization";
import type { DeleteResponse } from "../types/sample";

export function getCharacterizationFiles(params: CharacterizationFilesParams = {}) {
  return apiClient.get<CharacterizationFile[]>("/api/characterization-files", params);
}

export function getCharacterizationSamples(query = "") {
  return apiClient.get<CharacterizationSampleListItem[]>("/api/characterization/samples", {
    query,
  });
}

export function getCharacterizationTree(sampleId: string | number, query = "") {
  return apiClient.get<CharacterizationTree>(
    `/api/samples/${sampleId}/characterization-tree`,
    { query },
  );
}

export function createCharacterizationCollection(
  payload: CharacterizationCollectionPayload,
) {
  return apiClient.postJson<CharacterizationCollection, CharacterizationCollectionPayload>(
    "/api/characterization-collections",
    payload,
  );
}

export function getCharacterizationCollection(collectionId: string | number) {
  return apiClient.get<CharacterizationCollection>(
    `/api/characterization-collections/${collectionId}`,
  );
}

export function getCharacterizationFile(fileId: string | number) {
  return apiClient.get<CharacterizationFile>(`/api/characterization-files/${fileId}`);
}

export function uploadCharacterizationFiles(
  fields: CharacterizationUploadFields,
  files: File[],
) {
  const formData = new FormData();

  for (const [key, value] of Object.entries(fields)) {
    if (value !== undefined && value !== null && value !== "") {
      formData.append(key, String(value));
    }
  }

  for (const file of files) {
    formData.append("files", file, file.name);
  }

  return apiClient.postFormData<CharacterizationUploadResult>(
    "/api/characterization-files",
    formData,
  );
}

export function deleteCharacterizationFile(fileId: string | number) {
  return apiClient.delete<DeleteResponse>(`/api/characterization-files/${fileId}`);
}

export function buildCharacterizationPreviewUrl(fileId: string | number) {
  return apiClient.buildUrl(`/api/characterization-files/${fileId}/preview`);
}

export function buildCharacterizationDownloadUrl(fileId: string | number) {
  return apiClient.buildUrl(`/api/characterization-files/${fileId}/download`);
}

export function getCharacterizationPreviewText(fileId: string | number) {
  return apiClient.getText(`/api/characterization-files/${fileId}/preview`);
}

export function getCharacterizationPreviewBlob(fileId: string | number) {
  return apiClient.getBlob(`/api/characterization-files/${fileId}/preview`);
}

export function downloadCharacterizationFile(fileId: string | number) {
  return apiClient.getBlob(`/api/characterization-files/${fileId}/download`);
}
