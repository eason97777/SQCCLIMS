import { useEffect, useMemo, useState } from "react";
import { getSamples } from "../api/samplesApi";
import { getTestData } from "../api/testDataApi";
import { ProcessingHistoryTable } from "../components/processing/ProcessingHistoryTable";
import { ProcessingParamForm } from "../components/processing/ProcessingParamForm";
import { ProcessingResultViewer } from "../components/processing/ProcessingResultViewer";
import { useProcessingStore } from "../stores/processingStore";
import type { Sample } from "../types/sample";

export function ProcessingPage() {
  const {
    processingResults,
    currentResult,
    formState,
    loading,
    running,
    error,
    runProcessingTask,
    setCurrentResult,
    setFormState,
  } = useProcessingStore();
  const [samples, setSamples] = useState<Sample[]>([]);
  const [metricOptions, setMetricOptions] = useState<string[]>([]);
  const [samplesError, setSamplesError] = useState("");
  const [metricsError, setMetricsError] = useState("");
  const [localError, setLocalError] = useState("");

  const pageError = useMemo(
    () => localError || error || samplesError || metricsError,
    [error, localError, samplesError, metricsError],
  );

  useEffect(() => {
    let active = true;

    async function loadSupportingData() {
      setSamplesError("");
      setMetricsError("");

      try {
        const nextSamples = await getSamples();
        if (active) {
          setSamples(nextSamples);
        }
      } catch (err) {
        if (active) {
          setSamplesError(err instanceof Error ? err.message : "加载样品选项失败");
        }
      }

      try {
        const rows = await getTestData();
        if (active) {
          const metrics = Array.from(
            new Set(rows.map((row) => row.metric_name).filter(Boolean)),
          ).sort((a, b) => a.localeCompare(b, "zh-CN"));
          setMetricOptions(metrics);
        }
      } catch (err) {
        if (active) {
          setMetricsError(err instanceof Error ? err.message : "加载指标选项失败");
        }
      }
    }

    void loadSupportingData();

    return () => {
      active = false;
    };
  }, []);

  async function handleRun() {
    setLocalError("");
    try {
      await runProcessingTask();
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "运行处理任务失败");
    }
  }

  return (
    <section>
      <div className="section-head">
        <div>
          <p className="eyebrow">Processing</p>
          <h2>数据处理模块</h2>
        </div>
      </div>

      {pageError ? (
        <section className="panel panel-section-spacing">
          <div className="empty-row">
            <div className="page-message">
              <strong>数据处理操作失败</strong>
              <span>{pageError}</span>
            </div>
          </div>
        </section>
      ) : null}

      <div className="split-layout processing-layout">
        <section className="panel form-panel">
          <ProcessingParamForm
            samples={samples}
            metricOptions={metricOptions}
            formState={formState}
            running={running}
            onChange={setFormState}
            onSubmit={handleRun}
          />
        </section>

        <section className="panel">
          <div className="panel-header">
            <h3>处理结果</h3>
          </div>
          {loading ? (
            <div className="empty-row">加载中...</div>
          ) : (
            <ProcessingResultViewer result={currentResult} />
          )}
        </section>
      </div>

      <section className="panel history-panel">
        <div className="panel-header">
          <h3>处理历史</h3>
        </div>
        {loading ? (
          <div className="empty-row">加载中...</div>
        ) : (
          <ProcessingHistoryTable
            results={processingResults}
            onSelect={setCurrentResult}
          />
        )}
      </section>
    </section>
  );
}
