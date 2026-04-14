from fastapi import FastAPI, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import uuid
import json
import asyncio
import pathlib
import logging
from backend.config_loader import load_vlm_config, load_input_config
from backend.vlm_router import VLMRouter
from backend.pipeline.ingestion import Ingester
from backend.pipeline.preprocessing import preprocess_frame, frame_to_base64
from backend.proxy_metrics import record_inference, get_metrics_collector
from backend.report_generator import generate_report, get_reports_dir
from backend.model_versioning import get_version_manager
from backend.notifier import Notifier

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
        self.active.remove(ws)

    async def broadcast(self, msg: dict):
        msg_json = json.dumps(msg)
        for ws in self.active:
            try:
                await ws.send_text(msg_json)
            except WebSocketDisconnect:
                self.active.remove(ws)

manager = ConnectionManager()
_job_store: dict = {}

def _get_vlm():
    return VLMRouter()

def _get_ingester():
    return Ingester()

@app.post("/upload")
async def upload(file: UploadFile, task_type: str = "defect_detection"):
    job_id = uuid.uuid4().hex[:8]
    file_bytes = await file.read()
    ingester = _get_ingester()
    vlm = _get_vlm()
    result = await ingester.ingest_upload(job_id, file_bytes)
    record_inference(result)
    metrics_collector = get_metrics_collector()
    version_manager = get_version_manager()
    report_path, report_content = generate_report(job_id, task_type, result, metrics_collector, version_manager)
    _job_store[job_id] = {
        "status": "completed",
        "task_type": task_type,
        "finding_count": len(result),
        "report_path": report_path,
        "report_content": report_content
    }
    await manager.broadcast(_job_store[job_id])
    return {"job_id": job_id, "status": "queued", "task_type": task_type, "finding_count": len(result)}

@app.post("/inspect")
async def inspect(body: dict):
    job_id = uuid.uuid4().hex[:8]
    task_type = body.get("task_type")
    source = body.get("source")
    if not task_type or not source:
        raise HTTPException(status_code=400, detail="Invalid request body")
    ingester = _get_ingester()
    vlm = _get_vlm()
    result = await ingester.ingest_camera_frame(job_id, source)
    record_inference(result)
    metrics_collector = get_metrics_collector()
    version_manager = get_version_manager()
    report_path, report_content = generate_report(job_id, task_type, result, metrics_collector, version_manager)
    _job_store[job_id] = {
        "status": "completed",
        "task_type": task_type,
        "finding_count": len(result),
        "report_path": report_path,
        "report_content": report_content
    }
    await manager.broadcast(_job_store[job_id])
    return {"job_id": job_id, "status": "queued"}

@app.get("/results/{job_id}")
async def get_results(job_id: str):
    if job_id not in _job_store:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_store[job_id]

@app.post("/report/{job_id}")
async def generate_report_endpoint(job_id: str):
    if job_id not in _job_store:
        raise HTTPException(status_code=404, detail="Job not found")
    report_path = _job_store[job_id]["report_path"]
    with open(report_path, "r") as f:
        report_content = f.read()
    return {"report_path": report_path, "report_content": report_content}

@app.get("/reports")
async def list_reports():
    reports_dir = get_reports_dir()
    report_files = [f for f in reports_dir.iterdir() if f.is_file() and f.suffix == ".md"]
    return [{"filename": f.name, "size_bytes": f.stat().st_size} for f in report_files]

@app.get("/models/versions")
async def list_model_versions():
    version_manager = get_version_manager()
    return {"versions": version_manager.list_versions()}

@app.post("/models/rollback")
async def rollback_model(body: dict):
    version_manager = get_version_manager()
    version = body.get("version")
    if not version:
        raise HTTPException(status_code=400, detail="Invalid request body")
    try:
        version_manager.rollback(version)
        return {"status": "success"}
    except Exception as e:
        logging.error(f"Failed to rollback model: {e}")
        return {"status": "failure"}

@app.get("/health")
async def health_check():
    ollama_reachable = True  # Placeholder for actual health check
    return {"status": "ok", "ollama_reachable": ollama_reachable}

@app.websocket("/ws/stream")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            body = json.loads(data)
            task_type = body.get("task_type")
            source = body.get("source")
            if not task_type or not source:
                raise HTTPException(status_code=400, detail="Invalid request body")
            ingester = _get_ingester()
            vlm = _get_vlm()
            result = await ingester.ingest_camera_frame(uuid.uuid4().hex[:8], source)
            record_inference(result)
            metrics_collector = get_metrics_collector()
            version_manager = get_version_manager()
            report_path, report_content = generate_report(uuid.uuid4().hex[:8], task_type, result, metrics_collector, version_manager)
            await manager.broadcast({"job_id": uuid.uuid4().hex[:8], "status": "completed", "task_type": task_type, "finding_count": len(result), "report_path": report_path, "report_content": report_content})
    except WebSocketDisconnect:
        await manager.disconnect(websocket)

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=False)
