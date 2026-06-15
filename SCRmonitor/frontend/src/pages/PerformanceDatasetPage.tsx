import { useEffect, useMemo, useState } from "react";
import { getSamples } from "../api/samplesApi";
import { DatasetFileTree } from "../components/performance/DatasetFileTree";
import { DatasetImportPanel } from "../components/performance/DatasetImportPanel";
import { DatasetSummaryCard } from "../components/performance/DatasetSummaryCard";
import { PerformanceDatasetFilter } from "../components/performance/PerformanceDatasetFilter";
import { PerformanceDatasetTable } from "../components/performance/PerformanceDatasetTable";
import { usePerformanceStore } from "../stores/performanceStore";
import type { PerformanceDataset, PerformanceDatasetFields } from "../types/performance";
import type { Sample } from "../types/sample";

type DirectoryFile = File & {
  webkitRelativePath?: string;
};

export function PerformanceDatasetPage() {
  const {
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
  } = usePerformanceStore();
  const [samples, setSamples] = useState<Sample[]>([]);
  const [samplesLoading, setSamplesLoading] = useState(true);
  const [samplesError, setSamplesError] = useState("");
  const [localError, setLocalError] = useState("");

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

  async function handleImport(fields: PerformanceDatasetFields, files: DirectoryFile[]) {
    setLocalError("");

    try {
      await uploadPerformanceDataset(fields, files);
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "导入性能数据集失败");
    }
  }

  async function handleViewFiles(dataset: PerformanceDataset) {
    setLocalError("");
    setSelectedDataset(dataset);

    try {
      await loadDatasetFiles(dataset.id);
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "加载数据集文件结构失败");
    }
  }

  async function handleDelete(dataset: PerformanceDataset) {
    const confirmed = window.confirm("确认删除这个性能数据集及其文件？");
    if (!confirmed) {
      return;
    }

    setLocalError("");

    try {
      await deletePerformanceDataset(dataset.id);
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "删除性能数据集失败");
    }
  }

  return (
    <section>
      <div className="section-head">
        <div>
          <p className="eyebrow">Performance Datasets</p>
          <h2>性能数据集</h2>
        </div>
        <div className="toolbar">
          <PerformanceDatasetFilter
            filters={filters}
            samples={samples}
            onChange={setFilters}
          />
          <button
            className="ghost-button"
            type="button"
            onClick={() => void refreshPerformanceDatasets()}
          >
            刷新
          </button>
        </div>
      </div>

      {pageError ? (
        <section className="panel panel-section-spacing">
          <div className="empty-row">
            <div className="page-message">
              <strong>性能数据集操作失败</strong>
              <span>{pageError}</span>
            </div>
          </div>
        </section>
      ) : null}

      <section className="panel data-import-panel">
        <div className="panel-header">
          <h3>性能数据导入</h3>
        </div>
        <div className="import-grid">
          {samplesLoading ? (
            <div className="empty-row">加载样品选项中...</div>
          ) : (
            <DatasetImportPanel
              samples={samples}
              uploading={uploading}
              onImport={handleImport}
            />
          )}
        </div>
      </section>

      <section className="panel data-library-panel">
        <div className="panel-header">
          <h3>性能数据集库</h3>
        </div>
        {loading ? (
          <div className="empty-row">加载中...</div>
        ) : (
          <PerformanceDatasetTable
            datasets={datasets}
            onViewFiles={(dataset) => void handleViewFiles(dataset)}
            onDelete={(dataset) => void handleDelete(dataset)}
          />
        )}
      </section>

      <div className="split-layout">
        <section className="panel">
          <div className="panel-header">
            <h3>数据集概览</h3>
          </div>
          <DatasetSummaryCard dataset={selectedDataset} />
        </section>

        <section className="panel">
          <div className="panel-header">
            <h3>文件结构</h3>
          </div>
          <div className="table-wrap">
            <DatasetFileTree files={datasetFiles} />
          </div>
        </section>
      </div>
    </section>
  );
}
