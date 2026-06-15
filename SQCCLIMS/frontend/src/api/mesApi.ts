import { apiClient } from "./apiClient";
import type {
  AdvanceMesSampleRoutePayload,
  CreateMesRouteLayerPayload,
  CreateMesRouteStepPayload,
  CreateMesRouteTemplatePayload,
  CreateMesSampleRoutePayload,
  MesRouteTemplate,
  MesSampleRoute,
  UpdateMesRouteStepPayload,
} from "../types/mes";

export function getMesRouteTemplateByProject(projectCode: string) {
  return apiClient.get<MesRouteTemplate>("/api/mes-route-templates/by-project", {
    project_code: projectCode,
  });
}

export function createMesRouteTemplate(payload: CreateMesRouteTemplatePayload) {
  return apiClient.postJson<MesRouteTemplate, CreateMesRouteTemplatePayload>(
    "/api/mes-route-templates",
    payload,
  );
}

export function createMesRouteLayer(
  templateId: string | number,
  payload: CreateMesRouteLayerPayload,
) {
  return apiClient.postJson<MesRouteTemplate, CreateMesRouteLayerPayload>(
    `/api/mes-route-templates/${templateId}/layers`,
    payload,
  );
}

export function createMesRouteStep(
  layerId: string | number,
  payload: CreateMesRouteStepPayload,
) {
  return apiClient.postJson<MesRouteTemplate, CreateMesRouteStepPayload>(
    `/api/mes-route-layers/${layerId}/steps`,
    payload,
  );
}

export function createMesSampleRoute(payload: CreateMesSampleRoutePayload) {
  return apiClient.postJson<MesSampleRoute, CreateMesSampleRoutePayload>(
    "/api/mes-sample-routes",
    payload,
  );
}

export function getSampleMesRoute(sampleId: string | number) {
  return apiClient.get<MesSampleRoute>(`/api/samples/${sampleId}/mes-route`);
}

export function advanceMesSampleRoute(
  sampleRouteId: string | number,
  payload: AdvanceMesSampleRoutePayload,
) {
  return apiClient.postJson<MesSampleRoute, AdvanceMesSampleRoutePayload>(
    `/api/mes-sample-routes/${sampleRouteId}/advance`,
    payload,
  );
}

export function updateMesRouteStep(stepId: string | number, payload: UpdateMesRouteStepPayload) {
  return apiClient.patchJson<MesRouteTemplate, UpdateMesRouteStepPayload>(
    `/api/mes-route-steps/${stepId}`,
    payload,
  );
}

export function deleteMesRouteStep(stepId: string | number) {
  return apiClient.delete<MesRouteTemplate>(`/api/mes-route-steps/${stepId}`);
}
