export type SummaryStatusCount = {
  status: string;
  count: number;
};

export type SummaryRecentData = {
  id: number;
  test_name: string;
  metric_name: string;
  numeric_value: number;
  unit: string;
  measured_at: string;
  sample_uid?: string;
  sample_display_code?: string;
  sample_code: string;
  sample_name: string;
};

export type SummaryLatestResult = {
  id: number;
  job_name: string;
  method: string;
  created_at: string;
} | null;

export type DashboardSummary = {
  sample_count: number;
  data_count: number;
  result_count: number;
  metric_count: number;
  status_counts: SummaryStatusCount[];
  recent_data: SummaryRecentData[];
  latest_result: SummaryLatestResult;
};
