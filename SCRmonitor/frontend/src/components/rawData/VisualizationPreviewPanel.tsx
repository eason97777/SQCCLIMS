import { useEffect, useMemo, useState } from "react";
import type {
  ParsedDataRecord,
  ParsedRecordOptionsResponse,
  ProcessingJobRecord,
  VisualizationChartMetadata,
  CdVisualizationPayload,
  VisualizationOutput,
  VisualizationSchemaField,
} from "../../types/rawData";
import { downloadVisualizationCharts, getParsedRecordOptions } from "../../api/rawDataApi";

type VisualizationPreviewPanelProps = {
  selectedParsedData: ParsedDataRecord | null;
  processingJobs: ProcessingJobRecord[];
  onVisualize: (parsedDataId: number, payload?: CdVisualizationPayload) => Promise<void> | void;
};

type ConfigPanelKey = "analysis" | "parameters" | "filters" | "advanced";
type AnalysisScopeMode = "all" | "select";
type ChartEditForm = {
  chartKey: string;
  title: string;
  xLabel: string;
  yLabel: string;
  yMin: string;
  yMax: string;
  decimalPlaces: string;
  yStep: string;
};

const CHART_ORDER = [
  "Horizontal_Left",
  "Horizontal_Right",
  "Horizontal_Overall",
  "Vertical_Left",
  "Vertical_Right",
  "Vertical_Overall",
];

const DEFAULT_DOSE_ORDER = ["Dose6", "Dose6.5", "Dose7", "Dose7.5", "Dose8", "Dose8.5", "Dose9"];
const FALLBACK_CATEGORICAL_FIELDS = ["dose", "side", "direction", "row_group", "die_no", "location"];
const FALLBACK_NUMERIC_FIELDS = ["cd_value"];
const FALLBACK_FILTERABLE_FIELDS = ["row_group", "side", "direction", "dose", "location"];

function defaultChartEditForm(chart?: VisualizationChartMetadata | null): ChartEditForm {
  return {
    chartKey: chart?.key || "",
    title: chart?.title || chart?.key || "",
    xLabel: "",
    yLabel: "结线宽 (nm)",
    yMin: "",
    yMax: "",
    decimalPlaces: "0",
    yStep: "",
  };
}

function optionalFormNumber(value: string) {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const number = Number(trimmed);
  return Number.isFinite(number) ? number : null;
}

function optionalFormInteger(value: string, fallback: number) {
  const number = Number(value);
  return Number.isFinite(number) ? Math.max(0, Math.trunc(number)) : fallback;
}

function parseOutputJson(value: string): VisualizationOutput | null {
  try {
    return JSON.parse(value || "{}") as VisualizationOutput;
  } catch {
    return null;
  }
}

function latestByFinishedAt(jobs: ProcessingJobRecord[]) {
  return [...jobs].sort((a, b) => {
    const left = new Date(a.finished_at || a.started_at || "").getTime() || 0;
    const right = new Date(b.finished_at || b.started_at || "").getTime() || 0;
    return right - left;
  })[0];
}

function sortCharts(charts: VisualizationChartMetadata[]) {
  return [...charts].sort((a, b) => {
    const left = CHART_ORDER.indexOf(a.key);
    const right = CHART_ORDER.indexOf(b.key);
    const safeLeft = left === -1 ? CHART_ORDER.length : left;
    const safeRight = right === -1 ? CHART_ORDER.length : right;
    return safeLeft - safeRight || a.key.localeCompare(b.key);
  });
}

function uniqueValues(values: string[]) {
  return [...new Set(values.map((value) => value.trim()).filter(Boolean))];
}

function fieldOptions(preferredFields: string[], allFields: string[]) {
  return uniqueValues([...preferredFields, ...allFields]);
}

function schemaFieldMap(fields: VisualizationSchemaField[]) {
  return new Map(fields.map((field) => [field.name, field]));
}

function toggleFilterValue(filters: Record<string, string[]>, field: string, value: string) {
  const currentValues = filters[field] || [];
  const nextValues = currentValues.includes(value)
    ? currentValues.filter((item) => item !== value)
    : [...currentValues, value];
  const nextFilters = { ...filters };
  if (nextValues.length > 0) {
    nextFilters[field] = nextValues;
  } else {
    delete nextFilters[field];
  }
  return nextFilters;
}

function selectAllFilterValues(filters: Record<string, string[]>, field: string, values: string[]) {
  const nextFilters = { ...filters };
  if (values.length > 0) {
    nextFilters[field] = values;
  } else {
    delete nextFilters[field];
  }
  return nextFilters;
}

function compactFilters(filters: Record<string, string[]>) {
  return Object.fromEntries(Object.entries(filters).filter(([, values]) => values.length > 0));
}

function moveOrderValue(values: string[], index: number, direction: -1 | 1) {
  const nextIndex = index + direction;
  if (nextIndex < 0 || nextIndex >= values.length) {
    return values;
  }
  const nextValues = [...values];
  [nextValues[index], nextValues[nextIndex]] = [nextValues[nextIndex], nextValues[index]];
  return nextValues;
}

export function VisualizationPreviewPanel({
  selectedParsedData,
  processingJobs,
  onVisualize,
}: VisualizationPreviewPanelProps) {
  const [xField, setXField] = useState("");
  const [yField, setYField] = useState("");
  const [splitField, setSplitField] = useState("");
  const [seriesField, setSeriesField] = useState("");
  const [mergeField] = useState("");
  const [filters, setFilters] = useState<Record<string, string[]>>({});
  const [analysisScopeMode, setAnalysisScopeMode] = useState<AnalysisScopeMode>("all");
  const [selectedRowGroups, setSelectedRowGroups] = useState<string[]>([]);
  const [xOrderState, setXOrderState] = useState({ field: "", values: [] as string[] });
  const [chartEditForm, setChartEditForm] = useState<ChartEditForm>(defaultChartEditForm());
  const [selectedChartKeys, setSelectedChartKeys] = useState<string[]>([]);
  const [recordOptions, setRecordOptions] = useState<ParsedRecordOptionsResponse | null>(null);
  const [recordOptionsLoading, setRecordOptionsLoading] = useState(false);
  const [recordOptionsError, setRecordOptionsError] = useState("");
  const [expandedPanels, setExpandedPanels] = useState<Record<ConfigPanelKey, boolean>>({
    analysis: true,
    parameters: false,
    filters: true,
    advanced: false,
  });

  const { successJob, failedJob, output } = useMemo(() => {
    if (!selectedParsedData || selectedParsedData.data_type !== "cd_sem") {
      return { successJob: undefined, failedJob: undefined, output: null };
    }

    const relatedJobs = processingJobs.filter(
      (job) => job.job_type === "visualization" && job.parsed_data_id === selectedParsedData.id,
    );
    const latestSuccess = latestByFinishedAt(
      relatedJobs.filter((job) => job.status === "success" && parseOutputJson(job.output_json)?.chart_url),
    );
    const latestFailed = latestByFinishedAt(relatedJobs.filter((job) => job.status === "failed"));

    return {
      successJob: latestSuccess,
      failedJob: latestFailed,
      output: latestSuccess ? parseOutputJson(latestSuccess.output_json) : null,
    };
  }, [processingJobs, selectedParsedData]);

  useEffect(() => {
    if (!selectedParsedData || selectedParsedData.data_type !== "cd_sem") {
      setRecordOptions(null);
      setRecordOptionsError("");
      setRecordOptionsLoading(false);
      return;
    }

    const abortToken = { cancelled: false };
    setRecordOptionsLoading(true);
    setRecordOptionsError("");

    getParsedRecordOptions(selectedParsedData.id)
      .then((loadedOptions) => {
        if (!abortToken.cancelled) {
          setRecordOptions(loadedOptions);
        }
      })
      .catch((error: unknown) => {
        if (!abortToken.cancelled) {
          setRecordOptions(null);
          setRecordOptionsError(error instanceof Error ? error.message : "record options load failed");
        }
      })
      .finally(() => {
        if (!abortToken.cancelled) {
          setRecordOptionsLoading(false);
        }
      });

    return () => {
      abortToken.cancelled = true;
    };
  }, [selectedParsedData]);

  const charts = useMemo(() => sortCharts(output?.charts || []), [output?.charts]);
  const hasCharts = charts.length > 0;
  const downloadableChartKeys = useMemo(
    () => charts.filter((chart) => chart.chart_url).map((chart) => chart.key),
    [charts],
  );
  const selectedDownloadableChartKeys = selectedChartKeys.filter((key) => downloadableChartKeys.includes(key));
  const schema = output?.schema;
  const fields = useMemo(() => schema?.fields || [], [schema?.fields]);
  const fieldMap = useMemo(() => schemaFieldMap(fields), [fields]);
  const schemaFields = useMemo(() => fields.map((field) => field.name).filter(Boolean), [fields]);
  const categoricalFields = schema?.categorical_fields?.length
    ? schema.categorical_fields
    : FALLBACK_CATEGORICAL_FIELDS;
  const numericFields = schema?.numeric_fields?.length ? schema.numeric_fields : FALLBACK_NUMERIC_FIELDS;
  const filterableFields = schema?.filterable_fields?.length
    ? schema.filterable_fields
    : schema?.categorical_fields?.length
      ? schema.categorical_fields
      : FALLBACK_FILTERABLE_FIELDS;
  const ordinaryFilterFields = filterableFields.filter((field) => field !== "row_group");
  const xFieldOptions = fieldOptions(categoricalFields, schemaFields);
  const yFieldOptions = fieldOptions(numericFields, schemaFields);
  const categoricalFieldOptions = fieldOptions(categoricalFields, schemaFields);
  const effectiveXField = xField || schema?.defaults?.x_field || "dose";
  const effectiveYField = yField || schema?.defaults?.y_field || "cd_value";
  const effectiveSplitField = splitField || schema?.defaults?.split_field || "direction";
  const effectiveSeriesField = seriesField || schema?.defaults?.series_field || "side";
  const effectiveMergeField = mergeField || schema?.defaults?.merge_field || "side";
  const activeFilters = compactFilters(filters);

  if (!selectedParsedData || selectedParsedData.data_type !== "cd_sem") {
    return null;
  }
  const activeParsedData = selectedParsedData;

  function fieldValues(fieldName: string) {
    const field = fieldMap.get(fieldName);
    if (field?.values?.length) {
      return field.values;
    }
    const optionValues = recordOptions?.options[fieldName as keyof ParsedRecordOptionsResponse["options"]] || [];
    const recordValues = optionValues.map((value) => String(value));
    if (fieldName === "dose" && recordValues.length === 0) {
      return DEFAULT_DOSE_ORDER;
    }
    return recordValues;
  }

  function defaultXOrder() {
    if (effectiveXField === "dose" && schema?.defaults?.x_order?.length) {
      return schema.defaults.x_order;
    }
    const values = fieldValues(effectiveXField);
    if (values.length > 0) {
      return values;
    }
    return effectiveXField === "dose" ? DEFAULT_DOSE_ORDER : [];
  }

  const currentXOrder = xOrderState.field === effectiveXField && xOrderState.values.length > 0
    ? xOrderState.values
    : defaultXOrder();
  const rowGroupValues = fieldValues("row_group");
  const activeRowGroups = selectedRowGroups.filter((value) => rowGroupValues.includes(value));

  function setCurrentXOrder(values: string[]) {
    setXOrderState({ field: effectiveXField, values });
  }

  function resetXOrder() {
    setCurrentXOrder(defaultXOrder());
  }

  function togglePanel(panel: ConfigPanelKey) {
    setExpandedPanels((currentPanels) => ({ ...currentPanels, [panel]: !currentPanels[panel] }));
  }

  function buildPayload(): CdVisualizationPayload {
    const payloadFilters = { ...activeFilters };
    if (analysisScopeMode === "select" && activeRowGroups.length > 0) {
      payloadFilters.row_group = activeRowGroups;
    } else {
      delete payloadFilters.row_group;
    }

    return {
      chart_type: "violin",
      x_field: effectiveXField,
      y_field: effectiveYField,
      split_field: effectiveSplitField,
      series_field: effectiveSeriesField,
      merge_field: effectiveMergeField,
      merge_rule: { label: "Overall", source_values: ["Left", "Right"] },
      output_mode: "notebook_six_pack",
      inspect_schema: true,
      filters: payloadFilters,
      x_order: currentXOrder,
      title_prefix: activeParsedData.raw_data_code || activeParsedData.sample_display_code || "",
      title: "CD Distribution by Dose",
    };
  }

  function openChartEdit(chart: VisualizationChartMetadata) {
    setChartEditForm(defaultChartEditForm(chart));
  }

  function closeChartEdit() {
    setChartEditForm(defaultChartEditForm());
  }

  function updateChartEditForm(field: keyof ChartEditForm, value: string) {
    setChartEditForm((current) => ({ ...current, [field]: value }));
  }

  function toggleSelectedChart(chartKey: string) {
    setSelectedChartKeys((currentKeys) =>
      currentKeys.includes(chartKey)
        ? currentKeys.filter((key) => key !== chartKey)
        : [...currentKeys, chartKey],
    );
  }

  function saveSelectedCharts() {
    if (!successJob || selectedDownloadableChartKeys.length === 0) {
      return;
    }
    void downloadVisualizationCharts(successJob.id, selectedDownloadableChartKeys);
  }

  function submitChartEdit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!chartEditForm.chartKey) {
      return;
    }

    const payload = buildPayload();
    payload.chart_overrides = {
      chart_key: chartEditForm.chartKey,
      title: chartEditForm.title.trim() || chartEditForm.chartKey,
      x_label: chartEditForm.xLabel.trim(),
      y_label: chartEditForm.yLabel.trim() || "结线宽 (nm)",
      y_min: optionalFormNumber(chartEditForm.yMin),
      y_max: optionalFormNumber(chartEditForm.yMax),
      decimal_places: optionalFormInteger(chartEditForm.decimalPlaces, 0),
      y_step: optionalFormNumber(chartEditForm.yStep),
    };

    closeChartEdit();
    void onVisualize(activeParsedData.id, payload);
  }

  function renderConfigPanel(
    panel: ConfigPanelKey,
    title: string,
    children: React.ReactNode,
    action?: React.ReactNode,
  ) {
    const isExpanded = expandedPanels[panel];
    return (
      <section className={`visualization-config-panel ${isExpanded ? "expanded" : "collapsed"}`}>
        <button
          className="visualization-config-panel-header"
          type="button"
          aria-expanded={isExpanded}
          onClick={() => togglePanel(panel)}
        >
          <span>{title}</span>
          <span>{isExpanded ? "收起" : "展开"}</span>
        </button>
        {isExpanded ? (
          <div className="visualization-config-panel-body">
            {action}
            {children}
          </div>
        ) : null}
      </section>
    );
  }

  return (
    <section className="raw-detail-section visualization-preview-section">
      <div className="visualization-workbench">
        <aside className="visualization-sidebar visualization-parameter-panel">
          {renderConfigPanel(
            "analysis",
            "分析范围",
            <>
              <div className="visualization-segment-buttons visualization-scope-buttons">
                <label>
                  <input
                    checked={analysisScopeMode === "all"}
                    type="checkbox"
                    onChange={() => setAnalysisScopeMode("all")}
                  />
                  <span>全部行合并</span>
                </label>
                <label>
                  <input
                    checked={analysisScopeMode === "select"}
                    type="checkbox"
                    onChange={() => setAnalysisScopeMode("select")}
                  />
                  <span>选择 row_group</span>
                </label>
              </div>
              {analysisScopeMode === "select" ? (
                rowGroupValues.length > 0 ? (
                  <fieldset className="visualization-filter-group">
                    <legend>row_group</legend>
                    <div className="visualization-filter-options">
                      {rowGroupValues.map((value) => (
                        <label className={activeRowGroups.includes(value) ? "active" : ""} key={value}>
                          <input
                            checked={activeRowGroups.includes(value)}
                            type="checkbox"
                            onChange={() =>
                              setSelectedRowGroups((currentValues) =>
                                currentValues.includes(value)
                                  ? currentValues.filter((item) => item !== value)
                                  : [...currentValues, value],
                              )
                            }
                          />
                          <span>{value}</span>
                        </label>
                      ))}
                    </div>
                  </fieldset>
                ) : (
                  <p className="visualization-filter-empty">暂无可选值</p>
                )
              ) : null}
              <p className="visualization-helper-text">
                如果不同行对应不同 CD 尺寸结构，请选择具体 row_group；如果各行图形一致，可全部合并查看整体均匀性。
              </p>
            </>,
          )}

          {renderConfigPanel(
            "parameters",
            "基础参数",
            <>
              <div className="visualization-parameter-grid">
                <label>
                  X 轴
                  <select
                    value={effectiveXField}
                    onChange={(event) => {
                      setXField(event.target.value);
                      setXOrderState({ field: "", values: [] });
                    }}
                  >
                    {xFieldOptions.map((field) => (
                      <option key={field} value={field}>{field}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Y 轴
                  <select value={effectiveYField} onChange={(event) => setYField(event.target.value)}>
                    {yFieldOptions.map((field) => (
                      <option key={field} value={field}>{field}</option>
                    ))}
                  </select>
                </label>
                <label>
                  拆图字段
                  <select value={effectiveSplitField} onChange={(event) => setSplitField(event.target.value)}>
                    {categoricalFieldOptions.map((field) => (
                      <option key={field} value={field}>{field}</option>
                    ))}
                  </select>
                </label>
                <label>
                  系列字段
                  <select value={effectiveSeriesField} onChange={(event) => setSeriesField(event.target.value)}>
                    {categoricalFieldOptions.map((field) => (
                      <option key={field} value={field}>{field}</option>
                    ))}
                  </select>
                </label>
              </div>
              <dl className="visualization-default-params">
                <div>
                  <dt>merge_field</dt>
                  <dd>{effectiveMergeField}</dd>
                </div>
                <div>
                  <dt>output_mode</dt>
                  <dd>notebook_six_pack</dd>
                </div>
              </dl>
            </>,
          )}

          {renderConfigPanel(
            "filters",
            "筛选条件",
            ordinaryFilterFields.length > 0 ? (
              <div className="visualization-filter-list">
                {ordinaryFilterFields.map((fieldName) => {
                  const values = fieldValues(fieldName);
                  const selectedValues = filters[fieldName] || [];
                  return (
                    <fieldset className="visualization-filter-group" key={fieldName}>
                      <legend>
                        <span>{fieldName}</span>
                        {values.length > 0 ? (
                          <button
                            type="button"
                            onClick={() =>
                              setFilters((currentFilters) => selectAllFilterValues(currentFilters, fieldName, values))
                            }
                          >
                            全选
                          </button>
                        ) : null}
                      </legend>
                      {values.length > 0 ? (
                        <div className="visualization-filter-options">
                          {values.map((value) => (
                            <label className={selectedValues.includes(value) ? "active" : ""} key={value}>
                              <input
                                checked={selectedValues.includes(value)}
                                type="checkbox"
                                onChange={() =>
                                  setFilters((currentFilters) => toggleFilterValue(currentFilters, fieldName, value))
                                }
                              />
                              <span>{value}</span>
                            </label>
                          ))}
                        </div>
                      ) : (
                        <p className="visualization-filter-empty">暂无可选值</p>
                      )}
                    </fieldset>
                  );
                })}
              </div>
            ) : (
              <p className="visualization-filter-empty">暂无可用筛选字段</p>
            ),
            <button className="visualization-panel-action" type="button" onClick={() => setFilters({})}>
              清空筛选
            </button>,
          )}

          {renderConfigPanel(
            "advanced",
            "高级配置",
            <>
              <div className="visualization-filter-headline">
                <h4>X 轴顺序</h4>
                <button type="button" onClick={resetXOrder}>重置顺序</button>
              </div>
              {currentXOrder.length > 0 ? (
                <ol className="visualization-order-list">
                  {currentXOrder.map((value: string, index: number) => (
                    <li key={value}>
                      <span>{value}</span>
                      <div>
                        <button
                          type="button"
                          disabled={index === 0}
                          onClick={() => setCurrentXOrder(moveOrderValue(currentXOrder, index, -1))}
                        >
                          上移
                        </button>
                        <button
                          type="button"
                          disabled={index === currentXOrder.length - 1}
                          onClick={() => setCurrentXOrder(moveOrderValue(currentXOrder, index, 1))}
                        >
                          下移
                        </button>
                      </div>
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="visualization-filter-empty">暂无可排序字段值</p>
              )}
            </>,
          )}

          <div className="visualization-action-bar">
            <button type="button" disabled={recordOptionsLoading} onClick={() => onVisualize(activeParsedData.id, buildPayload())}>
              生成图表
            </button>
            <button
              className="secondary"
              type="button"
              disabled={!successJob || selectedDownloadableChartKeys.length === 0}
              title={selectedDownloadableChartKeys.length === 0 ? "请先选择要保存的图表" : "保存选中的高清图表"}
              onClick={saveSelectedCharts}
            >
              保存选中
            </button>
          </div>
          {recordOptionsLoading ? <p className="visualization-filter-empty">Loading record options...</p> : null}
          {recordOptionsError ? <p className="visualization-filter-empty">{recordOptionsError}</p> : null}
        </aside>

        <div className="visualization-main">
          {!successJob || !output ? (
            <div className="visualization-empty-state">
              <strong>暂无图表结果</strong>
              <span>
                {failedJob?.error_message
                  ? `最近一次可视化失败：${failedJob.error_message}`
                  : "点击生成图表后查看 notebook_six_pack 结果。"}
              </span>
            </div>
          ) : (
            <section className="visualization-results-panel">
              <div className="visualization-preview-header">
                <h4>{hasCharts ? "多图结果" : "图表"}</h4>
                <div className="job-output-links">
                  {output.report_url ? <a href={output.report_url} target="_blank" rel="noreferrer">report</a> : null}
                  {output.report_json_url ? <a href={output.report_json_url} target="_blank" rel="noreferrer">json</a> : null}
                </div>
              </div>

              {hasCharts ? (
                <div className="visualization-chart-grid">
                  {charts.map((chart) => {
                    const isSelected = selectedChartKeys.includes(chart.key);
                    return (
                    <article className={`visualization-chart-card ${isSelected ? "selected" : ""}`} key={chart.key}>
                      <div className="visualization-chart-card-header">
                        <div className="visualization-chart-title-row">
                          <label className="visualization-chart-select" title="选择保存这张图">
                            <input
                              type="checkbox"
                              checked={isSelected}
                              disabled={!chart.chart_url}
                              onChange={() => toggleSelectedChart(chart.key)}
                            />
                            <span />
                          </label>
                          <h5>{chart.key}</h5>
                          <button
                            className="visualization-chart-edit-button"
                            type="button"
                            title="编辑图表信息"
                            aria-label={`编辑 ${chart.key}`}
                            onClick={() => openChartEdit(chart)}
                          >
                            ✎
                          </button>
                        </div>
                        {chart.chart_url ? (
                          <a href={chart.chart_url} target="_blank" rel="noreferrer">
                            打开图片
                          </a>
                        ) : null}
                      </div>

                      {chart.chart_url ? (
                        <div className="visualization-chart-thumb">
                          <img src={chart.chart_url} alt={chart.title || chart.key} loading="lazy" />
                        </div>
                      ) : (
                        <div className="visualization-chart-missing">图片不可用</div>
                      )}
                    </article>
                    );
                  })}
                </div>
              ) : output.chart_url ? (
                <div className="visualization-single-chart">
                  <a href={output.chart_url} target="_blank" rel="noreferrer">打开图片</a>
                  <div className="visualization-chart-frame">
                    <img src={output.chart_url} alt="CD violin chart" />
                  </div>
                </div>
              ) : (
                <div className="visualization-empty-state">
                  <strong>图片不可用</strong>
                </div>
              )}
            </section>
          )}
        </div>
      </div>
      {chartEditForm.chartKey ? (
        <div className="visualization-edit-modal" role="dialog" aria-modal="true">
          <button
            className="visualization-edit-backdrop"
            type="button"
            aria-label="关闭图表编辑"
            onClick={closeChartEdit}
          />
          <form className="visualization-edit-panel" onSubmit={submitChartEdit}>
            <header>
              <h4>编辑图表信息</h4>
              <button className="ghost-button" type="button" onClick={closeChartEdit}>
                关闭
              </button>
            </header>
            <div className="visualization-edit-grid">
              <label>
                图表名称
                <input
                  value={chartEditForm.title}
                  onChange={(event) => updateChartEditForm("title", event.target.value)}
                />
              </label>
              <label>
                X轴标签
                <input
                  value={chartEditForm.xLabel}
                  onChange={(event) => updateChartEditForm("xLabel", event.target.value)}
                />
              </label>
              <label>
                Y轴标签
                <input
                  value={chartEditForm.yLabel}
                  onChange={(event) => updateChartEditForm("yLabel", event.target.value)}
                />
              </label>
              <label>
                Y轴最小值
                <input
                  type="number"
                  step="any"
                  value={chartEditForm.yMin}
                  onChange={(event) => updateChartEditForm("yMin", event.target.value)}
                />
              </label>
              <label>
                Y轴最大值
                <input
                  type="number"
                  step="any"
                  value={chartEditForm.yMax}
                  onChange={(event) => updateChartEditForm("yMax", event.target.value)}
                />
              </label>
              <label>
                小数点位数
                <input
                  min="0"
                  type="number"
                  value={chartEditForm.decimalPlaces}
                  onChange={(event) => updateChartEditForm("decimalPlaces", event.target.value)}
                />
              </label>
              <label>
                步进
                <input
                  type="number"
                  step="any"
                  value={chartEditForm.yStep}
                  onChange={(event) => updateChartEditForm("yStep", event.target.value)}
                />
              </label>
            </div>
            <footer>
              <button className="ghost-button" type="button" onClick={closeChartEdit}>
                取消
              </button>
              <button type="submit">应用并重新生成</button>
            </footer>
          </form>
        </div>
      ) : null}
    </section>
  );
}
