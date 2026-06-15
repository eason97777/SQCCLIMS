import { useCallback, useEffect, useState } from "react";
import {
  createSample as createSampleRequest,
  deleteSample as deleteSampleRequest,
  getSamples,
  updateSample as updateSampleRequest,
} from "../api/samplesApi";
import type { Sample, SampleListParams, SamplePayload } from "../types/sample";
import { normalizeFilterValue } from "../utils/searchUtils";

type SamplesFilters = Required<SampleListParams>;

type SamplesStoreState = {
  samples: Sample[];
  filters: SamplesFilters;
  loading: boolean;
  saving: boolean;
  error: string;
  setFilters: (nextFilters: Partial<SamplesFilters>) => void;
  refreshSamples: () => Promise<void>;
  createSample: (payload: SamplePayload) => Promise<Sample>;
  updateSample: (sampleId: number, payload: SamplePayload) => Promise<Sample>;
  deleteSample: (sampleId: number) => Promise<void>;
};

const DEFAULT_FILTERS: SamplesFilters = {
  query: "",
  status: "",
};

export function useSamplesStore(): SamplesStoreState {
  const [samples, setSamples] = useState<Sample[]>([]);
  const [filters, setFiltersState] = useState<SamplesFilters>(DEFAULT_FILTERS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const refreshSamples = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const nextSamples = await getSamples({
        query: "",
        status: filters.status,
      });
      setSamples(nextSamples);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载样品列表失败");
    } finally {
      setLoading(false);
    }
  }, [filters.status]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void refreshSamples();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [refreshSamples]);

  const setFilters = useCallback((nextFilters: Partial<SamplesFilters>) => {
    setFiltersState((current) => ({
      ...current,
      ...nextFilters,
      query:
        nextFilters.query !== undefined
          ? normalizeFilterValue(nextFilters.query)
          : current.query,
      status:
        nextFilters.status !== undefined
          ? normalizeFilterValue(nextFilters.status)
          : current.status,
    }));
  }, []);

  const createSample = useCallback(
    async (payload: SamplePayload) => {
      setSaving(true);
      setError("");

      try {
        const created = await createSampleRequest(payload);
        await refreshSamples();
        return created;
      } catch (err) {
        const message = err instanceof Error ? err.message : "创建样品失败";
        setError(message);
        throw err;
      } finally {
        setSaving(false);
      }
    },
    [refreshSamples],
  );

  const updateSample = useCallback(
    async (sampleId: number, payload: SamplePayload) => {
      setSaving(true);
      setError("");

      try {
        const updated = await updateSampleRequest(sampleId, payload);
        await refreshSamples();
        return updated;
      } catch (err) {
        const message = err instanceof Error ? err.message : "更新样品失败";
        setError(message);
        throw err;
      } finally {
        setSaving(false);
      }
    },
    [refreshSamples],
  );

  const deleteSample = useCallback(
    async (sampleId: number) => {
      setSaving(true);
      setError("");

      try {
        await deleteSampleRequest(sampleId);
        await refreshSamples();
      } catch (err) {
        const message = err instanceof Error ? err.message : "删除样品失败";
        setError(message);
        throw err;
      } finally {
        setSaving(false);
      }
    },
    [refreshSamples],
  );

  return {
    samples,
    filters,
    loading,
    saving,
    error,
    setFilters,
    refreshSamples,
    createSample,
    updateSample,
    deleteSample,
  };
}
