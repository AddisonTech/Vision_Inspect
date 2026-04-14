# Vision_Inspect
Vision_Inspect is a local shop-floor visual process monitoring system that uses Visual Language Models (VLMs) via Ollama for real-time inspection of manufacturing processes. The key principle is "sees everything, touches nothing, reports everything — no automated process control."

## Architecture
+-----------------+
| Camera/Upload   |
+-----------------+
          |
          v
+-----------------+
| Ingestion       |
+-----------------+
          |
          v
+-----------------+
| Preprocessing  |
+-----------------+
          |
          v
+-----------------+
| VLM Inference  (Ollama)|
+-----------------+
          |
          v
+-----------------+
| Report Generator|
+-----------------+
          |
          v
+-----------------+
| outputs/        |
+-----------------+

## Tech Stack Table
| Component       | Technology         |
|----------------|--------------------|
| Backend         | FastAPI            |
| Frontend        | React + MUI v5      |
| VLMs            | qwen3vl:8b, internvl3:8b (Ollama) |
| WebSocket       | Streaming          |

## Requirements
- Python 3.11+
- Node.js 18+
- Ollama with at least 8GB VRAM recommended

### Ollama Pull Commands
ollama pull qwen3vl:8b
ollama pull internvl3:8b

## Quick Start
1. Clone the repository:
   ```sh
   git clone https://github.com/your-repo/Vision_Inspect.git
   cd Vision_Inspect
   
2. Install dependencies:
   ```sh
   pip install -r backend/requirements.txt
   npm install
   
3. Run the backend server:
   ```sh
   uvicorn backend.main:app --host 0.0.0.0 --port 8000
   
4. Start the frontend:
   ```sh
   cd frontend && npm start
   
## Configuration Reference
| File | Purpose | Key Settings |
|------|---------|-------------|
| `backend/config.yaml` | Backend configuration | API keys, model versions |
| `frontend/src/config.js` | Frontend configuration | WebSocket URL, API endpoints |
| `notification_config.yaml` | Notification settings | Teams webhook, SMTP email |
| `models/config.yaml` | Model management | Active version |

## Input Modes
| Mode | YAML value | Description |
|------|-----------|-------------|
| Live Camera | live_camera | Real-time video stream from camera |
| Manual Upload | manual_upload | Upload images manually via API |
| Scheduled Capture | scheduled_capture | Periodic image capture at set intervals |
| Manual Trigger | manual_trigger | Trigger inspection by user action |

## Inspection Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/upload` | POST | Upload an image for inspection |
| `/inspect` | POST | Perform real-time inspection on live stream or uploaded image |
| `/results/{job_id}` | GET | Retrieve results of a specific job by ID |
| `/report/{job_id}` | POST | Generate and download a report for a specific job |
| `/reports` | GET | List all available reports |
| `/models/versions` | GET | List all model versions |
| `/models/rollback` | POST | Roll back to previous model version |
| `/health` | GET | Check system health status |
| `/ws/stream` | WS | WebSocket streaming for real-time updates |

## Proxy Metrics
- **Latency**: Time taken for the system to process and return results.
- **Confidence**: Confidence level of the inspection result.
- **Drift Alert**: Alerts when model performance degrades significantly.
- **Distribution Shift**: Detects changes in input data distribution.

Silent failure detection: The system will alert if it fails to process images or videos without generating any errors.

## Model Versioning
- Create versions with `POST /models/rollback`.
- List all versions with `GET /models/versions`.
- Activate a version by setting the active version using the API.

## Notifications
Configure Teams webhook and SMTP email in `notification_config.yaml`. Set severity thresholds: high triggers Teams, critical triggers email.

## Fine-Tuning
For QLoRA fine-tuning workflow, refer to [training/COLLECTING_DATA.md](https://github.com/your-repo/training/blob/main/COLLECTING_DATA.md).

## Important: Observation Only
**This system never modifies, interrupts, or sends commands to any monitored process. All reports are for human review only. No automated decisions are made.**
