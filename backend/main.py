from fastapi import FastAPI, UploadFile, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import uvicorn
import uuid
import json
import asyncio
import logging
import cv2
from datetime import datetime
from pathlib import Path

from backend.config_loader import load_vlm_config, load_input_config, load_inspection_config
from backend.vlm_router import VLMRouter
from backend.pipeline.ingestion import Ingester
from backend.pipeline.preprocessing import preprocess_frame, frame_to_base64
from backend.proxy_metrics import record_inference, get_metrics_collector
from backend.report_generator import generate_report, get_reports_dir
from backend.model_versioning import get_version_manager
from backend.camera_manager import get_camera_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Vision_Inspect", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.active = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    async def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, msg: dict):
        msg_json = json.dumps(msg)
        for ws in list(self.active):
            try:
                await ws.send_text(msg_json)
            except WebSocketDisconnect:
                self.active.remove(ws)

manager = ConnectionManager()
_job_store: dict = {}


@app.on_event("startup")
async def startup():
    input_cfg = load_input_config()
    cam_cfg = input_cfg["input"]["live_camera"]
    cam = get_camera_manager()
    cam.start(
        device_index=cam_cfg.get("device_index", 0),
        stream_url=cam_cfg.get("stream_url", ""),
    )


@app.get("/stream")
async def mjpeg_stream():
    """MJPEG stream from the live camera — open directly in an <img> tag."""
    async def generate():
        cam = get_camera_manager()
        while True:
            frame = cam.get_latest_frame()
            if frame is not None:
                _, jpeg = cv2.imencode(
                    ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70]
                )
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n"
                    + jpeg.tobytes()
                    + b"\r\n"
                )
            await asyncio.sleep(1 / 15)  # 15 fps

    return StreamingResponse(
        generate(), media_type="multipart/x-mixed-replace; boundary=frame"
    )


def _run_inspection(task_type: str, source: str, job_id: str) -> dict:
    """Blocking: ingest → preprocess → VLM → metrics. Run in executor."""
    input_cfg = load_input_config()
    inspection_cfg = load_inspection_config()
    vlm_cfg = load_vlm_config()

    ingester = Ingester(input_cfg["input"]["live_camera"])
    vlm = VLMRouter(vlm_cfg)

    ingest_result = ingester.ingest_camera_frame()

    if not ingest_result.frames:
        logger.warning("No camera frame available — returning empty result")
        return {
            "job_id": job_id,
            "timestamp": datetime.utcnow().isoformat(),
            "task_type": task_type,
            "findings": [],
            "confidence": 0.0,
            "pass_fail": "UNKNOWN",
            "notes": "No camera frame available",
            "model_used": "none",
            "latency_ms": 0.0,
        }

    frame = ingest_result.frames[0]
    preprocessed = preprocess_frame(frame, inspection_cfg["preprocessing"])
    image_b64 = frame_to_base64(preprocessed)

    vlm_result = vlm.call(task_type, image_b64)

    latency_ms = vlm_result.get("latency_ms", 0.0)
    confidence = vlm_result.get("confidence", 0.0)
    record_inference(latency_ms, confidence)

    metrics_collector = get_metrics_collector()
    metrics = metrics_collector.get_metrics()

    version_manager = get_version_manager()
    active_version = version_manager.get_active_version()
    model_version_str = (
        active_version["model_name"] if active_version else vlm_result.get("model", "unknown")
    )

    generate_report(job_id, source, vlm_result, metrics, model_version_str)
    report_path = get_reports_dir() / f"{job_id}.md"

    return {
        "job_id": job_id,
        "timestamp": datetime.utcnow().isoformat(),
        "task_type": task_type,
        "findings": vlm_result.get("findings", []),
        "confidence": confidence,
        "pass_fail": vlm_result.get("pass_fail", "UNKNOWN"),
        "notes": vlm_result.get("notes", ""),
        "model_used": vlm_result.get("model", "unknown"),
        "latency_ms": latency_ms,
        "report_path": str(report_path),
    }


@app.post("/upload")
async def upload(file: UploadFile, task_type: str = "defect_detection"):
    job_id = uuid.uuid4().hex[:8]
    file_bytes = await file.read()
    filename = file.filename or "upload"

    input_cfg = load_input_config()
    inspection_cfg = load_inspection_config()
    vlm_cfg = load_vlm_config()

    loop = asyncio.get_event_loop()
    ingester = Ingester(input_cfg["input"]["live_camera"])
    vlm = VLMRouter(vlm_cfg)

    ingest_result = await loop.run_in_executor(
        None, ingester.ingest_upload, file_bytes, filename
    )

    if not ingest_result.frames:
        raise HTTPException(status_code=422, detail="Could not decode image")

    frame = ingest_result.frames[0]
    preprocessed = preprocess_frame(frame, inspection_cfg["preprocessing"])
    image_b64 = frame_to_base64(preprocessed)

    vlm_result = await loop.run_in_executor(None, vlm.call, task_type, image_b64)

    latency_ms = vlm_result.get("latency_ms", 0.0)
    confidence = vlm_result.get("confidence", 0.0)
    record_inference(latency_ms, confidence)

    metrics_collector = get_metrics_collector()
    metrics = metrics_collector.get_metrics()
    version_manager = get_version_manager()
    active_version = version_manager.get_active_version()
    model_version_str = (
        active_version["model_name"] if active_version else vlm_result.get("model", "unknown")
    )

    generate_report(job_id, task_type, vlm_result, metrics, model_version_str)
    report_path = get_reports_dir() / f"{job_id}.md"

    job_data = {
        "job_id": job_id,
        "timestamp": datetime.utcnow().isoformat(),
        "task_type": task_type,
        "findings": vlm_result.get("findings", []),
        "confidence": confidence,
        "pass_fail": vlm_result.get("pass_fail", "UNKNOWN"),
        "notes": vlm_result.get("notes", ""),
        "model_used": vlm_result.get("model", "unknown"),
        "latency_ms": latency_ms,
        "report_path": str(report_path),
    }
    _job_store[job_id] = job_data
    await manager.broadcast({"type": "result", "data": job_data})
    return job_data


@app.post("/inspect")
async def inspect(body: dict):
    task_type = body.get("task_type")
    source = body.get("source")
    if not task_type or not source:
        raise HTTPException(status_code=400, detail="task_type and source are required")

    job_id = uuid.uuid4().hex[:8]
    loop = asyncio.get_event_loop()
    job_data = await loop.run_in_executor(None, _run_inspection, task_type, source, job_id)

    _job_store[job_id] = job_data
    await manager.broadcast({"type": "result", "data": job_data})
    return job_data


@app.get("/results/{job_id}")
async def get_results(job_id: str):
    if job_id not in _job_store:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_store[job_id]


@app.get("/reports")
async def list_reports():
    reports_dir = get_reports_dir()
    if not reports_dir.exists():
        return []
    report_files = [f for f in reports_dir.iterdir() if f.is_file() and f.suffix == ".md"]
    return [{"filename": f.name, "size_bytes": f.stat().st_size} for f in report_files]


@app.post("/report/{job_id}")
async def get_report(job_id: str):
    if job_id not in _job_store:
        raise HTTPException(status_code=404, detail="Job not found")
    report_path = Path(_job_store[job_id]["report_path"])
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Report file not found")
    return {"report_path": str(report_path), "report_content": report_path.read_text()}


@app.get("/models/versions")
async def list_model_versions():
    version_manager = get_version_manager()
    return {"versions": version_manager.list_versions()}


@app.post("/models/rollback")
async def rollback_model(body: dict):
    version_manager = get_version_manager()
    version = body.get("version")
    if not version:
        raise HTTPException(status_code=400, detail="version is required")
    success = version_manager.rollback(version)
    return {"status": "success" if success else "failure"}


def _probe_cameras() -> list[dict]:
    """Blocking — run in executor. Probes indices 0-9 for available cameras."""
    import sys
    found = []
    for idx in range(10):
        backend = cv2.CAP_DSHOW if sys.platform == "win32" else 0
        cap = cv2.VideoCapture(idx, backend) if backend else cv2.VideoCapture(idx)
        if cap.isOpened():
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()
            found.append({"device_index": idx, "label": f"Camera {idx}  ({w}×{h})", "stream_url": ""})
    return found


@app.get("/cameras")
async def list_cameras():
    cam = get_camera_manager()
    loop = asyncio.get_event_loop()
    cameras = await loop.run_in_executor(None, _probe_cameras)
    active = cam.active_source
    for c in cameras:
        c["active"] = (
            c["device_index"] == active["device_index"]
            and active["stream_url"] == ""
        )
    return {"cameras": cameras, "active": active, "paused": cam.paused}


@app.post("/cameras/toggle")
async def toggle_camera():
    cam = get_camera_manager()
    loop = asyncio.get_event_loop()
    if cam.paused:
        await loop.run_in_executor(None, cam.resume)
        return {"paused": False}
    else:
        await loop.run_in_executor(None, cam.pause)
        return {"paused": True}


@app.post("/cameras/select")
async def select_camera(body: dict):
    device_index = body.get("device_index", 0)
    stream_url = body.get("stream_url", "")
    if not isinstance(device_index, int) or device_index < 0:
        raise HTTPException(status_code=400, detail="device_index must be a non-negative integer")
    cam = get_camera_manager()
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, cam.switch, device_index, stream_url)
    return {"status": "ok", "device_index": device_index, "stream_url": stream_url}


@app.get("/health")
async def health_check():
    import httpx
    ollama_reachable = False
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get("http://localhost:11434/api/tags", timeout=3)
            ollama_reachable = r.status_code == 200
    except Exception:
        pass
    return {"status": "ok", "ollama_reachable": ollama_reachable}


@app.websocket("/ws/stream")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            body = json.loads(data)
            task_type = body.get("task_type")
            source = body.get("source", "camera")
            if not task_type:
                continue
            job_id = uuid.uuid4().hex[:8]
            loop = asyncio.get_event_loop()
            job_data = await loop.run_in_executor(None, _run_inspection, task_type, source, job_id)
            _job_store[job_id] = job_data
            await manager.broadcast({"type": "result", "data": job_data})
    except WebSocketDisconnect:
        await manager.disconnect(websocket)


if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=False)
