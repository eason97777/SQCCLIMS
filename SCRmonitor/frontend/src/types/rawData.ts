export type RawDataType =
  | "resistance"
  | "cd_sem"
  | "sem_image"
  | "xps"
  | "xrd"
  | "afm"
  | "report"
  | "instrument_folder"
  | "generic_file";

export type RawDataRecord = {
  id: number;
  sample_id: number;
  sample_uid: string;
  sample_display_code: string;
  raw_data_code: string;
  raw_data_name: string;
  data_type: RawDataType | string;
  data_category: string;
  source_type: string;
  instrument: string;
  operator: string;
  measured_at: string;
  parser_status: string;
  status: string;
  file_count: number;
  total_size: number;
  storage_path: string;
  metadata_json: string;
  notes: string;
  created_at: string;
  updated_at: string;
  parsed_data_count?: number;
  processing_job_count?: number;
  files?: RawDataFile[];
};

export type RawDataFile = {
  id: number;
  raw_data_id: number;
  original_filename: string;
  stored_filename: string;
  relative_path: string;
  file_path: string;
  file_ext: string;
  mime_type: string;
  file_size: number;
  sha256: string;
  file_role: string;
  preview_supported: number;
  created_at: string;
};

export type DeleteRawDataFileResponse = {
  deleted_file_id: number;
  raw_data_id: number;
  deleted_parsed_data_ids?: number[];
  deleted_processing_job_ids?: number[];
  deleted_output_paths?: string[];
  strategy: string;
  message?: string;
  raw_data?: RawDataRecord;
};

export type RawDataListParams = {
  raw_data_id?: string | number;
  sample_id?: string | number;
  data_type?: string;
  parser_status?: string;
  status?: string;
  query?: string;
};

export type RawDataPayload = {
  sample_id: string | number;
  raw_data_name: string;
  data_type: string;
  source_type?: string;
  instrument?: string;
  operator?: string;
  measured_at?: string;
  metadata_json?: string;
  notes?: string;
};

export type ParsedDataRecord = {
  id: number;
  raw_data_id: number;
  sample_id: number;
  sample_uid: string;
  sample_display_code: string;
  raw_data_code: string;
  data_type: string;
  parser_name: string;
  parser_version: string;
  parsed_status: string;
  schema_version: string;
  records_json: string;
  summary_json: string;
  plots_json: string;
  warnings_json: string;
  errors_json: string;
  output_file_path: string;
  created_at: string;
};

export type ParsedRecordItem = {
  id: number;
  parsed_data_id: number;
  raw_data_id: number | null;
  sample_id: number | null;
  sample_uid: string | null;
  raw_data_code: string | null;
  data_type: string;
  record_index: number | null;
  primary_key: string | null;
  group_key: string | null;
  x_value: number | null;
  y_value: number | null;
  numeric_value: number | null;
  raw_value: string | null;
  cleaned_value: string | null;
  is_outlier: number | boolean;
  outlier_reason: string | null;
  die_id: string | null;
  area: string | null;
  row_index: number | null;
  col_index: number | null;
  row_header: string | null;
  col_header: string | null;
  row_group: string | null;
  side: string | null;
  direction: string | null;
  dose: string | null;
  location: string | null;
  extra_json: string | null;
  created_at: string;
};

export type ParsedRecordsParams = {
  page?: number;
  page_size?: number;
  data_type?: string;
  die_id?: string;
  area?: string;
  is_outlier?: boolean | number | string;
  is_na?: boolean | number | string;
  row_group?: string;
  side?: string;
  direction?: string;
  dose?: string;
  location?: string;
  q?: string;
};

export type ParsedRecordsResponse = {
  items: ParsedRecordItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  filters: {
    parsed_data_id: number;
    data_type: string | null;
    die_id: string | null;
    area: string | null;
    is_outlier: boolean | null;
    is_na: boolean | null;
    row_group: string | null;
    side: string | null;
    direction: string | null;
    dose: string | null;
    location: string | null;
    q: string | null;
  };
};

export type ParsedRecordOptionsResponse = {
  parsed_data_id: number;
  data_type: string;
  options: {
    die_id: string[];
    area: string[];
    row_group: string[];
    side: string[];
    direction: string[];
    dose: string[];
    location: string[];
    is_outlier: number[];
    is_na: number[];
  };
  counts: {
    total: number;
  };
};

export type ResistanceStats = {
  die_id?: string | null;
  area?: string | null;
  count_total?: number;
  count_valid?: number;
  count_na?: number;
  count_normal?: number;
  count_outlier?: number;
  yield_rate?: number | null;
  max?: number | null;
  min?: number | null;
  range?: number | null;
  average?: number | null;
  std?: number | null;
  three_sigma?: number | null;
  uniformity?: number | null;
};

export type ResistanceLayoutValue = {
  id: number;
  die_id: string | null;
  area: string | null;
  row_index: number | null;
  col_index: number | null;
  row_header: string | null;
  col_header: string | null;
  raw_value: string | null;
  cleaned_value: string | null;
  numeric_value: number | null;
  value: number | null;
  is_na: boolean;
  is_outlier: boolean;
  outlier_reason: string | null;
};

export type ResistanceSummaryRequest = {
  cleaning_config?: {
    lower?: number | null;
    upper?: number | null;
  };
  metric?: "numeric_value" | "cleaned_value" | "raw_value";
  area?: string | null;
  die_id?: string | null;
};

export type ResistanceSummaryResponse = {
  parsed_data_id: number;
  cleaning_config: {
    lower: number | null;
    upper: number | null;
  };
  metric: string;
  filters: {
    die_id: string | null;
    area: string | null;
  };
  overall_summary: ResistanceStats;
  die_summary: ResistanceStats[];
  area_summary: ResistanceStats[];
  layout_values: ResistanceLayoutValue[];
};

export type ProcessingJobRecord = {
  id: number;
  job_type: string;
  job_name: string;
  raw_data_id: number | null;
  parsed_data_id: number | null;
  sample_id: number | null;
  sample_uid: string;
  data_type: string;
  script_name: string;
  script_version: string;
  input_json: string;
  output_json: string;
  status: string;
  error_message: string;
  started_at: string;
  finished_at: string;
};

export type ResistanceVisualizationPayload = {
  chart_type: "resistance_wafer_heatmap";
  metric: string;
  area: string;
  cleaning_config: {
    enabled: boolean;
    lower_limit: number | null;
    upper_limit: number | null;
  };
  display: {
    show_die_label: boolean;
    show_value: boolean;
    decimal_places: number;
  };
  summary: {
    overall_summary: Record<string, unknown>;
    die_summary: Array<Record<string, unknown>>;
    area_summary: Array<Record<string, unknown>>;
  };
  layout_values: Array<Array<{
    die_id: string;
    value: number | null;
    label: string;
    has_data: boolean;
  } | null>>;
};

export type CdVisualizationPayload = {
  chart_type: "violin";
  x_field?: string;
  y_field?: string;
  hue_field?: string;
  facet_field?: string;
  split_field?: string;
  series_field?: string;
  merge_field?: string;
  merge_rule?: {
    label: string;
    source_values: string[];
  };
  output_mode?: "single_chart" | "notebook_six_pack" | string;
  x_order?: string[];
  inspect_schema?: boolean;
  title_prefix?: string;
  wafer_label?: string;
  include_overall?: boolean;
  filters?: Record<string, string[]>;
  title?: string;
  chart_overrides?: {
    chart_key?: string;
    title?: string;
    x_label?: string;
    y_label?: string;
    y_min?: number | null;
    y_max?: number | null;
    decimal_places?: number;
    y_step?: number | null;
  };
};

export type VisualizationPayload = CdVisualizationPayload | ResistanceVisualizationPayload;

export type VisualizationChartMetadata = {
  key: string;
  title: string;
  chart_url?: string;
  chart_path?: string;
  direction: string;
  side: string;
  point_count: number;
  group_count: number;
  warnings: string[];
};

export type VisualizationSchemaField = {
  name: string;
  kind: "numeric" | "categorical" | string;
  non_empty_count?: number;
  empty_count?: number;
  unique_count?: number;
  sample_values?: Array<string | number>;
  values?: string[];
  recommended_roles?: string[];
  min?: number;
  max?: number;
};

export type VisualizationSchemaMetadata = {
  fields: VisualizationSchemaField[];
  defaults: {
    x_field?: string;
    y_field?: string;
    split_field?: string;
    series_field?: string;
    merge_field?: string;
    output_mode?: string;
    x_order?: string[];
  };
  numeric_fields: string[];
  categorical_fields: string[];
  filterable_fields?: string[];
  warnings?: string[];
};

export type VisualizationOutput = {
  chart_url?: string;
  report_url?: string;
  report_json_url?: string;
  charts?: VisualizationChartMetadata[];
  schema?: VisualizationSchemaMetadata;
};

export type MockParsedDataPayload = {
  raw_data_id: number;
  parser_name?: string;
  parser_version?: string;
  records?: Array<Record<string, unknown>>;
  summary?: Record<string, unknown>;
  warnings?: string[];
  plots?: Array<Record<string, unknown>>;
  errors?: string[];
};
