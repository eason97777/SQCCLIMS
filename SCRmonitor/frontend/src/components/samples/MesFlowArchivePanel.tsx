import { useCallback, useEffect, useMemo, useState } from "react";
import {
  advanceMesSampleRoute,
  createMesRouteLayer,
  createMesRouteStep,
  createMesRouteTemplate,
  createMesSampleRoute,
  deleteMesRouteStep,
  getMesRouteTemplateByProject,
  getSampleMesRoute,
  updateMesRouteStep,
} from "../../api/mesApi";
import { ApiError } from "../../api/apiClient";
import type { MesRouteLayer, MesRouteTemplate, MesSampleRoute } from "../../types/mes";
import type { Sample } from "../../types/sample";
import { PROCESS_STAGES } from "../../utils/processStages";
import { getSampleProjectCode } from "../../utils/sampleFields";
import { SelectCombobox } from "./SelectCombobox";

type MesFlowArchivePanelProps = {
  sample: Partial<Sample> | null;
  samples?: Sample[];
};

type DisplayStep = {
  layerName: string;
  stepName: string;
  stepType: string;
  status: string;
  nextLayerName: string;
  debugStatus: string;
};

type MapNode = {
  id: number;
  sequence: number;
  layerName: string;
  stepName: string;
  status: string;
  isSelected: boolean;
  isCurrent: boolean;
};

function layerSpecialRequirement(layer: MesRouteLayer) {
  const specialSteps = layer.steps.filter((step) => step.default_instruction);
  if (specialSteps.length === 0) {
    return "无";
  }
  if (specialSteps.length === 1) {
    return specialSteps[0].default_instruction || "1 项";
  }
  return `${specialSteps.length} 项`;
}

function selectedLayerFromTemplate(template: MesRouteTemplate | null, activeLayerName?: string) {
  if (!template?.layers.length) {
    return null;
  }
  if (activeLayerName) {
    const activeLayer = template.layers.find((layer) => layer.layer_name === activeLayerName);
    if (activeLayer) {
      return activeLayer;
    }
  }
  return template.layers.find((layer) => layer.layer_name === "CPW") ?? template.layers[0];
}

function routeCurrentStep(route: MesSampleRoute | null) {
  if (!route) {
    return null;
  }
  return route.steps.find((step) => step.id === route.current_sample_step_id) ?? null;
}

function statusLabel(status: string) {
  if (status === "active") {
    return "进行中";
  }
  if (status === "pending") {
    return "待开始";
  }
  if (status === "completed") {
    return "已完成";
  }
  if (status === "skipped") {
    return "已跳过";
  }
  if (status === "empty") {
    return "无工步";
  }
  return status || "-";
}

function mapNodeStatusClass(status: string) {
  if (status === "active") {
    return "active";
  }
  if (status === "completed") {
    return "completed";
  }
  if (status === "skipped") {
    return "skipped";
  }
  return "pending";
}

export function MesFlowArchivePanel({ sample, samples = [] }: MesFlowArchivePanelProps) {
  const [template, setTemplate] = useState<MesRouteTemplate | null>(null);
  const [sampleRoute, setSampleRoute] = useState<MesSampleRoute | null>(null);
  const [isLayerDrawerOpen, setIsLayerDrawerOpen] = useState(false);
  const [drawerMode, setDrawerMode] = useState<"layers" | "template">("layers");
  const [selectedLayerId, setSelectedLayerId] = useState<number | null>(null);
  const [hasManualLayerSelection, setHasManualLayerSelection] = useState(false);
  const [selectedDrawerLayerId, setSelectedDrawerLayerId] = useState<number | null>(null);
  const [editingInstructions, setEditingInstructions] = useState<Record<number, string>>({});
  const [newLayerName, setNewLayerName] = useState("");
  const [newStepName, setNewStepName] = useState("");
  const [newStepInstruction, setNewStepInstruction] = useState("");
  const [layerCandidateOpen, setLayerCandidateOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [advancing, setAdvancing] = useState(false);
  const [savingStepId, setSavingStepId] = useState<number | null>(null);
  const [message, setMessage] = useState("");

  const projectCode = sample ? getSampleProjectCode(sample) : "";
  const currentStep = useMemo(() => routeCurrentStep(sampleRoute), [sampleRoute]);
  const activeTemplateLayer = useMemo(
    () => selectedLayerFromTemplate(template, currentStep?.layer_name),
    [currentStep?.layer_name, template],
  );
  const selectedLayer = useMemo(
    () => {
      if (!template?.layers.length) {
        return null;
      }
      return (
        (hasManualLayerSelection
          ? template.layers.find((layer) => layer.id === selectedLayerId)
          : null) ??
        activeTemplateLayer ??
        template.layers[0]
      );
    },
    [activeTemplateLayer, hasManualLayerSelection, selectedLayerId, template],
  );
  const selectedLayerSampleSteps = useMemo(
    () => (sampleRoute?.steps ?? []).filter((step) => step.layer_name === selectedLayer?.layer_name),
    [sampleRoute?.steps, selectedLayer?.layer_name],
  );
  const displayStep = useMemo<DisplayStep>(() => {
    if (!selectedLayer) {
      return {
        layerName: "-",
        stepName: "当前图层暂无工步记录。",
        stepType: "",
        status: "empty",
        nextLayerName: "-",
        debugStatus: "empty",
      };
    }

    const activeStep = selectedLayerSampleSteps.find((step) => step.status === "active");
    const pendingStep = selectedLayerSampleSteps.find((step) => step.status === "pending");
    const fallbackTemplateStep = selectedLayer.steps[0];
    const chosenStep = activeStep ?? pendingStep;
    const allCompleted =
      selectedLayerSampleSteps.length > 0 &&
      selectedLayerSampleSteps.every((step) => step.status === "completed" || step.status === "skipped");
    const nextLayer =
      template?.layers.find((layer) => layer.sequence_no > selectedLayer.sequence_no)?.layer_name ?? "-";

    if (chosenStep) {
      return {
        layerName: chosenStep.layer_name,
        stepName: chosenStep.step_name,
        stepType: chosenStep.step_name,
        status: chosenStep.status,
        nextLayerName: nextLayer,
        debugStatus: chosenStep.status,
      };
    }

    if (allCompleted) {
      return {
        layerName: selectedLayer.layer_name,
        stepName: selectedLayer.steps.at(-1)?.step_name ?? "已完成",
        stepType: selectedLayer.steps.at(-1)?.step_name ?? "",
        status: "completed",
        nextLayerName: nextLayer,
        debugStatus: "completed",
      };
    }

    if (fallbackTemplateStep) {
      return {
        layerName: selectedLayer.layer_name,
        stepName: fallbackTemplateStep.step_name,
        stepType: fallbackTemplateStep.step_name,
        status: "pending",
        nextLayerName: nextLayer,
        debugStatus: "template_pending",
      };
    }

    return {
      layerName: selectedLayer.layer_name,
      stepName: "当前图层暂无工步记录。",
      stepType: "",
      status: "empty",
      nextLayerName: nextLayer,
      debugStatus: "empty",
    };
  }, [selectedLayer, selectedLayerSampleSteps, template?.layers]);
  const selectedDrawerLayer = useMemo(() => {
    if (!template?.layers.length) {
      return null;
    }
    return (
      template.layers.find((layer) => layer.id === selectedDrawerLayerId) ??
      selectedLayer ??
      template.layers[0]
    );
  }, [selectedDrawerLayerId, selectedLayer, template]);
  const layerNameCandidates = useMemo(() => {
    const keyword = newLayerName.trim().toLowerCase();
    const names = Array.from(new Set((template?.layers ?? []).map((layer) => layer.layer_name).filter(Boolean)));
    const matched = keyword
      ? names.filter((name) => name.toLowerCase().includes(keyword))
      : names;
    return matched.slice(0, 5);
  }, [newLayerName, template?.layers]);

  const mapNodes = useMemo<MapNode[]>(() => {
    const routeSteps = sampleRoute?.steps ?? [];
    return (template?.layers ?? []).map((layer) => {
      const layerSteps = routeSteps.filter((step) => step.layer_name === layer.layer_name);
      const activeStep = layerSteps.find((step) => step.status === "active");
      const pendingStep = layerSteps.find((step) => step.status === "pending");
      const completedOrSkipped =
        layerSteps.length > 0 &&
        layerSteps.every((step) => step.status === "completed" || step.status === "skipped");
      const skipped = layerSteps.length > 0 && layerSteps.every((step) => step.status === "skipped");
      const templateStep = layer.steps[0];
      const status = activeStep
        ? "active"
        : completedOrSkipped
          ? skipped
            ? "skipped"
            : "completed"
          : pendingStep
            ? "pending"
            : "pending";

      return {
        id: layer.id,
        sequence: layer.sequence_no,
        layerName: layer.layer_name,
        stepName: activeStep?.step_name ?? pendingStep?.step_name ?? templateStep?.step_name ?? layer.layer_name,
        status,
        isSelected: layer.id === selectedLayer?.id,
        isCurrent: layer.layer_name === currentStep?.layer_name,
      };
    });
  }, [currentStep?.layer_name, sampleRoute?.steps, selectedLayer?.id, template?.layers]);
  const completedNodeCount = useMemo(
    () => mapNodes.filter((node) => node.status === "completed").length,
    [mapNodes],
  );
  const flowProgressText = mapNodes.length
    ? `${completedNodeCount} / ${mapNodes.length} (${Math.round((completedNodeCount / mapNodes.length) * 100)}%)`
    : "-";
  const currentOperator = currentStep?.operator || sample?.owner || "-";
  const currentStartedAt = currentStep?.started_at
    ? currentStep.started_at.replace("T", " ").slice(0, 19)
    : "-";

  const loadMesFlow = useCallback(async () => {
    setMessage("");
    setTemplate(null);
    setSampleRoute(null);

    if (!projectCode) {
      return;
    }

    try {
      try {
        const nextTemplate = await getMesRouteTemplateByProject(projectCode);
        setTemplate(nextTemplate);
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) {
          setMessage(`项目 ${projectCode} 还没有 MES 流程模板，可先创建模板后维护图层和工段。`);
        } else {
          throw err;
        }
      }

      if (sample?.id) {
        try {
          const route = await getSampleMesRoute(sample.id);
          setSampleRoute(route);
        } catch (err) {
          if (!(err instanceof ApiError && err.status === 404)) {
            throw err;
          }
        }
      }
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "加载 MES 流程模板失败");
    }
  }, [projectCode, sample?.id]);

  useEffect(() => {
    void loadMesFlow();
  }, [loadMesFlow]);

  useEffect(() => {
    if (!template) {
      setEditingInstructions({});
      setSelectedDrawerLayerId(null);
      setSelectedLayerId(null);
      setHasManualLayerSelection(false);
      return;
    }

    const nextInstructions: Record<number, string> = {};
    for (const layer of template.layers) {
      for (const step of layer.steps) {
        nextInstructions[step.id] = step.default_instruction;
      }
    }
    setEditingInstructions(nextInstructions);
  }, [template]);

  useEffect(() => {
    function handlePointerDown(event: PointerEvent) {
      const target = event.target as HTMLElement | null;
      if (!target?.closest(".mes-template-layer-add-field")) {
        setLayerCandidateOpen(false);
      }
    }

    window.addEventListener("pointerdown", handlePointerDown);
    return () => window.removeEventListener("pointerdown", handlePointerDown);
  }, []);

  useEffect(() => {
    if (!template?.layers.length) {
      return;
    }
    const hasSelectedLayer = template.layers.some((layer) => layer.id === selectedLayerId);
    if (!hasSelectedLayer) {
      setSelectedLayerId(activeTemplateLayer?.id ?? template.layers[0].id);
      setHasManualLayerSelection(false);
    }
  }, [activeTemplateLayer?.id, selectedLayerId, template]);

  useEffect(() => {
    setHasManualLayerSelection(false);
    setSelectedLayerId(activeTemplateLayer?.id ?? template?.layers[0]?.id ?? null);
  }, [activeTemplateLayer?.id, sampleRoute?.id, template?.id]);

  useEffect(() => {
    if (!template?.layers.length) {
      return;
    }
    const hasSelectedLayer = template.layers.some((layer) => layer.id === selectedDrawerLayerId);
    if (!hasSelectedLayer) {
      setSelectedDrawerLayerId(selectedLayer?.id ?? template.layers[0].id);
    }
  }, [selectedDrawerLayerId, selectedLayer?.id, template]);

  async function handleCreateRoute() {
    if (!sample?.id) {
      setMessage("请先选择或保存一个样品，再建立流程实例。");
      return;
    }
    if (!template) {
      setMessage("当前项目没有可用流程模板。");
      return;
    }

    setSaving(true);
    setMessage("");
    try {
      const route = await createMesSampleRoute({
        sample_id: sample.id,
        route_template_id: template.id,
      });
      setSampleRoute(route);
      setMessage("样品流程实例已建立。");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "建立样品流程失败");
    } finally {
      setSaving(false);
    }
  }

  async function handleCreateTemplate() {
    if (!projectCode) {
      setMessage("请先输入项目编号，再创建 MES 流程模板。");
      return;
    }

    setSaving(true);
    setMessage("");
    try {
      const nextTemplate = await createMesRouteTemplate({
        project_code: projectCode,
        route_name: `${projectCode} standard wafer route`,
        version: "v1.0",
        status: "active",
        description: `Default route template for ${projectCode}.`,
      });
      setTemplate(nextTemplate);
      setDrawerMode("template");
      setIsLayerDrawerOpen(true);
      setMessage(`项目 ${projectCode} 的 MES 模板已创建，请继续新增图层和工段。`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "创建 MES 流程模板失败");
    } finally {
      setSaving(false);
    }
  }

  async function handleAddLayer() {
    const layerName = newLayerName.trim();
    if (!template || !layerName) {
      setMessage("请先输入图层名称。");
      return;
    }

    setSaving(true);
    setMessage("");
    try {
      const nextTemplate = await createMesRouteLayer(template.id, {
        layer_name: layerName,
        sequence_no: template.layers.length + 1,
      });
      setTemplate(nextTemplate);
      const createdLayer = nextTemplate.layers.find((layer) => layer.layer_name === layerName);
      setSelectedDrawerLayerId(createdLayer?.id ?? nextTemplate.layers.at(-1)?.id ?? null);
      setNewLayerName("");
      setMessage("图层已新增。");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "新增图层失败");
    } finally {
      setSaving(false);
    }
  }

  async function handleAddStep() {
    const stepName = newStepName.trim();
    if (!selectedDrawerLayer || !stepName) {
      setMessage("请先选择图层并输入工段名称。");
      return;
    }

    setSaving(true);
    setMessage("");
    try {
      const nextTemplate = await createMesRouteStep(selectedDrawerLayer.id, {
        step_name: stepName,
        step_type: "process_step",
        sequence_no: selectedDrawerLayer.steps.length + 1,
        default_instruction: newStepInstruction.trim(),
      });
      setTemplate(nextTemplate);
      const nextLayer = nextTemplate.layers.find((layer) => layer.id === selectedDrawerLayer.id);
      setSelectedDrawerLayerId(nextLayer?.id ?? selectedDrawerLayer.id);
      setNewStepName("");
      setNewStepInstruction("");
      setMessage("工段已新增。");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "新增工段失败");
    } finally {
      setSaving(false);
    }
  }

  async function handleSkipRoute() {
    if (!sampleRoute || !currentStep) {
      setMessage("当前没有可流转的 active 工步。");
      return;
    }

    setAdvancing(true);
    setMessage("");
    try {
      const route = await advanceMesSampleRoute(sampleRoute.id, { action: "skip" });
      setSampleRoute(route);
      setMessage("当前工步已跳过，流程已推进。");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "流程推进失败");
    } finally {
      setAdvancing(false);
    }
  }

  async function handleSaveStepInstruction(stepId: number) {
    setSavingStepId(stepId);
    setMessage("");
    try {
      const nextTemplate = await updateMesRouteStep(stepId, {
        default_instruction: editingInstructions[stepId] ?? "",
      });
      setTemplate(nextTemplate);
      setMessage("模板特殊要求已保存，后续新建流程会使用新模板。");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "保存特殊要求失败");
    } finally {
      setSavingStepId(null);
    }
  }

  function openTemplateDrawer() {
    setDrawerMode("template");
    setSelectedDrawerLayerId(selectedLayer?.id ?? template?.layers[0]?.id ?? null);
    setIsLayerDrawerOpen(true);
  }

  function handleSkipCurrentStep() {
    if (!window.confirm("确定要跳过当前工步吗？这可能会影响后续物料追溯。")) {
      return;
    }
    void handleSkipRoute();
  }

  async function handleDeleteStep(stepId: number, stepName: string) {
    if (!window.confirm(`确定删除工段「${stepName}」吗？`)) {
      return;
    }

    setSavingStepId(stepId);
    setMessage("");
    try {
      const nextTemplate = await deleteMesRouteStep(stepId);
      setTemplate(nextTemplate);
      setMessage("工段已删除。");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "删除工段失败");
    } finally {
      setSavingStepId(null);
    }
  }

  return (
    <>
      <section className="panel mes-flow-panel panel-section-spacing">
        <div className="mes-flow-header">
          <div>
            <h3>流程实例（工艺地图模式）</h3>
            <p className="subtle-text">
              按项目编号套用流程模板，自动生成样品的 MES 流程实例。
            </p>
          </div>
          <div className="mes-flow-actions">
            <button className="mes-template-text-button" type="button" disabled={!template} onClick={openTemplateDrawer}>
              维护模板
            </button>
            {!template && projectCode ? (
              <button className="ghost-button" type="button" disabled={saving} onClick={handleCreateTemplate}>
                创建模板
              </button>
            ) : null}
            <button className="mes-sync-template-button" type="button" disabled={saving || !sample || (!template && !projectCode)} onClick={sampleRoute ? loadMesFlow : handleCreateRoute}>
              {sampleRoute ? "同步流程模板" : saving ? "生成中..." : "保存并生成流程实例"}
            </button>
          </div>
        </div>

        <div className="mes-flow-stack mes-instance-stack">
          <div className="mes-map-summary">
            {[
              ["项目编号", projectCode || "-"],
              ["模板版本", template?.version ?? "-"],
              ["生成状态", sampleRoute ? "已生成" : "未生成"],
              ["当前层", activeTemplateLayer?.layer_name ?? selectedLayer?.layer_name ?? "-"],
              ["当前工步", currentStep?.step_name ?? "-"],
              ["流程进度", flowProgressText],
            ].map(([label, value]) => (
              <div className="mes-map-summary-item" key={label}>
                <span>{label}</span>
                <strong className={label === "生成状态" && sampleRoute ? "with-status-dot" : ""}>{value}</strong>
              </div>
            ))}
          </div>

          {message ? <p className="mes-flow-message">{message}</p> : null}

          <div className="mes-process-map-shell">
            <div className="mes-process-map-scroll" role="tablist" aria-label="工艺地图">
              <div className="mes-process-map-grid">
                {mapNodes.map((node, index) => {
                  const rowIndex = Math.floor(index / 6);
                  const columnIndex = index % 6;
                  const gridColumn = rowIndex % 2 === 0 ? columnIndex + 1 : 6 - columnIndex;
                  const isRowEnd = index % 6 === 5 || index === mapNodes.length - 1;
                  const shouldTurn = isRowEnd && index !== mapNodes.length - 1;
                  const directionClass = rowIndex % 2 === 0 ? "forward" : "reverse";
                  const turnClass = rowIndex % 2 === 0 ? "turn-right" : "turn-left";

                  return (
                    <div
                      className={`mes-map-node-wrap ${directionClass} ${isRowEnd ? "row-end" : ""} ${shouldTurn ? `turn-down ${turnClass}` : ""}`}
                      key={node.id}
                      style={{
                        gridColumn,
                        gridRow: rowIndex + 1,
                      }}
                    >
                      <button
                        className={`mes-map-node ${mapNodeStatusClass(node.status)} ${node.isSelected ? "selected" : ""} ${node.isCurrent ? "current" : ""}`}
                        type="button"
                        role="tab"
                        aria-selected={node.isSelected}
                        onClick={() => {
                          setSelectedLayerId(node.id);
                          setHasManualLayerSelection(true);
                        }}
                      >
                        <span>{String(node.sequence).padStart(2, "0")}</span>
                        <strong>{node.layerName}</strong>
                        <small>{statusLabel(node.status)}</small>
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>

            <aside className="mes-process-minimap">
              <strong>流程全景缩略图</strong>
              <div className="mes-minimap-grid" aria-hidden="true">
                {mapNodes.map((node) => (
                  <span className={`mes-minimap-dot ${mapNodeStatusClass(node.status)} ${node.isSelected ? "selected" : ""}`} key={node.id} />
                ))}
              </div>
              <div className="mes-minimap-legend">
                <span><i className="completed" />已完成</span>
                <span><i className="active" />进行中</span>
                <span><i className="pending" />待开始</span>
                <span><i className="skipped" />跳过</span>
              </div>
            </aside>
          </div>

          <section className="mes-map-operation-bar">
            {[
              ["当前工步", displayStep.status === "empty" ? displayStep.stepName : `${displayStep.layerName} / ${displayStep.stepName}`],
              ["状态", statusLabel(displayStep.status)],
              ["负责人", currentOperator],
              ["开始时间", currentStartedAt],
              ["下一步", displayStep.nextLayerName],
            ].map(([label, value]) => (
              <div className="mes-map-operation-field" key={label}>
                <span>{label}</span>
                <strong className={label === "状态" ? `mes-status-badge status-${displayStep.status}` : ""}>{value}</strong>
              </div>
            ))}
              <div className="mes-step-operation-actions">
                <button
                  className="mes-skip-step-button"
                  type="button"
                  disabled={!sampleRoute || !currentStep || advancing}
                  onClick={handleSkipCurrentStep}
                >
                  跳过
                </button>
              </div>
          </section>

          <details className="mes-execution-records">
            <summary>工步执行记录（点击展开）</summary>
            <div className="mes-execution-record-list">
              {(sampleRoute?.steps ?? []).slice(0, 30).map((step) => (
                <div key={step.id}>
                  <span>{String(step.layer_sequence_no).padStart(2, "0")}</span>
                  <strong>{step.layer_name} / {step.step_name}</strong>
                  <em>{statusLabel(step.status)}</em>
                  <small>{step.operator || "-"} · {step.started_at ? step.started_at.replace("T", " ").slice(0, 19) : "未开始"}</small>
                </div>
              ))}
              {sampleRoute?.steps.length ? null : <p>暂无工步执行记录。</p>}
            </div>
          </details>
        </div>
      </section>

      {isLayerDrawerOpen && template && drawerMode === "template" ? (
        <div className="mes-template-modal-shell" role="dialog" aria-modal="true">
          <div className="mes-template-modal">
            <header className="mes-template-modal-topbar">
              <div className="topbar-title">
                <button className="drawer-trigger ghost-button" type="button" aria-label="菜单" disabled>
                  ☰
                </button>
                <div>
                  <p className="eyebrow">SAMPLE MAINTENANCE</p>
                  <h2>样品建档维护</h2>
                </div>
              </div>
              <div className="mes-template-modal-actions">
                <span className="mes-saved-state">● 已保存</span>
                <button className="ghost-button" type="button" disabled>
                  版本历史
                </button>
                <button className="ghost-button mes-template-close-button" type="button" onClick={() => setIsLayerDrawerOpen(false)}>
                  ×
                </button>
              </div>
            </header>

            <main className="mes-template-editor">
              <aside className="mes-template-context-column">
                <section className="mes-template-context-card">
                  <header>
                    <h3>样品清单</h3>
                  </header>
                  <input aria-label="按样品 UID 搜索" placeholder="按样品 UID 搜索" readOnly />
                  <div className="mes-template-sample-list">
                    {samples.slice(0, 8).map((item) => (
                      <button
                        className={item.id === sample?.id ? "active" : ""}
                        key={item.id}
                        type="button"
                        disabled
                      >
                        <span>{item.sample_uid}</span>
                        <strong>{item.sample_display_code}</strong>
                        <em>{item.status}</em>
                      </button>
                    ))}
                    {samples.length ? null : <p className="subtle-text">暂无样品。</p>}
                  </div>
                </section>

              </aside>

              <section className="mes-template-editor-main">
                <div className="mes-template-editor-heading">
                  <div>
                    <h3>维护项目流程模板</h3>
                    <p className="subtle-text">复制为草稿版本后编辑，发布后仅影响后续新建样品。</p>
                  </div>
                </div>

                <div className="mes-template-compact-summary">
                  <div><span>项目编号</span><strong>{template.project_code}</strong></div>
                  <div><span>当前版本</span><strong>{template.version}</strong></div>
                  <div><span>编辑版本</span><strong>{template.status === "active" ? `${template.version} 草稿` : template.status}</strong></div>
                  <div><span>模板状态</span><strong>{template.status}</strong></div>
                  <div><span>更新时间</span><strong>{template.updated_at ? template.updated_at.replace("T", " ").slice(0, 16) : "-"}</strong></div>
                </div>

                <div className="mes-template-single-section-title">
                  <strong>工段维护</strong>
                  <span>选择左侧图层后维护对应工段。</span>
                </div>

                  <div className="mes-template-three-column">
                    <section className="mes-template-layer-column">
                      <header>
                        <div>
                          <h4>图层列表</h4>
                          <span>共 {template.layers.length} 层</span>
                        </div>
                        <div className="mes-template-inline-add">
                          <div className="mes-template-layer-add-field">
                            <input
                              value={newLayerName}
                              placeholder="新增图层"
                              onFocus={() => setLayerCandidateOpen(true)}
                              onClick={() => setLayerCandidateOpen(true)}
                              onChange={(event) => {
                                setNewLayerName(event.target.value);
                                setLayerCandidateOpen(true);
                              }}
                            />
                            {layerCandidateOpen && layerNameCandidates.length > 0 ? (
                              <div className="mes-template-layer-candidates">
                                {layerNameCandidates.map((name) => (
                                  <button
                                    key={name}
                                    type="button"
                                    onMouseDown={(event) => event.preventDefault()}
                                    onClick={() => {
                                      setNewLayerName(name);
                                      setLayerCandidateOpen(false);
                                    }}
                                  >
                                    {name}
                                  </button>
                                ))}
                              </div>
                            ) : null}
                          </div>
                          <button className="ghost-button" type="button" disabled={saving} onClick={handleAddLayer}>
                            + 新增图层
                          </button>
                        </div>
                      </header>
                      <div className="mes-template-layer-list">
                        {template.layers.map((layer) => (
                          <button
                            className={`mes-template-layer-row-card ${layer.id === selectedDrawerLayer?.id ? "active" : ""}`}
                            key={layer.id}
                            type="button"
                            onClick={() => setSelectedDrawerLayerId(layer.id)}
                          >
                            <span>{String(layer.sequence_no).padStart(2, "0")}</span>
                            <div>
                              <strong>{layer.layer_name}</strong>
                              <small>{layer.steps.length} 工段 · {layerSpecialRequirement(layer)}</small>
                            </div>
                            <em>拖拽</em>
                          </button>
                        ))}
                      </div>
                    </section>

                    <section className="mes-template-detail-column">
                      <header>
                        <div>
                          <h4>当前选中图层：{selectedDrawerLayer?.layer_name ?? "-"}</h4>
                          <span>{selectedDrawerLayer?.steps.length ?? 0} 个工段</span>
                        </div>
                      </header>

                      <div className="mes-template-layer-info-strip">
                        <div><span>图层名称</span><strong>{selectedDrawerLayer?.layer_name ?? "-"}</strong></div>
                        <div><span>备注</span><strong>{selectedDrawerLayer?.note || "无"}</strong></div>
                        <div><span>特殊要求</span><strong>{selectedDrawerLayer ? layerSpecialRequirement(selectedDrawerLayer) : "-"}</strong></div>
                      </div>

                      <div className="mes-template-step-table-head">
                        <h4>工段列表</h4>
                        <div className="mes-template-step-add-row">
                          <SelectCombobox
                            value={newStepName}
                            placeholder="工段名称"
                            options={PROCESS_STAGES}
                            onChange={setNewStepName}
                          />
                          <input
                            value={newStepInstruction}
                            placeholder="特殊要求"
                            onChange={(event) => setNewStepInstruction(event.target.value)}
                          />
                          <button type="button" disabled={saving || !selectedDrawerLayer} onClick={handleAddStep}>
                            + 新增工段
                          </button>
                        </div>
                      </div>

                      <div className="mes-template-step-table-wrap">
                        <table className="mes-template-step-table">
                          <thead>
                            <tr>
                              <th>工步序号</th>
                              <th>工段名称</th>
                              <th>特殊要求</th>
                              <th>操作</th>
                            </tr>
                          </thead>
                          <tbody>
                            {(selectedDrawerLayer?.steps ?? []).map((step) => (
                              <tr key={step.id}>
                                <td>{String(step.sequence_no).padStart(2, "0")}</td>
                                <td>{step.step_name}</td>
                                <td>
                                  <input
                                    value={editingInstructions[step.id] ?? ""}
                                    placeholder="特殊要求"
                                    onChange={(event) =>
                                      setEditingInstructions((current) => ({
                                        ...current,
                                        [step.id]: event.target.value,
                                      }))
                                    }
                                  />
                                </td>
                                <td>
                                  <div className="mes-template-table-actions">
                                    <button
                                      className="ghost-button"
                                      type="button"
                                      disabled={
                                        savingStepId === step.id ||
                                        (editingInstructions[step.id] ?? "") === (step.default_instruction ?? "")
                                      }
                                      onClick={() => handleSaveStepInstruction(step.id)}
                                    >
                                      保存
                                    </button>
                                    <button
                                      className="danger-button"
                                      type="button"
                                      disabled={savingStepId === step.id}
                                      onClick={() => handleDeleteStep(step.id, step.step_name)}
                                    >
                                      删除
                                    </button>
                                  </div>
                                </td>
                              </tr>
                            ))}
                            {selectedDrawerLayer?.steps.length ? null : (
                              <tr>
                                <td colSpan={4}>暂无工段，可在上方新增。</td>
                              </tr>
                            )}
                          </tbody>
                        </table>
                      </div>
                    </section>
                  </div>
              </section>
            </main>

            <footer className="mes-template-modal-footer">
              <span />
              <div>
                <button className="ghost-button" type="button" onClick={() => setIsLayerDrawerOpen(false)}>
                  取消
                </button>
                <button type="button" onClick={() => setIsLayerDrawerOpen(false)}>
                  应用选中图层
                </button>
              </div>
            </footer>
          </div>
        </div>
      ) : null}
    </>
  );
}
