import collections
import statistics
import logging

class ProxyMetricsCollector:
    def __init__(self, window_size: int = 50):
        self._latency: collections.deque = collections.deque(maxlen=window_size)
        self._confidence: collections.deque = collections.deque(maxlen=window_size)

    def record(self, latency_ms: float, confidence: float) -> None:
        self._latency.append(latency_ms)
        self._confidence.append(confidence)

    def get_metrics(self) -> dict:
        if not self._latency or not self._confidence:
            return {
                'mean_latency_ms': 0.0,
                'p95_latency_ms': 0.0,
                'mean_confidence': 0.0,
                'confidence_std': 0.0,
                'confidence_drift_alert': False,
                'distribution_shift_score': 0.0,
                'distribution_shift_alert': False,
                'sample_count': 0
            }
        latencies = list(self._latency)
        confidences = list(self._confidence)
        mean_latency_ms = sum(latencies) / len(latencies)
        p95_latency_ms = sorted(latencies)[int(len(latencies) * 0.95)]
        mean_confidence = sum(confidences) / len(confidences)
        confidence_std = statistics.stdev(confidences) if len(confidences) > 1 else 0
        shift = abs(mean_confidence - 0.5) * confidence_std
        confidence_drift_alert = confidence_std > 0.15
        distribution_shift_alert = shift > 0.3
        return {
            'mean_latency_ms': round(mean_latency_ms, 2),
            'p95_latency_ms': round(p95_latency_ms, 2),
            'mean_confidence': round(mean_confidence, 2),
            'confidence_std': round(confidence_std, 2),
            'confidence_drift_alert': confidence_drift_alert,
            'distribution_shift_score': round(shift, 2),
            'distribution_shift_alert': distribution_shift_alert,
            'sample_count': len(latencies)
        }

    def detect_silent_failures(self) -> list[str]:
        if len(self._latency) <= 5:
            return []
        mean_latency = sum(self._latency) / len(self._latency)
        mean_confidence = sum(self._confidence) / len(self._confidence)
        warnings = []
        if self._latency[-1] > mean_latency * 3:
            warnings.append("Latency spike detected")
        if mean_confidence < 0.4:
            warnings.append("Confidence collapse detected")
        if self.get_metrics()['distribution_shift_alert']:
            warnings.append("Distribution shift detected")
        return warnings

    def to_report_section(self) -> str:
        metrics = self.get_metrics()
        warnings = self.detect_silent_failures()
        table = f"""
| Metric                | Value       |
|-----------------------|-------------|
| Mean Latency (ms)     | {metrics['mean_latency_ms']} |
| P95 Latency (ms)      | {metrics['p95_latency_ms']}  |
| Mean Confidence       | {metrics['mean_confidence']} |
| Confidence Std        | {metrics['confidence_std']}  |
| Confidence Drift Alert| {'Yes' if metrics['confidence_drift_alert'] else 'No'} |
| Distribution Shift Score| {metrics['distribution_shift_score']} |
| Distribution Shift Alert| {'Yes' if metrics['distribution_shift_alert'] else 'No'} |
| Sample Count          | {metrics['sample_count']}  |

**Active Warnings:**
- {', '.join(warnings)}
"""
        return table

_collector = ProxyMetricsCollector()

def get_metrics_collector() -> ProxyMetricsCollector:
    return _collector

def record_inference(latency_ms: float, confidence: float) -> None:
    _collector.record(latency_ms, confidence)
