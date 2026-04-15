"""
Singleton background thread that keeps the camera open and maintains the
latest frame in memory. Both the MJPEG stream endpoint and the inspection
pipeline read from here, so the camera is only opened once.
"""

import cv2
import sys
import threading
import time
import logging

logger = logging.getLogger(__name__)


class CameraManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._frame = None
        self._running = False
        self._paused = False
        self._thread: threading.Thread | None = None
        self._device_index: int = 0
        self._stream_url: str = ""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self, device_index: int = 0, stream_url: str = "") -> None:
        if self._running:
            return
        self._device_index = device_index
        self._stream_url = stream_url
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="camera-reader")
        self._thread.start()
        logger.info("CameraManager started (device_index=%s stream_url=%r)", device_index, stream_url)

    def stop(self) -> None:
        self._running = False

    def pause(self) -> None:
        """Release the camera and clear the frame buffer. Stream goes dark."""
        logger.info("CameraManager: pausing")
        self._paused = True
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        with self._lock:
            self._frame = None

    def resume(self) -> None:
        """Re-open the camera and restart the capture loop."""
        if not self._paused:
            return
        logger.info("CameraManager: resuming")
        self._paused = False
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="camera-reader")
        self._thread.start()

    @property
    def paused(self) -> bool:
        return self._paused

    def switch(self, device_index: int = 0, stream_url: str = "") -> None:
        """Stop the current capture loop and start a new one on a different source."""
        logger.info("CameraManager: switching to device_index=%s stream_url=%r", device_index, stream_url)
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        with self._lock:
            self._frame = None
        self._device_index = device_index
        self._stream_url = stream_url
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="camera-reader")
        self._thread.start()

    @property
    def active_source(self) -> dict:
        return {"device_index": self._device_index, "stream_url": self._stream_url}

    def get_latest_frame(self):
        """Return a copy of the most recent frame (BGR ndarray), or None."""
        with self._lock:
            return self._frame.copy() if self._frame is not None else None

    def is_available(self) -> bool:
        with self._lock:
            return self._frame is not None

    # ------------------------------------------------------------------
    # Internal capture loop
    # ------------------------------------------------------------------

    def _open_cap(self):
        source = self._stream_url if self._stream_url else self._device_index
        if sys.platform == "win32" and isinstance(source, int):
            cap = cv2.VideoCapture(source, cv2.CAP_DSHOW)
        else:
            cap = cv2.VideoCapture(source)
        return cap if cap.isOpened() else None

    def _loop(self) -> None:
        cap = self._open_cap()
        if cap is None:
            logger.warning("CameraManager: could not open camera source — live feed unavailable")
            return

        logger.info("CameraManager: camera open at %.0fx%.0f",
                    cap.get(cv2.CAP_PROP_FRAME_WIDTH),
                    cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        consecutive_failures = 0
        while self._running:
            ret, frame = cap.read()
            if ret:
                consecutive_failures = 0
                with self._lock:
                    self._frame = frame          # BGR — OpenCV native
            else:
                consecutive_failures += 1
                logger.warning("CameraManager: read failed (%d consecutive)", consecutive_failures)
                if consecutive_failures >= 10:
                    logger.error("CameraManager: too many failures, attempting reopen")
                    cap.release()
                    time.sleep(2)
                    cap = self._open_cap()
                    if cap is None:
                        logger.error("CameraManager: reopen failed — giving up")
                        break
                    consecutive_failures = 0

        cap.release()
        logger.info("CameraManager: stopped")


# Module-level singleton
_manager = CameraManager()


def get_camera_manager() -> CameraManager:
    return _manager
