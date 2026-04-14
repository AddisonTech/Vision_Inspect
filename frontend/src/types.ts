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
}
