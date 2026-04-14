import cv2
import numpy as np
import base64

def preprocess_frame(frame: np.ndarray, config: dict) -> np.ndarray:
    brightness_target = config.get('brightness_target', 128)
    brightness_tolerance = config.get('brightness_tolerance', 30)
    resize_max_dimension = config.get('resize_max_dimension', 1024)
    normalize = config.get('normalize', True)

    mean = np.mean(frame)
    if abs(mean - brightness_target) > brightness_tolerance:
        scale_factor = brightness_target / mean
        frame = cv2.convertScaleAbs(frame, alpha=scale_factor, beta=0)
        frame = np.clip(frame, 0, 255).astype(np.uint8)

    h, w = frame.shape[:2]
    if max(h, w) > resize_max_dimension:
        scale_factor = resize_max_dimension / max(h, w)
        frame = cv2.resize(frame, (int(w * scale_factor), int(h * scale_factor)))

    if normalize:
        frame = frame.astype(np.float32) / 255.0

    return frame

def frame_to_base64(frame: np.ndarray) -> str:
    if frame.dtype == np.float32 and np.max(frame) <= 1.0:
        frame = (frame * 255).astype(np.uint8)
    _, encoded_image = cv2.imencode('.jpg', frame)
    return base64.b64encode(encoded_image.tobytes()).decode('utf-8')

def preprocess_batch(frames: list, config: dict) -> list:
    return [preprocess_frame(f, config) for f in frames]
