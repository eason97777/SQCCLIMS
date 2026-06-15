import { useCallback, useEffect, useState } from "react";
import {
  createRawData as createRawDataRequest,
  createMockParsedData,
  deleteRawData as deleteRawDataRequest,
  deleteRawDataFile as deleteRawDataFileRequest,
  getRawData,
  getRawDataDetail,
  parseRawData,
  rawDataFileDownloadUrl,
  uploadRawDataFiles,
  visualizeParsedData,
} from "../api/rawDataApi";
import { normalizeFilterValue } from "../utils/searchUtils";
import type {
  RawDataListParams,
  RawDataPayload,
  RawDataRecord,
  VisualizationPayload,
} from "../types/rawData";

type RawDataFilters = Required<RawDataListParams>;

type RawDataStoreState = {
  rawData: RawDataRecord[];
  selectedRawData: RawDataRecord | null;
  filters: RawDataFilters;
  loading: boolean;
  saving: boolean;
  uploading: boolean;
  parsing: boolean;
  error: string;
  setFilters: (nextFilters: Partial<RawDataFilters>) => void;
  refreshRawData: () => Promise<void>;
  createRawData: (payload: RawDataPayload) => Promise<RawDataRecord>;
  loadRawDataDetail: (rawDataId: number) => Promise<RawDataRecord | null>;
  uploadFiles: (rawDataId: number, files: File[]) => Promise<RawDataRecord | null>;
  parseRawDataRecord: (rawDataId: number) => Promise<RawDataRecord | null>;
  createMockParsedResult: (rawDataId: number) => Promise<void>;
  visualizeParsedDataRecord: (parsedDataId: number, payload?: VisualizationPayload) => Promise<void>;
  deleteRawData: (rawDataId: number) => Promise<void>;
  downloadRawDataFile: (fileId: number) => void;
  deleteRawDataFile: (fileId: number, rawDataId: number) => Promise<void>;
  setSelectedRawData: (rawData: RawDataRecord | null) => void;
};

const DEFAULT_FILTERS: RawDataFilters = {
  raw_data_id: "",
  sample_id: "",
  data_type: "",
  parser_status: "",
  status: "",
  query: "",
};

function isValidRawDataId(rawDataId: unknown): rawDataId is number {
  return typeof rawDataId === "number" && Number.isFinite(rawDataId) && rawDataId > 0;
}

function parserNameForDataType(dataType: string) {
  if (dataType === "cd_sem") {
    return "cd_template_parser";
  }
  if (dataType === "resistance") {
    return "resistance_csv_parser";
  }
  throw new Error("当前数据类型暂无 parser");
}

export function useRawDataStore(): RawDataStoreState {
  const [rawData, setRawData] = useState<RawDataRecord[]>([]);
  const [selectedRawData, setSelectedRawData] = useState<RawDataRecord | null>(null);
  const [filters, setFiltersState] = useState<RawDataFilters>(DEFAULT_FILTERS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [parsing, setParsing] = useState(false);
  const [error, setError] = useState("");

  const refreshRawData = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const nextRawData = await getRawData(filters);
      setRawData(nextRawData);
      setSelectedRawData((current) => {
        if (!current) {
          return null;
        }

        const currentRow = nextRawData.find((record) => record.id === current.id);
        return currentRow ? { ...current, ...currentRow } : null;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载 Raw Data 失败");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void refreshRawData();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [refreshRawData]);

  const setFilters = useCallback((nextFilters: Partial<RawDataFilters>) => {
    setFiltersState((current) => ({
      ...current,
      ...nextFilters,
      raw_data_id:
        nextFilters.raw_data_id !== undefined
          ? String(nextFilters.raw_data_id)
          : current.raw_data_id,
      sample_id:
        nextFilters.sample_id !== undefined
          ? String(nextFilters.sample_id)
          : current.sample_id,
      data_type:
        nextFilters.data_type !== undefined
          ? String(nextFilters.data_type)
          : current.data_type,
      parser_status:
        nextFilters.parser_status !== undefined
          ? String(nextFilters.parser_status)
          : current.parser_status,
      status:
        nextFilters.status !== undefined ? String(nextFilters.status) : current.status,
      query:
        nextFilters.query !== undefined
          ? normalizeFilterValue(nextFilters.query)
          : current.query,
    }));
  }, []);

  const createRawData = useCallback(
    async (payload: RawDataPayload) => {
      setSaving(true);
      setError("");

      try {
        const created = await createRawDataRequest(payload);
        await refreshRawData();
        setSelectedRawData(created);
        return created;
      } catch (err) {
        const message = err instanceof Error ? err.message : "创建 Raw Data 失败";
        setError(message);
        throw err;
      } finally {
        setSaving(false);
      }
    },
    [refreshRawData],
  );

  const loadRawDataDetail = useCallback(async (rawDataId: number) => {
    if (!isValidRawDataId(rawDataId)) {
      setSelectedRawData(null);
      return null;
    }

    setError("");

    try {
      const detail = await getRawDataDetail(rawDataId);
      setSelectedRawData(detail);
      return detail;
    } catch (err) {
      const message = err instanceof Error ? err.message : "加载 Raw Data 详情失败";
      setError(message);
      throw err;
    }
  }, []);

  const uploadFiles = useCallback(
    async (rawDataId: number, files: File[]) => {
      if (!isValidRawDataId(rawDataId)) {
        setSelectedRawData(null);
        return null;
      }

      setUploading(true);
      setError("");

      try {
        const detail = await uploadRawDataFiles(rawDataId, files);
        setSelectedRawData(detail);
        await refreshRawData();
        return detail;
      } catch (err) {
        const message = err instanceof Error ? err.message : "上传 Raw Data 文件失败";
        setError(message);
        throw err;
      } finally {
        setUploading(false);
      }
    },
    [refreshRawData],
  );

  const createMockParsedResult = useCallback(
    async (rawDataId: number) => {
      if (!isValidRawDataId(rawDataId)) {
        setSelectedRawData(null);
        return;
      }

      setSaving(true);
      setError("");

      try {
        const current = await getRawDataDetail(rawDataId);
        await createMockParsedData({
          raw_data_id: rawDataId,
          parser_name: "mock_parser",
          parser_version: "0.1.0",
          records: [
            {
              raw_data_id: rawDataId,
              sample_id: current.sample_id,
              sample_uid: current.sample_uid,
              data_type: current.data_type,
              source: "mock",
            },
          ],
          summary: {
            file_count: current.file_count,
            total_size: current.total_size,
            mock: true,
          },
          warnings: ["mock parsed_data 仅用于验证数据链路"],
        });
        const detail = await getRawDataDetail(rawDataId);
        setSelectedRawData(detail);
        await refreshRawData();
      } catch (err) {
        const message = err instanceof Error ? err.message : "生成模拟标准化结果失败";
        setError(message);
        throw err;
      } finally {
        setSaving(false);
      }
    },
    [refreshRawData],
  );

  const parseRawDataRecord = useCallback(
    async (rawDataId: number) => {
      if (!isValidRawDataId(rawDataId)) {
        setSelectedRawData(null);
        return null;
      }

      setParsing(true);
      setError("");

      try {
        const current = selectedRawData?.id === rawDataId
          ? selectedRawData
          : await getRawDataDetail(rawDataId);
        const detail = await parseRawData(rawDataId, parserNameForDataType(current.data_type));
        setSelectedRawData(detail);
        await refreshRawData();
        return detail;
      } catch (err) {
        const message = err instanceof Error ? err.message : "运行 Raw Data 解析失败";
        setError(message);
        throw err;
      } finally {
        setParsing(false);
      }
    },
    [refreshRawData, selectedRawData],
  );

  const visualizeParsedDataRecord = useCallback(async (
    parsedDataId: number,
    payload: VisualizationPayload = { chart_type: "violin" },
  ) => {
    setSaving(true);
    setError("");

    try {
      await visualizeParsedData(parsedDataId, payload);
    } catch (err) {
      const message = err instanceof Error ? err.message : "生成 CD 小提琴图失败";
      setError(message);
      throw err;
    } finally {
      setSaving(false);
    }
  }, []);

  const deleteRawData = useCallback(
    async (rawDataId: number) => {
      if (!isValidRawDataId(rawDataId)) {
        setSelectedRawData(null);
        return;
      }

      setSaving(true);
      setError("");

      try {
        await deleteRawDataRequest(rawDataId);
        setSelectedRawData((current) => (current?.id === rawDataId ? null : current));
        await refreshRawData();
      } catch (err) {
        const message = err instanceof Error ? err.message : "删除 Raw Data 失败";
        setError(message);
        throw err;
      } finally {
        setSaving(false);
      }
    },
    [refreshRawData],
  );

  const downloadRawDataFile = useCallback((fileId: number) => {
    window.location.href = rawDataFileDownloadUrl(fileId);
  }, []);

  const deleteRawDataFile = useCallback(
    async (fileId: number, rawDataId: number) => {
      if (!isValidRawDataId(rawDataId)) {
        setSelectedRawData(null);
        return;
      }

      setSaving(true);
      setError("");

      try {
        const result = await deleteRawDataFileRequest(fileId);
        const detail = result.raw_data ?? await getRawDataDetail(rawDataId);
        setSelectedRawData(detail);
        await refreshRawData();
      } catch (err) {
        const message = err instanceof Error ? err.message : "删除 Raw Data 源文件失败";
        setError(message);
        throw err;
      } finally {
        setSaving(false);
      }
    },
    [refreshRawData],
  );

  return {
    rawData,
    selectedRawData,
    filters,
    loading,
    saving,
    uploading,
    parsing,
    error,
    setFilters,
    refreshRawData,
    createRawData,
    loadRawDataDetail,
    uploadFiles,
    parseRawDataRecord,
    createMockParsedResult,
    visualizeParsedDataRecord,
    deleteRawData,
    downloadRawDataFile,
    deleteRawDataFile,
    setSelectedRawData,
  };
}
