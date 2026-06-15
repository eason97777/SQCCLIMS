import { useCallback, useEffect, useState } from "react";
import {
  createTestData as createTestDataRequest,
  deleteTestData as deleteTestDataRequest,
  getTestData,
  importTestDataCsv,
} from "../api/testDataApi";
import { parseCsvFile as parseCsvFileFromUtil } from "../utils/csvImport";
import { buildSearchText, normalizeFilterValue } from "../utils/searchUtils";
import type {
  CsvImportRecord,
  TestDataListParams,
  TestDataPayload,
  TestDataRecord,
} from "../types/testData";

type TestDataFilters = Required<TestDataListParams>;

type TestDataStoreState = {
  testData: TestDataRecord[];
  filters: TestDataFilters;
  loading: boolean;
  saving: boolean;
  importing: boolean;
  error: string;
  setFilters: (nextFilters: Partial<TestDataFilters>) => void;
  refreshTestData: () => Promise<void>;
  createTestData: (payload: TestDataPayload) => Promise<TestDataRecord>;
  deleteTestData: (recordId: number) => Promise<void>;
  importCsvRecords: (records: CsvImportRecord[]) => Promise<void>;
};

const DEFAULT_FILTERS: TestDataFilters = {
  sample_id: "",
  query: "",
};

export function useTestDataStore(): TestDataStoreState {
  const [testData, setTestData] = useState<TestDataRecord[]>([]);
  const [filters, setFiltersState] = useState<TestDataFilters>(DEFAULT_FILTERS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState("");

  const refreshTestData = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const nextTestData = await getTestData({
        sample_id: filters.sample_id,
        query: "",
      });
      const normalizedQuery = normalizeFilterValue(filters.query);
      const filteredTestData = normalizedQuery
        ? nextTestData.filter((row) =>
            buildSearchText([
              row.sample_code,
              row.sample_display_code,
              row.sample_uid,
              row.test_name,
              row.metric_name,
              row.unit,
              row.operator,
              row.environment,
              row.raw_note,
            ]).includes(normalizedQuery),
          )
        : nextTestData;
      setTestData(filteredTestData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载测试数据失败");
    } finally {
      setLoading(false);
    }
  }, [filters.query, filters.sample_id]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void refreshTestData();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [refreshTestData]);

  const setFilters = useCallback((nextFilters: Partial<TestDataFilters>) => {
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

  const createTestData = useCallback(
    async (payload: TestDataPayload) => {
      setSaving(true);
      setError("");

      try {
        const created = await createTestDataRequest(payload);
        await refreshTestData();
        return created;
      } catch (err) {
        const message = err instanceof Error ? err.message : "保存测试数据失败";
        setError(message);
        throw err;
      } finally {
        setSaving(false);
      }
    },
    [refreshTestData],
  );

  const deleteTestData = useCallback(
    async (recordId: number) => {
      setSaving(true);
      setError("");

      try {
        await deleteTestDataRequest(recordId);
        await refreshTestData();
      } catch (err) {
        const message = err instanceof Error ? err.message : "删除测试数据失败";
        setError(message);
        throw err;
      } finally {
        setSaving(false);
      }
    },
    [refreshTestData],
  );

  const importCsvRecords = useCallback(
    async (records: CsvImportRecord[]) => {
      setImporting(true);
      setError("");

      try {
        await importTestDataCsv(records);
        await refreshTestData();
      } catch (err) {
        const message = err instanceof Error ? err.message : "CSV 导入失败";
        setError(message);
        throw err;
      } finally {
        setImporting(false);
      }
    },
    [refreshTestData],
  );

  return {
    testData,
    filters,
    loading,
    saving,
    importing,
    error,
    setFilters,
    refreshTestData,
    createTestData,
    deleteTestData,
    importCsvRecords,
  };
}

export async function parseCsvFile(file: File) {
  const result = await parseCsvFileFromUtil(file);
  if (result.errors.length > 0) {
    throw new Error(
      `CSV 解析失败：第 ${result.errors[0].row} 行，${result.errors[0].reason}`,
    );
  }
  return result.records;
}
