import { apiClient } from "./apiClient";
import type { DashboardSummary } from "../types/dashboard";

export function getDashboardSummary() {
  return apiClient.get<DashboardSummary>("/api/summary");
}
