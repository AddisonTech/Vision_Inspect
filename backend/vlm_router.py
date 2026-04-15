import requests
import json
import time
import logging
from pathlib import Path
import yaml
from backend.config_loader import load_vlm_config

logger = logging.getLogger(__name__)


def _load_prompts() -> dict:
    path = Path(__file__).resolve().parent.parent / "configs" / "prompts.yaml"
    with open(path, "r") as f:
        return yaml.safe_load(f)


class VLMRouter:
    def __init__(self, config: dict = None):
        self._cfg = config or load_vlm_config()
        self._prompts = _load_prompts()

    def get_model(self, task_type: str) -> str:
        ocr_task_types = self._cfg.get("routing", {}).get("ocr_task_types", [])
        if task_type in ocr_task_types:
            return self._cfg["fallback_model"]["name"]
        return self._cfg["primary_model"]["name"]

    def build_prompt(self, task_type: str) -> str:
        task_cfg = self._prompts.get("tasks", {}).get(task_type)
        if task_cfg:
            return task_cfg["prompt"].strip()
        logger.warning("No prompt configured for task_type=%s, using generic fallback", task_type)
        return (
            'Inspect this image and respond ONLY with valid JSON:\n'
            '{"findings":[],"confidence":0.0,"pass_fail":"UNKNOWN","notes":"No prompt configured for this task type"}'
        )

    def build_system(self) -> str:
        return self._prompts.get("system", "").strip()

    def call(self, task_type: str, image_b64: str, timeout: int = 300) -> dict:
        base_url = self._cfg["ollama"]["base_url"]
        model = self.get_model(task_type)
        prompt = self.build_prompt(task_type)
        system = self.build_system()

        payload = dict(
            model=model,
            system=system,
            prompt=prompt,
            images=[image_b64],
            stream=False,
            format="json",
            options=dict(
                temperature=self._cfg.get("primary_model", {}).get("temperature", 0.1),
                num_ctx=self._cfg.get("primary_model", {}).get("context_length", 8192),
            ),
        )

        logger.info("VLM call: model=%s task=%s", model, task_type)
        start = time.time()
        try:
            resp = requests.post(
                base_url + "/api/generate",
                json=payload,
                timeout=timeout,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error("Ollama request failed: %s", e)
            return dict(
                findings=[], confidence=0.0, pass_fail="UNKNOWN",
                notes=f"Ollama request failed: {e}",
                model=model, task_type=task_type, latency_ms=0.0,
            )

        latency_ms = round((time.time() - start) * 1000, 2)
        raw = resp.json().get("response", "")
        logger.info("VLM response in %.0fms: %.200s", latency_ms, raw)

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("VLM returned non-JSON; wrapping raw response. raw=%.300s", raw)
            data = dict(findings=[], confidence=0.0, pass_fail="UNKNOWN", notes=raw[:500])

        # Normalise findings — ensure each is a dict with required keys.
        normalised = []
        for f in data.get("findings", []):
            if isinstance(f, dict):
                normalised.append({
                    "label": f.get("label", "unknown"),
                    "confidence": float(f.get("confidence", 0.0)),
                    "severity": f.get("severity", "low"),
                    "bbox": f.get("bbox"),
                    "description": f.get("description", ""),
                })
            elif isinstance(f, (list, tuple)) and len(f) >= 4:
                # Fallback for legacy tuple format
                normalised.append({
                    "label": f[0], "confidence": float(f[1]),
                    "severity": f[2], "bbox": None, "description": f[3],
                })
        data["findings"] = normalised
        data["model"] = model
        data["task_type"] = task_type
        data["latency_ms"] = latency_ms
        return data
