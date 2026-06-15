import { useCallback, useEffect, useState } from "react";
import { getDashboardSummary } from "../api/dashboardApi";
import type { DashboardSummary } from "../types/dashboard";

type DashboardStoreState = {
  summary: DashboardSummary | null;
  loading: boolean;
  error: string;
  refreshDashboardSummary: () => Promise<void>;
};

export function useDashboardStore(): DashboardStoreState {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const refreshDashboardSummary = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const nextSummary = await getDashboardSummary();
      setSummary(nextSummary);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载总览数据失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void refreshDashboardSummary();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [refreshDashboardSummary]);

  return {
    summary,
    loading,
    error,
    refreshDashboardSummary,
  };
}
