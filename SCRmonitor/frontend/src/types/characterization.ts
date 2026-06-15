import type { Sample } from "./sample";

export type CharacterizationFile = {
  id: number;
  collection_id: number | null;
  sample_id: number;
  category: string;
  technique: string;
  title: string;
  original_filename: string;
  stored_filename: string;
  storage_path: string;
  mime_type: string;
  file_size: number;
  relative_path: string;
  thumbnail_path: string;
  captured_at: string;
  operator: string;
  notes: string;
  created_at: string;
  sample_uid?: string;
  sample_display_code?: string;
  sample_code?: string;
  sample_name?: string;
  collection_name?: string;
  collection_storage_dir?: string;
  collection_instrument?: string;
  preview_type?: "image" | "pdf" | "text" | "download";
  is_previewable?: boolean;
};

export type CharacterizationFilesParams = {
  sample_id?: string | number;
  category?: string;
  query?: string;
};

export type CharacterizationCollection = {
  id: number;
  sample_id: number;
  category: string;
  name: string;
  technique: string;
  instrument: string;
  captured_at: string;
  operator: string;
  notes: string;
  storage_dir: string;
  created_at: string;
  updated_at: string;
  sample_uid?: string;
  sample_display_code?: string;
  sample_code?: string;
  sample_name?: string;
  file_count?: number;
  total_bytes?: number;
  latest_file_at?: string | null;
  files?: CharacterizationFile[];
};

export type CharacterizationCategoryNode = {
  name: string;
  collections: CharacterizationCollection[];
  file_count: number;
};

export type CharacterizationTree = {
  sample: Sample;
  categories: CharacterizationCategoryNode[];
};

export type CharacterizationSampleListItem = Sample;

export type CharacterizationCollectionPayload = {
  sample_id: string | number;
  category?: string;
  collection_name?: string;
  name?: string;
  technique?: string;
  instrument?: string;
  captured_at?: string;
  operator?: string;
  notes?: string;
};

export type CharacterizationUploadFields = {
  sample_id: string | number;
  collection_id?: string | number;
  category?: string;
  collection_name?: string;
  name?: string;
  technique?: string;
  instrument?: string;
  captured_at?: string;
  operator?: string;
  title?: string;
  notes?: string;
};

export type CharacterizationUploadResult = {
  inserted: number;
  ids: number[];
  collection_id: number;
};
