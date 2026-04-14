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
        cap = cv2.VideoCapture(self.stream_url if self.stream_url else self.device_index)
        if not cap.isOpened():
            return IngestResult(
                frames=[],
                source_type="live_camera",
                source_path="",
                timestamp=self._now(),
                frame_count=0,
                width=0,
                height=0
            )
        
        for _ in range(self.buffer_frames):
            ret, frame = cap.read()
            if not ret:
                break
        
        frames = [cv2.cvtColor(frame, cv2.COLOR_RGB2BGR) for _ in range(min(1, self.buffer_frames))]
        cap.release()
        
        return IngestResult(
            frames=frames,
            source_type="live_camera",
            source_path="",
            timestamp=self._now(),
            frame_count=len(frames),
            width=frames[0].shape[1] if frames else 0,
            height=frames[0].shape[0] if frames else 0
        )

    def ingest_scheduled(self) -> IngestResult:
        return self.ingest_camera_frame()

    def ingest_manual_trigger(self) -> IngestResult:
        return self.ingest_camera_frame()

    @staticmethod
    def _now() -> str:
        return datetime.now().isoformat()
