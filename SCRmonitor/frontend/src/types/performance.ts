export type PerformanceDataset = {
  id: number;
  sample_id: number;
  aliquot_code: string;
  dataset_name: string;
  test_type: string;
  data_format: string;
  source_folder_name: string;
  storage_dir: string;
  file_count: number;
  total_bytes: number;
  collected_at: string;
  operator: string;
  status: string;
  notes: string;
  created_at: string;
  sample_uid?: string;
  sample_display_code?: string;
  sample_code: string;
  sample_name: string;
};

export type PerformanceDatasetFile = {
  id: number;
  dataset_id: number;
  relative_path: string;
  original_filename: string;
  stored_filename: string;
  storage_path: string;
  mime_type: string;
  file_size: number;
  created_at: string;
};

export type PerformanceDatasetListParams = {
  sample_id?: string | number;
  query?: string;
};

export type PerformanceDatasetFields = {
  sample_id: string | number;
  aliquot_code?: string;
  dataset_name: string;
  test_type?: string;
  data_format?: string;
  source_folder_name?: string;
  collected_at?: string;
  operator?: string;
  status?: string;
  notes?: string;
};
