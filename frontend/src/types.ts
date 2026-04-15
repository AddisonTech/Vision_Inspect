export interface InspectionFinding {
  label: string;
  confidence: number;
  severity: string;
  bbox?: number[];
  description: string;
}

export interface InspectionResult {
  job_id: string;
  timestamp: string;
  model_used: string;
  pass_fail: string;
  findings: InspectionFinding[];
  notes: string;
}

export interface ProxyMetrics {
  mean_latency_ms: number;
  mean_confidence: number;
  confidence_drift_alert: boolean;
  distribution_shift_alert: boolean;
  sample_count: number;
}

export interface Report {
  filename: string;
  size_bytes: number;
  created_at: string;
}

export interface InspectionRecord {
  job_id: string;
  timestamp: string;
  task_type: string;
  source: string;
  model_used: string;
  pass_fail: string;
  confidence: number;
  latency_ms: number;
  finding_count: number;
  notes: string;
  findings: InspectionFinding[];
  report_path: string;
}

export interface InspectionStats {
  total: number;
  today: number;
  passed: number;
  failed: number;
  review: number;
  unknown: number;
  pass_rate: number;
  avg_confidence: number;
  avg_latency_ms: number;
  by_task: { task_type: string; count: number; avg_confidence: number; passed: number }[];
}
