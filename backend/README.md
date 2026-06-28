# Drill Recognition Backend (Phase 1)

Local FastAPI server for the PC connected to the camera. Handles drill session management, camera recording, ML analysis, and report delivery to a tablet/web client over the local network.

## Setup

From the project root (`NCC Project/`):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
```

Ensure the ML model exists (first analysis run downloads it automatically):

```bash
python main.py --drill kadam_tal --input data/sample.mp4
# or
python main.py --drill salute --input data/front_salute.mp4
```

## Run Server

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Or from project root:

```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

Access from tablet on the same Wi-Fi:

```text
http://<PC_LOCAL_IP>:8000
```

Interactive API docs: `http://<PC_LOCAL_IP>:8000/docs`

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Server bind host |
| `PORT` | `8000` | Server port |
| `CAMERA_TYPE` | `usb` | `usb` or `ip` |
| `USB_CAMERA_INDEX` / `CAMERA_ID` | `0` | OpenCV USB camera index |
| `IP_CAMERA_HOST` | — | IP camera LAN address |
| `IP_CAMERA_RTSP_MAIN` | — | Main RTSP URL (recording + ML) |
| `IP_CAMERA_RTSP_SUB` | — | Sub RTSP URL (tablet preview) |
| `PREVIEW_USE_SUBSTREAM` | `true` | Use sub stream for preview when available |
| `RECORDING_FPS` / `CAMERA_FPS` | `30` | Recording frame rate |
| `RECORDING_WIDTH` / `CAMERA_WIDTH` | `1280` | Recording width |
| `RECORDING_HEIGHT` / `CAMERA_HEIGHT` | `720` | Recording height |
| `DIFFICULTY` | `2` | ML scoring difficulty (0–5) |

Copy `backend/.env.example` to `backend/.env` and set RTSP URLs for IP camera mode.

### IP Camera Setup (Secureye / PoE LAN)

1. Connect camera → PoE switch → PC (same LAN as tablet).
2. Confirm RTSP URL in VLC: **Media → Open Network Stream**.
3. Set in `backend/.env`:

```env
CAMERA_TYPE=ip
IP_CAMERA_RTSP_MAIN=rtsp://admin:password@192.168.1.50:554/main
IP_CAMERA_RTSP_SUB=rtsp://admin:password@192.168.1.50:554/sub
PREVIEW_USE_SUBSTREAM=true
```

4. Test endpoints:
   - `GET /status`
   - `GET /camera/diagnostics`
   - `GET /camera/snapshot`


## Supported Drill Types

| Drill | Status |
|-------|--------|
| `kadam_tal` | Fully supported (knee peak detection + PDF report) |
| `salute` | Fully supported (salute frame detection + posture scoring) |

## Session State Machine

```text
CREATED → READY → RECORDING → SAVING → PROCESSING → REPORT_READY
```

Invalid transitions return `409 INVALID_SESSION_STATE`.

## API Flow

```text
1. GET  /health
2. GET  /status
3. POST /sessions
4. POST /sessions/{id}/recording/start
5. POST /sessions/{id}/recording/stop
6. GET  /sessions/{id}/progress        (polling)
   WS  /ws/sessions/{id}               (live updates)
7. GET  /sessions/{id}/report
8. GET  /media/raw/{session_id}.mp4
```

### Example: Create Session

```bash
curl -X POST http://localhost:8000/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "cadet_id": "C101",
    "cadet_name": "Raj Kumar",
    "drill_type": "kadam_tal",
    "camera_id": "0"
  }'
```

### Example: Start / Stop Recording

```bash
curl -X POST http://localhost:8000/sessions/DRILL-20260628-0001/recording/start
curl -X POST http://localhost:8000/sessions/DRILL-20260628-0001/recording/stop
```

### Example: Fetch Report

```bash
curl http://localhost:8000/sessions/DRILL-20260628-0001/report
```

## Folder Structure

```text
backend/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── api/
│   ├── services/
│   ├── models/
│   ├── db/
│   └── ml/
├── media/
│   ├── raw/
│   ├── annotated/
│   └── frames/
├── reports/
└── database/
```

## WebSocket Messages

```json
{"type": "status_update", "session_id": "...", "status": "RECORDING", "message": "..."}
{"type": "processing_update", "session_id": "...", "stage": "pose_extraction", "progress": 45}
{"type": "report_ready", "session_id": "...", "status": "REPORT_READY", "report_url": "/sessions/.../report"}
```

## Testing Without Camera

For API testing without a physical camera, process an existing video through the standalone ML pipeline:

```bash
python main.py --input data/your_video.mp4
```

The backend recording APIs require a connected camera.

## Phase 1 Deliverables

- FastAPI backend with health/status endpoints
- Session CRUD with SQLite persistence
- Camera recording (single active session)
- Background ML processing via `kadam_tal` pipeline
- JSON report generation and retrieval
- Static media serving under `/media`
- WebSocket progress updates
