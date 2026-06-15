export type TestDataRecord = {
  id: number;
  sample_id: number;
  test_name: string;
  metric_name: string;
  numeric_value: number;
  unit: string;
  measured_at: string;
  operator: string;
  environment: string;
  raw_note: string;
  created_at: string;
  sample_uid?: string;
  sample_display_code?: string;
  sample_code: string;
  sample_name: string;
  sample_batch: string;
};

export type TestDataListParams = {
  sample_id?: string | number;
  query?: string;
};

export type TestDataPayload = {
  sample_id?: string | number;
  sample_code?: string;
  test_name: string;
  metric_name: string;
  numeric_value: string | number;
  unit?: string;
  measured_at?: string;
  operator?: string;
  environment?: string;
  raw_note?: string;
};

export type CsvImportRecord = Record<string, string>;

export type BulkCreateResult = {
  inserted: number;
  errors: Array<{
    index: number;
    error: string;
  }>;
};
