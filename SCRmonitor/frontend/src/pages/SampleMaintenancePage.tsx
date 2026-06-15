import { useEffect, useMemo, useState } from "react";
import { MesFlowArchivePanel } from "../components/samples/MesFlowArchivePanel";
import { SampleForm } from "../components/samples/SampleForm";
import { SampleMaintenancePanel } from "../components/samples/SampleMaintenancePanel";
import { SampleTable } from "../components/samples/SampleTable";
import { useSampleMaintenanceStore } from "../stores/sampleMaintenanceStore";
import { useSamplesStore } from "../stores/samplesStore";
import type { Sample, SamplePayload } from "../types/sample";
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

  async function handleDelete(sample: Sample) {
    const sampleLabel = getSampleProjectCode(sample) || getSampleName(sample);
    const confirmed = window.confirm(
      `确认删除样品 ${sampleLabel}？删除后会同时删除关联测试数据。`,
    );
    if (!confirmed) {
      return;
    }

    setLocalError("");

    try {
      await deleteSample(sample.id);
      if (editingSample?.id === sample.id) {
        setEditingSample(null);
      }
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "删除样品失败");
    }
  }

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
              onDelete={(sample) => void handleDelete(sample)}
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
    </section>
  );
}
