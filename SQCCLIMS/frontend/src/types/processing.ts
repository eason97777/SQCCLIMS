export type ProcessingMethod = "stats" | "qc" | "normalize";

export type ProcessingResultRecord = {
  id: number;
  job_name: string;
  method: string;
  sample_id: number | null;
  parameters_json: string;
  result_json: string;
  created_at: string;
  sample_uid?: string | null;
  sample_display_code?: string | null;
  sample_code?: string | null;
  sample_name?: string | null;
};

export type ProcessingRequest = {
  job_name?: string;
  method: ProcessingMethod | string;
  sample_id?: string | number | null;
  parameters?: {
    metric_name?: string;
    lower_limit?: string | number;
    upper_limit?: string | number;
  };
};
