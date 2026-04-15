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
from backend.database import init_db, save_inspection, get_inspection, list_inspections, get_stats
from backend import keyence_listener

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
# Short-term in-memory cache — survives only while the process is running.
# DB is the source of truth for anything older than the current session.
_job_store: dict = {}


def _on_keyence_result(result: dict) -> None:
    """
    Called by the EtherNet/IP poller on every new inspection.
    Saves to DB and schedules a WebSocket broadcast.
    Runs in the executor thread — uses asyncio.run_coroutine_threadsafe.
    """
    job_id = uuid.uuid4().hex[:8]
    job = {
        "job_id": job_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "task_type": "keyence_inspection",
        "source": "keyence_camera",
        "findings": [],
        "confidence": 1.0 if result.get("pass_fail") == "PASS" else 0.0,
        "pass_fail": result.get("pass_fail", "UNKNOWN"),
        "notes": f"Program {result.get('program_number', '?')} | Count {result.get('inspection_count', '?')}",
        "model_used": "keyence_vs_l1500cx",
        "latency_ms": 0.0,
        "finding_count": 0,
        "report_path": "",
    }
    _job_store[job_id] = job
    save_inspection(job)

    # Broadcast to WebSocket clients from the event loop
    loop = asyncio.get_event_loop()
    if loop.is_running():
        asyncio.run_coroutine_threadsafe(
            manager.broadcast({"type": "result", "data": job}),
            loop,
        )
    logger.info("keyence: saved job %s — %s", job_id, job["pass_fail"])


@app.on_event("startup")
async def startup():
    init_db()
    input_cfg = load_input_config()
    cam_cfg = input_cfg["input"]["live_camera"]
    cam = get_camera_manager()
    cam.start(
        device_index=cam_cfg.get("device_index", 0),
        stream_url=cam_cfg.get("stream_url", ""),
        gige_ip=cam_cfg.get("gige_ip", ""),
        cti_path=cam_cfg.get("cti_path", ""),
    )
    if cam_cfg.get("gige_ip"):
        keyence_listener.start_poller(host=cam_cfg["gige_ip"], port=44818)
        keyence_listener.set_result_callback(_on_keyence_result)
        logger.info("Keyence EtherNet/IP poller started → %s:44818", cam_cfg["gige_ip"])


# ---------------------------------------------------------------------------
# Camera stream
# ---------------------------------------------------------------------------

@app.get("/stream")
async def mjpeg_stream():
    async def generate():
        cam = get_camera_manager()
        while True:
            frame = cam.get_latest_frame()
            if frame is not None:
                _, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                yield (
                    b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                    + jpeg.tobytes()
                    + b"\r\n"
                )
            await asyncio.sleep(1 / 15)

    return StreamingResponse(generate(), media_type="multipart/x-mixed-replace; boundary=frame")


# ---------------------------------------------------------------------------
# Inspection pipeline helpers
# ---------------------------------------------------------------------------

def _build_job(job_id: str, task_type: str, source: str,
               vlm_result: dict, report_path: Path) -> dict:
    return {
        "job_id": job_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "task_type": task_type,
        "source": source,
        "findings": vlm_result.get("findings", []),
        "confidence": float(vlm_result.get("confidence", 0.0)),
        "pass_fail": vlm_result.get("pass_fail", "UNKNOWN"),
        "notes": vlm_result.get("notes", ""),
        "model_used": vlm_result.get("model", "unknown"),
        "latency_ms": float(vlm_result.get("latency_ms", 0.0)),
        "finding_count": len(vlm_result.get("findings", [])),
        "report_path": str(report_path),
    }


def _run_vlm(frame, task_type: str) -> dict:
    inspection_cfg = load_inspection_config()
    vlm_cfg = load_vlm_config()
    vlm = VLMRouter(vlm_cfg)
    preprocessed = preprocess_frame(frame, inspection_cfg["preprocessing"])
    image_b64 = frame_to_base64(preprocessed)
    return vlm.call(task_type, image_b64)


def _run_inspection(task_type: str, source: str, job_id: str) -> dict:
    """Blocking: ingest → preprocess → VLM → record metrics → persist."""
    input_cfg = load_input_config()
    ingester = Ingester(input_cfg["input"]["live_camera"])
    ingest_result = ingester.ingest_camera_frame()

    if not ingest_result.frames:
        logger.warning("No camera frame — returning empty result")
        vlm_result = {
            "findings": [], "confidence": 0.0,
            "pass_fail": "UNKNOWN", "notes": "No camera frame available",
            "model": "none", "latency_ms": 0.0,
        }
    else:
        vlm_result = _run_vlm(ingest_result.frames[0], task_type)

    record_inference(vlm_result.get("latency_ms", 0.0), vlm_result.get("confidence", 0.0))
    metrics = get_metrics_collector().get_metrics()

    version_manager = get_version_manager()
    active_ver = version_manager.get_active_version()
    model_ver = active_ver["model_name"] if active_ver else vlm_result.get("model", "unknown")

    generate_report(job_id, source, vlm_result, metrics, model_ver)
    report_path = get_reports_dir() / f"{job_id}.md"

    job = _build_job(job_id, task_type, source, vlm_result, report_path)
    save_inspection(job)
    return job


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

@app.post("/upload")
async def upload(file: UploadFile, task_type: str = "defect_detection"):
    job_id = uuid.uuid4().hex[:8]
    file_bytes = await file.read()
    filename = file.filename or "upload"

    input_cfg = load_input_config()
    loop = asyncio.get_event_loop()
    ingester = Ingester(input_cfg["input"]["live_camera"])
    ingest_result = await loop.run_in_executor(None, ingester.ingest_upload, file_bytes, filename)

    if not ingest_result.frames:
        raise HTTPException(status_code=422, detail="Could not decode image")

    vlm_result = await loop.run_in_executor(None, _run_vlm, ingest_result.frames[0], task_type)

    record_inference(vlm_result.get("latency_ms", 0.0), vlm_result.get("confidence", 0.0))
    metrics = get_metrics_collector().get_metrics()
    version_manager = get_version_manager()
    active_ver = version_manager.get_active_version()
    model_ver = active_ver["model_name"] if active_ver else vlm_result.get("model", "unknown")

    generate_report(job_id, task_type, vlm_result, metrics, model_ver)
    report_path = get_reports_dir() / f"{job_id}.md"

    job = _build_job(job_id, task_type, filename, vlm_result, report_path)
    _job_store[job_id] = job
    await loop.run_in_executor(None, save_inspection, job)
    await manager.broadcast({"type": "result", "data": job})
    return job


# ---------------------------------------------------------------------------
# Inspect (live camera trigger)
# ---------------------------------------------------------------------------

@app.post("/inspect")
async def inspect(body: dict):
    task_type = body.get("task_type")
    source = body.get("source")
    if not task_type or not source:
        raise HTTPException(status_code=400, detail="task_type and source are required")

    job_id = uuid.uuid4().hex[:8]
    loop = asyncio.get_event_loop()
    job = await loop.run_in_executor(None, _run_inspection, task_type, source, job_id)
    _job_store[job_id] = job
    await manager.broadcast({"type": "result", "data": job})
    return job


# ---------------------------------------------------------------------------
# Results / inspections
# ---------------------------------------------------------------------------

@app.get("/results/{job_id}")
async def get_results(job_id: str):
    if job_id in _job_store:
        return _job_store[job_id]
    loop = asyncio.get_event_loop()
    record = await loop.run_in_executor(None, get_inspection, job_id)
    if not record:
        raise HTTPException(status_code=404, detail="Job not found")
    return record


@app.get("/inspections")
async def get_inspections(
    limit: int = 50,
    offset: int = 0,
    task_type: str | None = None,
    pass_fail: str | None = None,
    since: str | None = None,
):
    loop = asyncio.get_event_loop()
    records = await loop.run_in_executor(
        None, list_inspections, limit, offset, task_type, pass_fail, since
    )
    return records


@app.get("/inspections/stats")
async def inspection_stats():
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, get_stats)


# ---------------------------------------------------------------------------
# Reports (legacy — kept for backward compat, now queries DB)
# ---------------------------------------------------------------------------

@app.get("/reports")
async def list_reports(limit: int = 50):
    loop = asyncio.get_event_loop()
    records = await loop.run_in_executor(None, list_inspections, limit, 0, None, None, None)
    # Shape to old Report schema for any callers that haven't updated
    return [
        {
            "filename": f"{r['job_id']}.md",
            "size_bytes": Path(r["report_path"]).stat().st_size if Path(r["report_path"]).exists() else 0,
            "created_at": r["timestamp"],
            **r,
        }
        for r in records
    ]


@app.post("/report/{job_id}")
async def get_report(job_id: str):
    record = _job_store.get(job_id) or get_inspection(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="Job not found")
    report_path = Path(record["report_path"])
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Report file not found")
    return {"report_path": str(report_path), "report_content": report_path.read_text()}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

@app.get("/models/versions")
async def list_model_versions():
    return {"versions": get_version_manager().list_versions()}


@app.post("/models/rollback")
async def rollback_model(body: dict):
    version = body.get("version")
    if not version:
        raise HTTPException(status_code=400, detail="version is required")
    success = get_version_manager().rollback(version)
    return {"status": "success" if success else "failure"}


# ---------------------------------------------------------------------------
# Cameras
# ---------------------------------------------------------------------------

def _probe_cameras() -> list[dict]:
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
        c["active"] = (c["device_index"] == active["device_index"] and active["stream_url"] == "")
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
    gige_ip = body.get("gige_ip", "")
    cti_path = body.get("cti_path", "")
    if not isinstance(device_index, int) or device_index < 0:
        raise HTTPException(status_code=400, detail="device_index must be a non-negative integer")
    cam = get_camera_manager()
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, cam.switch, device_index, stream_url, gige_ip, cti_path)
    return {"status": "ok", "device_index": device_index, "stream_url": stream_url,
            "gige_ip": gige_ip, "cti_path": cti_path}


# ---------------------------------------------------------------------------
# Keyence camera output (Data Output tool TCP push)
# ---------------------------------------------------------------------------

@app.get("/keyence/result")
async def keyence_result():
    """
    Returns the most recent result pushed by the camera over the
    non-procedural TCP connection, plus connection status.
    Returns 204 if no inspection data has arrived yet.
    """
    result = keyence_listener.get_latest_result()
    connected = keyence_listener.is_connected()
    if not result:
        from fastapi.responses import Response
        return Response(status_code=204, headers={"X-Camera-Connected": str(connected)})
    return {**result, "connected": connected}


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

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
            job = await loop.run_in_executor(None, _run_inspection, task_type, source, job_id)
            _job_store[job_id] = job
            await manager.broadcast({"type": "result", "data": job})
    except WebSocketDisconnect:
        await manager.disconnect(websocket)


if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=False)
