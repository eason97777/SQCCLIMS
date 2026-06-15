import { useEffect, useMemo, useState } from "react";
import { MesFlowArchivePanel } from "../components/samples/MesFlowArchivePanel";
import { SampleForm } from "../components/samples/SampleForm";
import { SampleMaintenancePanel } from "../components/samples/SampleMaintenancePanel";
import { SampleTable } from "../components/samples/SampleTable";
import {
  DeleteConfirmDialog,
  type DeletePreviewLine,
} from "../components/common/DeleteConfirmDialog";
import { getSampleDeletePreview } from "../api/samplesApi";
import { useSampleMaintenanceStore } from "../stores/sampleMaintenanceStore";
import { useSamplesStore } from "../stores/samplesStore";
import type { Sample, SampleDeletePreview, SamplePayload } from "../types/sample";
import {
  getSampleName,
  getSampleProjectCode,
  sortSamplesByBusinessRule,
} from "../utils/sampleFields";

export function SampleMaintenancePage() {
  const {
    samples,
    loading,
    saving,
    error,
    createSample,
    updateSample,
    deleteSample,
  } = useSamplesStore();
  const [editingSample, setEditingSample] = useState<Sample | null>(null);
  const [hasAutoSelectedSample, setHasAutoSelectedSample] = useState(false);
  const [sampleDraft, setSampleDraft] = useState<SamplePayload | null>(null);
  const [localError, setLocalError] = useState("");
  const [pendingDelete, setPendingDelete] = useState<Sample | null>(null);
  const [preview, setPreview] = useState<SampleDeletePreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState("");
  const [deleting, setDeleting] = useState(false);
  const {
    options: maintenanceOptions,
    addOption,
    removeOption,
  } = useSampleMaintenanceStore(samples);

  const pageError = useMemo(() => localError || error, [error, localError]);
  const sortedSamples = useMemo(() => sortSamplesByBusinessRule(samples), [samples]);
  const mesTargetSample = useMemo<Partial<Sample> | null>(() => {
    if (sampleDraft) {
      return {
        ...(editingSample ?? {}),
        ...sampleDraft,
      };
    }
    return editingSample ?? sortedSamples[0] ?? null;
  }, [editingSample, sampleDraft, sortedSamples]);

  useEffect(() => {
    if (!hasAutoSelectedSample && !editingSample && sortedSamples.length > 0) {
      setEditingSample(sortedSamples[0]);
      setHasAutoSelectedSample(true);
    }
  }, [editingSample, hasAutoSelectedSample, sortedSamples]);

  async function handleSubmit(payload: SamplePayload) {
    setLocalError("");

    try {
      if (editingSample) {
        await updateSample(editingSample.id, payload);
      } else {
        await createSample(payload);
      }
      setEditingSample(null);
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "保存样品失败");
    }
  }

  function requestDelete(sample: Sample) {
    setPendingDelete(sample);
    setPreview(null);
    setPreviewError("");
    setPreviewLoading(true);
    getSampleDeletePreview(sample.id)
      .then((result) => setPreview(result))
      .catch((err) =>
        setPreviewError(err instanceof Error ? err.message : "获取删除影响范围失败"),
      )
      .finally(() => setPreviewLoading(false));
  }

  function cancelDelete() {
    setPendingDelete(null);
    setPreview(null);
    setPreviewError("");
    setPreviewLoading(false);
  }

  async function confirmDelete() {
    if (!pendingDelete) {
      return;
    }
    const sample = pendingDelete;
    setLocalError("");
    setDeleting(true);
    try {
      await deleteSample(sample.id);
      if (editingSample?.id === sample.id) {
        setEditingSample(null);
      }
      cancelDelete();
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "删除样品失败");
    } finally {
      setDeleting(false);
    }
  }

  const deletePreviewLines = useMemo<DeletePreviewLine[]>(() => {
    if (!preview) {
      return [];
    }
    const candidates: DeletePreviewLine[] = [
      { label: "条测试数据", count: preview.test_data },
      { label: "条工艺记录", count: preview.process_records },
      { label: "组 Raw Data", count: preview.raw_data },
      { label: "条解析数据", count: preview.parsed_data },
      { label: "条解析记录", count: preview.parsed_records },
      { label: "个表征文件", count: preview.characterization_files },
      { label: "个性能数据集", count: preview.performance_datasets },
      { label: "个关联文件", count: preview.files_total },
    ];
    return candidates.filter((line) => line.count > 0);
  }, [preview]);

  const deleteLabel = pendingDelete
    ? getSampleProjectCode(pendingDelete) || getSampleName(pendingDelete)
    : "";

  return (
    <section>
      {pageError ? (
        <section className="panel panel-section-spacing">
          <div className="empty-row">
            <div className="page-message">
              <strong>样品维护操作失败</strong>
              <span>{pageError}</span>
            </div>
          </div>
        </section>
      ) : null}

      <SampleMaintenancePanel
        options={maintenanceOptions}
        onAddOption={addOption}
        onRemoveOption={removeOption}
      />

      <div className="sample-maintenance-workbench">
        <section className="panel sample-list-card">
          <div className="panel-header">
            <h3>样品清单</h3>
          </div>
          {loading ? (
            <div className="empty-row">加载中...</div>
          ) : (
            <SampleTable
              samples={sortedSamples}
              selectedSampleId={editingSample?.id ?? null}
              onSelect={setEditingSample}
              onEdit={setEditingSample}
              onDelete={(sample) => requestDelete(sample)}
            />
          )}
        </section>

        <section className="panel current-sample-card form-panel">
          <SampleForm
            key={editingSample?.id ?? "new-sample"}
            initialValue={editingSample}
            maintenanceOptions={maintenanceOptions}
            samples={samples}
            submitting={saving}
            onDraftChange={(draft) => setSampleDraft(getSampleProjectCode(draft) ? draft : null)}
            onSubmit={handleSubmit}
            onCancel={() => setEditingSample(null)}
          />
        </section>
      </div>

      <MesFlowArchivePanel sample={mesTargetSample} samples={samples} />

      <DeleteConfirmDialog
        open={pendingDelete !== null}
        title="删除样品"
        message={`确认删除样品 ${deleteLabel}？此操作不可撤销。`}
        previewLines={deletePreviewLines}
        loading={previewLoading}
        error={previewError}
        deleting={deleting}
        onConfirm={() => void confirmDelete()}
        onCancel={cancelDelete}
      />
    </section>
  );
}
