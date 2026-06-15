import { useEffect, useMemo, useState } from "react";
import { getSamples } from "../api/samplesApi";
import { DataImportPanel } from "../components/testData/DataImportPanel";
import { MetricInputForm } from "../components/testData/MetricInputForm";
import { TestDataFilter } from "../components/testData/TestDataFilter";
import { TestDataTable } from "../components/testData/TestDataTable";
import { parseCsvFile, useTestDataStore } from "../stores/testDataStore";
import type { Sample } from "../types/sample";
import type { TestDataPayload, TestDataRecord } from "../types/testData";

export function TestDataPage() {
  const {
    testData,
    filters,
    loading,
    saving,
    importing,
    error,
    setFilters,
    createTestData,
    deleteTestData,
    importCsvRecords,
  } = useTestDataStore();
  const [samples, setSamples] = useState<Sample[]>([]);
  const [samplesLoading, setSamplesLoading] = useState(true);
  const [samplesError, setSamplesError] = useState("");
  const [localError, setLocalError] = useState("");
  const [importMessage, setImportMessage] = useState("");

  const pageError = useMemo(
    () => localError || error || samplesError,
    [error, localError, samplesError],
  );

  useEffect(() => {
    let active = true;

    async function loadSamples() {
      setSamplesLoading(true);
      setSamplesError("");

      try {
        const nextSamples = await getSamples();
        if (active) {
          setSamples(nextSamples);
        }
      } catch (err) {
        if (active) {
          setSamplesError(err instanceof Error ? err.message : "加载样品选项失败");
        }
      } finally {
        if (active) {
          setSamplesLoading(false);
        }
      }
    }

    void loadSamples();

    return () => {
      active = false;
    };
  }, []);

  async function handleCreate(payload: TestDataPayload) {
    setLocalError("");
    setImportMessage("");

    try {
      await createTestData(payload);
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "保存测试数据失败");
    }
  }

  async function handleDelete(record: TestDataRecord) {
    const confirmed = window.confirm("确认删除这条测试数据？");
    if (!confirmed) {
      return;
    }

    setLocalError("");
    setImportMessage("");

    try {
      await deleteTestData(record.id);
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "删除测试数据失败");
    }
  }

  async function handleImport(file: File) {
    setLocalError("");
    setImportMessage("");

    try {
      const records = await parseCsvFile(file);
      await importCsvRecords(records);
      setImportMessage(`CSV 导入完成：成功提交 ${records.length} 行。`);
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "CSV 导入失败");
    }
  }

  return (
    <section>
      {pageError ? (
        <section className="panel panel-section-spacing">
          <div className="empty-row">
            <div className="page-message">
              <strong>测试数据库操作失败</strong>
              <span>{pageError}</span>
            </div>
          </div>
        </section>
      ) : null}

      {importMessage ? (
        <section className="panel panel-section-spacing">
          <div className="empty-row">{importMessage}</div>
        </section>
      ) : null}

      <div className="split-layout">
        <section className="panel">
          <div className="panel-header">
            <h3>结构化数值记录</h3>
            <div className="toolbar test-data-panel-toolbar">
              <TestDataFilter
                filters={filters}
                onChange={setFilters}
              />
              <DataImportPanel importing={importing} onImport={handleImport} />
            </div>
          </div>
          {loading ? (
            <div className="empty-row">加载中...</div>
          ) : (
            <TestDataTable
              testData={testData}
              onDelete={(record) => void handleDelete(record)}
            />
          )}
        </section>

        <section className="panel form-panel">
          {samplesLoading ? (
            <div className="empty-row">加载样品选项中...</div>
          ) : (
            <MetricInputForm
              samples={samples}
              saving={saving}
              onSubmit={handleCreate}
            />
          )}
        </section>
      </div>
    </section>
  );
}
