import requests
import json
import time
import logging
from backend.config_loader import load_vlm_config

class VLMRouter:
    def __init__(self, config: dict = None):
        self._cfg = config or load_vlm_config()

    def get_model(self, task_type: str) -> str:
        routing = {
            "ocr_task_types": ["nameplate_ocr", "serial_number_extraction"],
            "primary_model": "model1",
            "fallback_model": "model2"
        }
        if task_type in routing["ocr_task_types"]:
            return routing["fallback_model"]
        else:
            return routing["primary_model"]

    def build_prompt(self, task_type: str) -> str:
        prompts = {
            "defect_detection": '{"findings":[],"confidence":0.0,"pass_fail":"UNKNOWN","notes":""}',
            "surface_anomaly_classification": '{"findings":[],"confidence":0.0,"pass_fail":"UNKNOWN","notes":""}',
            "nameplate_ocr": '{"findings":[],"confidence":0.0,"pass_fail":"UNKNOWN","notes":""}',
            "serial_number_extraction": '{"findings":[],"confidence":0.0,"pass_fail":"UNKNOWN","notes":""}',
            "engineering_drawing_interpretation": '{"findings":[],"confidence":0.0,"pass_fail":"UNKNOWN","notes":""}',
            "process_deviation_flagging": '{"findings":[],"confidence":0.0,"pass_fail":"UNKNOWN","notes":""}'
        }
        return prompts[task_type]

    def call(self, task_type: str, image_b64: str, timeout: int = 120) -> dict:
        base_url = self._cfg["ollama"]["base_url"]
        model = self.get_model(task_type)
        prompt = self.build_prompt(task_type)
        start = time.time()
        resp = requests.post(base_url + "/api/generate",
            json=dict(model=model, prompt=prompt, images=[image_b64], stream=False),
            timeout=timeout)
        latency_ms = round((time.time() - start) * 1000, 2)
        raw = resp.json().get("response", "")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = dict(findings=[], confidence=0.0, pass_fail="UNKNOWN", raw=raw)
        data["model"] = model
        data["task_type"] = task_type
        data["latency_ms"] = latency_ms
        return data
