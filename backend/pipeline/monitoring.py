import collections
import statistics

class FrameMonitor:
    def __init__(self, config: dict):
        self._config = config
        self._history = collections.deque(
            maxlen=config.get("video", {}).get("drift_window_frames", 30))

    def update(self, result) -> dict:
        self._history.append(result)
        anomaly_trend = sum(1 for r in self._history if 
            (getattr(r, "pass_fail", None) or r.get("pass_fail", "PASS") if isinstance(r, dict) else "PASS") == "FAIL")
        mean_confidence = statistics.mean([
            getattr(r, "confidence_scores", [0.5])[0] if isinstance(r, dict) else 0.5
            for r in self._history
        ])
        drift_detected = anomaly_trend >= config.get("video", {}).get("anomaly_trend_threshold", 3)
        return dict(anomaly_trend=anomaly_trend, mean_confidence=mean_confidence, drift_detected=drift_detected)

    def get_trend_summary(self) -> dict:
        h = list(self._history)
        n = len(h)
        if n == 0:
            return dict(frame_count_analyzed=0, anomaly_rate=0.0,
                       mean_confidence=0.0, drift_detected=False,
                       consecutive_anomaly_windows=0)
        anomaly_count = sum(1 for r in h if
            (getattr(r, "pass_fail", None) or r.get("pass_fail", "PASS") if isinstance(r, dict) else "PASS") == "FAIL")
        confs = [
            getattr(r, "confidence_scores", [0.5])[0] if isinstance(r, dict) else 0.5
            for r in h
        ]
        mean_conf = statistics.mean(confs)
        drift = anomaly_count >= self._config.get("video", {}).get("anomaly_trend_threshold", 3)
        return dict(
            frame_count_analyzed=n,
            anomaly_rate=round(anomaly_count / n, 3),
            mean_confidence=round(mean_conf, 4),
            drift_detected=drift,
            consecutive_anomaly_windows=anomaly_count,
        )
