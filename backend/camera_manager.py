"""
Camera manager with dual-mode capture:
  - GigE Vision mode  (default): uses Harvesters + a GenTL producer to talk
    directly to the Keyence VS-L1500CX (or any GigE Vision camera).
  - OpenCV fallback mode: used automatically when no .cti producer path is
    configured, or when the GigE transport layer fails to open.

Public API is identical to the previous OpenCV-only version so the rest of
the application (main.py, ingestion pipeline) needs zero changes.
"""

import cv2
import sys
import threading
import time
import logging
import numpy as np
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional Harvesters import — only required in GigE mode
# ---------------------------------------------------------------------------
try:
    from harvesters.core import Harvester
    _HARVESTERS_AVAILABLE = True
except ImportError:
    _HARVESTERS_AVAILABLE = False
    logger.warning("harvesters package not found — GigE mode unavailable, falling back to OpenCV")


class CameraManager:
    """
    Thread-safe singleton that keeps the camera open and maintains the latest
    frame in memory.  Both the MJPEG stream endpoint and the inspection
    pipeline call get_latest_frame().

    Parameters (set via start() / switch())
    ----------------------------------------
    device_index : int
        OpenCV device index.  Used only in OpenCV fallback mode.
    stream_url : str
        RTSP / HTTP URL.  Used only in OpenCV fallback mode.
    gige_ip : str
        IP of the GigE Vision camera (e.g. "169.254.69.245").
        When non-empty AND a cti_path is available, GigE mode is used.
    cti_path : str
        Absolute path to the GenTL producer .cti file.
        Example: "C:/mvIMPACT/lib/x86_64/mvGenTLProducer.cti"
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._frame: np.ndarray | None = None
        self._running = False
        self._paused = False
        self._thread: threading.Thread | None = None

        # OpenCV fallback params
        self._device_index: int = 0
        self._stream_url: str = ""

        # GigE params
        self._gige_ip: str = ""
        self._cti_path: str = ""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self, device_index: int = 0, stream_url: str = "",
              gige_ip: str = "", cti_path: str = "") -> None:
        if self._running:
            return
        self._device_index = device_index
        self._stream_url = stream_url
        self._gige_ip = gige_ip
        self._cti_path = cti_path
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="camera-reader")
        self._thread.start()
        logger.info(
            "CameraManager started (gige_ip=%r cti_path=%r device_index=%s stream_url=%r)",
            gige_ip, cti_path, device_index, stream_url,
        )

    def stop(self) -> None:
        self._running = False

    def pause(self) -> None:
        logger.info("CameraManager: pausing")
        self._paused = True
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        with self._lock:
            self._frame = None

    def resume(self) -> None:
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

    def switch(self, device_index: int = 0, stream_url: str = "",
               gige_ip: str = "", cti_path: str = "") -> None:
        logger.info(
            "CameraManager: switching to gige_ip=%r device_index=%s stream_url=%r",
            gige_ip, device_index, stream_url,
        )
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        with self._lock:
            self._frame = None
        self._device_index = device_index
        self._stream_url = stream_url
        self._gige_ip = gige_ip
        self._cti_path = cti_path
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="camera-reader")
        self._thread.start()

    @property
    def active_source(self) -> dict:
        return {
            "device_index": self._device_index,
            "stream_url": self._stream_url,
            "gige_ip": self._gige_ip,
            "cti_path": self._cti_path,
        }

    def get_latest_frame(self) -> np.ndarray | None:
        """Return a copy of the most recent frame (BGR ndarray), or None."""
        with self._lock:
            return self._frame.copy() if self._frame is not None else None

    def is_available(self) -> bool:
        with self._lock:
            return self._frame is not None

    # ------------------------------------------------------------------
    # Internal dispatch
    # ------------------------------------------------------------------

    def _loop(self) -> None:
        use_gige = (
            _HARVESTERS_AVAILABLE
            and bool(self._gige_ip)
            and bool(self._cti_path)
            and Path(self._cti_path).is_file()
        )
        if use_gige:
            logger.info("CameraManager: using GigE Vision mode via Harvesters")
            self._loop_gige()
        else:
            if self._gige_ip and not _HARVESTERS_AVAILABLE:
                logger.warning("CameraManager: gige_ip set but harvesters not installed — falling back to OpenCV")
            elif self._gige_ip and self._cti_path and not Path(self._cti_path).is_file():
                logger.warning("CameraManager: .cti not found at %r — falling back to OpenCV", self._cti_path)
            logger.info("CameraManager: using OpenCV mode")
            self._loop_opencv()

    # ------------------------------------------------------------------
    # GigE Vision capture loop (Harvesters)
    # ------------------------------------------------------------------

    def _loop_gige(self) -> None:
        h = Harvester()
        try:
            h.add_file(self._cti_path)
            h.update()

            # Log all discovered devices for diagnostics
            logger.info("CameraManager: %d device(s) found by GenTL producer", len(h.device_info_list))
            for i, info in enumerate(h.device_info_list):
                props = {k: getattr(info, k, "?") for k in
                         ("id_", "vendor", "model", "serial_number",
                          "ip_address", "user_defined_name", "access_status")}
                logger.info("CameraManager: device[%d] %s", i, props)

            # Match camera by IP across all possible attribute names
            target_idx = 0
            found = False
            for i, info in enumerate(h.device_info_list):
                ip = (getattr(info, "ip_address", None)
                      or getattr(info, "device_ip_address", None)
                      or "")
                # Also check the id_ string which sometimes contains the IP
                id_str = getattr(info, "id_", "") or ""
                if ip == self._gige_ip or self._gige_ip in id_str:
                    target_idx = i
                    found = True
                    logger.info("CameraManager: matched camera at IP %s (index %d)", self._gige_ip, i)
                    break
            if not found:
                logger.warning(
                    "CameraManager: IP %s not matched — using index 0 (first available device)",
                    self._gige_ip,
                )

            with h.create(target_idx) as ia:
                n = ia.remote_device.node_map
                try:
                    n.AcquisitionMode.value = "Continuous"
                except Exception:
                    pass

                ia.start()
                logger.info("CameraManager: GigE acquisition started on %s", self._gige_ip)

                consecutive_failures = 0
                while self._running:
                    try:
                        with ia.fetch(timeout=2.0) as buffer:
                            component = buffer.payload.components[0]
                            w = component.width
                            h_px = component.height
                            n_ch = component.num_components_per_pixel
                            raw = (
                                component.data.reshape(h_px, w, n_ch)
                                if n_ch > 1
                                else component.data.reshape(h_px, w)
                            )

                            pixel_fmt = str(component.data_format).upper()
                            if "BAYER" in pixel_fmt:
                                frame = cv2.cvtColor(raw, self._bayer_code(pixel_fmt))
                            elif "MONO" in pixel_fmt or "GRAY" in pixel_fmt:
                                frame = cv2.cvtColor(raw.astype(np.uint8), cv2.COLOR_GRAY2BGR)
                            elif "RGB" in pixel_fmt:
                                frame = cv2.cvtColor(raw, cv2.COLOR_RGB2BGR)
                            else:
                                frame = raw if raw.ndim == 3 else cv2.cvtColor(raw, cv2.COLOR_GRAY2BGR)

                            with self._lock:
                                self._frame = frame
                            consecutive_failures = 0

                    except Exception as exc:
                        consecutive_failures += 1
                        logger.warning("CameraManager: GigE fetch error (%d): %s", consecutive_failures, exc)
                        if consecutive_failures >= 10:
                            logger.error("CameraManager: too many GigE errors — stopping")
                            break

                ia.stop()

        except Exception as exc:
            logger.error("CameraManager: GigE init failed (%s) — falling back to OpenCV", exc)
            self._loop_opencv()
        finally:
            h.reset()
            logger.info("CameraManager: GigE loop exited")

    @staticmethod
    def _bayer_code(pixel_fmt: str) -> int:
        mapping = {
            "BAYERRG": cv2.COLOR_BAYER_RG2BGR,
            "BAYERGR": cv2.COLOR_BAYER_GR2BGR,
            "BAYERBG": cv2.COLOR_BAYER_BG2BGR,
            "BAYERGB": cv2.COLOR_BAYER_GB2BGR,
        }
        for key, code in mapping.items():
            if key in pixel_fmt:
                return code
        return cv2.COLOR_BAYER_RG2BGR

    # ------------------------------------------------------------------
    # OpenCV fallback capture loop
    # ------------------------------------------------------------------

    def _open_cap(self):
        source = self._stream_url if self._stream_url else self._device_index
        if sys.platform == "win32" and isinstance(source, int):
            cap = cv2.VideoCapture(source, cv2.CAP_DSHOW)
        else:
            cap = cv2.VideoCapture(source)
        return cap if cap.isOpened() else None

    def _loop_opencv(self) -> None:
        cap = self._open_cap()
        if cap is None:
            logger.warning("CameraManager: could not open camera source — live feed unavailable")
            return

        logger.info(
            "CameraManager: OpenCV camera open at %.0fx%.0f",
            cap.get(cv2.CAP_PROP_FRAME_WIDTH),
            cap.get(cv2.CAP_PROP_FRAME_HEIGHT),
        )

        consecutive_failures = 0
        while self._running:
            ret, frame = cap.read()
            if ret:
                consecutive_failures = 0
                with self._lock:
                    self._frame = frame
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
        logger.info("CameraManager: OpenCV loop stopped")


# Module-level singleton
_manager = CameraManager()


def get_camera_manager() -> CameraManager:
    return _manager
