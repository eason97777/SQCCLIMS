export type Sample = {
  id: number;
  sample_uid: string;
  sample_display_code: string;
  projectCode?: string;
  sampleName?: string;
  processType?: string;
  sampleSeq?: string;
  responsiblePerson?: string;
  manager?: string;
  leader?: string;
  assignee?: string;
  remark?: string;
  comment?: string;
  code?: string;
  sampleNo?: string;
  sample_code: string;
  name: string;
  category: string;
  batch: string;
  owner: string;
  status: string;
  received_at: string;
  notes: string;
  created_at: string;
  updated_at: string;
  data_count?: number;
  last_measured_at?: string | null;
  collection_count?: number;
  characterization_file_count?: number;
  characterization_category_count?: number;
  latest_characterization_at?: string | null;
};

export type SamplePayload = {
  projectCode?: string;
  sampleName?: string;
  processType?: string;
  sampleSeq?: string;
  responsiblePerson?: string;
  remark?: string;
  sample_code: string;
  name: string;
  category?: string;
  batch?: string;
  owner?: string;
  status?: string;
  received_at?: string;
  notes?: string;
};

export type SampleListParams = {
  query?: string;
  status?: string;
};

export type DeleteResponse = {
  deleted: number;
};

export type SampleDeletePreview = {
  sample_display_code: string;
  test_data: number;
  process_records: number;
  raw_data: number;
  raw_data_files: number;
  parsed_data: number;
  parsed_records: number;
  characterization_files: number;
  performance_datasets: number;
  files_total: number;
};
