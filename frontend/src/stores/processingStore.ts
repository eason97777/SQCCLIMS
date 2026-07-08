import { useCallback, useEffect, useState } from "react";
import { getProcessingResults, runProcessing } from "../api/processingApi";
import {
  normalizeNumericText,
  normalizeWhitespace,
  trimText,
} from "../utils/textNormalize";
import type { ProcessingRequest, ProcessingResultRecord } from "../types/processing";

type ProcessingFormState = {
  job_name: string;
  sample_id: string;
  metric_name: string;
  method: "stats" | "qc" | "normalize";
  lower_limit: string;
  upper_limit: string;
};

type ProcessingStoreState = {
  processingResults: ProcessingResultRecord[];
  currentResult: ProcessingResultRecord | null;
  formState: ProcessingFormState;
  loading: boolean;
  running: boolean;
  error: string;
  refreshProcessingResults: () => Promise<void>;
  runProcessingTask: () => Promise<void>;
  setCurrentResult: (result: ProcessingResultRecord | null) => void;
  setFormState: (nextState: Partial<ProcessingFormState>) => void;
};

const DEFAULT_FORM_STATE: ProcessingFormState = {
  job_name: "统计处理",
  sample_id: "",
  metric_name: "",
  method: "stats",
  lower_limit: "",
  upper_limit: "",
};

export function useProcessingStore(): ProcessingStoreState {
  const [processingResults, setProcessingResults] = useState<ProcessingResultRecord[]>([]);
  const [currentResult, setCurrentResult] = useState<ProcessingResultRecord | null>(null);
  const [formState, setFormStateState] = useState<ProcessingFormState>(DEFAULT_FORM_STATE);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");

  const refreshProcessingResults = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const nextResults = await getProcessingResults();
      setProcessingResults(nextResults);
      if (!currentResult && nextResults.length) {
        setCurrentResult(nextResults[0]);
      }
      if (
        currentResult &&
        !nextResults.some((item) => String(item.id) === String(currentResult.id))
      ) {
        setCurrentResult(nextResults[0] || null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载分析历史失败");
    } finally {
      setLoading(false);
    }
  }, [currentResult]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void refreshProcessingResults();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [refreshProcessingResults]);

  const setFormState = useCallback((nextState: Partial<ProcessingFormState>) => {
    setFormStateState((current) => ({
      ...current,
      ...nextState,
    }));
  }, []);

  const runProcessingTask = useCallback(async () => {
    setRunning(true);
    setError("");

    const payload: ProcessingRequest = {
      job_name: normalizeWhitespace(formState.job_name),
      method: formState.method,
      sample_id: trimText(formState.sample_id) || "",
      parameters: {
        metric_name: normalizeWhitespace(formState.metric_name),
        lower_limit: normalizeNumericText(formState.lower_limit),
        upper_limit: normalizeNumericText(formState.upper_limit),
      },
    };

    try {
      const result = await runProcessing(payload);
      setCurrentResult(result);
      await refreshProcessingResults();
    } catch (err) {
      setError(err instanceof Error ? err.message : "运行分析任务失败");
      throw err;
    } finally {
      setRunning(false);
    }
  }, [formState, refreshProcessingResults]);

  return {
    processingResults,
    currentResult,
    formState,
    loading,
    running,
    error,
    refreshProcessingResults,
    runProcessingTask,
    setCurrentResult,
    setFormState,
  };
}
