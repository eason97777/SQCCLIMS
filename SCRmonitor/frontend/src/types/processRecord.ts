import type { Sample } from "./sample";

export type ProcessStage = "发料" | "光刻" | "检测" | "刻蚀" | "镀膜" | "湿法" | "MBE";

export type ProcessRecordStatus = "draft" | "submitted";

export type ProcessRecord = {
  id: number;
  stage: ProcessStage;
  layer_name: string;
  record_no: number;
  record_label: string;
  substrate_type: string;
  resistance_type: string;
  wafer_thickness: string;
  details?: Record<string, unknown>;
  status: ProcessRecordStatus;
  created_at: string;
  updated_at: string;
  sample: Pick<
    Sample,
    | "id"
    | "sample_uid"
    | "sample_display_code"
    | "sample_code"
    | "name"
    | "category"
    | "batch"
    | "owner"
    | "status"
  >;
};

export type ProcessRecordPayload = {
  id?: number;
  sample_id: number;
  stage: ProcessStage;
  layer_name?: string;
  record_no?: number;
  record_label?: string;
  substrate_type: string;
  resistance_type: string;
  wafer_thickness: string;
  details?: Record<string, unknown>;
  status: ProcessRecordStatus;
};

export type ProcessSampleLookupResponse = {
  sample: Sample;
  record: ProcessRecord | null;
};
