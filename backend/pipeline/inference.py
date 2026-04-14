import requests
import json
import time
from datetime import datetime
from dataclasses import dataclass
import numpy as np

from backend.config_loader import load_vlm_config
from backend.pipeline.preprocessing import frame_to_base64

TASK_PROMPTS = {
    "defect_detection": "Inspect the image for defects.",
    "surface_anomaly_classification": "Classify anomalies on the surface of the object.",
    "nameplate_ocr": "Extract text from nameplates using OCR.",
    "serial_number_extraction": "Extract serial numbers from images.",
    "engineering_drawing_interpretation": "Interpret engineering drawings in the image.",
    "process_deviation_flagging": "Flag deviations from the process in the image."
}

@dataclass
class InferenceResult:
    task_type: str
    model_used: str
    raw_response: str
    findings: list
    confidence_scores: list
    latency_ms: float
    timestamp: str

class VLMInferenceEngine:
    def __init__(self, vlm_config: dict):
        self.vlm_config = vlm_config

    def _get_model_for_task(self, task_type: str) -> str:
        if task_type in ["nameplate_ocr", "serial_number_extraction"]:
            return self.vlm_config["fallback_model"]
        else:
            return self.vlm_config["primary_model"]

    def _call_ollama(self, model: str, prompt: str, image_b64: str) -> dict:
        url = f"{self.vlm_config['ollama']['base_url']}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "images": [image_b64],
            "stream": False
        }
        headers = {
            "Content-Type": "application/json"
        }
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=self.vlm_config["timeout"])
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            return {}

    def run_inspection(self, frames: list, task_type: str,
                       inspection_config: dict) -> InferenceResult:
        model = self._get_model_for_task(task_type)
        prompt = TASK_PROMPTS.get(task_type, "Inspect the image.")
        image_b64 = frame_to_base64(frames[0])
        start_time = time.time()
        response = self._call_ollama(model, prompt, image_b64)
        latency_ms = (time.time() - start_time) * 1000
        raw_response = json.dumps(response)
        
        try:
            findings = response.get("findings", [])
            confidence_scores = [item.get("confidence", 0.0) for item in findings]
        except KeyError:
            findings = []
            confidence_scores = []

        if not findings or min(confidence_scores) < self.vlm_config["routing"]["retry_below_confidence"]:
            fallback_model = self._get_model_for_task(task_type)
            response = self._call_ollama(fallback_model, prompt, image_b64)
            try:
                findings = response.get("findings", [])
                confidence_scores = [item.get("confidence", 0.0) for item in findings]
            except KeyError:
                findings = []
                confidence_scores = []

        pass_fail = "PASS" if all(conf >= self.vlm_config["routing"]["pass_threshold"] for conf in confidence_scores) else "FAIL"
        
        return InferenceResult(
            task_type=task_type,
            model_used=model,
            raw_response=raw_response,
            findings=findings,
            confidence_scores=confidence_scores,
            latency_ms=latency_ms,
            timestamp=datetime.now().isoformat()
        )
