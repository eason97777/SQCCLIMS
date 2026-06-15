import { useCallback, useEffect, useState } from "react";
import {
  deletePerformanceDataset as deletePerformanceDatasetRequest,
  getPerformanceDatasetFiles,
  getPerformanceDatasets,
  uploadPerformanceDataset as uploadPerformanceDatasetRequest,
} from "../api/performanceApi";
import { buildSearchText, normalizeFilterValue } from "../utils/searchUtils";
import type {
  PerformanceDataset,
  PerformanceDatasetFields,
  PerformanceDatasetFile,
  PerformanceDatasetListParams,
} from "../types/performance";

type PerformanceFilters = Required<PerformanceDatasetListParams>;

type PerformanceStoreState = {
  datasets: PerformanceDataset[];
  selectedDataset: PerformanceDataset | null;
  datasetFiles: PerformanceDatasetFile[];
  filters: PerformanceFilters;
  loading: boolean;
  uploading: boolean;
  error: string;
  setFilters: (nextFilters: Partial<PerformanceFilters>) => void;
  setSelectedDataset: (dataset: PerformanceDataset | null) => void;
  refreshPerformanceDatasets: () => Promise<void>;
  loadDatasetFiles: (datasetId: number) => Promise<void>;
  uploadPerformanceDataset: (
    fields: PerformanceDatasetFields,
    files: File[],
  ) => Promise<void>;
  deletePerformanceDataset: (datasetId: number) => Promise<void>;
};

const DEFAULT_FILTERS: PerformanceFilters = {
  sample_id: "",
  query: "",
};

export function usePerformanceStore(): PerformanceStoreState {
  const [datasets, setDatasets] = useState<PerformanceDataset[]>([]);
  const [selectedDataset, setSelectedDataset] = useState<PerformanceDataset | null>(null);
  const [datasetFiles, setDatasetFiles] = useState<PerformanceDatasetFile[]>([]);
  const [filters, setFiltersState] = useState<PerformanceFilters>(DEFAULT_FILTERS);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");

  const refreshPerformanceDatasets = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const nextDatasets = await getPerformanceDatasets({
        sample_id: filters.sample_id,
        query: "",
      });
      const normalizedQuery = normalizeFilterValue(filters.query);
      const filteredDatasets = normalizedQuery
        ? nextDatasets.filter((dataset) =>
            buildSearchText([
              dataset.sample_code,
              dataset.sample_display_code,
              dataset.sample_uid,
              dataset.sample_name,
              dataset.aliquot_code,
              dataset.dataset_name,
              dataset.test_type,
              dataset.data_format,
              dataset.status,
              dataset.notes,
            ]).includes(normalizedQuery),
          )
        : nextDatasets;

      setDatasets(filteredDatasets);

      if (
        selectedDataset &&
        !filteredDatasets.some((dataset) => dataset.id === selectedDataset.id)
      ) {
        setSelectedDataset(null);
        setDatasetFiles([]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载性能数据集失败");
    } finally {
      setLoading(false);
    }
  }, [filters.query, filters.sample_id, selectedDataset]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void refreshPerformanceDatasets();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [refreshPerformanceDatasets]);

  const setFilters = useCallback((nextFilters: Partial<PerformanceFilters>) => {
    setFiltersState((current) => ({
      ...current,
      ...nextFilters,
      sample_id:
        nextFilters.sample_id !== undefined
          ? String(nextFilters.sample_id)
          : current.sample_id,
      query:
        nextFilters.query !== undefined
          ? normalizeFilterValue(nextFilters.query)
          : current.query,
    }));
  }, []);

  const loadDatasetFiles = useCallback(async (datasetId: number) => {
    setError("");
    try {
      const files = await getPerformanceDatasetFiles(datasetId);
      setDatasetFiles(files);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载数据集文件结构失败");
      throw err;
    }
  }, []);

  const uploadPerformanceDataset = useCallback(
    async (fields: PerformanceDatasetFields, files: File[]) => {
      setUploading(true);
      setError("");

      try {
        await uploadPerformanceDatasetRequest(fields, files);
        await refreshPerformanceDatasets();
      } catch (err) {
        setError(err instanceof Error ? err.message : "导入性能数据集失败");
        throw err;
      } finally {
        setUploading(false);
      }
    },
    [refreshPerformanceDatasets],
  );

  const deletePerformanceDataset = useCallback(
    async (datasetId: number) => {
      setUploading(true);
      setError("");

      try {
        await deletePerformanceDatasetRequest(datasetId);
        if (selectedDataset?.id === datasetId) {
          setSelectedDataset(null);
          setDatasetFiles([]);
        }
        await refreshPerformanceDatasets();
      } catch (err) {
        setError(err instanceof Error ? err.message : "删除性能数据集失败");
        throw err;
      } finally {
        setUploading(false);
      }
    },
    [refreshPerformanceDatasets, selectedDataset],
  );

  return {
    datasets,
    selectedDataset,
    datasetFiles,
    filters,
    loading,
    uploading,
    error,
    setFilters,
    setSelectedDataset,
    refreshPerformanceDatasets,
    loadDatasetFiles,
    uploadPerformanceDataset,
    deletePerformanceDataset,
  };
}
