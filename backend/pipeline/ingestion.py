import cv2
import numpy as np
from PIL import Image
import io
import base64
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
import tempfile
import os

@dataclass
class IngestResult:
    frames: list          # list of numpy arrays (BGR)
    source_type: str      # manual_upload | live_camera | scheduled | manual_trigger
    source_path: str
    timestamp: str        # ISO 8601
    frame_count: int
    width: int
    height: int

class Ingester:
    def __init__(self, config: dict):
        self.config = config
        self.device_index = config.get('device_index', 0)
        self.stream_url = config.get('stream_url', "")
        self.buffer_frames = config.get('buffer_frames', 3)
        self.duration_seconds = config.get('duration_seconds', 5)

    def ingest_upload(self, file_bytes: bytes, filename: str) -> IngestResult:
        if filename.endswith(('.mp4', '.avi', '.mkv')):
            cap = cv2.VideoCapture(io.BytesIO(file_bytes))
            frames = []
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                frames.append(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
            cap.release()
        else:
            image = Image.open(io.BytesIO(file_bytes))
            frames = [np.array(image)[:, :, ::-1]]
        
        return IngestResult(
            frames=frames,
            source_type="manual_upload",
            source_path="",
            timestamp=self._now(),
            frame_count=len(frames),
            width=frames[0].shape[1] if frames else 0,
            height=frames[0].shape[0] if frames else 0
        )

    def ingest_camera_frame(self) -> IngestResult:
        # Prefer the shared CameraManager (already open, no re-init cost).
        try:
            from backend.camera_manager import get_camera_manager
            cam = get_camera_manager()
            if cam.is_available():
                frame = cam.get_latest_frame()  # BGR ndarray
                return IngestResult(
                    frames=[frame],
                    source_type="live_camera",
                    source_path="",
                    timestamp=self._now(),
                    frame_count=1,
                    width=frame.shape[1],
                    height=frame.shape[0],
                )
        except Exception:
            pass  # Fall through to direct capture below

        # Direct capture fallback (e.g. CameraManager not started).
        import sys
        source = self.stream_url if self.stream_url else self.device_index
        backend_flag = cv2.CAP_DSHOW if (sys.platform == "win32" and isinstance(source, int)) else 0
        cap = cv2.VideoCapture(source, backend_flag) if backend_flag else cv2.VideoCapture(source)

        if not cap.isOpened():
            return IngestResult(
                frames=[], source_type="live_camera", source_path="",
                timestamp=self._now(), frame_count=0, width=0, height=0,
            )

        # Discard buffer_frames - 1 stale frames, keep the freshest.
        frame = None
        for _ in range(self.buffer_frames):
            ret, f = cap.read()
            if ret:
                frame = f
        cap.release()

        if frame is None:
            return IngestResult(
                frames=[], source_type="live_camera", source_path="",
                timestamp=self._now(), frame_count=0, width=0, height=0,
            )

        return IngestResult(
            frames=[frame],          # BGR — do NOT reorder channels here
            source_type="live_camera",
            source_path="",
            timestamp=self._now(),
            frame_count=1,
            width=frame.shape[1],
            height=frame.shape[0],
        )

    def ingest_scheduled(self) -> IngestResult:
        return self.ingest_camera_frame()

    def ingest_manual_trigger(self) -> IngestResult:
        return self.ingest_camera_frame()

    @staticmethod
    def _now() -> str:
        return datetime.now().isoformat()
