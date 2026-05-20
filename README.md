# Vision_Inspect

Local shop-floor visual process monitoring system. Uses VLMs via Ollama for real-time inspection of manufacturing processes. Core principle: sees everything, touches nothing, reports everything -- no automated process control.

## Architecture

Camera/Upload -> Ingestion -> Preprocessing -> VLM Inference (Ollama) -> Report Generator -> outputs/

## Tech Stack

| Component  | Technology                           |
|------------|--------------------------------------|
| Backend    | FastAPI                              |
| Frontend   | React + MUI v5                       |
| VLMs       | qwen3vl:8b, internvl3:8b (Ollama)    |
| WebSocket  | Streaming                            |

## Requirements

- Python 3.11+
- Node.js 18+
- Ollama with at least 8GB VRAM recommended

### Pull Ollama models

`sh
ollama pull qwen3vl:8b
ollama pull internvl3:8b
`

## Quick Start

`sh
git clone https://github.com/AddisonTech/Vision_Inspect.git
cd Vision_Inspect

# Backend
pip install -r requirements.txt
uvicorn backend.main:app --host 0.0.0.0 --port 8001

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
`

## Configuration

| File | Purpose |
|------|---------|
| `configs/vlm_config.yaml` | Model selection and Ollama settings |
| `configs/inspection_config.yaml` | Inspection thresholds and pipeline settings |
| `configs/notification_config.yaml` | Teams webhook, SMTP email, severity thresholds |
| `configs/input_config.yaml` | Input mode (live_camera, manual_upload, etc.) |

## Input Modes

| Mode | Description |
|------|-------------|
| live_camera | Real-time video stream from camera |
| manual_upload | Upload images via API |
| scheduled_capture | Periodic capture at set intervals |
| manual_trigger | User-triggered inspection |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/upload` | POST | Upload image for inspection |
| `/inspect` | POST | Inspect live stream or uploaded image |
| `/results/{job_id}` | GET | Retrieve job results |
| `/report/{job_id}` | POST | Generate and download report |
| `/reports` | GET | List all reports |
| `/models/versions` | GET | List model versions |
| `/models/rollback` | POST | Roll back to previous version |
| `/health` | GET | System health |
| `/ws/stream` | WS | Real-time WebSocket stream |

## Fine-Tuning

QLoRA fine-tuning workflow documented in [training/COLLECTING_DATA.md](training/COLLECTING_DATA.md).

## License

MIT

---

**This system never modifies, interrupts, or sends commands to any monitored process. All reports are for human review only.**