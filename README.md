# NCC Drill Recognition

Computer vision pipelines for NCC drill analysis, with a PC backend server and tablet webapp.

## Drills

| Drill | Package | Description |
|-------|---------|-------------|
| **Kadam Tal** | `knee_peak_detector/` | Detects knee peak frames, scores posture, generates PDF report |
| **Salute** | `salute_detector/` | Finds salute candidate frames, scores posture (elbow, heels, hands) |

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
python main.py --drill kadam_tal --input data/your_video.mp4
```

**Salute:**
```bash
python main.py --drill salute --input data/front_salute.mp4
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

## Tablet Webapp

```bash
cd tablet-webapp
npm install
npm run build   # required for /app on backend
```

Production URL (after backend is running): `http://<PC_IP>:8000/app`

Dev mode: `npm run dev` → `http://<PC_IP>:5173/app/`

See [tablet-webapp/README.md](tablet-webapp/README.md).

## Project Structure

```
salute_detector/      # Salute detection + posture scoring
knee_peak_detector/   # Kadam tal peak detection + scoring + PDF
backend/              # FastAPI server (recording, ML, reports)
tablet-webapp/        # React tablet control UI
main.py               # Unified CLI for both drills
```
