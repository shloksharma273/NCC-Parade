# NCC Drill Recognition

Computer vision pipelines for NCC drill analysis, with a PC backend server and tablet webapp.

## Drills

| Drill | Package | Description |
|-------|---------|-------------|
| **Kadam Tal** | `drill_detection/kadam_tal/` | Detects knee peak frames, scores posture, generates PDF report |
| **Salute** | `drill_detection/salute/` | Finds salute candidate frames, scores posture (elbow, heels, hands) |

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # optional: tune DIFFICULTY
```

## Run Pipelines (CLI)

**Kadam tal:**
```bash
python main.py --drill kadam_tal --input test_data/dataset/your_video.mp4
```

**Salute:**
```bash
python main.py --drill salute --input test_data/dataset/front_salute.mp4
```

**Kadam tal PDF report:**
```bash
python generate_report.py --results output/<video>/results.json
```

## Backend Server

```bash
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

On startup the server prints a QR code and serves:

| URL | Purpose |
|-----|---------|
| `http://<PC_IP>:8000/pair` | Pairing page with QR (open on PC) |
| `http://<PC_IP>:8000/app` | Tablet webapp (scan QR to open) |
| `http://<PC_IP>:8000/docs` | API documentation |

**Tablet pairing:** Scan the terminal or `/pair` QR code from the tablet. The webapp auto-saves the backend URL — no manual IP entry needed.

Create a session with `"drill_type": "salute"` or `"drill_type": "kadam_tal"`.

See [backend/README.md](backend/README.md).

## Tablet Webapp (Frontend)

```bash
cd frontend
npm install
npm run build   # required for /app on backend
```

Production URL (after backend is running): `http://<PC_IP>:8000/app`

Dev mode: `npm run dev` → `http://<PC_IP>:5173/app/`

See [frontend/README.md](frontend/README.md).

## Project Structure

The codebase is organized into five sections:

```
frontend/                    # 1. UI/UX — React tablet control app
backend/                     # 2. Backend — FastAPI server (sessions, ML, reports, DB)
│  └─ app/video_pipeline/    # 5. Video streaming & capture — camera / recording / preview
drill_detection/             # 3. Drill detection
│  ├─ salute/                #      a) salute detector + posture scoring
│  ├─ kadam_tal/             #      b) kadam tal peak detection + scoring + PDF
│  ├─ report_metadata.py     #      shared report metadata
│  └─ models/                #      MediaPipe holistic_landmarker.task
test_data/                   # 4. Test data
│  └─ dataset/               #      a) testing data set (sample drill videos)
│                            #      b) testing data reports → generated under backend/
main.py                      # Unified CLI for both drills
generate_report.py           # Kadam tal PDF report from results.json
```

> Generated reports, media, and the SQLite DB live under `backend/` (see
> [test_data/README.md](test_data/README.md)) so the running server can serve and index them.
